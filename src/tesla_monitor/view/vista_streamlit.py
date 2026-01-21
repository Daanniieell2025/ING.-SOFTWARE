"""
Vista Streamlit para Tesla Monitor (MVC)

Esta vista NO implementa el modelo ni la logica del sistema.
Solo:
- configura fuente de datos (Simulada / Serial / CSV)
- ejecuta el flujo del experimento via TeslaController
- muestra graficos a partir del CSV exportado o CSV cargado

Contrato con Controller:
- ctrl.set_checklist_validado(ok)
- ctrl.get_estado()
- ctrl.start_experimento(cfg)
- ctrl.tick()
- ctrl.stop_experimento()
- ctrl.set_servo_deg(deg)  (solo en RUNNING_MANUAL)
- ctrl.get_historial()
- ctrl.get_ultimo_csv_path()
- ctrl.get_tiempo_restante_s()
- ctrl.reset()

Nota:
- Se agrega una opcion "Preview servo" antes de iniciar (READY).
  Si el controller aun no tiene preview_servo_deg(), no rompe.
"""

import os
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from tesla_monitor.config.settings import SETTINGS
from tesla_monitor.controller.controller import (
    TeslaController,
    ConfigExperimento,
    ModoExperimento,
    EstadoController,
    construir_fuente_simulada,
)
from tesla_monitor.controller.fuentes import FuenteCSV, FuenteSerialESP32


# ============================================================
# Helpers de CSV y graficos
# ============================================================

def _listar_csvs_en_repo(base_dir: Path):
    rutas = []
    carpetas = [
        base_dir / "data",
        base_dir / "salidas",
        base_dir / "src" / "salidas",
        base_dir / "src" / "tesla_monitor" / "salidas",
    ]
    for carpeta in carpetas:
        if carpeta.exists():
            rutas.extend(list(carpeta.glob("*.csv")))
    return sorted(set(rutas))


