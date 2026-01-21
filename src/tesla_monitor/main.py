"""
Entry point para ejecutar la vista Streamlit del proyecto.

Forma recomendada de ejecucion (desde la raiz del repo):
    python -m streamlit run src/tesla_monitor/main.py

Alternativa equivalente:
    streamlit run src/tesla_monitor/main.py

Nota:
- Este archivo vive dentro del paquete tesla_monitor.
- Para que los imports funcionen incluso cuando Streamlit ejecuta el script,
  se agrega la carpeta "src" al sys.path.
"""

import os
import sys


def _asegurar_src_en_syspath() -> None:
    """
    Agrega la carpeta /src al sys.path para que los imports del paquete funcionen
    al ejecutar con streamlit run.

    Estructura esperada:
      repo/
        src/
          tesla_monitor/
            main.py
            view/
              vista_streamlit.py
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))   # .../src/tesla_monitor
    src_dir = os.path.dirname(base_dir)                     # .../src

    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)


def main() -> None:
    _asegurar_src_en_syspath()

    # Import despues de setear sys.path (import seguro)
    from tesla_monitor.view.vista_streamlit import iniciar

    # Streamlit ejecuta el script y espera que llamemos a la funcion que arma la UI
    iniciar()


if __name__ == "__main__":
    # Si alguien ejecuta esto con "python src/tesla_monitor/main.py",
    # va a correr igual, pero no es el flujo recomendado para Streamlit.
    # Dejamos un aviso suave.
    if "streamlit" not in " ".join(sys.argv).lower():
        print(
            "Aviso: este archivo se recomienda ejecutar con:\n"
            "  python -m streamlit run src/tesla_monitor/main.py\n"
        )

    main()
