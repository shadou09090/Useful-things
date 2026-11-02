#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Respaldos Incrementales - Programa de respaldos completos e incrementales.

Crea respaldos completos o incrementales de carpetas, comparando la fecha
de modificacion (mtime) de cada archivo con un manifiesto previo. Soporta
formatos .zip y .tar.gz, rotacion de respaldos, exclusiones configurables,
verificacion de integridad y restauracion.

Dependencias externas: streamlit
"""

import os
import sys
import json
import zipfile
import tarfile
import fnmatch
import shutil
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Rutas base
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CARPETA_LECTURA = BASE_DIR / "archivos_a_respaldar"
RESPALDOS_DIR = BASE_DIR / "respaldos"
MANIFEST_FILE = RESPALDOS_DIR / ".backup_manifest.json"
CONFIG_FILE = RESPALDOS_DIR / ".backup_config.json"

EXCLUSIONES_DEFAULT = [
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "*.pyc",
    ".DS_Store",
    "Thumbs.db",
    ".env",
]


# ===================================================================
#  Utilidades generales
# ===================================================================

def limpiar_pantalla():
    os.system("cls" if os.name == "nt" else "clear")


def pausar():
    input("\n    Presione ENTER para continuar...")


def mostrar_banner():
    print(r"""
    ============================================================
        RESPALDOS INCREMENTALES
        Copias de seguridad inteligentes
    ============================================================
    """)


def formatear_tamano(nbytes):
    """Devuelve un tamano legible (B, KB, MB, GB)."""
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return f"{nbytes:.2f} {unidad}"
        nbytes /= 1024
    return f"{nbytes:.2f} PB"


def limpiar_ruta(ruta_raw: str) -> str:
    """Elimina comillas y espacios sobrantes de una ruta pegada/arrastrada."""
    return ruta_raw.strip().strip('"').strip("'").strip()


# ===================================================================
#  Configuracion (exclusiones)
# ===================================================================

def cargar_config() -> dict:
    """Carga la configuracion desde .backup_config.json o crea una por defecto."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"exclusiones": list(EXCLUSIONES_DEFAULT), "rutas_default": []}


def guardar_config(config: dict):
    RESPALDOS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def esta_excluido(ruta_rel: str, exclusiones: list) -> bool:
    """Determina si un archivo/directorio debe excluirse."""
    partes = Path(ruta_rel).parts
    for patron in exclusiones:
        for parte in partes:
            if fnmatch.fnmatch(parte, patron):
                return True
        if fnmatch.fnmatch(ruta_rel, patron):
            return True
    return False


# ===================================================================
#  Manifiesto (mtime tracker)
# ===================================================================

def cargar_manifiesto() -> dict:
    if MANIFEST_FILE.exists():
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def guardar_manifiesto(manifiesto: dict):
    RESPALDOS_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifiesto, f, indent=2, ensure_ascii=False)


# ===================================================================
#  Recoleccion de archivos
# ===================================================================

def recolectar_archivos(carpeta_origen: Path, exclusiones: list):
    """Genera tuplas (ruta_absoluta, ruta_relativa, mtime) de archivos no excluidos."""
    for root, dirs, files in os.walk(carpeta_origen):
        # Filtrar directorios excluidos in-place para no descender
        dirs[:] = [d for d in dirs if not esta_excluido(d, exclusiones)]
        for nombre in files:
            ruta_abs = Path(root) / nombre
            ruta_rel = ruta_abs.relative_to(carpeta_origen).as_posix()
            if esta_excluido(ruta_rel, exclusiones):
                continue
            try:
                mtime = ruta_abs.stat().st_mtime
            except OSError:
                continue
            yield ruta_abs, ruta_rel, mtime


def filtrar_incrementales(archivos, manifiesto: dict, clave_carpeta: str):
    """Filtra solo archivos nuevos o modificados respecto al manifiesto."""
    datos_previos = manifiesto.get(clave_carpeta, {})
    for ruta_abs, ruta_rel, mtime in archivos:
        mtime_prev = datos_previos.get(ruta_rel)
        if mtime_prev is None or mtime > mtime_prev:
            yield ruta_abs, ruta_rel, mtime


# ===================================================================
#  Creacion de respaldos
# ===================================================================

