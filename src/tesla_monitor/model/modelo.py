"""
Sprint 1: Modelo del sistema

Este modulo representa la capa Modelo del patron MVC.

Su responsabilidad sera:
- Recibir datos desde los sensores
- Utilizar las ecuaciones del sistema
- Preparar la informacion para ser utilizada por el controlador y la vista


Sprint 2:
- Desarrollo de logica del Model, el cual recibe la muestra cruda desde el controller y aplica lo que esta en el archivo ecuaciones.py
- Se genera la MuestraProcesada y mantiene un historial de resultados

Sprint 3:
- Se incorpora un modelo electrico equivalente por tramos (dos resistencias equivalentes)
- La potencia teorica se calcula usando Req_baja o Req_alta segun Vin reconstruido desde el divisor
"""

from .muestra import MuestraCruda, MuestraProcesada
from . import ecuaciones


# Se define el cerebro del sistema, el que transforma los datos crudos a procesados

class Modelo:
    def __init__(
        # Se inicializa el modelo con los parametros fisicos del sistema
        self,
        L_m: float,
        y0_m: float,
        Rtop: float,
        Rbot: float,
        Req_baja: float,
        Req_alta: float,
        vin_umbral_req_v: float = 11.0,
        Kb: float = 1.0,
        Kl: float = 1.0
    ):

        # parametros geometricos
        self.L_m = L_m
        self.y0_m = y0_m

        # parametros electricos (divisor)
        self.Rtop = Rtop
        self.Rbot = Rbot

        # modelo electrico equivalente por tramos
        self.Req_baja = Req_baja
        self.Req_alta = Req_alta
        self.vin_umbral_req_v = vin_umbral_req_v

        # parametros de escala teoricos
        self.Kb = Kb
        self.Kl = Kl

        # historial de muestras procesadas
        self.historial: list[MuestraProcesada] = []


    # se procesa una muestra cruda y se genera una muestra procesada
    # calcula variables teoricas y experimentales
    # guarda el resultado en el historial del modelo

    def procesar_muestra(self, mc: MuestraCruda) -> MuestraProcesada:

        # 1) Distancia del loop a la bobina en base al angulo del servo
        r_m = ecuaciones.distancia(mc.servo_deg, self.L_m, self.y0_m)

        # 2) Voltaje real de entrada (reconstruido desde el divisor)
        V_in = ecuaciones.vin_real(mc.v_div, self.Rtop, self.Rbot)

        # 3) Seleccion de Req segun regimen (por tramos) y potencia teorica
        Req_usada = ecuaciones.req_por_tramos(
            V_in,
            req_baja=self.Req_baja,
            req_alta=self.Req_alta,
            umbral=self.vin_umbral_req_v
        )
        P_in = ecuaciones.potencia_in(V_in, Req_usada)

        # 4) Magnitudes experimentales
        B_exp = ecuaciones.b_exp(mc.v_rf)
        L_exp = ecuaciones.l_exp(mc.v_photo)

        # 5) Curvas teoricas
        B_teo = ecuaciones.b_teo(r_m, Kb=self.Kb, n=1.0)
        L_teo = ecuaciones.l_teo(r_m, Kl=self.Kl)

        # 6) Error absoluto y relativo
        err_B_abs = ecuaciones.error_abs(B_exp, B_teo)
        err_L_abs = ecuaciones.error_abs(L_exp, L_teo)

        err_B_rel = ecuaciones.error_rel(B_exp, B_teo)
        err_L_rel = ecuaciones.error_rel(L_exp, L_teo)

        # 7) Construccion de la muestra procesada
        mp = MuestraProcesada(
            t_ms=mc.t_ms,
            servo_deg=mc.servo_deg,
            v_div=mc.v_div,
            v_rf=mc.v_rf,
            v_photo=mc.v_photo,
            r_m=r_m,
            V_in=V_in,
            P_in=P_in,
            B_exp=B_exp,
            B_teo=B_teo,
            L_exp=L_exp,
            L_teo=L_teo,
            err_B_abs=err_B_abs,
            err_L_abs=err_L_abs,
            err_B_rel=err_B_rel,
            err_L_rel=err_L_rel,
        )

        # 8) Se guarda en el historial y lo devuelve
        self.historial.append(mp)
        return mp


    # Se limpia el historial de resultados del modelo

    def reset(self) -> None:
        self.historial.clear()


    # Entrega el historial de muestras procesadas para graficos o exportaciones

    def get_historial(self) -> list[MuestraProcesada]:
        # retorna una copia para evitar que otras capas modifiquen directamente el estado interno del modelo
        return list(self.historial)
