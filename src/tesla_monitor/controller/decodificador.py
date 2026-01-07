
# Este modulo se encarga de decodificr las tramas de datos que vienen del microcontrolador o de archivos de simulacion 
# Convierte lineas de texto en objetos MuestraCruda

# Importa la estructura de datos crudos utilizados por el modelo
from model.muestras import MuestraCruda

# se define la funcion de decodificacion de una linea del protocolo de comunicacion 
def decodificar_linea_data(linea: str) -> MuestraCruda:
    # se elimina el salto de linea y espacios laterales para normalizar entrada
    linea = linea.strip()

    # se valida que la linea comience con el prefijo esperado del protocolo
    if not linea.startswith("DATA,"):
        raise ValueError("Linea invalida: no comienza con 'DATA,'")

    # se separan los campos usando coma como separador 
    partes = linea.split(",")

    # formato esperado: 6 elementos -> ["DATA", t_ms, servo_deg, v_div, v_rf, v_photo]
    if len(partes) != 6:
        raise ValueError("Linea invalida: cantidad de campos distinta a 6")


    # Se extraen los campos que vienen como texto)
    t_ms_str = partes[1]
    servo_deg_str = partes[2]
    v_div_str = partes[3]
    v_rf_str = partes[4]
    v_photo_str = partes[5]

    # Se convierten los tipos segun lo esperado por MuestraCruda
    #  t_ms y servo_deg son enteros
    #  los voltajes son numeros decimales 
    try:
        t_ms = int(t_ms_str)
        servo_deg = int(servo_deg_str)
        v_div = float(v_div_str)
        v_rf = float(v_rf_str)
        v_photo = float(v_photo_str)
    except ValueError as e:
        # Si algun campo no se puede convertir, se informa que la linea no cumple el formato
        raise ValueError("Linea invalida: la conversion fallo") from e

    # Se construye la muestra cruda usando el formato comun del sistema 
    muestra = MuestraCruda(
        t_ms=t_ms,
        servo_deg=servo_deg,
        v_div=v_div,
        v_rf=v_rf,
        v_photo=v_photo
    )

    # Se retorna la muestra lista para ser enviada al Modelo
    return muestra