def pedir_carpeta_origen() -> Path | None:
    CARPETA_LECTURA.mkdir(parents=True, exist_ok=True)
    RESPALDOS_DIR.mkdir(parents=True, exist_ok=True)
    print("    Seleccione el origen a respaldar:")
    print(f"    [1] Usar carpeta local predeterminada para leer:")
    print(f"        -> {CARPETA_LECTURA}")
    print("    [2] Escribir o arrastrar otra ruta personalizada")
    opc = input("\n    Seleccione opcion (1/2) [Por defecto 1]: ").strip()

    if opc in ("", "1"):
        return CARPETA_LECTURA

    print("\n    Ingrese la ruta de la carpeta a respaldar")
    print("    (puede arrastrar la carpeta aqui):\n")
    ruta = limpiar_ruta(input("    > "))
    if not ruta:
        print("\n    [!] No se proporciono ninguna ruta.")
        return None
    carpeta = Path(ruta)
    if not carpeta.is_dir():
        print(f"\n    [!] La ruta no es un directorio valido: {carpeta}")
        return None
    return carpeta


def generar_nombre_respaldo(nombre_carpeta: str, tipo: str, formato: str) -> str:
    ahora = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = ".zip" if formato == "zip" else ".tar.gz"
    return f"backup_{nombre_carpeta}_{ahora}_{tipo}{ext}"


