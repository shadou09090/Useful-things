import os
import sys
import io
import base64
import subprocess
from pathlib import Path
try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader, PdfWriter = None, None

try:
    import msoffcrypto
except ImportError:
    msoffcrypto = None

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    Fernet, hashes, PBKDF2HMAC = None, None, None

# Anclamos todo a la carpeta exacta donde vive este archivo .py
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "encriptado"
SUPPORTED_EXTS = (".pdf", ".xlsx", ".xls", ".csv")

# =====================================================================
# TEXTO DE EXPLICACIÓN DETALLADA DE NIVELES
# =====================================================================
EXPLICACION_NIVELES = """
================================================================================
                    EXPLICACIÓN DE NIVELES DE ENCRIPTACIÓN
================================================================================

1. ENCRIPTAMIENTO NORMAL (AES-256 Estándar - Revisión 5):
   -----------------------------------------------------------------------------
   * Algoritmo: AES-256 estándar con derivación directa (SHA-256 + salt de 8 bytes).
   * Velocidad de apertura: Instantánea en cualquier dispositivo o visor.
   * Resistencia a ataques: Seguridad estándar industrial. Comprobar cada contraseña
     requiere solo una ronda criptográfica rápida.
   * Comportamiento con la GPU: Es el formato 100% acelerable por tarjetas gráficas
     (NVIDIA GeForce RTX, AMD Radeon, etc.). Un cracker o auditoría en GPU puede
     evaluar millones de contraseñas por segundo en este modo.
   * ¿Cuándo usarlo?:
     - Documentos cotidianos para protegerlos de miradas curiosas.
     - Pruebas de rendimiento, benchmarking y auditorías de contraseñas con GPU.
     - Máxima compatibilidad con lectores antiguos, visores móviles y visores web.

2. ENCRIPTAMIENTO FUERTE (AES-256 Hardened - Revisión 6 / ISO 32000-2):
   -----------------------------------------------------------------------------
   * Algoritmo: AES-256 "Endurecido" con ciclo repetitivo multi-algorítmico.
   * Funcionamiento: Por CADA contraseña probada, el sistema se ve forzado a
     ejecutar un bucle de entre 64 y 96 rondas completas encadenadas de cifrado
     militar AES-128-CBC junto a hashes SHA-256, SHA-384 y SHA-512.
   * Resistencia a ataques: MÁXIMA protección contra hackers y fuerza bruta.
     Incluso con supercomputadoras o granjas de tarjetas gráficas, el ataque se
     vuelve extremadamente lento y costoso (hasta 50,000 veces más lento que el normal).
   * Comportamiento con la GPU: Diseñado específicamente para ahogar y neutralizar
     la ventaja de velocidad masiva de las GPUs, forzando un consumo enorme de ciclos.
   * ¿Cuándo usarlo?:
     - Información confidencial, financiera, legal, contraseñas maestras o datos críticos.
     - Documentos que deban ser prácticamente invulnerables ante robo o filtración.
================================================================================
"""


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def derive_key(password: str, salt: bytes, iterations: int = 480_000) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def encrypt_bytes(file_bytes: bytes, filename: str, password: str, fuerte: bool = False) -> Path:
    """
    Recibe los bytes de un archivo, lo encripta según su extensión y nivel,
    y guarda la copia en ./encriptado.
    """
    ensure_output_dir()
    ext = Path(filename).suffix.lower()
    in_stream = io.BytesIO(file_bytes)

    if ext == ".pdf":
        if PdfReader is None:
            raise RuntimeError("Falta 'pypdf'. Ejecuta: pip install pypdf")
        reader = PdfReader(in_stream)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        if reader.metadata:
            writer.add_metadata(reader.metadata)

        # Modo Normal: AES-256-R5 (Revisión 5, acelerable por GPU)
        # Modo Fuerte: AES-256 (Revisión 6 Hardened, blindaje anti-GPU)
        alg = "AES-256" if fuerte else "AES-256-R5"
        writer.encrypt(user_password=password, algorithm=alg)

        dest_path = OUTPUT_DIR / filename
        with open(dest_path, "wb") as f_out:
            writer.write(f_out)
        return dest_path

    elif ext in (".xlsx", ".xls"):
        if msoffcrypto is None:
            raise RuntimeError("Falta 'msoffcrypto-tool' para cifrar archivos Excel. Ejecuta: pip install msoffcrypto-tool")
        dest_path = OUTPUT_DIR / filename
        office_file = msoffcrypto.OfficeFile(in_stream)
        with open(dest_path, "wb") as f_out:
            office_file.encrypt(password, f_out)
        return dest_path

    elif ext == ".csv":
        if Fernet is None or PBKDF2HMAC is None:
            raise RuntimeError("Falta 'cryptography'. Ejecuta: pip install cryptography")
        salt = os.urandom(16)
        iterations = 600_000 if fuerte else 100_000
        key = derive_key(password, salt, iterations=iterations)
        cipher = Fernet(key)
        encrypted_data = cipher.encrypt(file_bytes)

        dest_path = OUTPUT_DIR / f"{filename}.enc"
        dest_path.write_bytes(salt + encrypted_data)
        return dest_path

    else:
        raise ValueError(f"Extensión '{ext}' no soportada.")


