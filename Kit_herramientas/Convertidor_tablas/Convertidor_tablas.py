"""
Convertidor de Tablas - Convierte tablas desde CSV, Excel y PDF a formato LaTeX o Markdown.
Parte del repositorio Programas_utiles.
Dependencias: pandas, openpyxl, pymupdf, tabulate, streamlit
"""

import os
import sys
import re
import subprocess
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("\n[!] Error: Se requieren modulos externos para este programa (pandas, tabulate, etc.).")
    print("[*] Puedes instalarlos facilmente ejecutando: python instalar_dependencias.py")
    print("[*] O directamente con: pip install pandas openpyxl pymupdf tabulate streamlit\n")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Rutas relativas al script
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DIR_ENTRADA = BASE_DIR / "tablas_entrada"
DIR_SALIDA = BASE_DIR / "tablas_generadas"


def _asegurar_directorios():
    DIR_ENTRADA.mkdir(parents=True, exist_ok=True)
    DIR_SALIDA.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------
def limpiar_pantalla():
    os.system("cls" if os.name == "nt" else "clear")


def pausa():
    input("\n[*] Presiona Enter para continuar...")


def _escape_latex(texto: str) -> str:
    """Escapa caracteres especiales de LaTeX en el texto."""
    if not isinstance(texto, str):
        texto = str(texto)
    conv = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    regex = re.compile("|".join(re.escape(k) for k in conv))
    return regex.sub(lambda m: conv[m.group()], texto)


# ---------------------------------------------------------------------------
# Lectura de archivos
# ---------------------------------------------------------------------------
def _detectar_delimitador(ruta: Path) -> str:
    """Intenta detectar el delimitador de un CSV probando varios candidatos."""
    candidatos = [",", ";", "\t", "|"]
    with open(ruta, "r", encoding="utf-8", errors="replace") as f:
        muestra = f.read(8192)
    mejor, mejor_count = ",", 0
    for sep in candidatos:
        c = muestra.count(sep)
        if c > mejor_count:
            mejor, mejor_count = sep, c
    return mejor


def leer_csv(ruta: Path) -> pd.DataFrame:
    sep = _detectar_delimitador(ruta)
    return pd.read_csv(ruta, sep=sep, engine="python")


def leer_excel(ruta: Path) -> pd.DataFrame:
    return pd.read_excel(ruta, engine="openpyxl")


def leer_pdf_tablas(ruta: Path) -> list[tuple[str, pd.DataFrame]]:
    """Devuelve lista de (etiqueta, DataFrame) con todas las tablas del PDF."""
    import fitz  # pymupdf

    doc = fitz.open(str(ruta))
    resultados = []
    nombre_base = ruta.stem
    for num_pag, pagina in enumerate(doc, start=1):
        tabs = pagina.find_tables()
        for num_tab, tab in enumerate(tabs.tables, start=1):
            datos = tab.extract()
            if not datos or len(datos) < 2:
                continue
            encabezados = [str(c) if c else f"Col{i+1}" for i, c in enumerate(datos[0])]
            filas = datos[1:]
            df = pd.DataFrame(filas, columns=encabezados)
            etiqueta = f"{nombre_base}_p{num_pag}_t{num_tab}"
            resultados.append((etiqueta, df))
    doc.close()
    return resultados


# ---------------------------------------------------------------------------
# Generacion de formatos de salida
# ---------------------------------------------------------------------------
def df_a_latex(df: pd.DataFrame, estilo: str = "standard") -> str:
    """Convierte un DataFrame a codigo LaTeX tabular.
    estilo: 'standard' (con |c| y hline) o 'booktabs' (toprule/midrule/bottomrule).
    """
    ncols = len(df.columns)
    filas_tex = []

    if estilo == "booktabs":
        filas_tex.append(r"\begin{tabular}{" + " ".join(["c"] * ncols) + "}")
        filas_tex.append(r"\toprule")
        encabezado = " & ".join(_escape_latex(str(c)) for c in df.columns) + r" \\"
        filas_tex.append(encabezado)
        filas_tex.append(r"\midrule")
        for _, fila in df.iterrows():
            linea = " & ".join(_escape_latex(str(v)) for v in fila) + r" \\"
            filas_tex.append(linea)
        filas_tex.append(r"\bottomrule")
        filas_tex.append(r"\end{tabular}")
    else:
        col_spec = "|" + "|".join(["c"] * ncols) + "|"
        filas_tex.append(r"\begin{tabular}{" + col_spec + "}")
        filas_tex.append(r"\hline")
        encabezado = " & ".join(_escape_latex(str(c)) for c in df.columns) + r" \\"
        filas_tex.append(encabezado)
        filas_tex.append(r"\hline")
        for _, fila in df.iterrows():
            linea = " & ".join(_escape_latex(str(v)) for v in fila) + r" \\"
            filas_tex.append(linea)
            filas_tex.append(r"\hline")
        filas_tex.append(r"\end{tabular}")

    return "\n".join(filas_tex)