def crear_respaldo_zip(archivos_lista, carpeta_origen: Path, ruta_destino: Path):
    """Crea un archivo .zip con los archivos proporcionados."""
    total = len(archivos_lista)
    tamano_total = 0
    with zipfile.ZipFile(ruta_destino, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (ruta_abs, ruta_rel, _) in enumerate(archivos_lista, 1):
            try:
                tamano = ruta_abs.stat().st_size
                tamano_total += tamano
                zf.write(ruta_abs, ruta_rel)
                print(f"\r    [{i}/{total}] {ruta_rel} ({formatear_tamano(tamano)})", end="")
            except OSError as e:
                print(f"\n    [!] Error al agregar {ruta_rel}: {e}")
    print()
    return total, tamano_total


def crear_respaldo_targz(archivos_lista, carpeta_origen: Path, ruta_destino: Path):
    """Crea un archivo .tar.gz con los archivos proporcionados."""
    total = len(archivos_lista)
    tamano_total = 0
    with tarfile.open(ruta_destino, "w:gz") as tf:
        for i, (ruta_abs, ruta_rel, _) in enumerate(archivos_lista, 1):
            try:
                tamano = ruta_abs.stat().st_size
                tamano_total += tamano
                tf.add(ruta_abs, arcname=ruta_rel)
                print(f"\r    [{i}/{total}] {ruta_rel} ({formatear_tamano(tamano)})", end="")
            except OSError as e:
                print(f"\n    [!] Error al agregar {ruta_rel}: {e}")
    print()
    return total, tamano_total


def ejecutar_respaldo(formato: str, tipo: str):
    """Flujo principal para crear un respaldo (completo o incremental)."""
    limpiar_pantalla()
    mostrar_banner()
    etiqueta = "COMPLETO" if tipo == "full" else "INCREMENTAL"
    print(f"    --- Respaldo {etiqueta} ({formato.upper()}) ---\n")

    carpeta = pedir_carpeta_origen()
    if carpeta is None:
        pausar()
        return

    config = cargar_config()
    exclusiones = config.get("exclusiones", EXCLUSIONES_DEFAULT)

    print(f"\n    [*] Escaneando: {carpeta}")
    print(f"    [*] Exclusiones activas: {', '.join(exclusiones)}\n")

    archivos = list(recolectar_archivos(carpeta, exclusiones))
    nombre_carpeta = carpeta.name
    clave_carpeta = str(carpeta.resolve())

    if tipo == "incremental":
        manifiesto = cargar_manifiesto()
        archivos = list(filtrar_incrementales(archivos, manifiesto, clave_carpeta))
        if not archivos:
            print("    [*] No hay archivos nuevos o modificados desde el ultimo respaldo.")
            print("    [*] No se creo ningun archivo de respaldo.")
            pausar()
            return
        print(f"    [*] Archivos modificados/nuevos: {len(archivos)}")
    else:
        if not archivos:
            print("    [!] La carpeta esta vacia o todos los archivos estan excluidos.")
            pausar()
            return
        print(f"    [*] Archivos a respaldar: {len(archivos)}")

    RESPALDOS_DIR.mkdir(parents=True, exist_ok=True)
    nombre_archivo = generar_nombre_respaldo(nombre_carpeta, tipo, formato)
    ruta_destino = RESPALDOS_DIR / nombre_archivo

    print(f"    [*] Creando: {nombre_archivo}\n")

    if formato == "zip":
        n_archivos, tamano_total = crear_respaldo_zip(archivos, carpeta, ruta_destino)
    else:
        n_archivos, tamano_total = crear_respaldo_targz(archivos, carpeta, ruta_destino)

    # Actualizar manifiesto
    manifiesto = cargar_manifiesto()
    if clave_carpeta not in manifiesto:
        manifiesto[clave_carpeta] = {}
    for _, ruta_rel, mtime in archivos:
        manifiesto[clave_carpeta][ruta_rel] = mtime
    guardar_manifiesto(manifiesto)

    tamano_respaldo = ruta_destino.stat().st_size
    print(f"\n    [OK] Respaldo creado exitosamente")
    print(f"    [+] Archivo:  {nombre_archivo}")
    print(f"    [+] Archivos: {n_archivos}")
    print(f"    [+] Tamano original: {formatear_tamano(tamano_total)}")
    print(f"    [+] Tamano respaldo: {formatear_tamano(tamano_respaldo)}")
    pausar()


# ===================================================================
#  Historial de respaldos
# ===================================================================

def listar_respaldos() -> list:
    """Devuelve lista de dicts con info de cada respaldo en respaldos/."""
    if not RESPALDOS_DIR.exists():
        return []
    resultados = []
    for archivo in sorted(RESPALDOS_DIR.iterdir()):
        nombre = archivo.name
        if not (nombre.startswith("backup_") and (nombre.endswith(".zip") or nombre.endswith(".tar.gz"))):
            continue
        stat = archivo.stat()
        tamano = stat.st_size
        fecha = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

        # Determinar tipo
        if "_full." in nombre:
            tipo = "Completo"
        elif "_incremental." in nombre:
            tipo = "Incremental"
        else:
            tipo = "Desconocido"

        # Determinar formato
        if nombre.endswith(".zip"):
            fmt = "ZIP"
        else:
            fmt = "TAR.GZ"

        # Contar archivos internos
        n_archivos = 0
        try:
            if fmt == "ZIP":
                with zipfile.ZipFile(archivo, "r") as zf:
                    n_archivos = len(zf.namelist())
            else:
                with tarfile.open(archivo, "r:gz") as tf:
                    n_archivos = len(tf.getnames())
        except Exception:
            n_archivos = -1

        resultados.append({
            "nombre": nombre,
            "ruta": archivo,
            "fecha": fecha,
            "tamano": tamano,
            "tamano_str": formatear_tamano(tamano),
            "tipo": tipo,
            "formato": fmt,
            "n_archivos": n_archivos,
        })
    return resultados


def ver_historial():
    limpiar_pantalla()
    mostrar_banner()
    print("    --- Historial de Respaldos ---\n")

    respaldos = listar_respaldos()
    if not respaldos:
        print("    [!] No se encontraron respaldos en la carpeta 'respaldos/'.")
        pausar()
        return

    print(f"    {'#':<4} {'Fecha':<22} {'Tipo':<14} {'Formato':<8} {'Archivos':<10} {'Tamano':<12} Nombre")
    print(f"    {'='*4} {'='*22} {'='*14} {'='*8} {'='*10} {'='*12} {'='*30}")
    for i, r in enumerate(respaldos, 1):
        n_str = str(r['n_archivos']) if r['n_archivos'] >= 0 else "???"
        print(f"    {i:<4} {r['fecha']:<22} {r['tipo']:<14} {r['formato']:<8} {n_str:<10} {r['tamano_str']:<12} {r['nombre']}")

    print(f"\n    Total: {len(respaldos)} respaldo(s)")
    pausar()


# ===================================================================
#  Verificar integridad
# ===================================================================

def verificar_integridad():
    limpiar_pantalla()
    mostrar_banner()
    print("    --- Verificar Integridad de un Respaldo ---\n")

    respaldos = listar_respaldos()
    if not respaldos:
        print("    [!] No se encontraron respaldos.")
        pausar()
        return

    for i, r in enumerate(respaldos, 1):
        print(f"    {i}. {r['nombre']} ({r['tamano_str']})")

    print()
    try:
        opcion = int(input("    Seleccione el numero del respaldo: "))
        if opcion < 1 or opcion > len(respaldos):
            print("    [!] Opcion invalida.")
            pausar()
            return
    except ValueError:
        print("    [!] Entrada invalida.")
        pausar()
        return

    respaldo = respaldos[opcion - 1]
    ruta = respaldo["ruta"]
    print(f"\n    [*] Verificando: {respaldo['nombre']}")

    try:
        archivos_internos = []
        tamano_descomprimido = 0

        if respaldo["formato"] == "ZIP":
            with zipfile.ZipFile(ruta, "r") as zf:
                # Testear integridad
                resultado_test = zf.testzip()
                if resultado_test is not None:
                    print(f"    [!] Archivo corrupto detectado: {resultado_test}")
                else:
                    print("    [OK] Prueba de integridad ZIP superada")

                for info in zf.infolist():
                    if not info.is_dir():
                        archivos_internos.append(info.filename)
                        tamano_descomprimido += info.file_size
        else:
            with tarfile.open(ruta, "r:gz") as tf:
                for miembro in tf.getmembers():
                    if miembro.isfile():
                        archivos_internos.append(miembro.name)
                        tamano_descomprimido += miembro.size
            print("    [OK] Archivo TAR.GZ se puede abrir correctamente")

        print(f"\n    [+] Archivos contenidos:     {len(archivos_internos)}")
        print(f"    [+] Tamano comprimido:       {respaldo['tamano_str']}")
        print(f"    [+] Tamano descomprimido:    {formatear_tamano(tamano_descomprimido)}")
        print(f"    [+] Tipo:                    {respaldo['tipo']}")
        print(f"    [+] Fecha:                   {respaldo['fecha']}")

        print("\n    --- Contenido (primeros 30 archivos) ---")
        for j, nombre in enumerate(archivos_internos[:30], 1):
            print(f"        {j:>3}. {nombre}")
        if len(archivos_internos) > 30:
            print(f"        ... y {len(archivos_internos) - 30} archivos mas")

    except (zipfile.BadZipFile, tarfile.TarError) as e:
        print(f"    [!] Error: El archivo esta corrupto o danado: {e}")
    except Exception as e:
        print(f"    [!] Error inesperado: {e}")

    pausar()


# ===================================================================
#  Restaurar respaldo
# ===================================================================

def restaurar_respaldo():
    limpiar_pantalla()
    mostrar_banner()
    print("    --- Restaurar un Respaldo ---\n")

    respaldos = listar_respaldos()
    if not respaldos:
        print("    [!] No se encontraron respaldos.")
        pausar()
        return

    for i, r in enumerate(respaldos, 1):
        print(f"    {i}. {r['nombre']} ({r['tamano_str']}, {r['tipo']})")

    print()
    try:
        opcion = int(input("    Seleccione el numero del respaldo a restaurar: "))
        if opcion < 1 or opcion > len(respaldos):
            print("    [!] Opcion invalida.")
            pausar()
            return
    except ValueError:
        print("    [!] Entrada invalida.")
        pausar()
        return

    respaldo = respaldos[opcion - 1]
    ruta_respaldo = respaldo["ruta"]

    print("\n    Ingrese la ruta donde desea restaurar los archivos")
    print("    (puede arrastrar la carpeta aqui):\n")
    ruta_destino_str = limpiar_ruta(input("    > "))
    if not ruta_destino_str:
        print("    [!] No se proporciono ruta de destino.")
        pausar()
        return

    ruta_destino = Path(ruta_destino_str)
    ruta_destino.mkdir(parents=True, exist_ok=True)

    print(f"\n    [*] Restaurando: {respaldo['nombre']}")
    print(f"    [*] Destino:     {ruta_destino}\n")

    try:
        if respaldo["formato"] == "ZIP":
            with zipfile.ZipFile(ruta_respaldo, "r") as zf:
                miembros = zf.namelist()
                total = len(miembros)
                for i, nombre in enumerate(miembros, 1):
                    zf.extract(nombre, ruta_destino)
                    print(f"\r    [{i}/{total}] {nombre}", end="")
                print()
        else:
            with tarfile.open(ruta_respaldo, "r:gz") as tf:
                miembros = tf.getmembers()
                total = len(miembros)
                for i, miembro in enumerate(miembros, 1):
                    tf.extract(miembro, ruta_destino, filter='data')
                    print(f"\r    [{i}/{total}] {miembro.name}", end="")
                print()

        print(f"\n    [OK] Restauracion completada exitosamente")
        print(f"    [+] Archivos restaurados: {total}")
        print(f"    [+] Ubicacion: {ruta_destino}")

    except (zipfile.BadZipFile, tarfile.TarError) as e:
        print(f"    [!] Error al restaurar: {e}")
    except Exception as e:
        print(f"    [!] Error inesperado: {e}")

    pausar()


# ===================================================================
#  Configurar exclusiones
# ===================================================================

def configurar_exclusiones():
    while True:
        limpiar_pantalla()
        mostrar_banner()
        print("    --- Configurar Exclusiones ---\n")

        config = cargar_config()
        exclusiones = config.get("exclusiones", list(EXCLUSIONES_DEFAULT))

        print("    Patrones de exclusion actuales:\n")
        if exclusiones:
            for i, patron in enumerate(exclusiones, 1):
                print(f"        {i}. {patron}")
        else:
            print("        (sin exclusiones)")

        print(f"\n    {'='*50}")
        print("    1. Agregar patron de exclusion")
        print("    2. Eliminar patron de exclusion")
        print("    3. Restaurar exclusiones por defecto")
        print("    0. Volver al menu principal")
        print()

        opcion = input("    Seleccione una opcion: ").strip()

        if opcion == "1":
            nuevo = input("\n    Ingrese el patron a agregar (ej: *.log, .idea, dist): ").strip()
            if nuevo and nuevo not in exclusiones:
                exclusiones.append(nuevo)
                config["exclusiones"] = exclusiones
                guardar_config(config)
                print(f"    [OK] Patron '{nuevo}' agregado.")
            elif nuevo in exclusiones:
                print(f"    [!] El patron '{nuevo}' ya existe.")
            else:
                print("    [!] Patron vacio.")
            pausar()

        elif opcion == "2":
            if not exclusiones:
                print("    [!] No hay patrones para eliminar.")
                pausar()
                continue
            try:
                idx = int(input("\n    Numero del patron a eliminar: "))
                if 1 <= idx <= len(exclusiones):
                    eliminado = exclusiones.pop(idx - 1)
                    config["exclusiones"] = exclusiones
                    guardar_config(config)
                    print(f"    [OK] Patron '{eliminado}' eliminado.")
                else:
                    print("    [!] Numero fuera de rango.")
            except ValueError:
                print("    [!] Entrada invalida.")
            pausar()

        elif opcion == "3":
            config["exclusiones"] = list(EXCLUSIONES_DEFAULT)
            guardar_config(config)
            print("    [OK] Exclusiones restauradas a valores por defecto.")
            pausar()

        elif opcion == "0":
            break


# ===================================================================
#  Rotacion de respaldos
# ===================================================================

def rotacion_respaldos():
    limpiar_pantalla()
    mostrar_banner()
    print("    --- Rotacion de Respaldos ---\n")

    respaldos = listar_respaldos()
    if not respaldos:
        print("    [!] No se encontraron respaldos.")
        pausar()
        return

    print(f"    Respaldos actuales: {len(respaldos)}\n")
    for i, r in enumerate(respaldos, 1):
        print(f"    {i}. {r['nombre']} ({r['fecha']}, {r['tamano_str']})")

    print()
    try:
        n = int(input("    Cuantos respaldos desea conservar (los mas recientes)? "))
        if n < 1:
            print("    [!] Debe conservar al menos 1 respaldo.")
            pausar()
            return
    except ValueError:
        print("    [!] Entrada invalida.")
        pausar()
        return

    if n >= len(respaldos):
        print(f"\n    [*] Solo hay {len(respaldos)} respaldo(s). No se elimina nada.")
        pausar()
        return

    # Ordenar por fecha de modificacion (mas reciente al final)
    respaldos_ordenados = sorted(respaldos, key=lambda r: r["ruta"].stat().st_mtime)
    a_eliminar = respaldos_ordenados[:len(respaldos_ordenados) - n]

    print(f"\n    Se eliminaran {len(a_eliminar)} respaldo(s):\n")
    for r in a_eliminar:
        print(f"        [-] {r['nombre']}")

    confirmacion = input("\n    Confirmar eliminacion? (s/n): ").strip().lower()
    if confirmacion != "s":
        print("    [*] Operacion cancelada.")
        pausar()
        return

    eliminados = 0
    for r in a_eliminar:
        try:
            r["ruta"].unlink()
            eliminados += 1
            print(f"    [-] Eliminado: {r['nombre']}")
        except OSError as e:
            print(f"    [!] Error al eliminar {r['nombre']}: {e}")

    print(f"\n    [OK] {eliminados} respaldo(s) eliminado(s). Quedan {n} respaldo(s).")
    pausar()


# ===================================================================
#  Interfaz Streamlit
# ===================================================================

def iniciar_streamlit():
    """Genera y ejecuta la interfaz web con Streamlit."""
    st_script = BASE_DIR / "_st_respaldos_incrementales.py"
    contenido_st = r'''# -*- coding: utf-8 -*-
"""Interfaz Streamlit para Respaldos Incrementales."""
import streamlit as st
import json
import zipfile
import tarfile
import os
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
RESPALDOS_DIR = BASE_DIR / "respaldos"
MANIFEST_FILE = RESPALDOS_DIR / ".backup_manifest.json"
CONFIG_FILE = RESPALDOS_DIR / ".backup_config.json"

EXCLUSIONES_DEFAULT = [
    "__pycache__", ".git", "node_modules", ".venv",
    "*.pyc", ".DS_Store", "Thumbs.db", ".env",
]

# ---------------------------------------------------------------
# Funciones auxiliares (replicadas para uso standalone en Streamlit)
# ---------------------------------------------------------------

def formatear_tamano(nbytes):
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return f"{nbytes:.2f} {unidad}"
        nbytes /= 1024
    return f"{nbytes:.2f} PB"


def cargar_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"exclusiones": list(EXCLUSIONES_DEFAULT), "rutas_default": []}


def guardar_config(config):
    RESPALDOS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def cargar_manifiesto():
    if MANIFEST_FILE.exists():
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def guardar_manifiesto(manifiesto):
    RESPALDOS_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifiesto, f, indent=2, ensure_ascii=False)


import fnmatch

def esta_excluido(ruta_rel, exclusiones):
    partes = Path(ruta_rel).parts
    for patron in exclusiones:
        for parte in partes:
            if fnmatch.fnmatch(parte, patron):
                return True
        if fnmatch.fnmatch(ruta_rel, patron):
            return True
    return False


def recolectar_archivos(carpeta_origen, exclusiones):
    resultado = []
    for root, dirs, files in os.walk(carpeta_origen):
        dirs[:] = [d for d in dirs if not esta_excluido(d, exclusiones)]
        for nombre in files:
            ruta_abs = Path(root) / nombre
            ruta_rel = ruta_abs.relative_to(carpeta_origen).as_posix()
            if esta_excluido(ruta_rel, exclusiones):
                continue
            try:
                mtime = ruta_abs.stat().st_mtime
            except OSError:
                continue
            resultado.append((ruta_abs, ruta_rel, mtime))
    return resultado


def listar_respaldos():
    if not RESPALDOS_DIR.exists():
        return []
    resultados = []
    for archivo in sorted(RESPALDOS_DIR.iterdir()):
        nombre = archivo.name
        if not (nombre.startswith("backup_") and (nombre.endswith(".zip") or nombre.endswith(".tar.gz"))):
            continue
        stat = archivo.stat()
        tamano = stat.st_size
        fecha = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        tipo = "Completo" if "_full." in nombre else ("Incremental" if "_incremental." in nombre else "Desconocido")
        fmt = "ZIP" if nombre.endswith(".zip") else "TAR.GZ"
        n_archivos = 0
        try:
            if fmt == "ZIP":
                with zipfile.ZipFile(archivo, "r") as zf:
                    n_archivos = len(zf.namelist())
            else:
                with tarfile.open(archivo, "r:gz") as tf:
                    n_archivos = len(tf.getnames())
        except Exception:
            n_archivos = -1
        resultados.append({
            "nombre": nombre, "ruta": archivo, "fecha": fecha,
            "tamano": tamano, "tamano_str": formatear_tamano(tamano),
            "tipo": tipo, "formato": fmt, "n_archivos": n_archivos,
        })
    return resultados


# ---------------------------------------------------------------
# Interfaz Streamlit
# ---------------------------------------------------------------

st.set_page_config(page_title="Respaldos Incrementales", layout="wide")
st.title("Respaldos Incrementales")
st.caption("Copias de seguridad inteligentes - completas e incrementales")

tab_crear, tab_historial, tab_restaurar, tab_config = st.tabs([
    "Crear Respaldo", "Historial", "Restaurar", "Exclusiones"
])

# --- TAB: Crear Respaldo ----------------------------------------
with tab_crear:
    st.subheader("Crear un nuevo respaldo")

    col1, col2 = st.columns(2)
    with col1:
        carpeta_origen = st.text_input(
            "Ruta de la carpeta a respaldar",
            placeholder=r"C:\Users\...\mi_proyecto",
            help="Puede copiar y pegar la ruta de la carpeta."
        )
    with col2:
        formato = st.selectbox("Formato", ["ZIP", "TAR.GZ"])
        tipo = st.selectbox("Tipo de respaldo", ["Completo", "Incremental"])

    config = cargar_config()
    exclusiones = config.get("exclusiones", EXCLUSIONES_DEFAULT)
    st.info(f"Exclusiones activas: {', '.join(exclusiones)}")

    if st.button("Crear Respaldo", type="primary", use_container_width=True):
        ruta_limpia = carpeta_origen.strip().strip('"').strip("'").strip()
        if not ruta_limpia:
            st.error("Debe ingresar una ruta de carpeta.")
        elif not Path(ruta_limpia).is_dir():
            st.error(f"La ruta no es un directorio valido: {ruta_limpia}")
        else:
            carpeta = Path(ruta_limpia)
            nombre_carpeta = carpeta.name
            clave_carpeta = str(carpeta.resolve())
            fmt_ext = "zip" if formato == "ZIP" else "targz"
            tipo_clave = "full" if tipo == "Completo" else "incremental"

            with st.spinner("Escaneando archivos..."):
                archivos = recolectar_archivos(carpeta, exclusiones)

            if tipo_clave == "incremental":
                manifiesto = cargar_manifiesto()
                datos_previos = manifiesto.get(clave_carpeta, {})
                archivos = [
                    (ra, rr, mt) for ra, rr, mt in archivos
                    if datos_previos.get(rr) is None or mt > datos_previos.get(rr, 0)
                ]
                if not archivos:
                    st.warning("No hay archivos nuevos o modificados desde el ultimo respaldo.")
                    st.stop()

            if not archivos:
                st.warning("La carpeta esta vacia o todos los archivos estan excluidos.")
                st.stop()

            RESPALDOS_DIR.mkdir(parents=True, exist_ok=True)
            ahora = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = ".zip" if formato == "ZIP" else ".tar.gz"
            nombre_archivo = f"backup_{nombre_carpeta}_{ahora}_{tipo_clave}{ext}"
            ruta_destino = RESPALDOS_DIR / nombre_archivo

            barra = st.progress(0, text="Creando respaldo...")
            total = len(archivos)
            tamano_total = 0

            if formato == "ZIP":
                with zipfile.ZipFile(ruta_destino, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i, (ruta_abs, ruta_rel, _) in enumerate(archivos, 1):
                        try:
                            tamano_total += ruta_abs.stat().st_size
                            zf.write(ruta_abs, ruta_rel)
                        except OSError:
                            pass
                        barra.progress(i / total, text=f"[{i}/{total}] {ruta_rel}")
            else:
                with tarfile.open(ruta_destino, "w:gz") as tf:
                    for i, (ruta_abs, ruta_rel, _) in enumerate(archivos, 1):
                        try:
                            tamano_total += ruta_abs.stat().st_size
                            tf.add(ruta_abs, arcname=ruta_rel)
                        except OSError:
                            pass
                        barra.progress(i / total, text=f"[{i}/{total}] {ruta_rel}")

            # Actualizar manifiesto
            manifiesto = cargar_manifiesto()
            if clave_carpeta not in manifiesto:
                manifiesto[clave_carpeta] = {}
            for _, ruta_rel, mtime in archivos:
                manifiesto[clave_carpeta][ruta_rel] = mtime
            guardar_manifiesto(manifiesto)

            barra.progress(1.0, text="Completado")
            tamano_respaldo = ruta_destino.stat().st_size
            st.success(f"Respaldo creado: **{nombre_archivo}**")
            c1, c2, c3 = st.columns(3)
            c1.metric("Archivos", total)
            c2.metric("Tamano original", formatear_tamano(tamano_total))
            c3.metric("Tamano respaldo", formatear_tamano(tamano_respaldo))

# --- TAB: Historial ---------------------------------------------
with tab_historial:
    st.subheader("Historial de respaldos")
    if st.button("Actualizar historial", key="refresh_hist"):
        st.rerun()

    respaldos = listar_respaldos()
    if not respaldos:
        st.info("No se encontraron respaldos.")
    else:
        import pandas as pd
        df = pd.DataFrame([{
            "Nombre": r["nombre"],
            "Fecha": r["fecha"],
            "Tipo": r["tipo"],
            "Formato": r["formato"],
            "Archivos": r["n_archivos"] if r["n_archivos"] >= 0 else "???",
            "Tamano": r["tamano_str"],
        } for r in respaldos])
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Descargar respaldo")
        nombres = [r["nombre"] for r in respaldos]
        seleccion = st.selectbox("Seleccione un respaldo para descargar", nombres, key="dl_sel")
        idx = nombres.index(seleccion)
        ruta_dl = respaldos[idx]["ruta"]
        mime = "application/zip" if respaldos[idx]["formato"] == "ZIP" else "application/gzip"
        with open(ruta_dl, "rb") as f:
            st.download_button(
                "Descargar", data=f, file_name=seleccion,
                mime=mime, use_container_width=True,
            )

# --- TAB: Restaurar ---------------------------------------------
with tab_restaurar:
    st.subheader("Restaurar un respaldo")
    respaldos_rest = listar_respaldos()
    if not respaldos_rest:
        st.info("No se encontraron respaldos para restaurar.")
    else:
        nombres_rest = [r["nombre"] for r in respaldos_rest]
        seleccion_rest = st.selectbox("Seleccione el respaldo a restaurar", nombres_rest, key="rest_sel")
        destino_rest = st.text_input(
            "Ruta de destino para la restauracion",
            placeholder=r"C:\Users\...\restaurado",
        )
        if st.button("Restaurar", type="primary", use_container_width=True):
            ruta_limpia_dest = destino_rest.strip().strip('"').strip("'").strip()
            if not ruta_limpia_dest:
                st.error("Debe ingresar una ruta de destino.")
            else:
                idx_rest = nombres_rest.index(seleccion_rest)
                respaldo_sel = respaldos_rest[idx_rest]
                ruta_resp = respaldo_sel["ruta"]
                ruta_dest = Path(ruta_limpia_dest)
                ruta_dest.mkdir(parents=True, exist_ok=True)

                try:
                    with st.spinner("Restaurando archivos..."):
                        if respaldo_sel["formato"] == "ZIP":
                            with zipfile.ZipFile(ruta_resp, "r") as zf:
                                zf.extractall(ruta_dest)
                                total_rest = len(zf.namelist())
                        else:
                            with tarfile.open(ruta_resp, "r:gz") as tf:
                                tf.extractall(ruta_dest, filter='data')
                                total_rest = len(tf.getnames())
                    st.success(f"Restauracion completada: {total_rest} archivos en {ruta_dest}")
                except Exception as e:
                    st.error(f"Error al restaurar: {e}")

# --- TAB: Exclusiones -------------------------------------------
with tab_config:
    st.subheader("Patrones de exclusion")
    config = cargar_config()
    exclusiones_actuales = config.get("exclusiones", list(EXCLUSIONES_DEFAULT))

    st.write("Patrones actuales:")
    for i, patron in enumerate(exclusiones_actuales):
        col_p, col_b = st.columns([4, 1])
        col_p.code(patron)
        if col_b.button("Eliminar", key=f"del_{i}"):
            exclusiones_actuales.pop(i)
            config["exclusiones"] = exclusiones_actuales
            guardar_config(config)
            st.rerun()

    st.divider()
    nuevo_patron = st.text_input("Agregar nuevo patron", placeholder="Ej: *.log, .idea, dist")
    c1, c2 = st.columns(2)
    if c1.button("Agregar patron", use_container_width=True):
        if nuevo_patron.strip():
            if nuevo_patron.strip() not in exclusiones_actuales:
                exclusiones_actuales.append(nuevo_patron.strip())
                config["exclusiones"] = exclusiones_actuales
                guardar_config(config)
                st.success(f"Patron '{nuevo_patron.strip()}' agregado.")
                st.rerun()
            else:
                st.warning("El patron ya existe.")
        else:
            st.warning("Ingrese un patron valido.")

    if c2.button("Restaurar por defecto", use_container_width=True):
        config["exclusiones"] = list(EXCLUSIONES_DEFAULT)
        guardar_config(config)
        st.success("Exclusiones restauradas a valores por defecto.")
        st.rerun()
'''

    st_script.write_text(contenido_st, encoding="utf-8")
    print(f"\n    [*] Iniciando interfaz web...")
    print(f"    [*] Se abrira en su navegador predeterminado.")
    print(f"    [*] Cierre la ventana del navegador y presione Ctrl+C para detener.\n")
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(st_script)])
    except KeyboardInterrupt:
        pass


