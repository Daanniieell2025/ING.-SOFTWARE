"""
Sprint 2: Almacenamiento de datos (exportacion a CSV)

Este modulo se encarga de transformar el historial del Modelo (MuestraProcesada)
a un archivo CSV para analisis externo (Excel, Python, etc).

Idea:
- El Modelo guarda un historial de MuestraProcesada.
- El Controller llama exportar_csv(...) al finalizar el experimento.
- El CSV incluye tiempos absolutos y tiempos relativos para facilitar graficos.

Notas:
- t_ms viene desde la ESP32 (millis()).
- t_ms_rel y t_s_rel se calculan para que el grafico parta en t=0.
"""

import csv
from pathlib import Path
from typing import Iterable

from .muestra import MuestraProcesada


# Orden de columnas del CSV
# Esto define el formato de salida y permite mantener consistencia entre corridas.
CSV_HEADERS = [
    # tiempo absoluto entregado por la ESP32 (ms desde reset)
    "t_ms",
    # tiempo relativo: t_ms - t0_ms (ms)
    "t_ms_rel",
    # tiempo relativo en segundos (s)
    "t_s_rel",

    # medidas crudas
    "servo_deg",
    "v_div",
    "v_rf",
    "v_photo",

    # variables calculadas por el Modelo
    "r_m",
    "B_exp",
    "L_exp",
    "V_in",
    "P_in",
    "B_teo",
    "L_teo",

    # errores
    "err_B_abs",
    "err_L_abs",
    "err_B_rel",
    "err_L_rel",
]


def _fmt(v):
    """
    Formatea valores para escritura en CSV.
    - None -> ""
    - float -> redondeo razonable (evita notacion cientifica innecesaria en Excel)
    - int/str -> se deja tal cual
    """
    if v is None:
        return ""
    if isinstance(v, float):
        # Ajusta decimales segun tu preferencia (6 suele ser suficiente)
        return f"{v:.6f}"
    return v


def exportar_csv(muestras: Iterable[MuestraProcesada], ruta_csv: str) -> Path:
    """
    Exporta una secuencia de MuestraProcesada a un archivo CSV.

    Parametros:
    - muestras: iterable de MuestraProcesada (normalmente historial del Modelo)
    - ruta_csv: ruta de salida (puede incluir carpeta, ej "salidas/exp.csv")

    Retorna:
    - Path del archivo generado
    """
    path = Path(ruta_csv)

    # Crea la carpeta destino si no existe (ej: "salidas/")
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    # Convertimos a lista para:
    # - poder obtener la primera muestra (t0_ms)
    # - poder iterar mas de una vez si se requiere
    muestras_list = list(muestras)

    # Si no hay muestras, igual generamos el archivo con headers
    if len(muestras_list) == 0:
        with path.open(mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
        return path

    # t0_ms: tiempo absoluto de la primera muestra (referencia para tiempo relativo)
    t0_ms = muestras_list[0].t_ms

    # newline="" evita lineas en blanco en Windows
    with path.open(mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()

        for m in muestras_list:
            # tiempos relativos para graficos (parten en t=0)
            t_ms_rel = m.t_ms - t0_ms
            t_s_rel = t_ms_rel / 1000.0

            row = {
                "t_ms": m.t_ms,
                "t_ms_rel": t_ms_rel,
                "t_s_rel": t_s_rel,

                "servo_deg": m.servo_deg,
                "v_div": m.v_div,
                "v_rf": m.v_rf,
                "v_photo": m.v_photo,

                "r_m": m.r_m,
                "B_exp": m.B_exp,
                "L_exp": m.L_exp,
                "V_in": m.V_in,
                "P_in": m.P_in,
                "B_teo": m.B_teo,
                "L_teo": m.L_teo,

                "err_B_abs": m.err_B_abs,
                "err_L_abs": m.err_L_abs,
                "err_B_rel": m.err_B_rel,
                "err_L_rel": m.err_L_rel,
            }

            # Formatea valores para CSV (None -> "", floats con decimales fijos)
            row = {k: _fmt(v) for k, v in row.items()}

            writer.writerow(row)

    return path

