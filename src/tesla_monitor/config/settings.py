"""
Configuracion central del proyecto Tesla Monitor.

Idea:
- Aqui van los parametros fijos del sistema (geometria, divisor, limites de seguridad).
- El Controller usa estos valores para validar y ejecutar el experimento.
- La View puede leer estos limites para bloquear inputs (duracion, angulo servo, etc.).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # -------------------------------
    # Puertos / comunicacion (ESP32)
    # -------------------------------
    puerto_serial: str = "COM3"     # puerto serial (Windows)
    baudrate: int = 115200          # velocidad serial (debe coincidir con el firmware)
    timeout_s: float = 1.0          # timeout de lectura serial (segundos)

    # -------------------------------
    # Experimento (seguridad termica)
    # -------------------------------
    min_experimento_s: int = 1       # duracion minima permitida (evita valores vacios)
    max_experimento_s: int = 20      # limite duro por seguridad (bobina se calienta rapido)
    dt_ms: int = 50                  # periodo objetivo de muestreo (ms). 50 ms -> 20 Hz

    # -------------------------------
    # Servo (seguridad mecanica)
    # -------------------------------
    servo_deg_min: int = 0
    servo_deg_max: int = 30
    servo_deg_default: int = 0

    # -------------------------------
    # Geometria (en metros)
    # -------------------------------
    L_m: float = 0.22                # largo brazo: centro servo -> punta loop (m)
    y0_m: float = 0.325              # centro servo -> centro bobina secundaria (m)

    # -------------------------------
    # Divisor de tensiones (ohms)
    # Valores reales medidos (no nominales)
    # -------------------------------
    Rtop: float = 99_800.0           # resistencia superior (ohm) -> 99.8 kOhm
    Rbot: float = 9_935.0            # resistencia inferior (ohm) -> 9.935 kOhm

    # -------------------------------
    # Modelo electrico equivalente (por tramos)
    # -------------------------------
    Req_baja: float = 15.25          # equivalente para 9–10 V (sin arco)
    Req_alta: float = 19.64          # equivalente para 11–12 V (con corona/arco)
    vin_umbral_req_v: float = 11.0   # si Vin < 11 -> Req_baja ; si Vin >= 11 -> Req_alta


    # -------------------------------
    # Parametros teoricos (escala)
    # Se ajustan segun tendencia experimental
    # -------------------------------
    Kb: float = 0.3                  # escala teorica para B_teo
    Kl: float = 1.0                  # escala teorica para L_teo

    # -------------------------------
    # Rango operativo de voltaje (referencia)
    # -------------------------------
    vin_min_v: float = 9.0           # voltaje minimo de operacion (V)
    vin_max_v: float = 12.0          # voltaje maximo de operacion (V)

    # -------------------------------
    # Salida de datos
    # -------------------------------
    ruta_csv: str = "salidas/experimento.csv"  # ruta por defecto del CSV exportado


# Instancia global utilizada por el resto del proyecto
SETTINGS = Settings()