# ===================================================================
#  Menu principal
# ===================================================================

def menu_principal():
    while True:
        limpiar_pantalla()
        mostrar_banner()
        print("    1. Crear respaldo completo (.zip)")
        print("    2. Crear respaldo completo (.tar.gz)")
        print("    3. Crear respaldo incremental (.zip)")
        print("    4. Crear respaldo incremental (.tar.gz)")
        print("    5. Ver historial de respaldos")
        print("    6. Verificar integridad de un respaldo")
        print("    7. Restaurar un respaldo")
        print("    8. Configurar exclusiones")
        print("    9. Rotacion de respaldos")
        print("   10. Interfaz interactiva (Web)")
        print("    0. Salir")
        print()

        opcion = input("    Seleccione una opcion: ").strip()

        if opcion == "1":
            ejecutar_respaldo("zip", "full")
        elif opcion == "2":
            ejecutar_respaldo("targz", "full")
        elif opcion == "3":
            ejecutar_respaldo("zip", "incremental")
        elif opcion == "4":
            ejecutar_respaldo("targz", "incremental")
        elif opcion == "5":
            ver_historial()
        elif opcion == "6":
            verificar_integridad()
        elif opcion == "7":
            restaurar_respaldo()
        elif opcion == "8":
            configurar_exclusiones()
        elif opcion == "9":
            rotacion_respaldos()
        elif opcion == "10":
            iniciar_streamlit()
        elif opcion == "0":
            limpiar_pantalla()
            print("\n    [*] Hasta luego!\n")
            sys.exit(0)
        else:
            print("    [!] Opcion no valida.")
            pausar()


if __name__ == "__main__":
    menu_principal()
