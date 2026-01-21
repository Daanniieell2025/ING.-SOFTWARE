/*
  ============================================================
  ESP32 - ADC + Servo + Serial (pasarela de datos)
  ============================================================

  IDEA CLAVE:
  - Este firmware NO modela la bobina Tesla.
  - NO calcula Vin real ni potencia.
  - NO filtra ni promedia.
  - Solo lee sensores + mueve servo + manda datos al PC por Serial.


  INTERFAZ SERIAL (contrato):
  - PC -> ESP32: comandos de texto (una linea por comando)
  - ESP32 -> PC: lineas tipo CSV, faciles de parsear

  Lineas de datos:
    DATA,<ms>,<servo_deg>,<x_div>,<x_rf>,<x_photo>

  Donde:
  - ms = millis() desde que se encendio la ESP32
  - servo_deg = angulo actual reportado
  - x_* = voltajes aproximados (RAW=0) o ADC crudo (RAW=1)

  Comandos soportados:
  - PING     -> PONG
  - START    -> streaming = true
  - STOP     -> streaming = false
  - SERVO=15 -> mueve servo (0..30) o ERROR
  - RATE=20  -> cambia frecuencia en Hz (ej 20 Hz -> 50 ms)
  - RAW=0/1  -> cambia modo de envio
*/

#include <Arduino.h>     // Serial, millis, delay, analogRead, etc.
#include <ESP32Servo.h>  // PWM servo en ESP32
#include <string.h>      // strlen, strcmp, strncmp

// ============================================================
// 1) CONFIGURACION DE PINES (ajustar segun cableado real)
// ============================================================
//
// Importante:
// - ADC1 (GPIO 32..39) funciona bien siempre.
// - ADC2 puede fallar si se usa WiFi/BLE.
// - GPIO34/35 son solo entrada (perfectos para ADC).
//

static const int PIN_ADC_DIV   = 34;   // ADC divisor tension (Vbobina escalado)
static const int PIN_ADC_RF    = 32;   // ADC salida AD8307 (RF)
static const int PIN_ADC_PHOTO = 35;   // ADC salida fotodiodo (filtrado analogico)

// Servo:
// - No usar GPIO34/35 porque no pueden sacar PWM (son solo entrada).
static const int PIN_SERVO     = 27;   // GPIO con PWM para servo

// ============================================================
// 2) PARAMETROS DEL SERVO (seguridad mecanica)
// ============================================================
//
// Limite duro: protege la mecanica del montaje.
// Si llega un angulo fuera de rango desde PC, no se ejecuta.
//
static const int SERVO_MIN_DEG = 0;
static const int SERVO_MAX_DEG = 30;

// ============================================================
// 3) PARAMETROS DEL ADC (conversion a voltaje)
// ============================================================
//
// ADC del ESP32:
// - Resolucion tipica 12 bits => 0..4095
// - La conversion a voltaje es aproximada (Vref nominal 3.3V)
// - El proyecto usa estas lecturas como entrada cruda para Python
//
static const int ADC_BITS = 12;
static const int ADC_MAX  = (1 << ADC_BITS) - 1;  // 4095
static const float ADC_VREF = 3.3f;               // aproximacion

// ============================================================
// 4) ESTADO DEL SISTEMA (variables que cambian en ejecucion)
// ============================================================

Servo myServo;            // objeto servo
int servoDeg = 0;         // angulo actual (tambien se reporta en DATA)

bool streaming = false;   // streaming OFF por defecto (PC debe mandar START)
bool sendRaw   = false;   // RAW=0 por defecto (mandar voltajes, no enteros ADC)

// Frecuencia de muestreo:
// - 20 Hz por defecto: 50 ms entre muestras
// - Debe calzar con el dt_ms del software en PC (Settings)
// - El PC puede cambiarla mandando RATE=xx
float rateHz = 20.0f;
uint32_t samplePeriodMs = 50;
uint32_t lastSampleMs = 0;

// ============================================================
// 5) BUFFER DE COMANDOS (lectura por lineas)
// ============================================================
//
// Se arma el comando caracter por caracter hasta encontrar '\n'.
// Esto permite comandos simples como "SERVO=15\n".
//
static const int CMD_BUF_LEN = 128;
char cmdBuf[CMD_BUF_LEN];
int cmdIdx = 0;

