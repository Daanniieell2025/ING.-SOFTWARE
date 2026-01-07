"""
Sprint 1: Sensores del sistema Tesla Monitor

Este archivo define las clases de sensores utilizados en el proyecto.
En este sprint NO existe comunicacion real con hardware.
Las clases solo representan la estructura del sistema.

Sprint 2: Definicion de estrutura de datos del sistema

- Muestra directa que llega desde el controller
- Muestra procesada que el Model calcula y almacena
- Se define columnas de cada tipo de muestra

"""

from dataclasses import dataclass
from typing import Optional


# clase que recibe los datos crudos del controller 

@dataclass
class MuestraCruda:
    t_ms: int           # tiempo
    servo_deg: int    # angulo servo
    v_div: float      # voltaje divisor de tensiones
    v_rf: float       # voltaje sensor RF
    v_photo: float    # voltaje fotodiodo


# clase que recibe los resultados del procesamiento

@dataclass
class MuestraProcesada:
    t_ms: int           # tiempo
    servo_deg: int    # angulo servo
    v_div: float      # voltaje divisor de tensiones
    v_rf: float       # voltaje sensor RF
    v_photo: float    # voltaje fotodiodo

    r_m: float  # distancia entre loop y bobina

    B_exp: float      # campo electromagnetico experimental
    L_exp: float      # intensidad luminica experimental 

    V_in: Optional[float]  # voltaje de alimentacion convertido al real despues del divisor 
    P_in: Optional[float]  # potencia de bobina
    B_teo: Optional[float] # campo electromagnetico teorico
    L_teo: Optional[float] # intensidad luminica teorica

    # Error absoluto y relativo para B y L
    err_B_abs: Optional[float] 
    err_L_abs: Optional[float] 
    err_B_rel: Optional[float] 
    err_L_rel: Optional[float] 