def df_a_markdown(df: pd.DataFrame) -> str:
    """Convierte un DataFrame a tabla Markdown (GitHub Flavored)."""
    lineas = []
    encabezado = "| " + " | ".join(str(c) for c in df.columns) + " |"
    separador = "| " + " | ".join("---" for _ in df.columns) + " |"
    lineas.append(encabezado)
    lineas.append(separador)
    for _, fila in df.iterrows():
        linea = "| " + " | ".join(str(v) for v in fila) + " |"
        lineas.append(linea)
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Vista previa en terminal
# ---------------------------------------------------------------------------
def vista_previa_terminal(df: pd.DataFrame, titulo: str = ""):
    from tabulate import tabulate as _tabulate
    if titulo:
        print(f"\n  [+] {titulo}\n")
    print(_tabulate(df, headers="keys", tablefmt="fancy_grid", showindex=False))


# ---------------------------------------------------------------------------
# Guardar archivo de salida
# ---------------------------------------------------------------------------
def guardar_salida(contenido: str, nombre_archivo: str):
    _asegurar_directorios()
    ruta = DIR_SALIDA / nombre_archivo
    ruta.write_text(contenido, encoding="utf-8")
    print(f"\n  [OK] Archivo guardado en: {ruta}")


# ---------------------------------------------------------------------------
# Interaccion CLI: elegir archivo
# ---------------------------------------------------------------------------
def elegir_archivo(extensiones: list[str]) -> Path | None:
    """Pregunta al usuario si leer de tablas_entrada/ o dar ruta personalizada."""
    print("\n  [1] Leer desde carpeta tablas_entrada/")
    print("  [2] Introducir ruta personalizada")
    opcion = input("\n  Selecciona opcion: ").strip()

    if opcion == "1":
        _asegurar_directorios()
        archivos = [f for f in DIR_ENTRADA.iterdir() if f.suffix.lower() in extensiones]
        if not archivos:
            print(f"\n  [!] No se encontraron archivos {extensiones} en tablas_entrada/")
            return None
        print()
        for i, a in enumerate(archivos, 1):
            print(f"  [{i}] {a.name}")
        sel = input("\n  Numero de archivo: ").strip()
        try:
            return archivos[int(sel) - 1]
        except (ValueError, IndexError):
            print("  [!] Seleccion no valida.")
            return None
    elif opcion == "2":
        ruta = input("  Ruta del archivo: ").strip().strip('"').strip("'")
        p = Path(ruta)
        if p.exists() and p.suffix.lower() in extensiones:
            return p
        print("  [!] Archivo no encontrado o extension no soportada.")
        return None
    else:
        print("  [!] Opcion no valida.")
        return None


def elegir_estilo_latex() -> str:
    print("\n  Estilo de tabla LaTeX:")
    print("  [1] Estandar (lineas con \\hline)")
    print("  [2] Booktabs (\\toprule, \\midrule, \\bottomrule)")
    sel = input("  Selecciona estilo: ").strip()
    return "booktabs" if sel == "2" else "standard"


# ---------------------------------------------------------------------------
# Opciones del menu CLI
# ---------------------------------------------------------------------------
def convertir_csv_latex():
    ruta = elegir_archivo([".csv"])
    if not ruta:
        return
    df = leer_csv(ruta)
    estilo = elegir_estilo_latex()
    tex = df_a_latex(df, estilo)
    nombre = ruta.stem + "_tabla.tex"
    guardar_salida(tex, nombre)
    print("\n" + tex)


def convertir_csv_markdown():
    ruta = elegir_archivo([".csv"])
    if not ruta:
        return
    df = leer_csv(ruta)
    md = df_a_markdown(df)
    nombre = ruta.stem + "_tabla.md"
    guardar_salida(md, nombre)
    print("\n" + md)


