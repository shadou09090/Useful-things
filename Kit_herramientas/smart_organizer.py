import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

CATEGORIES = {
    "Documentos": {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".tex", ".md", ".epub"},
    "Imagenes": {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".tiff"},
    "Comprimidos": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "Ejecutables_Instaladores": {".exe", ".msi", ".deb", ".rpm", ".dmg", ".appimage", ".bat", ".sh", ".bin"},
    "Codigo_Datos": {".py", ".cpp", ".c", ".h", ".hpp", ".java", ".js", ".ts", ".html", ".css", ".sql", ".json", ".xml", ".yaml", ".yml", ".ipynb"},
    "Multimedia": {".mp4", ".mkv", ".avi", ".mov", ".mp3", ".wav", ".flac", ".ogg", ".m4a"},
    "Diseno_CAD": {".sldprt", ".sldasm", ".slddrw", ".stl", ".obj", ".step", ".stp", ".iges", ".igs", ".dwg", ".dxf", ".psd", ".ai"},
    "Imagenes_Disco": {".iso", ".img", ".vmdk", ".ova", ".vbox"}
}

TEMP_EXTENSIONS = {".crdownload", ".part", ".tmp", ".download"}
HISTORY_FILENAME = ".organizer_history.json"


class DirectoryOrganizer:
    def __init__(self, target_dir: Path):
        self.set_target_dir(target_dir)

    def set_target_dir(self, target_dir: Path):
        self.target_dir = target_dir.resolve()
        self.history_file = self.target_dir / HISTORY_FILENAME
        self.history = self.load_history()

    def load_history(self):
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [[(Path(curr), Path(orig)) for curr, orig in batch] for batch in data]
            except Exception:
                return []
        return []

    def save_history(self):
        try:
            serializable = [[[str(curr), str(orig)] for curr, orig in batch] for batch in self.history]
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)
        except Exception:
            pass

    def get_category(self, ext: str) -> str:
        ext_lower = ext.lower()
        for category, extensions in CATEGORIES.items():
            if ext_lower in extensions:
                return category
        return "Otros"

    def resolve_collision(self, destination: Path) -> Path:
        if not destination.exists():
            return destination
        stem = destination.stem
        suffix = destination.suffix
        parent = destination.parent
        counter = 1
        while True:
            new_dest = parent / f"{stem}_{counter}{suffix}"
            if not new_dest.exists():
                return new_dest
            counter += 1

    def scan_files(self):
        if not self.target_dir.exists() or not self.target_dir.is_dir():
            return []
        script_path = Path(__file__).resolve() if "__file__" in globals() else None
        files = []
        for item in self.target_dir.iterdir():
            if item.is_file():
                if script_path and item.resolve() == script_path:
                    continue
                if item.name.startswith(".") or item.name == HISTORY_FILENAME:
                    continue
                if item.suffix.lower() in TEMP_EXTENSIONS:
                    continue
                files.append(item)
        return files

    def organize(self, dry_run: bool = False):
        files = self.scan_files()
        if not files:
            return [], {}

        batch_moves = []
        logs = []
        summary = {}

        for file_path in files:
            category = self.get_category(file_path.suffix)
            dest_dir = self.target_dir / category
            dest_path = dest_dir / file_path.name

            if not dry_run:
                dest_dir.mkdir(exist_ok=True)
                final_dest = self.resolve_collision(dest_path)
                try:
                    shutil.move(str(file_path), str(final_dest))
                    batch_moves.append((final_dest, file_path))
                    summary[category] = summary.get(category, 0) + 1
                    logs.append({"archivo": file_path.name, "categoria": category, "destino": final_dest.name, "estado": "OK"})
                except Exception as e:
                    logs.append({"archivo": file_path.name, "categoria": category, "destino": "-", "estado": f"ERROR: {e}"})
            else:
                final_dest = self.resolve_collision(dest_path)
                summary[category] = summary.get(category, 0) + 1
                logs.append({"archivo": file_path.name, "categoria": category, "destino": final_dest.name, "estado": "SIMULADO"})

        if batch_moves and not dry_run:
            self.history.append(batch_moves)
            self.save_history()

        return logs, summary

    def undo_last_batch(self):
        self.history = self.load_history()
        if not self.history:
            return []

        last_batch = self.history.pop()
        restored_logs = []

        for current_path, original_path in reversed(last_batch):
            if current_path.exists():
                try:
                    target_restore = self.resolve_collision(original_path)
                    shutil.move(str(current_path), str(target_restore))
                    restored_logs.append({"archivo": current_path.name, "restaurado_en": target_restore.name, "estado": "RESTAURADO"})
                    if current_path.parent.exists() and not any(current_path.parent.iterdir()):
                        current_path.parent.rmdir()
                except Exception as e:
                    restored_logs.append({"archivo": current_path.name, "restaurado_en": "-", "estado": f"ERROR: {e}"})

        self.save_history()
        return restored_logs

    def monitor_cli(self, interval: int = 5):
        print(f"\n  [MONITOREANDO EN TIEMPO REAL] -> {self.target_dir}")
        print(f"  Escaneando cada {interval} segundos. Presiona Ctrl+C para detener y volver al menú.\n")
        try:
            while True:
                files = self.scan_files()
                if files:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"  [{timestamp}] Detectados {len(files)} archivo(s)...")
                    logs, _ = self.organize(dry_run=False)
                    for item in logs:
                        print(f"   -> [{item['estado']}] {item['archivo']} -> {item['categoria']}/{item['destino']}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n  [!] Monitoreo detenido por el usuario.")


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_header(current_dir: Path, history_count: int, pending_count: int):
    print("=" * 66)
    print("            ORGANIZADOR INTELIGENTE DE DIRECTORIOS            ")
    print("=" * 66)
    print(f"  Ruta activa         : {current_dir}")
    print(f"  Archivos sin ordenar: {pending_count}")
    print(f"  Lotes para deshacer : {history_count}")
    print("=" * 66)


