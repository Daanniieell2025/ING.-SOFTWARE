


class SensorTemperatura:
    def __init__(self, id, valor):  # self me sirve para para hacer referencia a atributos como id y valor
        self.id = id
        self.valor = valor

    def leer(self):
        print(f"sensor {self.id}: {self.valor} Celcius")

s1 = SensorTemperatura("T1", 22.5)

s1.leer()