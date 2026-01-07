"""
Sprint 1:  Almacenamiento de datos

Este modulo se encargara del almacenamiento de los datos adquiridos por el sistema, tales como:

- Lecturas de sensores
- Valores calculados
- Estados del sistema

Sprint 2: se exportan los resultados del modelo a archivos, transformando estructura de datos a CSV

"""

import csv
from pathlib import Path
from typing import Iterable

from .muestras import MuestraProcesada

# Orden de columnas del CSV
# Define el formato de salida de los datos del experimento
CSV_HEADERS = [
    "t_ms",
    "servo_deg",
    "v_div",
    "v_rf",
    "v_photo",
    "r_m",
    "B_exp",
    "L_exp",
    "V_in",
    "P_in",
    "B_teo",
    "L_teo",
    "err_B_abs",
    "err_L_abs",
    "err_B_rel",
    "err_L_rel",
]

# Exportacion de una secuencia de MuestraProcesada

def exportar_csv(muestras: Iterable[MuestraProcesada], ruta_csv:str) -> Path:
    # se convierte a path para manejar rutas de forma segura
    path = Path(ruta_csv)

    # si la carpeta de destino no existe, se crea
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    #se escribe el CSV con newline="" para evitar lineas en blanco en windows
    with path.open(mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()

        # para cada muestra, se construye un diccionario con las columnas definidas
        for m in muestras:
            row = {
                "t_ms": m.t_ms,
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

            # Normaliza valores None a campo vacio en el CSV
            for k, v in row.items():
                if v is None:
                    row[k] = ""
            writer.writerow(row)

    return path