def select_custom_path(current_dir: Path) -> Path:
    print("\n  [SELECTOR DE RUTA OBJETIVO]")
    print("  " + "-" * 60)
    home = Path.home()
    presets = {
        "1": ("Descargas (Downloads)", home / "Downloads"),
        "2": ("Escritorio (Desktop)", home / "Desktop"),
        "3": ("Documentos (Documents)", home / "Documents"),
        "4": ("Directorio actual de la terminal", Path.cwd())
    }
    for key, (label, p) in presets.items():
        status = "Disponible" if p.exists() else "No encontrado"
        print(f"  [{key}] {label}: {p} ({status})")
    print("  [5] Escribir o pegar una ruta personalizada manualmente")
    print("  [0] Cancelar")
    print("  " + "-" * 60)

    sub_choice = input("  Elige una opción de ruta: ").strip()
    if sub_choice in presets:
        chosen = presets[sub_choice][1]
        if chosen.exists() and chosen.is_dir():
            return chosen
        print("\n  [ERROR] El directorio predefinido no existe en este sistema.")
        return current_dir
    elif sub_choice == "5":
        raw_path = input("\n  Pega o escribe la ruta completa: ").strip().strip('"').strip("'")
        if raw_path:
            custom_path = Path(raw_path).expanduser()
            if custom_path.exists() and custom_path.is_dir():
                return custom_path
            create_q = input("  [!] La carpeta no existe. ¿Deseas crearla ahora? (s/n): ").strip().lower()
            if create_q == "s":
                try:
                    custom_path.mkdir(parents=True, exist_ok=True)
                    return custom_path
                except Exception as e:
                    print(f"  [ERROR] No se pudo crear la carpeta: {e}")
    return current_dir


def launch_streamlit_from_cli(target_dir: Path):
    print("\n  [*] Iniciando servidor de interfaz gráfica con Streamlit...")
    print("  [*] Presiona Ctrl+C en esta consola cuando quieras cerrar la interfaz web.\n")
    cmd = [sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve()), "--", str(target_dir)]
    try:
        subprocess.run(cmd)
    except FileNotFoundError:
        print("\n  [ERROR] Streamlit no está instalado. Instálalo con: pip install streamlit")
    except KeyboardInterrupt:
        print("\n  [*] Interfaz web cerrada. Regresando a la terminal...")


