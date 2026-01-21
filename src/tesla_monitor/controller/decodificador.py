"""
Este modulo decodifica tramas de datos que vienen desde el microcontrolador (ESP32)
o desde fuentes de simulacion.

Objetivo:
- Convertir una linea de texto con formato "DATA,..." en un objeto MuestraCruda.

Contrato esperado (firmware -> PC):
  DATA,<t_ms>,<servo_deg>,<v_div>,<v_rf>,<v_photo>

Ejemplo:
  DATA,12345,10,0.9150,0.6231,0.1042

Notas:
- Este decodificador asume RAW=0 (valores en voltaje como float).
- Las lineas que no sean DATA se manejan fuera (en FuenteSerialESP32), aqui solo se valida DATA.
"""

from tesla_monitor.model.muestra import MuestraCruda


def decodificar_linea_data(linea: str) -> MuestraCruda:
    """
    Decodifica una linea "DATA,..." y retorna una MuestraCruda.

    Parametros:
    - linea: string recibido por serial (o desde archivo), debe iniciar con "DATA,"

    Retorna:
    - MuestraCruda con los campos convertidos a tipo correcto

    Errores:
    - ValueError si el formato no coincide o si falla la conversion de tipos
    """

    # Normaliza la linea (quita espacios y saltos de linea)
    linea = linea.strip()

    # Verifica prefijo del protocolo
    if not linea.startswith("DATA,"):
        raise ValueError("Linea invalida: no comienza con 'DATA,'")

    # Separa campos
    partes = linea.split(",")

    # Formato esperado: 6 elementos
    # ["DATA", t_ms, servo_deg, v_div, v_rf, v_photo]
    if len(partes) != 6:
        raise ValueError("Linea invalida: cantidad de campos distinta a 6")

    # Extrae campos como texto
    t_ms_str = partes[1]
    servo_deg_str = partes[2]
    v_div_str = partes[3]
    v_rf_str = partes[4]
    v_photo_str = partes[5]

    # Convierte tipos
    # - t_ms, servo_deg: int
    # - v_div, v_rf, v_photo: float
    try:
        t_ms = int(t_ms_str)
        servo_deg = int(servo_deg_str)
        v_div = float(v_div_str)
        v_rf = float(v_rf_str)
        v_photo = float(v_photo_str)
    except ValueError as e:
        raise ValueError("Linea invalida: conversion de tipos fallo") from e

    # Construye y retorna la muestra cruda
    return MuestraCruda(
        t_ms=t_ms,
        servo_deg=servo_deg,
        v_div=v_div,
        v_rf=v_rf,
        v_photo=v_photo,
    )

