#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instalador interactivo de dependencias para el repositorio Programas_utiles.
Lee el archivo 'requirements.txt' y permite al usuario instalar todas las dependencias
o seleccionar un programa específico para instalar únicamente lo necesario.
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

NOMBRE_ARCHIVO_REQ = "requirements.txt"


class ProgramaDependencias:
    def __init__(self, nombre: str, archivo: str = "", dependencias: List[str] = None, solo_estandar: bool = False):
        self.nombre = nombre
        self.archivo = archivo
        self.dependencias = dependencias or []
        self.solo_estandar = solo_estandar

    def __repr__(self):
        return f"<Programa {self.nombre} (deps={len(self.dependencias)})>"


def obtener_ruta_requirements() -> Path:
    """Busca el archivo requirements.txt en el directorio actual o junto al script."""
    script_dir = Path(__file__).resolve().parent
    candidatos = [
        script_dir / NOMBRE_ARCHIVO_REQ,
        Path.cwd() / NOMBRE_ARCHIVO_REQ,
        script_dir / "dependencias.txt",
        Path.cwd() / "dependencias.txt"
    ]
    for ruta in candidatos:
        if ruta.is_file():
            return ruta
    return script_dir / NOMBRE_ARCHIVO_REQ


def parsear_requirements(ruta_txt: Path) -> Tuple[List[ProgramaDependencias], List[str]]:
    """
    Parsea el archivo requirements.txt extrayendo las secciones por programa
    y la lista consolidada de todas las dependencias únicas.
    """
    if not ruta_txt.is_file():
        print(f"[!] Error: No se encontro el archivo de dependencias en:\n    {ruta_txt}")
        sys.exit(1)

    programas: List[ProgramaDependencias] = []
    prog_actual: ProgramaDependencias = None
    todas_las_dependencias: List[str] = []
    vistas = set()

    with open(ruta_txt, "r", encoding="utf-8") as f:
        lineas = f.readlines()

    patron_header = re.compile(r"^#\s*\[PROGRAMA:\s*(.+?)\]", re.IGNORECASE)
    patron_archivo = re.compile(r"^#\s*Archivo:\s*(.+)", re.IGNORECASE)
    patron_estandar = re.compile(r"^#\s*-\s*\[PROGRAMA:\s*(.+?)\]\s*->\s*(.+)", re.IGNORECASE)

    for linea in lineas:
        linea_strip = linea.strip()

        # Detección de programas sin dependencias externas (biblioteca estándar)
        match_std = patron_estandar.match(linea_strip)
        if match_std:
            if prog_actual is not None:
                programas.append(prog_actual)
                prog_actual = None
            nom = match_std.group(1).strip()
            arch = match_std.group(2).strip()
            programas.append(ProgramaDependencias(nombre=nom, archivo=arch, dependencias=[], solo_estandar=True))
            continue

        # Detección de cabecera de programa con dependencias
        match_head = patron_header.match(linea_strip)
        if match_head:
            if prog_actual is not None:
                programas.append(prog_actual)
            nombre_prog = match_head.group(1).strip()
            prog_actual = ProgramaDependencias(nombre=nombre_prog, dependencias=[])
            continue

        # Detección de ruta del archivo del programa
        if prog_actual is not None:
            match_arc = patron_archivo.match(linea_strip)
            if match_arc:
                prog_actual.archivo = match_arc.group(1).strip()
                continue

            # Si es un paquete pip (no comentario, no vacío)
            if linea_strip and not linea_strip.startswith("#"):
                paquete = linea_strip
                prog_actual.dependencias.append(paquete)
                nombre_base = re.split(r"[><=~!;]", paquete)[0].strip().lower()
                if nombre_base not in vistas:
                    vistas.add(nombre_base)
                    todas_las_dependencias.append(paquete)

    if prog_actual is not None:
        programas.append(prog_actual)

    return programas, todas_las_dependencias


def limpiar_consola():
    """Limpia la terminal según el sistema operativo."""
    os.system("cls" if os.name == "nt" else "clear")