def run_streamlit_ui():
    import streamlit as st

    st.set_page_config(page_title="Smart Directory Organizer", layout="wide")

    initial_dir = Path.home() / "Downloads"
    if len(sys.argv) > 1:
        passed_path = Path(sys.argv[1])
        if passed_path.exists() and passed_path.is_dir():
            initial_dir = passed_path

    if "target_dir" not in st.session_state:
        st.session_state.target_dir = str(initial_dir.resolve())

    st.title("Organizador Inteligente de Directorios")

    with st.sidebar:
        st.header("Ruta de Trabajo")
        quick_select = st.selectbox(
            "Accesos rápidos",
            ["Ruta personalizada", "Downloads", "Desktop", "Documents", "Directorio Actual"]
        )

        if quick_select == "Downloads":
            default_val = str((Path.home() / "Downloads").resolve())
        elif quick_select == "Desktop":
            default_val = str((Path.home() / "Desktop").resolve())
        elif quick_select == "Documents":
            default_val = str((Path.home() / "Documents").resolve())
        elif quick_select == "Directorio Actual":
            default_val = str(Path.cwd().resolve())
        else:
            default_val = st.session_state.target_dir

        path_input = st.text_input("Escribe la ruta que quieras organizar:", value=default_val)

        if st.button("Aplicar Ruta", use_container_width=True):
            candidate = Path(path_input.strip().strip('"').strip("'")).expanduser()
            if candidate.exists() and candidate.is_dir():
                st.session_state.target_dir = str(candidate.resolve())
                st.success("Ruta actualizada correctamente.")
            else:
                st.error("La ruta ingresada no existe o no es una carpeta válida.")

        st.divider()
        st.subheader("Categorías Activas")
        for cat, exts in CATEGORIES.items():
            with st.expander(f"{cat} ({len(exts)})"):
                st.caption(", ".join(sorted(exts)))

    current_path = Path(st.session_state.target_dir)
    if not current_path.exists() or not current_path.is_dir():
        st.error(f"El directorio `{current_path}` no es accesible. Selecciónalo en la barra lateral.")
        return

    organizer = DirectoryOrganizer(current_path)
    pending_files = organizer.scan_files()

    col1, col2, col3 = st.columns(3)
    col1.metric("Directorio Objetivo", current_path.name)
    col2.metric("Archivos por Clasificar", len(pending_files))
    col3.metric("Lotes Disponibles para Deshacer", len(organizer.history))
    st.caption(f"Ruta completa activa: `{current_path}`")

    st.divider()

    btn1, btn2, btn3 = st.columns(3)

    if btn1.button("Organizar Archivos Ahora", type="primary", use_container_width=True):
        logs, summary = organizer.organize(dry_run=False)
        if logs:
            st.success(f"Se organizaron {len(logs)} archivo(s) exitosamente.")
            st.dataframe(logs, use_container_width=True)
        else:
            st.info("No hay archivos sueltos para organizar en esta ruta.")

    if btn2.button("Simular (Vista Previa)", use_container_width=True):
        logs, summary = organizer.organize(dry_run=True)
        if logs:
            st.warning("Vista previa de simulación (ningún archivo fue movido):")
            st.dataframe(logs, use_container_width=True)
        else:
            st.info("No hay archivos pendientes para simular.")

    if btn3.button("Deshacer Última Organización", use_container_width=True):
        restored = organizer.undo_last_batch()
        if restored:
            st.success(f"Se restauraron {len(restored)} archivo(s) a su ubicación original.")
            st.dataframe(restored, use_container_width=True)
        else:
            st.warning("No hay historial de movimientos para deshacer en esta carpeta.")

    st.subheader("Vista Previa del Contenido Actual")
    if pending_files:
        preview_rows = []
        cat_counts = {}
        for f in pending_files:
            cat = organizer.get_category(f.suffix)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            size_kb = round(f.stat().st_size / 1024, 2)
            preview_rows.append({
                "Archivo": f.name,
                "Extensión": f.suffix.lower() if f.suffix else "Sin extensión",
                "Categoría Destino": cat,
                "Tamaño (KB)": size_kb
            })

        c_table, c_chart = st.columns([2, 1])
        with c_table:
            st.dataframe(preview_rows, use_container_width=True, height=320)
        with c_chart:
            st.bar_chart(cat_counts)
    else:
        st.info("El directorio está completamente limpio. No hay archivos sueltos pendientes.")


