"""
Este modulo define las fuentes de datos crudos para el controller.

Una fuente de datos es un componente que entrega MuestraCruda, sin procesar:
- FuenteSimulada: genera datos de prueba (desarrollo / presentacion).
- FuenteSerialESP32: lee el puerto serial y decodifica tramas tipo DATA.
- FuenteCSV: lee un archivo CSV y entrega muestras una a una.

Idea de arquitectura:
- El Controller solo conoce el contrato FuenteDatos.leer_muestra().
- Asi se puede cambiar entre Serial / Simulada / CSV sin reescribir la logica del Controller.
"""

import csv
import random
from pathlib import Path
from typing import TextIO

from tesla_monitor.config.settings import SETTINGS
from tesla_monitor.model.muestra import MuestraCruda
from tesla_monitor.controller.decodificador import decodificar_linea_data


# ============================================================
# 0) CONTRATO BASE (interfaz)
# ============================================================

class FuenteDatos:
    """
    Contrato que deben cumplir todas las fuentes de datos.

    El controller trabajara con objetos que implementen:
    - leer_muestra() -> MuestraCruda

    Opcionalmente, algunas fuentes pueden implementar:
    - conectar() / cerrar() (si manejan recursos como serial o archivos)
    - start_stream() / stop_stream() (si el hardware soporta streaming)
    - set_servo_deg() (si la fuente controla servo)
    """

    def leer_muestra(self) -> MuestraCruda:
        raise NotImplementedError


# ============================================================
# 1) FUENTE SERIAL (ESP32 REAL)
# ============================================================

class FuenteSerialESP32(FuenteDatos):
    """
    Fuente conectada a una ESP32 real por puerto Serial.

    Responsabilidad:
    - Leer lineas desde el puerto serial.
    - Filtrar solo lineas "DATA,..." (las demas se ignoran).
    - Decodificar "DATA,..." a MuestraCruda usando decodificador.py.

    Contrato esperado desde el firmware:
      DATA,<ms>,<servo_deg>,<x_div>,<x_rf>,<x_photo>

    Nota:
    - El firmware puede imprimir lineas READY/INFO/OK/ERROR, y aqui se ignoran.
    """

    def __init__(self, puerto: str, baudrate: int = 115200, timeout_s: float = 1.0):
        self.puerto = puerto
        self.baudrate = baudrate
        self.timeout_s = timeout_s

        # Objeto serial (pyserial), se inicializa en conectar()
        self._ser = None

    # ----------------------------
    # Conexion y cierre
    # ----------------------------

    def conectar(self) -> None:
        """
        Abre el puerto serial.

        Se recomienda llamar esto una sola vez al inicio del programa (controller.iniciar_recursos()).
        """
        try:
            import serial  # pyserial
        except ImportError as e:
            raise ImportError("Falta instalar pyserial. Ejecuta: pip install pyserial") from e

        # Se crea la conexion serial con timeout (evita bloqueos infinitos)
        self._ser = serial.Serial(self.puerto, self.baudrate, timeout=self.timeout_s)

        # Limpia buffers por si habia basura o logs al conectar
        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()

    def cerrar(self) -> None:
        """
        Cierra el puerto serial.
        """
        if self._ser is not None and self._ser.is_open:
            self._ser.close()

    # ----------------------------
    # Envio de comandos a la ESP32
    # ----------------------------

    def enviar_comando(self, comando: str) -> None:
        """
        Envia un comando a la ESP32, agregando salto de linea.

        Ejemplos:
        - "PING"
        - "START"
        - "STOP"
        - "SERVO=15"
        - "RATE=20"
        - "RAW=0"
        """
        if self._ser is None:
            raise RuntimeError("Serial no conectado. Llama primero a conectar().")

        linea = comando.strip() + "\n"
        self._ser.write(linea.encode("utf-8"))

    def set_servo_deg(self, servo_deg: int) -> None:
        """
        Mueve el servo por comando serial.

        El rango permitido debe coincidir con el firmware (0..30) y con SETTINGS.
        """
        servo_deg = int(servo_deg)

        if servo_deg < SETTINGS.servo_deg_min or servo_deg > SETTINGS.servo_deg_max:
            raise ValueError(
                f"Angulo invalido: servo_deg debe estar entre "
                f"{SETTINGS.servo_deg_min} y {SETTINGS.servo_deg_max}"
            )

        self.enviar_comando(f"SERVO={servo_deg}")

    def start_stream(self) -> None:
        """
        Inicia streaming en la ESP32.

        Recomendacion:
        - Forzar RAW=0 para recibir voltajes (floats), como espera el pipeline en Python.
        - Forzar RATE segun dt_ms del settings para coherencia de muestreo.
        """
        # Fuerza modo de envio para que el decodificador reciba floats
        self.enviar_comando("RAW=0")

        # Fuerza frecuencia coherente con el dt_ms configurado en Python
        # ej: dt_ms=50 -> 20 Hz
        hz = max(1, int(round(1000.0 / float(SETTINGS.dt_ms))))
        self.enviar_comando(f"RATE={hz}")

        # Activa streaming
        self.enviar_comando("START")

    def stop_stream(self) -> None:
        """
        Detiene streaming en la ESP32.
        """
        self.enviar_comando("STOP")

    # ----------------------------
    # Lectura de muestras crudas
    # ----------------------------

    def leer_muestra(self) -> MuestraCruda:
        """
        Lee lineas del serial hasta encontrar una linea DATA valida.
        Luego la decodifica a MuestraCruda y la retorna.

        Si el puerto no entrega nada dentro del timeout, se levanta TimeoutError.
        """
        if self._ser is None:
            raise RuntimeError("Serial no conectado. Llama primero a conectar().")

        while True:
            raw = self._ser.readline()

            if not raw:
                raise TimeoutError("Timeout leyendo del puerto serial (no llego DATA).")

            linea = raw.decode("utf-8", errors="ignore").strip()

            if linea == "":
                continue

            if linea.startswith("DATA,"):
                return decodificar_linea_data(linea)

            # Si llega READY/INFO/OK/ERROR u otros logs, se ignora.
            # Si quisieras, aqui puedes agregar logging a consola o archivo.
            # print(f"[ESP32] {linea}")


