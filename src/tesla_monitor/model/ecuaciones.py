"""
Ecuaciones del sistema (Tesla Monitor)

Este modulo contiene las funciones matematicas utilizadas por el sistema, tales como:

- Calculos geometricos (distancia servo -> bobina)
- Reconstruccion de voltaje real desde el divisor de tension
- Potencia electrica teorica a partir del modelo equivalente
- Relaciones teoricas tipo 1/r^n para senales (RF y fotodiodo)
- Errores (absoluto y relativo) para comparacion teoria vs experimento

Nota:
- El comportamiento electrico de la bobina NO se modela como fisico completo.
- Se usa un modelo simple y defendible para el demo.
"""

import math


# -------------------------------------------------------
# Utilidades basicas
# -------------------------------------------------------

def deg_rad(theta_deg: float) -> float:
    """Convierte grados a radianes."""
    return theta_deg * math.pi / 180.0


# -------------------------------------------------------
# Geometria del sistema (servo / loop respecto a bobina)
# -------------------------------------------------------

def distancia(theta_deg: float, L_m: float, y0_m: float) -> float:
    """
    Distancia (m) entre el punto de medicion (loop) y el eje de la bobina,
    en funcion del angulo del servo.

    Parametros:
    - theta_deg: angulo en grados
    - L_m: longitud efectiva del brazo (m)
    - y0_m: distancia fija base (m)

    Modelo: ley del coseno adaptada a la geometria del montaje.
    """
    theta_rad = deg_rad(theta_deg)
    termino = L_m**2 + y0_m**2 - 2.0 * y0_m * L_m * math.sin(theta_rad)
    return math.sqrt(termino)


# -------------------------------------------------------
# Divisor de tension: reconstruccion de Vin real
# -------------------------------------------------------

def vin_real(v_div: float, Rtop: float, Rbot: float) -> float:
    """
    Reconstruye el voltaje real aplicado a la bobina a partir del divisor.

    Vdiv = Vin * (Rbot / (Rtop + Rbot))
    => Vin = Vdiv * (Rtop + Rbot) / Rbot
    """
    factor = (Rtop + Rbot) / Rbot
    return v_div * factor


# -------------------------------------------------------
# Modelo electrico equivalente (por tramos)
# -------------------------------------------------------

def req_por_tramos(vin: float, req_baja: float, req_alta: float, umbral: float = 11.0) -> float:
    """
    Selecciona la resistencia equivalente segun el voltaje real aplicado.

    Criterio:
    - Si Vin < umbral  -> Req_baja  (regimen sin arco)
    - Si Vin >= umbral -> Req_alta  (regimen activo con corona/arco)
    """
    return req_baja if vin < umbral else req_alta


def potencia_in(vin: float, req: float) -> float:
    """
    Potencia electrica teorica de entrada:
        Pin = Vin^2 / Req
    """
    req = max(req, 1e-12)  # proteccion simple contra division por cero
    return (vin ** 2) / req


# -------------------------------------------------------
# Relaciones teoricas para senales (modelo simple)
# -------------------------------------------------------

def tendencia(r: float, n: float) -> float:
    """
    Relacion teorica tipo 1 / r^n.
    """
    if r <= 0.0:
        return float("inf")
    return 1.0 / (r ** n)


def b_teo(r_m: float, Kb: float = 1.0, n: float = 1.0) -> float:
    """
    Senal teorica asociada al sensor RF:
        B_teo = Kb * (1 / r^n)
    """
    return Kb * tendencia(r_m, n)


def l_teo(r_m: float, Kl: float = 1.0) -> float:
    """
    Senal teorica asociada al fotodiodo:
        L_teo = Kl * (1 / r^2)
    """
    return Kl * tendencia(r_m, 2.0)


# -------------------------------------------------------
# Senales experimentales (paso directo)
# -------------------------------------------------------

def b_exp(v_rf: float) -> float:
    """Senal experimental RF (voltaje medido)."""
    return v_rf


def l_exp(v_photo: float) -> float:
    """Senal experimental fotodiodo (voltaje medido)."""
    return v_photo


# -------------------------------------------------------
# Errores
# -------------------------------------------------------

def error_abs(exp: float, teo: float) -> float:
    """Error absoluto: exp - teo."""
    return exp - teo


def error_rel(exp: float, teo: float, eps: float = 1e-12) -> float:
    """
    Error relativo: (exp - teo) / teo
    Si teo es cercano a cero, retorna infinito.
    """
    if abs(teo) < eps:
        return float("inf")
    return (exp - teo) / teo
