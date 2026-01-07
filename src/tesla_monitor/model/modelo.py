"""
Sprint 1: Modelo del sistema

Este modulo representa la capa Modelo del patron MVC.

Su responsabilidad sera:
- Recibir datos desde los sensores
- Utilizar las ecuaciones del sistema
- Preparar la informacion para ser utilizada por el controlador y la vista

En Sprint 2 este modulo contendra la logica principal de procesamiento de datos del sistema Tesla Monitor.


Sprint 2: 
- Desarrollo de logica del Model, el cual recibe la muestra cruda desde el controller y aplica lo que esta en el archivo ecuaciones.py
- Se genera la MuestraProcesada y mantiene un historial de resultados


"""

from .muestras import MuestraCruda, MuestraProcesada
from . import ecuaciones


# Se define el cerebro del sistema, el que trasnforma los datos crudos a procesados 

class Modelo:
    def __init__(  
        # Se inicializa el modelo con los parametros fisicos del sistema
        self,
        L_m: float,
        y0_m: float,
        Rtop: float,
        Rbot: float,
        Req: float,
        Kb: float = 1.0,
        Kl: float = 1.0 
    ):

# parametros geometricos
        self.L_m = L_m
        self.y0_m = y0_m

# parametros electricos
        self.Rtop = Rtop
        self.Rbot = Rbot
        self.Req = Req

# parametros de escala teoricos
        self.Kb = Kb
        self.Kl = Kl

# historial de muestras procesadas
        self.historial: list[MuestraProcesada] =[]


# se procesa una muestra cruda y se genera una muetsra procesada
# calcula variables teoricas y experimentales
# guarda el resultado en el historial del modelo

    def procesar_muestra(self, mc: MuestraCruda) -> MuestraProcesada:

        # 1) Distancia del loop a la bobina en base al angulo del servo
        r_m = ecuaciones.distancia(mc.servo_deg, self.L_m, self.y0_m)

        # 2) Voltaje real de entrada
        V_in = ecuaciones.vin_real(mc.v_div, self.Rtop, self.Rbot)

        # 3) Potencia teorica
        P_in = ecuaciones.potencia_in(V_in, self.Req)

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
            t_ms = mc.t_ms,
            servo_deg = mc.servo_deg,
            v_div = mc.v_div,
            v_rf = mc.v_rf,
            v_photo = mc.v_photo,
            r_m = r_m,
            V_in = V_in,
            P_in = P_in,
            B_exp = B_exp,
            B_teo = B_teo,
            L_exp = L_exp,
            L_teo = L_teo,
            err_B_abs = err_B_abs,
            err_L_abs = err_L_abs,
            err_B_rel = err_B_rel,
            err_L_rel = err_L_rel,
        )

        # 8) Se guarda en el historial y lo devuelve
        self.historial.append(mp)
        return mp

# Se limpia el historial de resultados del modelo
    
    def reset(self) -> None:
        self.historial.clear()

# Entrega el historial de muestras procesadas para graficos o exportaciones

    def get_historial(self) -> list[MuestraProcesada]:
        return list(self.historial)  # retorna una copia para evitar que otras capas modifiquen directamente el estado interno del modelo