# ============================================================
# 2) FUENTE SIMULADA (DESARROLLO / PRESENTACION)
# ============================================================

class FuenteSimulada(FuenteDatos):
    """
    Fuente simulada para probar el pipeline completo sin hardware real.

    Idea:
    - Genera senales con ruido simple (uniforme).
    - Mantiene el mismo formato de MuestraCruda usado por el modelo.
    - Permite testear controller + modelo + exportacion CSV.
    """

    def __init__(
        self,
        dt_ms: int = 50,
        servo_deg: int = 0,
        v_div_base: float = 0.95,
        v_rf_base: float = 0.6,
        v_photo_base: float = 0.1,
        ruido_v_div: float = 0.02,
        ruido_v_rf: float = 0.02,
        ruido_v_photo: float = 0.02,
    ):
        self.dt_ms = int(dt_ms)
        self.t_ms = 0

        self.servo_deg = int(servo_deg)

        self.v_div_base = float(v_div_base)
        self.v_rf_base = float(v_rf_base)
        self.v_photo_base = float(v_photo_base)

        self.ruido_v_div = float(ruido_v_div)
        self.ruido_v_rf = float(ruido_v_rf)
        self.ruido_v_photo = float(ruido_v_photo)

    def set_servo_deg(self, servo_deg: int) -> None:
        """
        Cambia el angulo del servo en la simulacion.

        Se mantiene el mismo rango que en firmware y settings para consistencia.
        """
        servo_deg = int(servo_deg)

        if servo_deg < SETTINGS.servo_deg_min or servo_deg > SETTINGS.servo_deg_max:
            raise ValueError(
                f"Angulo invalido: servo_deg debe estar entre "
                f"{SETTINGS.servo_deg_min} y {SETTINGS.servo_deg_max}"
            )

        self.servo_deg = servo_deg

    def leer_muestra(self) -> MuestraCruda:
        """
        Genera y retorna una MuestraCruda simulada.

        Nota:
        - t_ms avanza segun dt_ms de la simulacion (no depende del reloj real).
        - El controller igual duerme dt_ms para simular "tiempo real".
        """
        self.t_ms += self.dt_ms

        v_div = self.v_div_base + random.uniform(-self.ruido_v_div, self.ruido_v_div)
        v_rf = self.v_rf_base + random.uniform(-self.ruido_v_rf, self.ruido_v_rf)
        v_photo = self.v_photo_base + random.uniform(-self.ruido_v_photo, self.ruido_v_photo)

        return MuestraCruda(
            t_ms=self.t_ms,
            servo_deg=self.servo_deg,
            v_div=v_div,
            v_rf=v_rf,
            v_photo=v_photo,
        )


# ============================================================
# 3) FUENTE CSV (CARGA DE DATOS)
# ============================================================

class FuenteCSV(FuenteDatos):
    """
    Fuente basada en un archivo CSV.

    Espera un CSV con headers al menos:
    - t_ms
    - servo_deg
    - v_div
    - v_rf
    - v_photo

    Cada llamada a leer_muestra() devuelve la siguiente fila como MuestraCruda.
    """

    def __init__(self, ruta_csv: str):
        self.ruta_csv = ruta_csv
        self.path = Path(ruta_csv)

        if not self.path.exists():
            raise FileNotFoundError(f"No existe el archivo CSV: {ruta_csv}")

        self._archivo: TextIO = self.path.open(mode="r", encoding="utf-8", newline="")
        self._reader = csv.DictReader(self._archivo)

    def cerrar(self) -> None:
        """
        Cierra el archivo CSV.
        """
        self._archivo.close()

    def leer_muestra(self) -> MuestraCruda:
        """
        Lee la siguiente fila del CSV y la convierte a MuestraCruda.

        Cuando se termina el archivo, levanta StopIteration.
        """
        try:
            fila = next(self._reader)
        except StopIteration:
            raise StopIteration("Fin del archivo CSV")

        return MuestraCruda(
            t_ms=int(fila["t_ms"]),
            servo_deg=int(fila["servo_deg"]),
            v_div=float(fila["v_div"]),
            v_rf=float(fila["v_rf"]),
            v_photo=float(fila["v_photo"]),
        )

