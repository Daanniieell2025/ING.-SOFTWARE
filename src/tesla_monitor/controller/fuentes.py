
"""
Este modulo define las fuentes de datos crudos para el controller

Una fuente de datos es un componente que entrega MuestraCruda, sin procesar:
- FuenteSimulada: genera datos de prueba (para presentacion / desarrollo).
- FuenteSerialESP32: lee el puerto serial y decodifica tramas DATA.
- FuenteCSV: lee un archivo CSV y entrega muestras una a una.

""" 

import csv                           # Libreria estandar para leer archivos CSV
import random                        # Libreria para generar numeros aleatorios (simulacion)
from pathlib import Path             # Manejo robusto de rutas en el sistema
from typing import Optional, TextIO  # Tipos para claridad del codigo

# Importa la estructura de datos crudos utilizada por todo el sistema 
from model.muestras import MuestraCruda

# Importa el decodificador de tramas Serial tipo "DATA,..."
from controller.decodificador import decodificar_linea_data


class FuenteDatos:
    """
    El Controller trabajara con objetos que cumplan este contrato, de modo que
    pueda cambiar entre Serial/Simulacion/CSV sin reescribir su logica.
    """

    def leer_muestra(self) -> MuestraCruda:
        """
        Retorna una muestra cruda.
        Cada fuente concreta define como obtiene esa muestra.
        """
        raise NotImplementedError



# 1) FUENTE SERIAL (ESP32 REAL)
# ============================================================

class FuenteSerialESP32(FuenteDatos):
    """
    Fuente de datos conectada a una ESP32 real por puerto Serial (COM).

    Responsabilidad:
    - Leer lineas del puerto serial.
    - Decodificar lineas "DATA,..." a MuestraCruda usando decodificador.py.

    """

    def __init__(self, puerto: str, baudrate: int = 115200, timeout_s: float = 1.0):
        # Puerto serial 
        self.puerto = puerto

        # Velocidad serial, esta debe coincidir con el firmware ESP32
        self.baudrate = baudrate

        # Timeout para lectura (evita bloqueos infinitos)
        self.timeout_s = timeout_s

        # Objeto serial (se inicializa en conectar())
        self._ser = None

    def conectar(self) -> None:
        """
        Abre el puerto serial.
        """
        try:
            import serial  # pyserial (debe estar instalado)
        except ImportError as e:
            # Error claro si no esta instalada la libreria
            raise ImportError("Falta instalar pyserial. Ejecuta: pip install pyserial") from e

        # Se crea la conexion serial con timeout
        self._ser = serial.Serial(self.puerto, self.baudrate, timeout=self.timeout_s)

        # Limpia buffers por si habia basura al conectar
        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()

    def cerrar(self) -> None:
        """
        Cierra el puerto serial si esta abierto.
        """
        if self._ser is not None and self._ser.is_open:
            self._ser.close()

    def enviar_comando(self, comando: str) -> None:
        """
        Envia un comando a la ESP32, agregando salto de linea.

        Ejemplos:
        - "PING"
        - "START"
        - "STOP"
        - "SERVO=15"
        """
        if self._ser is None:
            raise RuntimeError("Serial no conectado. Llama primero a conectar().")

        # Normaliza: un comando por linea
        linea = comando.strip() + "\n"

        # Envia como bytes (UTF-8)
        self._ser.write(linea.encode("utf-8"))

    def set_servo_deg(self, servo_deg: int) -> None:
        """
        Envia comando para mover servo en la ESP32 (0..30 deg).
        """
        if servo_deg < 0 or servo_deg > 30:
            raise ValueError("Angulo invalido: servo_deg debe estar entre 0 y 30")

        # Se manda el comando con el formato del protocolo
        self.enviar_comando(f"SERVO={servo_deg}")

    def start_stream(self) -> None:
        """
        Le indica a la ESP32 que comience a transmitir datos periodicamente.
        """
        self.enviar_comando("START")

    def stop_stream(self) -> None:
        """
        Le indica a la ESP32 que detenga la transmision de datos.
        """
        self.enviar_comando("STOP")

    def leer_muestra(self) -> MuestraCruda:
        """
        Lee lineas del serial hasta encontrar una linea DATA valida.
        Luego la decodifica a MuestraCruda y la retorna.
        """
        if self._ser is None:
            raise RuntimeError("Serial no conectado. Llama primero a conectar().")

        while True:
            # Lee una linea completa del serial
            raw = self._ser.readline()

            # Si no llego nada (timeout), se levanta error controlado
            if not raw:
                raise TimeoutError("Timeout leyendo del puerto serial (no llego DATA).")

            # Decodifica bytes a string (ignorando errores raros)
            linea = raw.decode("utf-8", errors="ignore").strip()

            # Ignora lineas vacias
            if linea == "":
                continue

            # Si es una linea DATA, se intenta decodificar
            if linea.startswith("DATA,"):
                return decodificar_linea_data(linea)

            # Si es otra cosa (logs / ok / errores), se ignora por ahora
            # (Opcional: aqui podrias loguearlo)