// ============================================================
// 6) FUNCIONES DE APOYO
// ============================================================

// Convierte ADC (0..4095) a voltaje aproximado (0..3.3V)
// Nota: para mediciones exactas, se calibra en el lado PC con el divisor medido.
static float ConvertAdcToVolt(int adcValue)
{
  // V = (adc / 4095) * 3.3
  return ((float)adcValue * ADC_VREF) / (float)ADC_MAX;
}

// Mueve servo aplicando un limite duro 0..30.
// Si es invalido, responde "ERROR,ServoOutOfRange" y NO mueve.
static void ApplyServoAngleWithLimit(int requestedDeg)
{
  if (requestedDeg < SERVO_MIN_DEG || requestedDeg > SERVO_MAX_DEG)
  {
    Serial.println("ERROR,ServoOutOfRange");
    return;
  }

  // Guardamos estado y movemos fisicamente
  servoDeg = requestedDeg;
  myServo.write(servoDeg);

  // Confirmacion simple para el PC
  Serial.println("OK");
}

// Ajusta frecuencia de muestreo.
// Entrada: RATE=xx (Hz). Ej: RATE=20 => 50 ms.
// Responde OK o ERROR.
static void SetSampleRateHz(float requestedHz)
{
  // Proteccion: evitamos rates absurdos
  // (muy alto puede saturar serial y no aporta para este demo)
  if (requestedHz <= 0.1f || requestedHz > 500.0f)
  {
    Serial.println("ERROR,RateOutOfRange");
    return;
  }

  rateHz = requestedHz;

  // Convertimos Hz a periodo en ms
  samplePeriodMs = (uint32_t)(1000.0f / rateHz);

  // Seguridad: si rate es muy alto, el periodo podria quedar 0 por casting
  if (samplePeriodMs < 1) samplePeriodMs = 1;

  Serial.println("OK");
}

// Ajusta modo RAW.
// RAW=0 -> envia voltajes (float con 4 decimales)
// RAW=1 -> envia enteros ADC (0..4095)
static void SetRawMode(int rawFlag)
{
  sendRaw = (rawFlag != 0);
  Serial.println("OK");
}

// Lee sensores y manda una linea DATA CSV.
// Importante: NO filtra, NO promedia.
// La validacion/modelo se hace en Python.
static void ReadSensorsAndSendDataLine()
{
  // Tiempo desde encendido
  uint32_t msNow = millis();

  // Lecturas ADC crudas
  int adcDiv   = analogRead(PIN_ADC_DIV);
  int adcRf    = analogRead(PIN_ADC_RF);
  int adcPhoto = analogRead(PIN_ADC_PHOTO);

  // Cabecera CSV
  Serial.print("DATA,");
  Serial.print(msNow);
  Serial.print(",");
  Serial.print(servoDeg);
  Serial.print(",");

  // Payload segun modo RAW
  if (sendRaw)
  {
    // Enteros: mas facil para depurar ADC y calibrar luego
    Serial.print(adcDiv);   Serial.print(",");
    Serial.print(adcRf);    Serial.print(",");
    Serial.print(adcPhoto);
  }
  else
  {
    // Voltajes aproximados: facilita el pipeline (Python recibe floats)
    Serial.print(ConvertAdcToVolt(adcDiv),   4); Serial.print(",");
    Serial.print(ConvertAdcToVolt(adcRf),    4); Serial.print(",");
    Serial.print(ConvertAdcToVolt(adcPhoto), 4);
  }

  Serial.println();
}

// ============================================================
// 7) PARSEO DE COMANDOS (PC -> ESP32)
// ============================================================
//
// Este parser es deliberadamente simple:
// - Comandos cortos
// - Respuestas cortas
// - Facil de testear con Serial Monitor
//

