import streamlit as st
import pandas as pd
import time
from controller.controller import TeslaController

class Vista:
    """
    Clase encargada de renderizar la interfaz de usuario,Sigue el diseño de los mockups del Sprint 1.
    Esta se encarga de Mostral al usuario y recibir peticiones"""

    def __init__(self):
        st.set_page_config(page_title="Tesla Monitor - Dashboard", layout="wide")

    # Inicialización del controlador en el estado de la sesión para persistencia
        if 'controller' not in st.session_state:
            st.session_state.controller = TeslaController()
            st.session_state.ejecutando = False

        self.controller = st.session_state.controller


    def mostrar_interfaz(self):
        st.title("Sistema de Medición, Bobina Tesla ⚡")
        st.markdown("---")

        # Barra lateral (Configuración de sistema)
        st.sidebar.header("Configuración de Hardware")
        modo = st.sidebar.selectbox("Fuente de Datos", ["Simulación", "ESP32 Serial"])
        puerto = st.sidebar.text_input("Puerto COM", value="COM3") if modo == "ESP32 Serial" else None

        #boton de la barra lateral 

        if st.sidebar.button("Conectar / Inicializar"):
            self.controller.configurar_fuente(modo, puerto)
            st.sidebar.success(f"Conectado a {modo}")

        # Separacion por tabs/pestañas (aliniandose con los Mockups Sprint 1)

        #declaracion de cque pestañas tendra y sus nombres
        tab_estado, tab_graficos, tab_historial = st.tabs([
            "📍 Estado del Sistema", 
            "📊 Gráficos en Tiempo Real", 
            "📜 Historial de Datos"
        ])

        # Pestaña 1: contendra informacion sobre el estado del sistema
        with tab_estado:
            col1, col2 = st.columns([1, 2])
    
            with col1:
                st.subheader("Controles de Usuario")
                # Control del Servo (0-30 deg) [cite: 304, 397]
                angulo_servo = st.slider("Ángulo del servo θ", 0, 30, 15) #Slider que permite al usuario cambiar el angulo del servo

                #Boton para iniciar la prueba
                if st.button("Iniciar Test", type="primary"):
                    st.session_state.ejecutando = True

                #Boton para detener o resetear laa prueba    
                if st.button("Detener / Reset"):
                    st.session_state.ejecutando = False
                    self.controller.reiniciar_sistema()
                    st.rerun()

            with col2:
                st.subheader("Lectura Actual")
                placeholder_metrics = st.empty()
        
                # Mostrar la informacion en tiempo real en la pestaña de estado del sistema
                if st.session_state.ejecutando:
                    m_p = self.controller.obtener_y_procesar(angulo_servo)
                    if m_p:
                        with placeholder_metrics.container():
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Distancia (m)", f"{m_p.r_m:.3f}")
                            c2.metric("B Exp (V)", f"{m_p.B_exp:.2f}")
                            c3.metric("L Exp (V)", f"{m_p.L_exp:.2f}")
                    time.sleep(0.1)
                    st.rerun()

    # Pestaña 2: Contiene y grafica los graficos en tiempo real del experimento 
        with tab_graficos:
            st.subheader("Visualización Comparativa")
            historial = self.controller.model.get_historial()
    
            if historial:
                df = pd.DataFrame([vars(m) for m in historial])
        
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.write("**Intensidad de Campo (B) vs Distancia**")
                    # Comparamos Teórico vs Experimental
                    st.line_chart(df[['r_m', 'B_exp', 'B_teo']].set_index('r_m'))
            
                with col_g2:
                    st.write("**Intensidad Lumínica (L) vs Distancia**")
                    st.line_chart(df[['r_m', 'L_exp', 'L_teo']].set_index('r_m'))
            
                # Cálculo de error

                st.info(f"Error Relativo Promedio Campo B: {df['err_B_rel'].mean():.4%}")
    
            else:
                st.warning("No hay datos para graficar. Inicie el test en la pestaña 'Estado'.")

        # Pestaña 3: contiene el historial de datos 

        with tab_historial:
            st.subheader("Registros del Experimento")
            historial = controller.model.get_historial()
    
            if historial:
                df_hist = pd.DataFrame([vars(m) for m in historial])
                st.dataframe(df_hist) # Visualización tabular
        
                # Botón de descarga de datos
                if st.button("Exportar a CSV"):
                    ruta = self.controller.exportar_datos()
                    if ruta:
                        st.success(f"Datos exportados exitosamente en: {ruta}")
            else:
                st.info("El historial está vacío.")