# 2) FUENTE SIMULADA (PRESENTACION / TEST)
# ============================================================

class FuenteSimulada(FuenteDatos):
    """
    Fuente de datos simulada.

    Genera MuestraCruda con valores aleatorios para probar el pipeline:
    Fuente -> Controller -> Modelo -> Historial -> CSV / Graficos
    """

    def __init__(
        self,
        dt_ms: int = 50,
        servo_deg: int = 0,
        v_div_base: float = 0.0,
        v_rf_base: float = 0.6,
        v_photo_base: float = 0.1,
        ruido_v_div: float = 0.01,
        ruido_v_rf: float = 0.02,
        ruido_v_photo: float = 0.02,
    ):
        # Paso de tiempo simulado entre muestras
        self.dt_ms = dt_ms

        # Tiempo interno (ms) desde inicio
        self.t_ms = 0

        # Angulo del servo en la simulacion
        self.servo_deg = servo_deg

        # Valores promedio (base) de cada señal
        self.v_div_base = v_div_base
        self.v_rf_base = v_rf_base
        self.v_photo_base = v_photo_base

        # Amplitud de ruido (uniforme) para cada señal
        self.ruido_v_div = ruido_v_div
        self.ruido_v_rf = ruido_v_rf
        self.ruido_v_photo = ruido_v_photo

    def set_servo_deg(self, servo_deg: int) -> None:
        """
        Cambia el angulo del servo para la simulacion.
        Mantiene el mismo rango que el firmware (0..30) para consistencia.
        """
        if servo_deg < 0 or servo_deg > 30:
            raise ValueError("Angulo invalido: servo_deg debe estar entre 0 y 30")
        self.servo_deg = servo_deg

    def leer_muestra(self) -> MuestraCruda:
        """
        Genera y retorna una MuestraCruda simulada.
        """
        # Avanza el tiempo simulado
        self.t_ms += self.dt_ms

        # Genera voltajes con ruido aleatorio (uniforme)
        v_div = self.v_div_base + random.uniform(-self.ruido_v_div, self.ruido_v_div)
        v_rf = self.v_rf_base + random.uniform(-self.ruido_v_rf, self.ruido_v_rf)
        v_photo = self.v_photo_base + random.uniform(-self.ruido_v_photo, self.ruido_v_photo)

        # Construye la muestra cruda con el formato oficial
        return MuestraCruda(
            t_ms=self.t_ms,
            servo_deg=self.servo_deg,
            v_div=v_div,
            v_rf=v_rf,
            v_photo=v_photo,
        )



# 3) FUENTE CSV (CARGA DE DATOS)
# ============================================================

class FuenteCSV(FuenteDatos):
    """
    Fuente basada en un archivo CSV.

    Espera un CSV con headers (columnas) al menos:
    - t_ms
    - servo_deg
    - v_div
    - v_rf
    - v_photo

    Cada llamada a leer_muestra() devuelve la siguiente fila como MuestraCruda.
    """

    def __init__(self, ruta_csv: str):
        # Se guarda la ruta original
        self.ruta_csv = ruta_csv

        # Se crea un Path por seguridad
        self.path = Path(ruta_csv)

        # Validacion simple: archivo debe existir
        if not self.path.exists():
            raise FileNotFoundError(f"No existe el archivo CSV: {ruta_csv}")

        # Se abre el archivo
        self._archivo: TextIO = self.path.open(mode="r", encoding="utf-8", newline="")

        # DictReader permite leer filas por nombre de columna (headers)
        self._reader = csv.DictReader(self._archivo)

    def cerrar(self) -> None:
        """
        Cierra el archivo CSV.
        """
        self._archivo.close()

    def leer_muestra(self) -> MuestraCruda:
        """
        Lee la siguiente fila del CSV y la convierte en MuestraCruda.
        """
        try:
            fila = next(self._reader)  # Obtiene la siguiente fila del archivo
        except StopIteration:
            # No quedan filas: fin de archivo
            raise StopIteration("Fin del archivo CSV")

        # Convierte tipos (en CSV todo viene como texto)
        t_ms = int(fila["t_ms"])
        servo_deg = int(fila["servo_deg"])
        v_div = float(fila["v_div"])
        v_rf = float(fila["v_rf"])
        v_photo = float(fila["v_photo"])

        # Retorna la muestra cruda lista para el Modelo
        return MuestraCruda(
            t_ms=t_ms,
            servo_deg=servo_deg,
            v_div=v_div,
            v_rf=v_rf,
            v_photo=v_photo,
        )