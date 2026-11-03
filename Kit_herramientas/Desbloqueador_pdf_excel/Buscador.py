"""Desbloqueador de PDF y Excel con contraseña o lista de contraseñas.

Permite abrir un archivo protegido usando una contraseña que el usuario
proporcione o probando una lista de contraseñas desde un archivo TXT,
guardando una copia sin cifrado.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "por_desbloquear"
OUTPUT_DIR = ROOT / "crakeados"
PASSWORDS_DIR = ROOT / "Contraseñas"
HISTORY_DIR = ROOT / "historial"
HISTORY_FILE = HISTORY_DIR / "historial.jsonl"

PDF_EXTENSIONS = {".pdf"}
EXCEL_EXTENSIONS = {".xls", ".xlsx", ".xlsm", ".xltx", ".xltm"}
SUPPORTED_EXTENSIONS = PDF_EXTENSIONS | EXCEL_EXTENSIONS


def ensure_directories() -> None:
    for directory in (INPUT_DIR, OUTPUT_DIR, PASSWORDS_DIR, HISTORY_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in PDF_EXTENSIONS:
        return "PDF"
    if suffix in EXCEL_EXTENSIONS:
        return "Excel"
    return "desconocido"


def supported_files(directory: Path) -> list[Path]:
    return sorted(
        (item for item in directory.iterdir() if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda item: item.name.lower(),
    )


def text_files(directory: Path) -> list[Path]:
    return sorted(
        (item for item in directory.iterdir() if item.is_file() and item.suffix.lower() == ".txt"),
        key=lambda item: item.name.lower(),
    )


def choose_from(items: list[Path], title: str) -> Path | None:
    if not items:
        print("No hay archivos disponibles.")
        return None

    print(f"\n{title}")
    for index, item in enumerate(items, start=1):
        print(f"  {index}. {item.name}")
    print("  0. Cancelar")

    while True:
        value = input("Selecciona una opción: ").strip()
        if value == "0":
            return None
        try:
            selected = int(value)
        except ValueError:
            print("Escribe un número válido.")
            continue
        if 1 <= selected <= len(items):
            return items[selected - 1]
        print("La opción no existe.")


def unique_output_path(source: Path) -> Path:
    candidate = OUTPUT_DIR / source.name
    if not candidate.exists():
        return candidate
    stem, suffix = source.stem, source.suffix
    counter = 2
    while True:
        candidate = OUTPUT_DIR / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def read_passwords(password_file: Path) -> list[str]:
    """Lee todas las contraseñas no vacías de un TXT conservando el orden sin duplicados."""
    lines = [line.strip() for line in password_file.read_text(encoding="utf-8-sig", errors="replace").splitlines()]
    passwords: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if line and line not in seen:
            seen.add(line)
            passwords.append(line)
    if not passwords:
        raise ValueError("El archivo TXT no contiene ninguna contraseña válida.")
    return passwords


def read_single_password(password_file: Path) -> str:
    """Lee la primera contraseña válida de un TXT (mantenido por compatibilidad)."""
    return read_passwords(password_file)[0]


def password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def write_history(record: dict[str, object]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as history:
        history.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_password_sidecar(output_path: Path, password: str) -> Path:
    sidecar = output_path.with_name(output_path.name + ".password.txt")
    sidecar.write_text(password + "\n", encoding="utf-8")
    return sidecar


def unlock_file(source: Path, password: str, save_password: bool = False) -> Path:
    """Desbloquea un PDF o Excel con la contraseña indicada por el usuario."""
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"No existe el archivo: {source}")
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Solo se admiten PDF, XLS, XLSX, XLSM, XLTX y XLTM.")

    output = unique_output_path(source)
    try:
        if source.suffix.lower() in PDF_EXTENSIONS:
            try:
                import pikepdf
            except ImportError as exc:
                raise RuntimeError("Falta pikepdf. Instala las dependencias necesarias.") from exc

            with pikepdf.open(source, password=password) as pdf:
                pdf.save(output)
        else:
            try:
                import msoffcrypto
            except ImportError as exc:
                raise RuntimeError("Falta msoffcrypto-tool. Instala las dependencias necesarias.") from exc

            with source.open("rb") as encrypted_file:
                office_file = msoffcrypto.OfficeFile(encrypted_file)
                if office_file.is_encrypted():
                    office_file.load_key(password=password)
                    with output.open("wb") as decrypted_file:
                        office_file.decrypt(decrypted_file)
                else:
                    shutil.copy2(source, output)

        record: dict[str, object] = {
            "fecha": timestamp(),
            "resultado": "exitoso",
            "tipo": file_kind(source),
            "entrada": relative_path(source),
            "salida": relative_path(output),
            "hash_sha256_contrasena": password_hash(password),
            "contrasena_guardada": save_password,
        }
        if save_password:
            record["archivo_contrasena"] = relative_path(save_password_sidecar(output, password))
        write_history(record)
        return output
    except Exception:
        # Evita dejar una salida parcial si la biblioteca no pudo completar el proceso.
        if output.exists():
            output.unlink()
        raise


def try_unlock_with_passwords(
    source: Path,
    passwords: list[str],
    save_password: bool = False,
    verbose: bool = True,
) -> Path | None:
    """Prueba una lista de contraseñas secuencialmente contra un archivo protegido."""
    total = len(passwords)
    if verbose:
        print(f"\nProbando {total} contraseña(s) contra '{source.name}'...")

    for index, pwd in enumerate(passwords, start=1):
        if verbose:
            print(f"[{index}/{total}] Probando contraseña...", end="\r", flush=True)
        try:
            output = unlock_file(source, pwd, save_password=save_password)
            if verbose:
                print(" " * 60, end="\r")
                print(f"[+] ¡Éxito! Contraseña correcta encontrada: {pwd}")
                print(f"[+] Archivo guardado en: {output}")
            return output
        except (RuntimeError, FileNotFoundError, PermissionError) as fatal_err:
            if verbose:
                print(" " * 60, end="\r")
            raise fatal_err
        except Exception:
            # Contraseña incorrecta u otro error al intentar descifrar con esta clave
            continue

    if verbose:
        print(" " * 60, end="\r")
        print(f"[-] No se pudo desbloquear. Se probaron las {total} contraseñas sin éxito.")
    return None


def ask_save_password() -> bool:
    answer = input(
        "¿Guardar también la contraseña en un TXT junto al archivo desbloqueado? "
        "(s/N): "
    ).strip().lower()
    return answer in {"s", "si", "sí", "y", "yes"}


def unlock_interactive(source: Path | None = None, password: str | None = None) -> None:
    source = source or choose_from(supported_files(INPUT_DIR), "Archivos en por_desbloquear")
    if source is None:
        return
    if password is None:
        password = getpass.getpass("Contraseña conocida (Enter si no tiene): ")
    try:
        output = unlock_file(source, password, save_password=ask_save_password())
    except Exception as exc:
        print(f"No se pudo desbloquear: {exc}")
        return
    print(f"Archivo guardado en: {output}")


def unlock_from_password_txt() -> None:
    source = choose_from(supported_files(INPUT_DIR), "Archivo que se va a desbloquear")
    if source is None:
        return
    password_file = choose_from(text_files(PASSWORDS_DIR), "TXT de Contraseñas")
    if password_file is None:
        return
    try:
        passwords = read_passwords(password_file)
    except Exception as exc:
        print(f"Error al leer el archivo de contraseñas: {exc}")
        return

    try:
        try_unlock_with_passwords(source, passwords, save_password=ask_save_password())
    except Exception as exc:
        print(f"Error durante el desbloqueo: {exc}")


def add_password_txt() -> None:
    raw_path = input("Ruta del archivo .txt que contiene contraseñas: ").strip().strip('"')
    source = Path(raw_path).expanduser()
    if not source.is_file() or source.suffix.lower() != ".txt":
        print("La ruta no es un archivo .txt válido.")
        return
    try:
        passwords = read_passwords(source)
    except Exception as exc:
        print(f"No se copió: {exc}")
        return
    destination = PASSWORDS_DIR / source.name
    if destination.exists():
        destination = PASSWORDS_DIR / f"{source.stem}_copia{source.suffix}"
    shutil.copy2(source, destination)
    print(f"Copiado a: {destination} ({len(passwords)} contraseña(s) detectada(s))")


def show_history() -> None:
    if not HISTORY_FILE.exists():
        print("Todavía no hay archivos procesados.")
        return
    print("\nHistorial")
    for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        print(
            f"- {record.get('fecha', '?')} | {record.get('tipo', '?')} | "
            f"{record.get('entrada', '?')} -> {record.get('salida', '?')} | "
            f"contraseña guardada: {record.get('contrasena_guardada', False)}"
        )


def interactive_menu() -> None:
    ensure_directories()
    while True:
        print(
            "\n=== Desbloqueador de PDF y Excel ===\n"
            "1. Desbloquear un archivo con contraseña conocida\n"
            "2. Probar contraseñas desde un TXT y desbloquear\n"
            "3. Añadir un TXT a la carpeta Contraseñas\n"
            "4. Ver historial\n"
            "5. Salir"
        )
        option = input("Elige una opción: ").strip()
        if option == "1":
            unlock_interactive()
        elif option == "2":
            unlock_from_password_txt()
        elif option == "3":
            add_password_txt()
        elif option == "4":
            show_history()
        elif option == "5":
            print("Hasta luego.")
            return
        else:
            print("Opción no válida.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    unlock_parser = subparsers.add_parser("unlock", help="desbloquear un archivo protegido")
    unlock_parser.add_argument("--file", type=Path, required=True, help="ruta del PDF o Excel protegido")
    unlock_parser.add_argument(
        "--password-file",
        type=Path,
        help="TXT con contraseñas a probar",
    )
    unlock_parser.add_argument(
        "--record-password",
        action="store_true",
        help="guardar la contraseña en un TXT junto a la salida (desactivado por defecto)",
    )
    subparsers.add_parser("history", help="mostrar el historial")
    return parser


def main() -> int:
    ensure_directories()
    args = build_parser().parse_args()
    if args.command is None:
        interactive_menu()
        return 0
    if args.command == "history":
        show_history()
        return 0
    if args.command == "unlock":
        try:
            if args.password_file:
                passwords = read_passwords(args.password_file)
                output = try_unlock_with_passwords(
                    args.file,
                    passwords,
                    save_password=args.record_password,
                    verbose=True,
                )
                return 0 if output is not None else 1
            else:
                password = getpass.getpass("Contraseña conocida (no se mostrará): ")
                output = unlock_file(args.file, password, save_password=args.record_password)
                print(f"Archivo guardado en: {output}")
                return 0
        except Exception as exc:
            print(f"No se pudo desbloquear: {exc}", file=sys.stderr)
            return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
