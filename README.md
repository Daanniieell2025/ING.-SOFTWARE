# Tesla Monitor – Ingeniería de Software

Este proyecto corresponde al desarrollo de un sistema de monitoreo y control para una Bobina Tesla, realizado en el marco de la asignatura **Ingeniería de Software**.

El objetivo principal fue integrar hardware y software en un sistema funcional, capaz de adquirir datos experimentales desde sensores, procesarlos y mostrarlos de forma clara al usuario, aplicando una arquitectura modular basada en **MVC (Modelo–Vista–Controlador)**.

---

## Descripción del proyecto

El sistema permite:
- Leer datos desde sensores conectados a un microcontrolador ESP32.
- Enviar la información al computador mediante comunicación serial.
- Procesar las mediciones y compararlas con un modelo teórico.
- Visualizar resultados en tiempo real a través de una interfaz gráfica.
- Guardar los datos del experimento en archivos CSV para análisis posterior.
- Controlar el funcionamiento del sistema durante el experimento.

---

## Arquitectura del software

El software fue diseñado utilizando el patrón **MVC**, lo que permitió separar claramente las responsabilidades:

- **Modelo:** se encarga del procesamiento de los datos y del almacenamiento de resultados.
- **Vista:** corresponde a la interfaz gráfica del sistema, desarrollada en Streamlit.
- **Controlador:** gestiona la comunicación entre el hardware, el modelo y la vista.

Esta estructura facilita la mantención del sistema y su escalabilidad.

---

## Estructura del repositorio

