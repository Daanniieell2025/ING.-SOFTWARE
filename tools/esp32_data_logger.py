"""
esp32_data_logger.py
====================

OBJETIVO (fase actual del proyecto)
-----------------------------------
Generar una "tanda" de datos (base de datos) capturando lo que envia la ESP32
por USB Serial durante un tiempo fijo (por defecto 30 s) y guardandolo en CSV.

FLUJO DE USO (interactivo, como tu lo quieres)
----------------------------------------------
1) Se valida primero en Arduino IDE / Serial Monitor (ver DATA en pantalla).
2) Se cierra Arduino IDE (o al menos Serial Monitor) para liberar el COM3.
3) En terminal, dentro de carpeta tools/, ejecutamos:
      python ESP32-Data-Logger.py
4) El script:
   - Verifica comunicacion (PING->PONG)
   - Envia STOP (por si el firmware parte con AutoStream=ON)
   - Configura RAW y RATE
   - Inicia un "PREVIEW" (10 lineas DATA) para confirmar que esta llegando data
   - Pregunta si se quiere iniciar el experimento
   - Si se confirma, captura 30 s y guarda CSV en ../data/
   - Detiene streaming y muestra el path final del archivo

IMPORTANTE
-------------------
- La ESP32 NO hace modelo, NO filtra, NO promedia por software.
- Este script tampoco filtra ni promedia: SOLO CAPTURA Y GUARDA.
"""

from __future__ import annotations

import csv
import os
import time
from datetime import datetime

import serial  # pip install pyserial


# ============================================================
# 1) CONFIGURACIoN
# ============================================================

PORT = "COM3"               # Tu puerto
BAUD = 115200               # Debe coincidir con el firmware

CAPTURE_SECONDS = 30        # Duracion del experimento (s)
SAMPLE_RATE_HZ = 20         # Frecuencia solicitada al firmware (Hz)
SEND_RAW = 0                # 0 = voltajes (float) / 1 = ADC crudo (int)

PREVIEW_LINES = 10          # Cantidad de lineas DATA a mostrar como "preview"

# Carpeta donde se guardan los CSV (ejecutas desde tools/, por eso ../data)
DATA_DIR = os.path.join("..", "data")
FILE_PREFIX = "run"


# ============================================================
# 2) SERIAL: ENVIAR / LEER / ESPERAR RESPUESTA
# ============================================================

def send_command(ser: serial.Serial, command: str) -> None:
    """Envia un comando a la ESP32 terminado en '\\n'."""
    ser.write((command + "\n").encode("utf-8"))


def read_line(ser: serial.Serial) -> str | None:
    """
    Lee una linea si existe.
    Retorna string sin \\r/\\n o None si no hay datos disponibles.
    """
    if ser.in_waiting <= 0:
        return None
    raw = ser.readline()
    line = raw.decode("utf-8", errors="replace").strip()
    return line if line else None


def wait_for_exact_reply(ser: serial.Serial, expected: str, timeout_s: float = 2.0) -> bool:
    """
    Espera hasta recibir exactamente 'expected' (ej: 'PONG' o 'OK').
    Ignora READY/INFO/DATA/etc.
    """
    t0 = time.time()
    while (time.time() - t0) < timeout_s:
        line = read_line(ser)
        if line is None:
            time.sleep(0.01)
            continue
        if line == expected:
            return True
    return False


# ============================================================
# 3) PARSEO DE LiNEAS DATA
# ============================================================

def parse_data_line(line: str, send_raw: int) -> tuple[int, int, float | int, float | int, float | int] | None:
    """
    Parsea:
      DATA,<ms>,<servo_deg>,<x_div>,<x_rf>,<x_photo>

    Retorna:
      (ms, servo_deg, x_div, x_rf, x_photo)
    o None si la linea no cumple formato.
    """
    if not line.startswith("DATA,"):
        return None

    parts = line.split(",")
    if len(parts) != 6:
        return None

    try:
        ms = int(parts[1])
        servo_deg = int(parts[2])

        if send_raw == 1:
            x_div = int(parts[3])
            x_rf = int(parts[4])
            x_photo = int(parts[5])
        else:
            x_div = float(parts[3])
            x_rf = float(parts[4])
            x_photo = float(parts[5])

        return (ms, servo_deg, x_div, x_rf, x_photo)

    except ValueError:
        return None