def instalar_paquetes(lista_paquetes: List[str], descripcion: str) -> bool:
    """Ejecuta pip install con el intérprete actual de Python."""
    if not lista_paquetes:
        print("\n[i] No hay dependencias externas para instalar.")
        return True

    print("\n" + "=" * 70)
    print(f"[*] INSTALANDO DEPENDENCIAS PARA: {descripcion}")
    print("=" * 70)
    print("  Interprete de Python activo :", sys.executable)
    print("  Paquetes a instalar         :", ", ".join(lista_paquetes))
    print("=" * 70)
    print("Iniciando pip...\n")

    comando = [sys.executable, "-m", "pip", "install", *lista_paquetes]

    try:
        resultado = subprocess.run(comando, check=False)
        print("\n" + "-" * 70)
        if resultado.returncode == 0:
            print("[+] Instalacion finalizada con EXITO.")
            return True
        else:
            print(f"[-] pip finalizo con codigo de error: {resultado.returncode}")
            return False
    except Exception as e:
        print(f"[!] Ocurrio un error al ejecutar pip: {e}")
        return False


def mostrar_menu(programas: List[ProgramaDependencias], total_global: int):
    """Imprime el menú de opciones en consola."""
    print("=" * 74)
    print("         GESTOR DE INSTALACION DE DEPENDENCIAS (PYTHON)           ")
    print("=" * 74)
    print("  Seleccione el programa para el cual desea instalar sus dependencias:")
    print("=" * 74)
    print(f"  [ 1] TODAS las dependencias de todos los programas ({total_global} paquetes)")
    print("  " + "-" * 70)

    for idx, prog in enumerate(programas, start=2):
        if prog.solo_estandar:
            print(f"  [{idx:2d}] {prog.nombre:<45} [Libreria estandar]")
        else:
            deps_str = ", ".join(prog.dependencias)
            print(f"  [{idx:2d}] {prog.nombre:<45} ({deps_str})")

    print("  " + "-" * 70)
    print("  [ 0] Salir")
    print("=" * 74)


def main():
    ruta_txt = obtener_ruta_requirements()
    programas, todas_las_deps = parsear_requirements(ruta_txt)

    while True:
        limpiar_consola()
        mostrar_menu(programas, len(todas_las_deps))
        opcion = input("\nIngrese el numero de su opcion: ").strip()

        if opcion == "0":
            print("\nSaliendo del instalador.")
            sys.exit(0)

        elif opcion == "1":
            print(f"\nSe instalaran las {len(todas_las_deps)} dependencias del proyecto:")
            for d in todas_las_deps:
                print(f"  * {d}")
            confirmar = input("\nProceder con la instalacion global? (s/N): ").strip().lower()
            if confirmar in ("s", "si", "y", "yes"):
                instalar_paquetes(todas_las_deps, "TODOS LOS PROGRAMAS (Global)")
            else:
                print("Operacion cancelada.")
            input("\nPresione Enter para volver al menu...")

        else:
            try:
                num = int(opcion)
                indice = num - 2
                if 0 <= indice < len(programas):
                    prog = programas[indice]
                    if prog.solo_estandar:
                        print("\n" + "=" * 70)
                        print(f"[*] Programa: {prog.nombre}")
                        print(f"    Archivo : {prog.archivo}")
                        print("    Detalle : Este programa SOLO utiliza modulos de la biblioteca")
                        print("              estandar de Python (os, sys, socket, hashlib, etc.).")
                        print("              No requiere instalar paquetes externos.")
                        print("=" * 70)
                    else:
                        print(f"\nSe instalaran las dependencias de '{prog.nombre}':")
                        for d in prog.dependencias:
                            print(f"  * {d}")
                        confirmar = input("\nProceder con la instalacion? (s/N): ").strip().lower()
                        if confirmar in ("s", "si", "y", "yes"):
                            instalar_paquetes(prog.dependencias, prog.nombre)
                        else:
                            print("Operacion cancelada.")
                    input("\nPresione Enter para volver al menu...")
                else:
                    print("\n[!] Opcion no valida. Seleccione un numero de la lista.")
                    input("Presione Enter para continuar...")
            except ValueError:
                print("\n[!] Entrada invalida. Ingrese un numero.")
                input("Presione Enter para continuar...")


if __name__ == "__main__":
    main()
