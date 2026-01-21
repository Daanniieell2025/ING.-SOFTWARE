"""
Controller del sistema Tesla Monitor (Sprint 3)

Este modulo corresponde a la capa Controller del patron MVC.

Responsabilidades:
- Coordinar la interaccion entre Hardware (ESP32), Model y View
- Gestionar el flujo del experimento
- Aplicar validaciones de seguridad
- Controlar tiempos maximos de operacion
- Exportar resultados a CSV
"""

# ------------------------------------------------------------
# Imports estandar
# ------------------------------------------------------------

import time
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ------------------------------------------------------------
# Imports del proyecto
# ------------------------------------------------------------

from tesla_monitor.config.settings import SETTINGS
from tesla_monitor.model.modelo import Modelo
from tesla_monitor.model.almacenamiento import exportar_csv
from tesla_monitor.controller.fuentes import (
    FuenteDatos,
    FuenteSerialESP32,
    FuenteSimulada,
    FuenteCSV,
)

# ------------------------------------------------------------
# Enumeraciones de estado y modo
# ------------------------------------------------------------

class EstadoController(str, Enum):
    IDLE = "IDLE"
    READY = "READY"
    RUNNING_AUTO = "RUNNING_AUTO"
    RUNNING_MANUAL = "RUNNING_MANUAL"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