# ============================================================
# 4) UI DE TERMINAL: CONFIRMAR INICIO
# ============================================================

def ask_user_to_start() -> bool:
    """Pregunta al usuario si quiere iniciar el experimento."""
    print("\n--------------------------------------------")
    print("✅ Preview completado. Si viste datos coherentes, puedes iniciar.")
    print("Escribe 'iniciar' para comenzar, o 'cancelar' para salir.")
    print("--------------------------------------------")

    while True:
        user = input("> ").strip().lower()
        if user in ("iniciar", "inicio", "start", "s", "si", "sí", "y", "yes"):
            return True
        if user in ("cancelar", "cancel", "no", "n", "salir", "exit", "q"):
            return False
        print("No entendi. Escribe 'iniciar' o 'cancelar'.")


# ============================================================
# 5) PREVIEW: MOSTRAR N LINEAS DATA (RAPIDO)
# ============================================================

def preview_data_lines(ser: serial.Serial, send_raw: int, n_lines: int) -> int:
    """
    Inicia streaming, captura y muestra n lineas DATA, y luego detiene streaming.

    Retorna:
      cantidad de lineas DATA vaidas mostradas.
    """
    print("\n PREVIEW: mostrando lineas DATA para confirmar recepcion...")

    # Iniciar streaming
    send_command(ser, "START")
    if not wait_for_exact_reply(ser, "OK", timeout_s=2.0):
        print("❌ La ESP32 no respondio OK a START (preview).")
        return 0

    shown = 0
    t0 = time.time()

    # Intentamos obtener n lineas validas, con un timeout global para no quedar pegados
    while shown < n_lines:
        # Timeout global de seguridad (por si no llega data)
        if (time.time() - t0) > 5.0:
            print("⚠️ Timeout en preview: no llegaron suficientes lineas DATA.")
            break

        line = read_line(ser)
        if line is None:
            time.sleep(0.001)
            continue

        parsed = parse_data_line(line, send_raw)
        if parsed is None:
            continue

        # Mostramos la linea en formato legible
        ms, servo, x1, x2, x3 = parsed
        if send_raw == 1:
            print(f"DATA  ms={ms:<8} servo={servo:<3} adc_div={x1:<5} adc_rf={x2:<5} adc_photo={x3:<5}")
        else:
            print(f"DATA  ms={ms:<8} servo={servo:<3} v_div={x1:<7.4f} v_rf={x2:<7.4f} v_photo={x3:<7.4f}")

        shown += 1

    # Detener streaming
    send_command(ser, "STOP")
    wait_for_exact_reply(ser, "OK", timeout_s=2.0)

    print(f"✅ Preview listo: {shown}/{n_lines} lineas mostradas.\n")
    return shown


# ============================================================
# 6) MAIN: FLUJO COMPLETO
# ============================================================