def convertir_excel_latex():
    ruta = elegir_archivo([".xlsx"])
    if not ruta:
        return
    df = leer_excel(ruta)
    estilo = elegir_estilo_latex()
    tex = df_a_latex(df, estilo)
    nombre = ruta.stem + "_tabla.tex"
    guardar_salida(tex, nombre)
    print("\n" + tex)


def convertir_excel_markdown():
    ruta = elegir_archivo([".xlsx"])
    if not ruta:
        return
    df = leer_excel(ruta)
    md = df_a_markdown(df)
    nombre = ruta.stem + "_tabla.md"
    guardar_salida(md, nombre)
    print("\n" + md)


def convertir_pdf_latex():
    ruta = elegir_archivo([".pdf"])
    if not ruta:
        return
    tablas = leer_pdf_tablas(ruta)
    if not tablas:
        print("\n  [!] No se encontraron tablas en el PDF.")
        return
    estilo = elegir_estilo_latex()
    for etiqueta, df in tablas:
        tex = df_a_latex(df, estilo)
        nombre = etiqueta + ".tex"
        guardar_salida(tex, nombre)
        print(f"\n--- {etiqueta} ---")
        print(tex)


def convertir_pdf_markdown():
    ruta = elegir_archivo([".pdf"])
    if not ruta:
        return
    tablas = leer_pdf_tablas(ruta)
    if not tablas:
        print("\n  [!] No se encontraron tablas en el PDF.")
        return
    for etiqueta, df in tablas:
        md = df_a_markdown(df)
        nombre = etiqueta + ".md"
        guardar_salida(md, nombre)
        print(f"\n--- {etiqueta} ---")
        print(md)


def vista_previa():
    ruta = elegir_archivo([".csv", ".xlsx", ".pdf"])
    if not ruta:
        return
    ext = ruta.suffix.lower()
    if ext == ".csv":
        df = leer_csv(ruta)
        vista_previa_terminal(df, ruta.name)
    elif ext == ".xlsx":
        df = leer_excel(ruta)
        vista_previa_terminal(df, ruta.name)
    elif ext == ".pdf":
        tablas = leer_pdf_tablas(ruta)
        if not tablas:
            print("\n  [!] No se encontraron tablas en el PDF.")
            return
        for etiqueta, df in tablas:
            vista_previa_terminal(df, etiqueta)


def conversion_por_lotes():
    _asegurar_directorios()
    archivos = [
        f
        for f in DIR_ENTRADA.iterdir()
        if f.suffix.lower() in [".csv", ".xlsx", ".pdf"]
    ]
    if not archivos:
        print("\n  [!] No se encontraron archivos soportados en tablas_entrada/")
        return

    estilo = elegir_estilo_latex()
    total = 0

    for archivo in archivos:
        ext = archivo.suffix.lower()
        print(f"\n  [-] Procesando: {archivo.name}")
        try:
            if ext == ".csv":
                df = leer_csv(archivo)
                guardar_salida(df_a_latex(df, estilo), archivo.stem + "_tabla.tex")
                guardar_salida(df_a_markdown(df), archivo.stem + "_tabla.md")
                total += 1
            elif ext == ".xlsx":
                df = leer_excel(archivo)
                guardar_salida(df_a_latex(df, estilo), archivo.stem + "_tabla.tex")
                guardar_salida(df_a_markdown(df), archivo.stem + "_tabla.md")
                total += 1
            elif ext == ".pdf":
                tablas = leer_pdf_tablas(archivo)
                for etiqueta, df in tablas:
                    guardar_salida(df_a_latex(df, estilo), etiqueta + ".tex")
                    guardar_salida(df_a_markdown(df), etiqueta + ".md")
                    total += 1
        except Exception as e:
            print(f"  [!] Error procesando {archivo.name}: {e}")

    print(f"\n  [OK] Lote finalizado. {total} tabla(s) convertida(s).")


# ---------------------------------------------------------------------------
# Interfaz Streamlit
# ---------------------------------------------------------------------------
def iniciar_streamlit():
    ruta_script = Path(__file__).resolve()
    print("\n  [*] Iniciando interfaz interactiva (Web)...")
    print("  [*] Presiona Ctrl+C en esta consola para volver al menu.\n")
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(ruta_script), "--", "--web"])
    except KeyboardInterrupt:
        print("\n  [*] Interfaz interactiva cerrada.")