class ModoExperimento(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


# ------------------------------------------------------------
# Configuracion del experimento
# ------------------------------------------------------------

@dataclass
class ConfigExperimento:
    modo: ModoExperimento
    duracion_s: float
    servo_deg_inicial: int = 0
    ruta_csv: Optional[str] = None


# ------------------------------------------------------------
# Controller principal
# ------------------------------------------------------------

class TeslaController:

    def __init__(self, fuente: FuenteDatos, settings=SETTINGS):

        self.fuente = fuente
        self.settings = settings

        # Modelo con parametros actualizados (dos Req)
        self.modelo = Modelo(
            L_m=self.settings.L_m,
            y0_m=self.settings.y0_m,
            Rtop=self.settings.Rtop,
            Rbot=self.settings.Rbot,
            Req_baja=self.settings.Req_baja,
            Req_alta=self.settings.Req_alta,
            vin_umbral_req_v=self.settings.vin_umbral_req_v,
            Kb=self.settings.Kb,
            Kl=self.settings.Kl,
        )

        self._estado = EstadoController.IDLE
        self._checklist_ok = False
        self._cfg: Optional[ConfigExperimento] = None

        self._t_inicio: Optional[float] = None
        self._t_fin: Optional[float] = None

        self._ultimo_csv: Optional[Path] = None
        self._iniciado = False
        self._servo_deg_actual = 0
        self._error_msg: Optional[str] = None

    # --------------------------------------------------------
    # Getters
    # --------------------------------------------------------

    def get_estado(self) -> EstadoController:
        return self._estado

    def get_error_msg(self) -> Optional[str]:
        return self._error_msg

    def get_ultimo_csv_path(self) -> Optional[Path]:
        return self._ultimo_csv

    def get_tiempo_restante_s(self) -> Optional[float]:
        if self._t_fin is None:
            return None
        return max(0.0, self._t_fin - time.time())

    def get_historial(self):
        return self.modelo.get_historial()

    # --------------------------------------------------------
    # Checklist de seguridad
    # --------------------------------------------------------

    def set_checklist_validado(self, ok: bool) -> None:
        """
        La View llama a este metodo cuando el usuario completa el checklist.

        Regla importante para Streamlit:
        - No debemos cambiar FINISHED -> READY automaticamente,
        porque la vista hace rerun y volveria a ocultar el estado FINISHED.
        """
        self._checklist_ok = bool(ok)

        # Si el checklist se valida, solo habilitamos READY desde IDLE
        if self._checklist_ok and self._estado == EstadoController.IDLE:
            self._estado = EstadoController.READY

        # Si el checklist se desmarca, solo volvemos a IDLE si estabamos en READY
        if (not self._checklist_ok) and self._estado == EstadoController.READY:
            self._estado = EstadoController.IDLE

    # --------------------------------------------------------
    # Recursos
    # --------------------------------------------------------

    def iniciar_recursos(self) -> None:
        if self._iniciado:
            return

        if isinstance(self.fuente, FuenteSerialESP32):
            self.fuente.conectar()

        self._iniciado = True

    def cerrar_recursos(self) -> None:
        if not self._iniciado:
            return

        if isinstance(self.fuente, FuenteSerialESP32):
            try:
                self.fuente.stop_stream()
            except Exception:
                pass
            self.fuente.cerrar()

        if isinstance(self.fuente, FuenteCSV):
            self.fuente.cerrar()

        self._iniciado = False

    # --------------------------------------------------------
    # Control del servo
    # --------------------------------------------------------

    def set_servo_deg(self, servo_deg: int) -> None:

        if self._estado != EstadoController.RUNNING_MANUAL:
            raise RuntimeError("Servo solo permitido en modo MANUAL.")

        servo_deg = int(servo_deg)

        if (
            servo_deg < self.settings.servo_deg_min
            or servo_deg > self.settings.servo_deg_max
        ):
            raise ValueError("Angulo de servo fuera de rango.")

        self._servo_deg_actual = servo_deg

        if isinstance(self.fuente, (FuenteSerialESP32, FuenteSimulada)):
            self.fuente.set_servo_deg(self._servo_deg_actual)

    def preview_servo_deg(self, servo_deg: int) -> None:
        """
        Permite mover el servo antes de iniciar el experimento (estado READY).
        Util para previsualizar la posicion inicial y validar que el servo responde.
        """
        if self._estado != EstadoController.READY:
            raise RuntimeError("preview_servo_deg solo permitido en estado READY.")

        servo_deg = int(servo_deg)

        if (
            servo_deg < self.settings.servo_deg_min
            or servo_deg > self.settings.servo_deg_max
        ):
            raise ValueError("Angulo de servo fuera de rango.")

        self._servo_deg_actual = servo_deg

        if isinstance(self.fuente, (FuenteSerialESP32, FuenteSimulada)):
            self.fuente.set_servo_deg(self._servo_deg_actual)

    # --------------------------------------------------------
    # Inicio y fin de experimento
    # --------------------------------------------------------

    def start_experimento(self, cfg: ConfigExperimento) -> None:

        if not self._checklist_ok:
            raise RuntimeError("Checklist no validado.")

        if self._estado != EstadoController.READY:
            raise RuntimeError("Controller no esta en estado READY.")

        if cfg.duracion_s < self.settings.min_experimento_s:
            raise ValueError("Duracion menor al minimo permitido.")

        if cfg.duracion_s > self.settings.max_experimento_s:
            raise ValueError("Duracion excede limite de seguridad.")

        if cfg.ruta_csv is None:
            cfg.ruta_csv = self.settings.ruta_csv

        self._cfg = cfg
        self.modelo.reset()
        self._ultimo_csv = None

        self.iniciar_recursos()

        if isinstance(self.fuente, FuenteSerialESP32):
            self.fuente.start_stream()

        self._servo_deg_actual = int(cfg.servo_deg_inicial)

        if (
            self._servo_deg_actual < self.settings.servo_deg_min
            or self._servo_deg_actual > self.settings.servo_deg_max
        ):
            raise ValueError("Angulo de servo inicial fuera de rango.")

        if isinstance(self.fuente, (FuenteSerialESP32, FuenteSimulada)):
            self.fuente.set_servo_deg(self._servo_deg_actual)

        self._t_inicio = time.time()
        self._t_fin = self._t_inicio + float(cfg.duracion_s)

        self._estado = (
            EstadoController.RUNNING_AUTO
            if cfg.modo == ModoExperimento.AUTO
            else EstadoController.RUNNING_MANUAL
        )

        self._error_msg = None

    def stop_experimento(self) -> None:
        if self._estado not in (
            EstadoController.RUNNING_AUTO,
            EstadoController.RUNNING_MANUAL,
        ):
            return
        self._finalizar_experimento()

    # --------------------------------------------------------
    # Loop principal
    # --------------------------------------------------------

    def tick(self) -> None:

        if self._estado not in (
            EstadoController.RUNNING_AUTO,
            EstadoController.RUNNING_MANUAL,
        ):
            return

        restante = self.get_tiempo_restante_s()

        if restante is not None and restante <= 0.0:
            self._finalizar_experimento()
            return

        try:
            mc = self.fuente.leer_muestra()
        except Exception as e:
            self._estado = EstadoController.ERROR
            self._error_msg = f"Error leyendo muestra: {e}"
            self._detener_stream_si_aplica()
            return

        self.modelo.procesar_muestra(mc)

        # Nota:
        # - No se usa time.sleep aqui.
        # - Con ESP32 real, la fuente bloquea hasta que llega DATA (rate lo define firmware).
        # - Con Simulada, el tiempo interno avanza por dt_ms sin depender del reloj real.
        # - La vista (Streamlit) controla la frecuencia de llamados a tick() y puede hacer batch ticks.

    # --------------------------------------------------------
    # Finalizacion
    # --------------------------------------------------------

    def _detener_stream_si_aplica(self) -> None:
        if isinstance(self.fuente, FuenteSerialESP32):
            try:
                self.fuente.stop_stream()
            except Exception:
                pass

    def _finalizar_experimento(self) -> None:

        self._detener_stream_si_aplica()

        historial = self.modelo.get_historial()
        ruta_csv = (
            self._cfg.ruta_csv if self._cfg is not None else self.settings.ruta_csv
        )

        self._ultimo_csv = exportar_csv(historial, ruta_csv)

        self._estado = EstadoController.FINISHED
        self._t_inicio = None
        self._t_fin = None

    # --------------------------------------------------------
    # Reset
    # --------------------------------------------------------

    def reset(self) -> None:

        if self._estado in (
            EstadoController.RUNNING_AUTO,
            EstadoController.RUNNING_MANUAL,
        ):
            self.stop_experimento()

        self.modelo.reset()
        self._cfg = None
        self._ultimo_csv = None
        self._t_inicio = None
        self._t_fin = None
        self._checklist_ok = False
        self._estado = EstadoController.IDLE
        self._error_msg = None
        self.cerrar_recursos()


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def construir_fuente_serial() -> FuenteSerialESP32:
    return FuenteSerialESP32(
        puerto=SETTINGS.puerto_serial,
        baudrate=SETTINGS.baudrate,
        timeout_s=SETTINGS.timeout_s,
    )


def construir_fuente_simulada() -> FuenteSimulada:
    return FuenteSimulada(
        dt_ms=SETTINGS.dt_ms,
        servo_deg=0,
        v_div_base=0.95,
        v_rf_base=0.6,
        v_photo_base=0.1,
        ruido_v_div=0.02,
        ruido_v_rf=0.02,
        ruido_v_photo=0.02,
    )
