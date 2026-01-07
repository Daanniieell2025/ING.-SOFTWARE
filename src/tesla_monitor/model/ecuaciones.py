"""
Sprint 1: Ecuaciones del sistema

Este modulo contendra las ecuaciones matematicas utilizadas por el sistema, tales como:

- Calculos geometricos
- Conversion de magnitudes fisicas
- Relaciones entre variables del sistema

En Sprint 1 no se implementan ecuaciones. Estas seran desarrolladas en Sprint 2.


Sprint 2: Implementacion de ecuaciones asociadas al sistema

"""

import math

# funcion de convierte grados a radianes

def deg_rad(theta_deg: float) -> float:
    return theta_deg * math.pi/ 180.0

# funcion de distancia entre loop y bobina

def distancia(theta_deg: float, L_m: float, y0_m: float) -> float:  # L_m: longitud efectiva del brazo, y0_m: distancia base fija
    theta_rad = deg_rad(theta_deg)
    termino = L_m**2 + y0_m**2 - 2.0*y0_m*L_m*math.sin(theta_rad)
    return math.sqrt(termino)

# funcion que reconstuye el voltaje de alimentacion de la bobina depsues del divisor

def vin_real(v_div: float, Rtop: float, Rbot: float) -> float:   # Rtop es la resistencia superior y Rbot es la resistencia inferior
    factor = (Rtop + Rbot) / Rbot
    V_in = v_div * factor
    return V_in

# funcion para calcular la potencia teorica a partir del voltaje de alimentacion

def potencia_in(vin_real: float, Req: float) -> float:   # Req es la resistencia equivalente del modelo
    return (vin_real **2) / Req

# funcion que representa una relacion teorica del tipo 1/r^n
# se utiliza para modelar la tendencia fisica que decrece con la distancia

def tendencia(r: float, n: float) -> float:
    if r<= 0.0:
        return float("inf")
    return 1.0 / (r**n)

# funcion que modela la tendencia teorica del campo electromagnetico en funcion de la distancia
# Kb es un factor de escala teorico utilizado para comparar curvas

def b_teo(r_m: float, Kb: float = 1.0, n: float = 1.0) -> float:
    return Kb * tendencia(r_m, n)

# funcion que modela la tendencia teorica de la intensidad luminica del arco electrico generado por la bobina
# Kl es un factor de escala teorico utilizado para comparar curvas

def l_teo(r_m: float, Kl: float = 1.0) -> float:
    return Kl * tendencia(r_m, 2.0)

# funcion que define la magnitud experimental del campo electromagnetico a partir del voltaje del sensor RF

def b_exp(v_rf: float) -> float:
    return v_rf

# funcion que define la magnitud de la intensidad liminica del arco electrico 

def l_exp(v_photo: float) -> float:
    return v_photo

# funcion que calcula el error absoluto entre valor experimental y teorico

def error_abs(exp: float, teo: float) -> float:
    return exp - teo

# funcion que calcula el error relativo entre valor experimental y teorico

def error_rel(exp: float, teo: float, eps: float = 1e-12) -> float:
    if abs(teo) < eps:
        return float("inf")
    return (exp - teo) / teo