def interfaz_web():
    """Interfaz Streamlit completa."""
    import streamlit as st

    st.set_page_config(page_title="Convertidor de Tablas", layout="wide")
    st.title("Convertidor de Tablas")
    st.markdown("Convierte tablas desde **CSV**, **Excel** y **PDF** a formato **LaTeX** o **Markdown**.")

    archivo = st.file_uploader(
        "Sube un archivo con tablas",
        type=["csv", "xlsx", "pdf"],
    )

    formato = st.selectbox(
        "Formato de salida",
        ["LaTeX estandar", "LaTeX booktabs", "Markdown"],
    )

    if archivo is not None:
        nombre = archivo.name
        ext = Path(nombre).suffix.lower()
        tmp_dir = BASE_DIR / "tablas_entrada"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / nombre
        tmp_path.write_bytes(archivo.getvalue())

        tablas: list[tuple[str, pd.DataFrame]] = []

        try:
            if ext == ".csv":
                df = leer_csv(tmp_path)
                tablas.append((Path(nombre).stem, df))
            elif ext == ".xlsx":
                df = leer_excel(tmp_path)
                tablas.append((Path(nombre).stem, df))
            elif ext == ".pdf":
                tablas = leer_pdf_tablas(tmp_path)
                if not tablas:
                    st.warning("No se encontraron tablas en el PDF.")
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
            tablas = []

        for etiqueta, df in tablas:
            st.subheader(f"Tabla: {etiqueta}")
            st.dataframe(df, use_container_width=True)

            if formato == "LaTeX estandar":
                codigo = df_a_latex(df, "standard")
                ext_out = ".tex"
                lang = "latex"
            elif formato == "LaTeX booktabs":
                codigo = df_a_latex(df, "booktabs")
                ext_out = ".tex"
                lang = "latex"
            else:
                codigo = df_a_markdown(df)
                ext_out = ".md"
                lang = "markdown"

            st.markdown("**Codigo generado:**")
            st.code(codigo, language=lang)

            nombre_salida = etiqueta + "_tabla" + ext_out
            st.download_button(
                label=f"Descargar {nombre_salida}",
                data=codigo.encode("utf-8"),
                file_name=nombre_salida,
                mime="text/plain",
                key=f"dl_{etiqueta}",
            )


# ---------------------------------------------------------------------------
# Menu principal CLI
# ---------------------------------------------------------------------------
BANNER = r"""
  ============================================
       CONVERTIDOR DE TABLAS
       CSV / Excel / PDF -> LaTeX / Markdown
  ============================================
"""


def menu_principal():
    _asegurar_directorios()
    while True:
        limpiar_pantalla()
        print(BANNER)
        print("  [1] Convertir CSV a LaTeX")
        print("  [2] Convertir CSV a Markdown")
        print("  [3] Convertir Excel (.xlsx) a LaTeX")
        print("  [4] Convertir Excel (.xlsx) a Markdown")
        print("  [5] Extraer tablas de un PDF y convertir a LaTeX")
        print("  [6] Extraer tablas de un PDF y convertir a Markdown")
        print("  [7] Vista previa de tabla en terminal")
        print("  [8] Conversion por lotes (todos los archivos)")
        print("  [9] Interfaz interactiva (Web)")
        print("  [0] Salir")
        print()

        opcion = input("  Selecciona una opcion: ").strip()

        if opcion == "1":
            convertir_csv_latex()
            pausa()
        elif opcion == "2":
            convertir_csv_markdown()
            pausa()
        elif opcion == "3":
            convertir_excel_latex()
            pausa()
        elif opcion == "4":
            convertir_excel_markdown()
            pausa()
        elif opcion == "5":
            convertir_pdf_latex()
            pausa()
        elif opcion == "6":
            convertir_pdf_markdown()
            pausa()
        elif opcion == "7":
            vista_previa()
            pausa()
        elif opcion == "8":
            conversion_por_lotes()
            pausa()
        elif opcion == "9":
            iniciar_streamlit()
        elif opcion == "0":
            print("\n  [*] Hasta luego!\n")
            break
        else:
            print("\n  [!] Opcion no valida.")
            pausa()


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--web" in sys.argv:
        interfaz_web()
    else:
        menu_principal()
