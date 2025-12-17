"""
Sprint 1:  Microcontrolador del sistema

Este modulo representa el microcontrolador utilizado en el sistema Tesla Monitor.

El microcontrolador sera responsable de:
- Leer los sensores del sistema
- Controlar el servomotor
- Enviar datos al software de monitoreo

En Sprint 1 no existe comunicacion real con hardware. Este archivo define unicamente la estructura general.
"""


class ServoMotor:
    """
    Servomotor del sistema:  Representa el actuador encargado de posicionar mecanicamente el loop del sensor RF.
    """

    def __init__(self):
        self.angulo_actual = 0

    def mover_a(self, angulo):
        """
        Mueve el servomotor al angulo indicado.

        Sprint 1:
        - No se envian señales reales
        - El metodo solo representa la accion
        """
        self.angulo_actual = angulo


class Microcontrolador:
    """
    Microcontrolador del sistema:  Representa la unidad encargada de interactuar con los sensores y actuadores del sistema.
    """

    def __init__(self):
        self.servo = ServoMotor()

    def iniciar(self):
        """
        Inicializa el microcontrolador.

        Sprint 1:
        - Metodo representativo
        - No realiza acciones reales
        """
        pass

    def detener(self):
        """
        Detiene la operacion del microcontrolador.

        Sprint 1:
        - Metodo representativo
        """
        pass