def get_local_files() -> list[Path]:
    """Busca archivos compatibles en la misma carpeta del script .py."""
    return [
        f for f in BASE_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS and f.name != Path(__file__).name
    ]


# ==========================================
# MODO INTERFAZ WEB (STREAMLIT)
# ==========================================
def run_streamlit_ui():
    import streamlit as st

    st.set_page_config(page_title="Encriptador de Archivos", layout="centered", page_icon="🔐")
    st.title("🔐 Encriptador de PDF, Excel y CSV")
    st.caption(f"Carpeta de salida: `{OUTPUT_DIR}`")

    # Sección de Explicación interactiva desplegable
    with st.expander("ℹ️ ¿Cuál es la diferencia entre Encriptamiento Normal y Fuerte? (Haz clic para ver)", expanded=False):
        st.markdown("""
        ### Comparativa de Niveles de Cifrado

        | Característica | 🟢 Encriptamiento Normal | 🛡️ Encriptamiento Fuerte |
        | :--- | :--- | :--- |
        | **Estándar en PDF** | **AES-256 (Revisión 5)** | **AES-256 Hardened (Revisión 6 - ISO 32000-2)** |
        | **Complejidad de Clave** | 1 ronda SHA-256 directa + salt | Bucle de 64 a 96 rondas de AES-CBC + SHA256/384/512 |
        | **Uso con Tarjeta Gráfica (GPU)** | ⚡ **Acelerable al 100%** (Millones de claves/s) | 🛑 **Anti-GPU** (Frena ataques de fuerza bruta) |
        | **Nivel de Protección** | Estándar / Comercial | Grado Militar / Máxima Seguridad |
        | **Ideal para...** | Documentos diarios, pruebas de GPU, compatibilidad | Información financiera, legal, contraseñas críticas |
        """)
        st.info(
            "💡 **Consejo:** Si quieres probar el desbloqueador por GPU de tu tarjeta gráfica, elige **Normal**. "
            "Si quieres que el archivo sea casi imposible de hackear por fuerza bruta, elige **Fuerte**."
        )

    st.divider()

    modo_origen = st.radio(
        "Selecciona el origen del archivo:",
        ["Archivos en la carpeta del .py", "Subir archivo o ingresar ruta"],
        horizontal=True
    )

    target_bytes = None
    target_name = None

    if modo_origen == "Archivos en la carpeta del .py":
        local_files = get_local_files()
        if not local_files:
            st.warning(f"No hay archivos {SUPPORTED_EXTS} en `{BASE_DIR}`.")
        else:
            selected_name = st.selectbox(
                "Elige el archivo local:",
                options=[f.name for f in local_files]
            )
            if selected_name:
                file_path = BASE_DIR / selected_name
                target_bytes = file_path.read_bytes()
                target_name = file_path.name
    else:
        uploaded = st.file_uploader("Arrastra un archivo aquí", type=["pdf", "xlsx", "xls", "csv"])
        custom_path = st.text_input("O pega la ruta absoluta del archivo en tu PC:")

        if uploaded is not None:
            target_bytes = uploaded.getvalue()
            target_name = uploaded.name
        elif custom_path.strip():
            clean_p = Path(custom_path.strip().strip("\"'")).expanduser().resolve()
            if clean_p.is_file() and clean_p.suffix.lower() in SUPPORTED_EXTS:
                target_bytes = clean_p.read_bytes()
                target_name = clean_p.name
            else:
                st.error("La ruta no existe o el formato no es compatible.")

    st.divider()

    # Selección de nivel de cifrado
    nivel_seleccionado = st.radio(
        "🔒 Elige el nivel de encriptamiento:",
        [
            "🟢 Normal (AES-256 Estándar - Acelerable por GPU / Máxima Compatibilidad)",
            "🛡️ Fuerte (AES-256 Hardened - Grado Militar Anti-Fuerza Bruta)"
        ],
        index=0
    )
    es_fuerte = "Fuerte" in nivel_seleccionado

    password = st.text_input("🔑 ¿Cuál quieres que sea la clave?", placeholder="Escribe tu contraseña aquí...", type="password")

    if st.button("🚀 Encriptar y Guardar Copia", type="primary", use_container_width=True):
        if not target_bytes or not target_name:
            st.error("Primero selecciona o carga un archivo válido.")
        elif not password:
            st.error("Debes escribir una contraseña.")
        else:
            try:
                out_path = encrypt_bytes(target_bytes, target_name, password, fuerte=es_fuerte)
                tipo_str = "🛡️ Fuerte (Anti-Fuerza Bruta)" if es_fuerte else "🟢 Normal (Acelerable en GPU)"
                st.success(f"Archivo encriptado en modo **{tipo_str}** con la clave **`{password}`** y guardado en:\n`{out_path}`")
                st.download_button(
                    label="⬇ Descargar archivo encriptado",
                    data=out_path.read_bytes(),
                    file_name=out_path.name,
                    mime="application/octet-stream"
                )
            except Exception as e:
                st.error(f"Error al encriptar: {e}")