static void ProcessCommandLine(const char* line)
{
  // Saltar espacios y saltos de linea residuales
  while (*line == ' ' || *line == '\t' || *line == '\r' || *line == '\n') line++;

  // Comando vacio
  if (strlen(line) == 0) return;

  // PING: permite saber si el PC esta conectado y la ESP32 responde
  if (strcmp(line, "PING") == 0)
  {
    Serial.println("PONG");
    return;
  }

  // START: comienza streaming periodico
  if (strcmp(line, "START") == 0)
  {
    streaming = true;
    Serial.println("OK");
    return;
  }

  // STOP: detiene streaming
  if (strcmp(line, "STOP") == 0)
  {
    streaming = false;
    Serial.println("OK");
    return;
  }

  // SERVO=xx: mover servo (solo si esta en rango)
  if (strncmp(line, "SERVO=", 6) == 0)
  {
    int val = atoi(line + 6);
    ApplyServoAngleWithLimit(val);
    return;
  }

  // RATE=xx: cambia frecuencia de muestreo (Hz)
  if (strncmp(line, "RATE=", 5) == 0)
  {
    float hz = atof(line + 5);
    SetSampleRateHz(hz);
    return;
  }

  // RAW=0/1: cambia modo de envio
  if (strncmp(line, "RAW=", 4) == 0)
  {
    int raw = atoi(line + 4);
    SetRawMode(raw);
    return;
  }

  // Comando desconocido
  Serial.println("ERROR,UnknownCommand");
}

// Arma lineas de comando leyendo byte a byte.
// Ventaja: soporta terminales que envian \r\n y evita lecturas parciales.
static void PollSerialAndBuildLines()
{
  while (Serial.available() > 0)
  {
    char c = (char)Serial.read();

    // Fin de linea: procesamos comando
    if (c == '\n')
    {
      cmdBuf[cmdIdx] = '\0';
      ProcessCommandLine(cmdBuf);
      cmdIdx = 0;
      continue;
    }

    // Ignorar '\r' (Windows)
    if (c == '\r')
    {
      continue;
    }

    // Guardar caracter si hay espacio
    if (cmdIdx < CMD_BUF_LEN - 1)
    {
      cmdBuf[cmdIdx] = c;
      cmdIdx++;
    }
    else
    {
      // Si el comando es demasiado largo, reseteamos buffer
      cmdIdx = 0;
      Serial.println("ERROR,CmdTooLong");
    }
  }
}

// ============================================================
// 8) SETUP Y LOOP
// ============================================================

void setup()
{
  // 1) Serial USB
  Serial.begin(115200);

  // 2) ADC configuracion general
  analogReadResolution(ADC_BITS);

  // Atenuacion 11 dB:
  // - ayuda a medir mejor cerca del rango alto (hasta aprox 3.3V)
  // - si tu senal es siempre baja, igual funciona bien
  analogSetPinAttenuation(PIN_ADC_DIV,   ADC_11db);
  analogSetPinAttenuation(PIN_ADC_RF,    ADC_11db);
  analogSetPinAttenuation(PIN_ADC_PHOTO, ADC_11db);

  // 3) Servo: frecuencia tipica 50 Hz y rango de pulso
  myServo.setPeriodHertz(50);
  myServo.attach(PIN_SERVO, 500, 2400);

  // Posicion inicial segura
  myServo.write(servoDeg);

  // 4) Mensajes de inicio (logs)
  // Nota: la capa FuenteSerial en Python ignora lineas que no sean DATA,
  // por lo que estos logs no rompen el pipeline.
  Serial.println("READY");
  Serial.println("INFO,AutoStream=OFF");
  Serial.print("INFO,RateHz="); Serial.println(rateHz, 2);
  Serial.print("INFO,Raw="); Serial.println(sendRaw ? 1 : 0);
}

void loop()
{
  // (A) Leer comandos entrantes desde PC
  PollSerialAndBuildLines();

  // (B) Si streaming activo, mandar una muestra cada samplePeriodMs
  if (streaming)
  {
    uint32_t msNow = millis();

    if ((msNow - lastSampleMs) >= samplePeriodMs)
    {
      lastSampleMs = msNow;
      ReadSensorsAndSendDataLine();
    }
  }

  // (C) Pequeño delay para no saturar CPU
  delay(1);
}