def _leer_csv_df(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    if "t_s_rel" in df.columns:
        df = df.sort_values("t_s_rel")
    elif "t_ms_rel" in df.columns:
        df = df.sort_values("t_ms_rel")
    elif "t_ms" in df.columns:
        df = df.sort_values("t_ms")

    return df


def _columna_tiempo(df: pd.DataFrame) -> str:
    for c in ["t_s_rel", "t_ms_rel", "t_ms"]:
        if c in df.columns:
            return c
    return df.columns[0]


def _plot_line(df: pd.DataFrame, x: str, y: str, titulo: str):
    if x not in df.columns or y not in df.columns:
        return

    st.write(titulo)

    dfp = df[[x, y]].dropna().copy()
    if len(dfp) == 0:
        return

    dfp = dfp.set_index(x)
    st.line_chart(dfp)


def _plot_line_multi(df: pd.DataFrame, x: str, ys: list, titulo: str):
    if x not in df.columns:
        return

    cols = [x] + [y for y in ys if y in df.columns]
    if len(cols) <= 1:
        return

    st.write(titulo)

    dfp = df[cols].dropna().copy()
    if len(dfp) == 0:
        return

    dfp = dfp.set_index(x)
    st.line_chart(dfp)


# ============================================================
# Helpers de session_state
# ============================================================

def _get_ctrl():
    return st.session_state.get("ctrl")


def _set_ctrl(ctrl):
    st.session_state["ctrl"] = ctrl


# ============================================================
# Fabrica de fuentes
# ============================================================

def _crear_fuente(tipo_fuente: str, puerto_serial: str, ruta_csv: str):
    if tipo_fuente == "Simulada":
        return construir_fuente_simulada()

    if tipo_fuente == "ESP32 (Serial)":
        return FuenteSerialESP32(
            puerto=puerto_serial,
            baudrate=SETTINGS.baudrate,
            timeout_s=SETTINGS.timeout_s,
        )

    if tipo_fuente == "CSV":
        return FuenteCSV(ruta_csv)

    raise ValueError("Fuente no soportada")


# ============================================================
# Helpers: historial -> DataFrame (graficos en vivo)
# ============================================================

def _historial_a_df(hist):
    if hist is None or len(hist) == 0:
        return pd.DataFrame()

    t0 = hist[0].t_ms
    data = {
        "t_s_rel": [(m.t_ms - t0) / 1000.0 for m in hist],
        "B_exp": [m.B_exp for m in hist],
        "L_exp": [m.L_exp for m in hist],
        "V_in": [m.V_in for m in hist],
        "P_in": [m.P_in for m in hist],
    }

    # Si existen teoricas, las incluimos
    if hasattr(hist[0], "B_teo"):
        data["B_teo"] = [m.B_teo for m in hist]
    if hasattr(hist[0], "L_teo"):
        data["L_teo"] = [m.L_teo for m in hist]

    return pd.DataFrame(data)


# ============================================================
# UI principal
# ============================================================

def iniciar():
    st.set_page_config(page_title="Tesla Monitor", layout="wide")

    st.title("Tesla Monitor")
    st.caption("Vista Streamlit: Checklist + Experimento (Controller) + Graficos CSV")

    base_dir = Path(os.getcwd())

    # ------------------------------
    # Sidebar: Configuracion
    # ------------------------------

    st.sidebar.header("Configuracion")

    seccion = st.sidebar.selectbox(
        "Seccion",
        ["Experimento", "Graficos CSV"],
        index=0,
    )

    tipo_fuente = st.sidebar.selectbox(
        "Fuente de datos",
        ["Simulada", "ESP32 (Serial)", "CSV"],
        index=0,
    )

    puerto_serial = st.sidebar.text_input("Puerto (solo Serial)", value=SETTINGS.puerto_serial)

    ruta_csv_fuente = ""
    csv_subido = None

    if tipo_fuente == "CSV":
        csv_subido = st.sidebar.file_uploader("Subir CSV (fuente)", type=["csv"])
        if csv_subido is not None:
            tmp_dir = base_dir / "_tmp"
            tmp_dir.mkdir(exist_ok=True)
            ruta_csv_fuente = str(tmp_dir / "fuente.csv")
            with open(ruta_csv_fuente, "wb") as f:
                f.write(csv_subido.getbuffer())
        else:
            st.sidebar.info("Sube un CSV para usarlo como fuente")

    # ------------------------------
    # Sidebar: Checklist
    # ------------------------------

    st.sidebar.divider()
    st.sidebar.subheader("Checklist de seguridad")

    c1 = st.sidebar.checkbox("Conexiones y aislacion verificadas")
    c2 = st.sidebar.checkbox("Fuente y regulador configurados en rango seguro")
    c3 = st.sidebar.checkbox("Divisor de tension verificado con tester")

    checklist_ok = bool(c1 and c2 and c3)

    # ------------------------------
    # Crear/recrear Controller si cambia la fuente
    # ------------------------------

    ctrl = _get_ctrl()
    need_new_ctrl = False

    prev_tipo = st.session_state.get("tipo_fuente")
    prev_csv = st.session_state.get("ruta_csv_fuente")

    if prev_tipo != tipo_fuente:
        need_new_ctrl = True
    if tipo_fuente == "CSV" and prev_csv != ruta_csv_fuente:
        need_new_ctrl = True

    if tipo_fuente == "CSV" and ruta_csv_fuente == "":
        _set_ctrl(None)
        ctrl = None
    elif ctrl is None or need_new_ctrl:
        fuente = _crear_fuente(tipo_fuente, puerto_serial, ruta_csv_fuente)
        ctrl = TeslaController(fuente)
        _set_ctrl(ctrl)
        st.session_state["tipo_fuente"] = tipo_fuente
        st.session_state["ruta_csv_fuente"] = ruta_csv_fuente

    # Enviar checklist al controller
    if ctrl is not None:
        ctrl.set_checklist_validado(checklist_ok)

    if checklist_ok:
        st.sidebar.success("Checklist completo")
    else:
        st.sidebar.warning("Completa el checklist para habilitar el experimento")

    # ============================================================
    # Seccion: Experimento
    # ============================================================

    if seccion == "Experimento":
        if ctrl is None:
            st.error("No hay controller disponible. Revisa la fuente en la sidebar.")
            return

        estado = ctrl.get_estado()

        st.subheader("Estado del sistema")
        st.write("Estado:", estado)

        if estado == EstadoController.ERROR:
            st.error("Error: " + str(ctrl.get_error_msg()))

        col_cfg, col_run = st.columns([1, 1])

        # ------------------------------
        # Columna: configuracion
        # ------------------------------
        with col_cfg:
            st.subheader("Parametros del experimento")

            modo_str = st.selectbox(
                "Modo",
                [ModoExperimento.AUTO.value, ModoExperimento.MANUAL.value],
                index=0,
            )

            no_enviar_servo = st.checkbox(
                "No enviar comando al servo (solo registrar)",
                value=False,
            )

            duracion = st.slider(
                "Duracion (s)",
                min_value=int(SETTINGS.min_experimento_s),
                max_value=int(SETTINGS.max_experimento_s),
                value=min(15, int(SETTINGS.max_experimento_s)),
            )

            servo_inicial = st.number_input(
                "Angulo inicial (deg)",
                min_value=int(SETTINGS.servo_deg_min),
                max_value=int(SETTINGS.servo_deg_max),
                value=int(SETTINGS.servo_deg_default),
                step=1,
            )

            ruta_salida = st.text_input("Ruta CSV salida", value=SETTINGS.ruta_csv)

            # Preview servo (antes de iniciar): solo en READY y si el usuario permite enviar servo
            b_preview = st.button(
                "Preview servo (mover ahora)",
                disabled=(estado != EstadoController.READY or no_enviar_servo),
            )
            if b_preview:
                if hasattr(ctrl, "preview_servo_deg"):
                    try:
                        ctrl.preview_servo_deg(int(servo_inicial))
                        st.success("Servo previsualizado")
                    except Exception as e:
                        st.error(f"No se pudo previsualizar servo: {e}")
                else:
                    st.warning("preview_servo_deg aun no esta implementado en controller")

            puede_iniciar = (estado == EstadoController.READY)

            b_start = st.button("Iniciar experimento", disabled=(not puede_iniciar))
            b_stop = st.button(
                "Detener",
                disabled=(estado not in (EstadoController.RUNNING_AUTO, EstadoController.RUNNING_MANUAL)),
            )
            b_reset = st.button("Reset")

            if b_reset:
                ctrl.reset()
                st.rerun()

            if b_start:
                st.session_state["duracion_total_s"] = float(duracion)

                cfg = ConfigExperimento(
                    modo=ModoExperimento(modo_str),
                    duracion_s=float(duracion),
                    servo_deg_inicial=int(servo_inicial),
                    ruta_csv=str(ruta_salida),
                )

                ctrl.start_experimento(cfg)
                st.success("Experimento iniciado")

            if b_stop:
                ctrl.stop_experimento()
                st.warning("Experimento detenido")

        # ------------------------------
        # Columna: ejecucion
        # ------------------------------
        with col_run:
            st.subheader("Ejecucion")

            estado = ctrl.get_estado()

            tiempo_box = st.empty()
            progreso_box = st.empty()

            if estado in (EstadoController.RUNNING_AUTO, EstadoController.RUNNING_MANUAL):
                restante = ctrl.get_tiempo_restante_s()

                if restante is None:
                    tiempo_box.metric("Tiempo restante (s)", "-")
                    progreso_box.progress(0)
                else:
                    restante = max(0.0, float(restante))
                    tiempo_box.metric("Tiempo restante (s)", round(restante, 2))

                    total = st.session_state.get("duracion_total_s", float(duracion))
                    total = float(total) if float(total) > 0 else 1.0
                    fr = (total - restante) / total
                    fr = max(0.0, min(1.0, fr))
                    progreso_box.progress(int(fr * 100))

            # ====================================================
            # Modo MANUAL (tiempo real):
            # - slider de angulo
            # - boton aplicar servo
            # - muestreo automatico (batch ticks)
            # - graficos en vivo desde historial
            # ====================================================
            if estado == EstadoController.RUNNING_MANUAL:
                st.caption("Modo MANUAL: graficos en tiempo real y opcion de mover el servo durante la ejecucion.")

                servo_objetivo = st.slider(
                    "Angulo objetivo (deg)",
                    min_value=int(SETTINGS.servo_deg_min),
                    max_value=int(SETTINGS.servo_deg_max),
                    value=int(servo_inicial),
                    step=1,
                )

                if no_enviar_servo:
                    st.info("No se enviara comando al servo durante ejecucion.")
                else:
                    if st.button("Aplicar servo"):
                        try:
                            ctrl.set_servo_deg(int(servo_objetivo))
                            st.success("Servo actualizado")
                        except Exception as e:
                            st.error(f"No se pudo mover servo: {e}")

                # Batch ticks para aumentar densidad de datos sin tocar settings aun
                dt_s = SETTINGS.dt_ms / 1000.0
                refresh_s = 0.2
                n_ticks = max(1, int(refresh_s / dt_s))

                for _ in range(n_ticks):
                    ctrl.tick()

                # Graficos en vivo desde historial (no CSV)
                hist = ctrl.get_historial()
                df_live = _historial_a_df(hist)

                if len(df_live) > 0:
                    st.subheader("Graficos en vivo")

                    tcol = "t_s_rel"
                    _plot_line(df_live, tcol, "B_exp", "RF (B_exp) vs tiempo (vivo)")
                    _plot_line(df_live, tcol, "L_exp", "Luz (L_exp) vs tiempo (vivo)")
                    _plot_line(df_live, tcol, "V_in", "Voltaje entrada (V_in) vs tiempo (vivo)")
                    _plot_line(df_live, tcol, "P_in", "Potencia entrada (P_in) vs tiempo (vivo)")

                    if "B_teo" in df_live.columns:
                        _plot_line_multi(df_live, tcol, ["B_exp", "B_teo"], "B_exp vs B_teo (vivo)")
                    if "L_teo" in df_live.columns:
                        _plot_line_multi(df_live, tcol, ["L_exp", "L_teo"], "L_exp vs L_teo (vivo)")

            # ====================================================
            # Modo AUTO:
            # - batch ticks para muestreo mas denso
            # - graficos solo al finalizar
            # ====================================================
            if estado == EstadoController.RUNNING_AUTO:
                st.caption("Modo AUTO: el experimento avanza automaticamente.")

                dt_s = SETTINGS.dt_ms / 1000.0
                refresh_s = 0.2
                n_ticks = max(1, int(refresh_s / dt_s))

                for _ in range(n_ticks):
                    ctrl.tick()

            # ====================================================
            # FINISHED:
            # - descarga CSV
            # - graficos desde CSV exportado
            # ====================================================
            if estado == EstadoController.FINISHED:
                st.success("Experimento finalizado")

                path_csv = ctrl.get_ultimo_csv_path()
                if path_csv is not None and Path(path_csv).exists():
                    st.write("CSV generado:", str(path_csv))

                    data = Path(path_csv).read_bytes()
                    st.download_button(
                        "Descargar CSV",
                        data=data,
                        file_name=Path(path_csv).name,
                        mime="text/csv",
                    )

                    df = _leer_csv_df(Path(path_csv))
                    tcol = _columna_tiempo(df)

                    st.subheader("Graficos (desde CSV exportado)")

                    cols = df.columns.tolist()

                    for y, title in [
                        ("B_exp", "RF (B_exp) vs tiempo"),
                        ("L_exp", "Luz (L_exp) vs tiempo"),
                        ("V_in", "Voltaje entrada (V_in) vs tiempo"),
                        ("P_in", "Potencia entrada (P_in) vs tiempo"),
                    ]:
                        if y in cols:
                            _plot_line(df, tcol, y, title)

                    if "B_teo" in cols and "B_exp" in cols:
                        _plot_line_multi(df, tcol, ["B_exp", "B_teo"], "B_exp vs B_teo")

                    if "L_teo" in cols and "L_exp" in cols:
                        _plot_line_multi(df, tcol, ["L_exp", "L_teo"], "L_exp vs L_teo")

                    st.subheader("Vista previa")
                    st.dataframe(df.head(50))

            # Auto-refresh cuando esta corriendo
            if estado in (EstadoController.RUNNING_AUTO, EstadoController.RUNNING_MANUAL):
                time.sleep(0.2)
                st.rerun()

    # ============================================================
    # Seccion: Graficos CSV (carga manual)
    # ============================================================

    if seccion == "Graficos CSV":
        st.subheader("Cargar un CSV y graficar")

        col_left, col_right = st.columns([1, 2])

        with col_left:
            csv_up = st.file_uploader("Subir CSV", type=["csv"], key="csv_graficos")

            rutas = _listar_csvs_en_repo(base_dir)
            opciones = ["(ninguno)"] + [str(p) for p in rutas]
            elegido = st.selectbox("O usar uno del repo", opciones)

        df = None
        nombre = None

        if csv_up is not None:
            tmp_dir = base_dir / "_tmp"
            tmp_dir.mkdir(exist_ok=True)
            p = tmp_dir / "graficos.csv"
            with open(p, "wb") as f:
                f.write(csv_up.getbuffer())
            df = _leer_csv_df(p)
            nombre = "CSV subido"

        elif elegido != "(ninguno)":
            p = Path(elegido)
            if p.exists():
                df = _leer_csv_df(p)
                nombre = p.name

        with col_right:
            if df is None:
                st.info("Sube un CSV o selecciona uno para ver graficos")
            else:
                st.write("Archivo:", nombre)
                st.write("Filas:", len(df))

                tcol = _columna_tiempo(df)

                cols = [c for c in df.columns if c != tcol]
                seleccion = st.multiselect(
                    "Variables a graficar",
                    cols,
                    default=[c for c in ["B_exp", "L_exp", "V_in"] if c in cols],
                )

                if len(seleccion) == 0:
                    st.warning("Selecciona al menos una variable")
                else:
                    for y in seleccion:
                        _plot_line(df, tcol, y, f"{y} vs {tcol}")

                st.subheader("Vista previa")
                st.dataframe(df.head(50))


if __name__ == "__main__":
    iniciar()