def main() -> None:
    # Asegurar carpeta data/
    os.makedirs(DATA_DIR, exist_ok=True)

    # Nombre del CSV con timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{FILE_PREFIX}_{timestamp}_{CAPTURE_SECONDS}s.csv"
    output_path = os.path.join(DATA_DIR, filename)

    # Abrir puerto serial
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.2)
    except serial.SerialException as e:
        print("❌ No pude abrir el puerto serial.")
        print("Causas tipicas:")
        print("- Arduino IDE / Serial Monitor está abierto y ocupa COM3")
        print("- COM incorrecto")
        print("- Driver/cable")
        print(f"Detalle: {e}")
        return

    try:
        # Esperar reset tipico al abrir puerto
        time.sleep(2.0)

        # Limpiar buffer
        ser.reset_input_buffer()

        # Verificar comunicacion
        send_command(ser, "PING")
        if not wait_for_exact_reply(ser, "PONG", timeout_s=2.0):
            print("❌ No recibi PONG. Revisa firmware/BAUD/COM/cable.")
            return

        # STOP por seguridad (si el firmware parte en AutoStream)
        send_command(ser, "STOP")
        wait_for_exact_reply(ser, "OK", timeout_s=1.0)

        # Configurar RAW
        send_command(ser, f"RAW={SEND_RAW}")
        if not wait_for_exact_reply(ser, "OK", timeout_s=2.0):
            print("❌ La ESP32 no respondio OK a RAW=...")
            return

        # Configurar RATE
        send_command(ser, f"RATE={SAMPLE_RATE_HZ}")
        if not wait_for_exact_reply(ser, "OK", timeout_s=2.0):
            print("❌ La ESP32 no respondio OK a RATE=...")
            return

        # Mostrar configuracion en consola
        print("\n--------------------------------------------")
        print("✅ Conexion OK (PING/PONG). Configuracion enviada.")
        print(f" RATE={SAMPLE_RATE_HZ} Hz | RAW={SEND_RAW} | DUR={CAPTURE_SECONDS} s | PORT={PORT}")
        print("--------------------------------------------")

        # PREVIEW (10 lineas DATA)
        shown = preview_data_lines(ser, SEND_RAW, PREVIEW_LINES)
        if shown == 0:
            print("❌ No se mostraron lineas DATA en preview. No iniciare captura.")
            print("Revisa: firmware, conexiones ADC, baud, o si el ESP esta reiniciándose.")
            return

        # Preguntar si inicia experimento
        if not ask_user_to_start():
            print("🚫 Experimento cancelado por el usuario. No se genero CSV.")
            return

        # Abrir archivo CSV y escribir encabezados
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Encabezados: agregamos tiempo absoluto y tiempo relativo
            # ms_abs  = millis() absoluto desde reset de la ESP32
            # ms_rel  = ms_abs - ms_abs_primera_muestra
            # s_rel   = ms_rel / 1000.0
            if SEND_RAW == 1:
                writer.writerow(["ms_abs", "ms_rel", "s_rel", "servo_deg", "adc_div", "adc_rf", "adc_photo"])
            else:
                writer.writerow(["ms_abs", "ms_rel", "s_rel", "servo_deg", "v_div", "v_rf", "v_photo"])

            # Iniciar streaming real
            send_command(ser, "START")
            if not wait_for_exact_reply(ser, "OK", timeout_s=2.0):
                print("❌ La ESP32 no respondio OK a START (captura).")
                return

            print("\n🟢 Experimento iniciado.")
            print(f"⏱️ Capturando durante {CAPTURE_SECONDS} segundos...")

            # Captura por tiempo
            t0 = time.time()
            saved_rows = 0

            # Guardamos el ms inicial de la primera muestra valida
            ms0_abs = None

            while (time.time() - t0) < CAPTURE_SECONDS:
                line = read_line(ser)
                if line is None:
                    time.sleep(0.001)
                    continue

                parsed = parse_data_line(line, SEND_RAW)
                if parsed is None:
                    continue

                ms_abs, servo_deg, x_div, x_rf, x_photo = parsed

                # Definir el origen temporal en la primera muestra valida
                if ms0_abs is None:
                    ms0_abs = ms_abs

                # Calculo de tiempo relativo
                ms_rel = ms_abs - ms0_abs
                s_rel = ms_rel / 1000.0

                # Guardar fila con tiempos agregados
                writer.writerow([ms_abs, ms_rel, f"{s_rel:.3f}", servo_deg, x_div, x_rf, x_photo])
                saved_rows += 1

            # Detener streaming al final
            send_command(ser, "STOP")
            wait_for_exact_reply(ser, "OK", timeout_s=2.0)


        # Mensaje final
        print("\n✅ Experimento terminado.")
        print(f"📄 CSV generado: {output_path}")
        print(f"📊 Filas guardadas: {saved_rows}")
        print("👉 Revisa la carpeta 'data' para ver el archivo.")

    finally:
        ser.close()


if __name__ == "__main__":
    main()