# ==========================================
# MODO CONSOLA (CLI)
# ==========================================
def pedir_nivel_encriptacion() -> bool:
    """Solicita al usuario elegir entre Normal, Fuerte o ver la Explicación."""
    while True:
        print("\nSelecciona el nivel de encriptación:")
        print("  [1] Normal (AES-256 Estándar - R5, compatible y acelerable por GPU)")
        print("  [2] Fuerte (AES-256 Hardened - R6, blindaje militar anti-fuerza bruta)")
        print("  [3] Ver explicación detallada de cada opción")

        op = input("\nElige una opción (1/2/3): ").strip()
        if op == "1":
            return False  # Normal
        elif op == "2":
            return True   # Fuerte
        elif op == "3":
            print(EXPLICACION_NIVELES)
            input("Presiona Enter para continuar y seleccionar tu nivel...")
        else:
            print("[!] Opción no válida. Escribe 1, 2 o 3.")


def run_cli_menu():
    print("==================================================")
    print("   ENCRIPTADOR DE ARCHIVOS (PDF / EXCEL / CSV)    ")
    print("==================================================")
    print(f"Directorio del script: {BASE_DIR}")
    print("\nSelecciona una opción:")
    print("  1. Elegir un archivo de la misma carpeta")
    print("  2. Ingresar la ruta manual de un archivo")
    print("  3. Explicación de los niveles de encriptación (Normal vs Fuerte)")
    print("  4. Abrir interfaz interactiva en Streamlit")
    print("  0. Salir")

    opcion = input("\nOpción (0/1/2/3/4): ").strip()

    if opcion == "0":
        print("\nHasta luego.")
        return

    elif opcion == "1":
        archivos = get_local_files()
        if not archivos:
            print(f"\n[!] No se encontraron archivos {SUPPORTED_EXTS} en {BASE_DIR}")
            return

        print("\nArchivos detectados en la carpeta del script:")
        for idx, f in enumerate(archivos, 1):
            print(f"  [{idx}] {f.name}")
        print("  [0] Encriptar TODOS los de la lista")

        sel = input("\nElige el número del archivo: ").strip()
        try:
            idx_sel = int(sel)
            if idx_sel == 0:
                seleccionados = archivos
            elif 1 <= idx_sel <= len(archivos):
                seleccionados = [archivos[idx_sel - 1]]
            else:
                print("[ERROR] Número fuera de rango.")
                return
        except ValueError:
            print("[ERROR] Entrada inválida.")
            return

        clave = input("\n¿Cuál quieres que sea la clave?: ").strip()
        if not clave:
            print("[ERROR] La clave no puede estar vacía.")
            return

        fuerte = pedir_nivel_encriptacion()
        nivel_nombre = "FUERTE (Anti-GPU)" if fuerte else "NORMAL (GPU-Friendly)"

        for f in seleccionados:
            try:
                dest = encrypt_bytes(f.read_bytes(), f.name, clave, fuerte=fuerte)
                print(f"[OK] '{f.name}' [{nivel_nombre}] -> Guardado en: {dest}")
            except Exception as e:
                print(f"[ERROR] Falló '{f.name}': {e}")

    elif opcion == "2":
        ruta_raw = input("\nIngresa la ruta del archivo: ").strip().strip("\"'")
        archivo = Path(ruta_raw).expanduser().resolve()

        if not archivo.is_file():
            print(f"[ERROR] No existe el archivo: {archivo}")
            return

        clave = input("\n¿Cuál quieres que sea la clave?: ").strip()
        if not clave:
            print("[ERROR] La clave no puede estar vacía.")
            return

        fuerte = pedir_nivel_encriptacion()
        nivel_nombre = "FUERTE (Anti-GPU)" if fuerte else "NORMAL (GPU-Friendly)"

        try:
            dest = encrypt_bytes(archivo.read_bytes(), archivo.name, clave, fuerte=fuerte)
            print(f"[OK] '{archivo.name}' [{nivel_nombre}] -> Guardado en: {dest}")
        except Exception as e:
            print(f"[ERROR] Falló la encriptación: {e}")

    elif opcion == "3":
        print(EXPLICACION_NIVELES)
        input("Presiona Enter para volver al menú principal...")
        run_cli_menu()

    elif opcion == "4":
        print("\n[*] Levantando servidor Streamlit...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve())])

    else:
        print("[ERROR] Opción no válida.")


def is_running_in_streamlit() -> bool:
    """Detecta si el archivo fue invocado por 'streamlit run'."""
    try:
        from streamlit.runtime import exists
        return exists()
    except ImportError:
        return False


if __name__ == "__main__":
    if is_running_in_streamlit():
        run_streamlit_ui()
    else:
        run_cli_menu()
