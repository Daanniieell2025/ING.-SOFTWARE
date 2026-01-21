"""
Sprint 2: Definicion de estructura de datos del sistema

- MuestraCruda: llega desde Fuente (serial/simulada/csv)
- MuestraProcesada: sale del Modelo y se almacena en historial

Estas clases son el contrato comun entre Controller, Model y View.
"""

from dataclasses import dataclass


@dataclass
class MuestraCruda:
    t_ms: int
    servo_deg: int
    v_div: float
    v_rf: float
    v_photo: float


@dataclass
class MuestraProcesada:
    t_ms: int
    servo_deg: int
    v_div: float
    v_rf: float
    v_photo: float

    r_m: float

    V_in: float
    P_in: float

    B_exp: float
    B_teo: float

    L_exp: float
    L_teo: float

    err_B_abs: float
    err_L_abs: float
    err_B_rel: float
    err_L_rel: float