def run_cli():
    default_downloads = Path.home() / "Downloads"
    if not default_downloads.exists():
        default_downloads = Path.cwd()

    organizer = DirectoryOrganizer(default_downloads)

    while True:
        organizer.history = organizer.load_history()
        pending = organizer.scan_files()
        clear_screen()
        print_header(organizer.target_dir, len(organizer.history), len(pending))
        print("  [1] Organizar directorio ahora")
        print("  [2] Simular organización (Vista previa sin mover archivos)")
        print("  [3] Modo Centinela (Monitoreo automático en tiempo real)")
        print("  [4] Deshacer la última organización")
        print("  [5] Elegir o escribir la ruta que quieras organizar")
        print("  [6] Abrir interfaz gráfica interactiva (Streamlit Web UI)")
        print("  [7] Ver categorías y extensiones configuradas")
        print("  [0] Salir")
        print("-" * 66)

        choice = input("  Selecciona una opción: ").strip()

        if choice == "1":
            logs, summary = organizer.organize(dry_run=False)
            if not logs:
                print("\n  [!] No hay archivos sueltos para organizar.")
            else:
                print("\n  [ORGANIZACIÓN COMPLETADA]")
                for item in logs:
                    print(f"   [{item['estado']}] {item['archivo']} -> {item['categoria']}/{item['destino']}")
                print("\n  Resumen por categoría:")
                for cat, count in sorted(summary.items()):
                    print(f"   - {cat}: {count} archivo(s)")
            input("\n  Presiona Enter para continuar...")

        elif choice == "2":
            logs, summary = organizer.organize(dry_run=True)
            if not logs:
                print("\n  [!] No hay archivos sueltos para simular.")
            else:
                print("\n  [SIMULACIÓN - NINGÚN ARCHIVO FUE MOVIDO]")
                for item in logs:
                    print(f"   [{item['estado']}] {item['archivo']} -> {item['categoria']}/{item['destino']}")
            input("\n  Presiona Enter para continuar...")

        elif choice == "3":
            interval_input = input("  Intervalo en segundos (Enter para 5s): ").strip()
            interval = int(interval_input) if interval_input.isdigit() and int(interval_input) > 0 else 5
            organizer.monitor_cli(interval=interval)
            input("\n  Presiona Enter para continuar...")

        elif choice == "4":
            restored = organizer.undo_last_batch()
            if not restored:
                print("\n  [!] No hay operaciones registradas para deshacer en esta ruta.")
            else:
                print(f"\n  [OK] Se restauraron {len(restored)} archivo(s) a su estado original.")
                for r in restored:
                    print(f"   - {r['archivo']} -> {r['restaurado_en']} ({r['estado']})")
            input("\n  Presiona Enter para continuar...")

        elif choice == "5":
            new_dir = select_custom_path(organizer.target_dir)
            organizer.set_target_dir(new_dir)
            print(f"\n  [OK] Ruta activa configurada en: {organizer.target_dir}")
            input("\n  Presiona Enter para continuar...")

        elif choice == "6":
            launch_streamlit_from_cli(organizer.target_dir)
            input("\n  Presiona Enter para continuar...")

        elif choice == "7":
            print("\n  [MAPEO DE CATEGORÍAS]")
            print("  " + "-" * 60)
            for cat, exts in CATEGORIES.items():
                print(f"  * {cat}:\n    {', '.join(sorted(exts))}\n")
            input("  Presiona Enter para continuar...")

        elif choice == "0":
            print("\n  Saliendo del programa...")
            sys.exit(0)
        else:
            print("\n  [!] Opción no válida.")
            time.sleep(1)


def is_running_in_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


if __name__ == "__main__":
    if is_running_in_streamlit():
        run_streamlit_ui()
    else:
        run_cli()