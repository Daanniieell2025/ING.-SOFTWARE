"""
Sprint 1: Sensores del sistema Tesla Monitor

Este archivo define las clases de sensores utilizados en el proyecto.
En este sprint NO existe comunicacion real con hardware.
Las clases solo representan la estructura del sistema.
"""


class RfSensor:
    """
    Sensor RF:  Representa el sensor encargado de detectar actividad RF generada por la bobina de Tesla.
    """

    def __init__(self):
        self.valor = None

    def leer(self):
        """
        Lee el valor del sensor RF
        """
        return self.valor


class PhotodiodeSensor:
    """
    Sensor de fotodiodo:  Representa el sensor encargado de medir la intensidad luminosa del arco electrico.
    """

    def __init__(self):
        self.valor = None

    def leer(self):
        """
        Lee el valor del sensor de fotodiodo.

        """
        return self.valor
