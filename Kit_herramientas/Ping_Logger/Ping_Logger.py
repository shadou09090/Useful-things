#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ping Logger - Monitor de latencia y perdida de paquetes de red.
Registra resultados de ping a archivos CSV con marcas de tiempo.
"""

import os
import sys
import csv
import re
import socket
import time
import subprocess
import statistics
import platform
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# ==============================================================================
# Constantes y rutas
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
REGISTROS_DIR = BASE_DIR / "registros"
HOSTS_ENTRADA_DIR = BASE_DIR / "hosts_entrada"
SISTEMA = platform.system().lower()
SEPARADOR = "=" * 60


# ==============================================================================
# Funciones auxiliares
# ==============================================================================
def limpiar_pantalla():
    """Limpia la pantalla de la terminal."""
    os.system("cls" if os.name == "nt" else "clear")


def pausa():
    """Pausa hasta que el usuario presione Enter."""
    input("\n[*] Presiona Enter para continuar...")


def mostrar_encabezado(titulo: str):
    """Muestra un encabezado formateado."""
    limpiar_pantalla()
    print(SEPARADOR)
    print(f"  PING LOGGER - {titulo}")
    print(SEPARADOR)
    print()


def crear_directorios():
    """Crea los directorios necesarios (lectura y generacion)."""
    REGISTROS_DIR.mkdir(parents=True, exist_ok=True)
    HOSTS_ENTRADA_DIR.mkdir(parents=True, exist_ok=True)
    archivo_hosts = HOSTS_ENTRADA_DIR / "hosts.txt"
    if not archivo_hosts.exists():
        archivo_hosts.write_text("8.8.8.8\n1.1.1.1\ngoogle.com\ngithub.com\n", encoding="utf-8")


def obtener_gateway_local() -> str:
    """Intenta obtener la IP del gateway local."""
    try:
        if SISTEMA == "windows":
            resultado = subprocess.run(
                ["ipconfig"], capture_output=True, text=True, timeout=10
            )
            # Buscar "Puerta de enlace predeterminada" o "Default Gateway"
            patron = re.search(
                r"(?:Puerta de enlace predeterminada|Default Gateway)[.\s:]+(\d+\.\d+\.\d+\.\d+)",
                resultado.stdout,
            )
            if patron:
                return patron.group(1)
        else:
            resultado = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, timeout=10,
            )
            patron = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", resultado.stdout)
            if patron:
                return patron.group(1)
    except Exception:
        pass
    return "192.168.1.1"


# ==============================================================================
# Funciones de Ping y Parseo
# ==============================================================================
def ejecutar_ping(host: str) -> dict:
    """
    Ejecuta un ping al host y devuelve un diccionario con los resultados.
    Retorna: {timestamp, host, latency_ms, packet_loss, status}
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resultado = {
        "timestamp": timestamp,
        "host": host,
        "latency_ms": None,
        "packet_loss": 1,
        "status": "ERROR",
    }

    try:
        if SISTEMA == "windows":
            cmd = ["ping", "-n", "1", "-w", "1000", host]
        else:
            cmd = ["ping", "-c", "1", "-W", "1", host]

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5
        )
        salida = proc.stdout + proc.stderr

        # Parsear latencia
        # Windows: tiempo=XXms, time=XXms, tiempo<1ms
        # Linux/Mac: time=XX.X ms
        patron = re.search(
            r"(?:tiempo|time)[=<]\s*(\d+(?:\.\d+)?)\s*ms", salida, re.IGNORECASE
        )

        if patron:
            resultado["latency_ms"] = round(float(patron.group(1)), 2)
            resultado["packet_loss"] = 0
            resultado["status"] = "OK"
        elif proc.returncode == 0:
            # Ping exitoso pero no pudimos parsear latencia
            resultado["latency_ms"] = 0.0
            resultado["packet_loss"] = 0
            resultado["status"] = "OK"
        else:
            resultado["status"] = "TIMEOUT"

    except subprocess.TimeoutExpired:
        resultado["status"] = "TIMEOUT"
    except FileNotFoundError:
        resultado["status"] = "ERROR"
    except Exception:
        resultado["status"] = "ERROR"

    return resultado


def generar_nombre_csv(host: str) -> str:
    """Genera un nombre de archivo CSV basado en el host y la fecha/hora."""
    host_limpio = re.sub(r"[^a-zA-Z0-9_.-]", "_", host)
    ahora = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"ping_{host_limpio}_{ahora}.csv"


def escribir_cabecera_csv(ruta_csv: Path):
    """Escribe la cabecera del archivo CSV."""
    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "host", "latency_ms", "packet_loss", "status"])


def escribir_fila_csv(ruta_csv: Path, resultado: dict):
    """Escribe una fila de resultado en el archivo CSV."""
    with open(ruta_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            resultado["timestamp"],
            resultado["host"],
            resultado["latency_ms"] if resultado["latency_ms"] is not None else "",
            resultado["packet_loss"],
            resultado["status"],
        ])


def leer_csv(ruta_csv: Path) -> list:
    """Lee un archivo CSV y retorna una lista de diccionarios."""
    registros = []
    with open(ruta_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            registros.append(fila)
    return registros


def calcular_estadisticas(registros: list) -> dict:
    """Calcula estadisticas de una lista de registros de ping."""
    if not registros:
        return {}

    total = len(registros)
    perdidos = sum(1 for r in registros if r["packet_loss"] == "1" or r["packet_loss"] == 1)
    exitosos = total - perdidos

    latencias = []
    for r in registros:
        lat = r.get("latency_ms", "")
        if lat and lat != "" and lat != "None":
            try:
                latencias.append(float(lat))
            except ValueError:
                pass

    stats = {
        "total_pings": total,
        "paquetes_perdidos": perdidos,
        "paquetes_exitosos": exitosos,
        "porcentaje_perdida": round((perdidos / total) * 100, 2) if total > 0 else 0,
        "porcentaje_disponibilidad": round((exitosos / total) * 100, 2) if total > 0 else 0,
    }

    if latencias:
        latencias_ordenadas = sorted(latencias)
        indice_p95 = int(len(latencias_ordenadas) * 0.95)
        if indice_p95 >= len(latencias_ordenadas):
            indice_p95 = len(latencias_ordenadas) - 1

        stats["latencia_promedio"] = round(statistics.mean(latencias), 2)
        stats["latencia_min"] = round(min(latencias), 2)
        stats["latencia_max"] = round(max(latencias), 2)
        stats["latencia_p95"] = round(latencias_ordenadas[indice_p95], 2)
        if len(latencias) > 1:
            stats["desviacion_estandar"] = round(statistics.stdev(latencias), 2)
        else:
            stats["desviacion_estandar"] = 0.0
    else:
        stats["latencia_promedio"] = None
        stats["latencia_min"] = None
        stats["latencia_max"] = None
        stats["latencia_p95"] = None
        stats["desviacion_estandar"] = None

    # Calcular ventana de caida mas larga
    max_caida = 0
    caida_actual = 0
    for r in registros:
        if r["packet_loss"] == "1" or r["packet_loss"] == 1:
            caida_actual += 1
            if caida_actual > max_caida:
                max_caida = caida_actual
        else:
            caida_actual = 0
    stats["mayor_ventana_caida"] = max_caida

    return stats


# ==============================================================================
# Opcion 1: Monitoreo continuo de un solo host
# ==============================================================================
def monitoreo_continuo():
    """Monitorea continuamente un host, registrando cada ping a CSV."""
    mostrar_encabezado("Monitoreo continuo")

    host = input("[+] Ingresa el host o IP a monitorear: ").strip()
    if not host:
        print("[-] Debes ingresar un host valido.")
        pausa()
        return

    try:
        intervalo = int(input("[+] Intervalo entre pings en segundos (por defecto 2): ").strip() or "2")
        if intervalo < 1:
            intervalo = 1
    except ValueError:
        intervalo = 2

    crear_directorios()
    nombre_csv = generar_nombre_csv(host)
    ruta_csv = REGISTROS_DIR / nombre_csv
    escribir_cabecera_csv(ruta_csv)

    print(f"\n[*] Iniciando monitoreo de: {host}")
    print(f"[*] Intervalo: {intervalo} segundo(s)")
    print(f"[*] Registro CSV: {ruta_csv.name}")
    print("[*] Presiona Ctrl+C para detener\n")
    print(f"{'No.':<6} {'Hora':<20} {'Latencia':<12} {'Estado':<10} {'Perdida%':<10} {'Prom.':<10}")
    print("-" * 68)

    pings_total = 0
    pings_perdidos = 0
    latencias = []

    try:
        while True:
            resultado = ejecutar_ping(host)
            escribir_fila_csv(ruta_csv, resultado)

            pings_total += 1
            if resultado["packet_loss"] == 1:
                pings_perdidos += 1
            if resultado["latency_ms"] is not None:
                latencias.append(resultado["latency_ms"])

            porc_perdida = round((pings_perdidos / pings_total) * 100, 2)
            promedio = round(statistics.mean(latencias), 2) if latencias else "-"
            lat_str = f"{resultado['latency_ms']} ms" if resultado["latency_ms"] is not None else "---"
            hora_corta = resultado["timestamp"].split(" ")[1]

            print(
                f"{pings_total:<6} {hora_corta:<20} {lat_str:<12} "
                f"{resultado['status']:<10} {porc_perdida:<10} {promedio:<10}"
            )

            time.sleep(intervalo)

    except KeyboardInterrupt:
        print(f"\n\n[OK] Monitoreo detenido.")
        print(f"[*] Total pings: {pings_total}")
        print(f"[*] Paquetes perdidos: {pings_perdidos}")
        if latencias:
            print(f"[*] Latencia promedio: {round(statistics.mean(latencias), 2)} ms")
        print(f"[*] Registro guardado en: {ruta_csv}")
        pausa()


# ==============================================================================
# Opcion 2: Prueba rapida de conectividad
# ==============================================================================
def prueba_rapida():
    """Realiza una prueba rapida de conectividad a varios hosts."""
    mostrar_encabezado("Prueba rapida de conectividad")

    gateway = obtener_gateway_local()
    host_custom = input("[+] Ingresa un host adicional para probar (o Enter para omitir): ").strip()

    hosts = ["8.8.8.8", "1.1.1.1", gateway]
    nombres = ["Google DNS", "Cloudflare DNS", f"Gateway Local ({gateway})"]

    if host_custom:
        hosts.append(host_custom)
        nombres.append(f"Personalizado ({host_custom})")

    num_pings = 5
    print(f"\n[*] Realizando {num_pings} pings a cada host...\n")

    for host, nombre in zip(hosts, nombres):
        print(f"  {nombre}")
        print(f"  {'~' * 40}")

        latencias_host = []
        perdidos = 0

        for i in range(num_pings):
            resultado = ejecutar_ping(host)
            if resultado["packet_loss"] == 1:
                perdidos += 1
                print(f"    Ping {i + 1}: TIMEOUT / ERROR")
            else:
                lat = resultado["latency_ms"]
                latencias_host.append(lat)
                print(f"    Ping {i + 1}: {lat} ms")
            time.sleep(0.3)

        # Resumen
        porc = round((perdidos / num_pings) * 100, 1)
        if latencias_host:
            prom = round(statistics.mean(latencias_host), 2)
            print(f"    --- Promedio: {prom} ms | Perdida: {porc}%")
        else:
            print(f"    --- Sin respuesta | Perdida: {porc}%")
        print()

    pausa()


# ==============================================================================
# Opcion 3: Monitorear multiples hosts simultaneamente
# ==============================================================================
def monitoreo_multiple():
    """Monitorea multiples hosts simultaneamente usando hilos."""
    mostrar_encabezado("Monitoreo de multiples hosts")

    archivo_hosts = HOSTS_ENTRADA_DIR / "hosts.txt"
    print("  Selecciona la fuente de hosts:")
    print(f"  [1] Cargar desde archivo de lectura: hosts_entrada/hosts.txt")
    print(f"  [2] Escribir hosts manualmente separados por comas")
    sel = input("\n[+] Selecciona opcion (1/2) [Por defecto 1]: ").strip()

    if sel in ("", "1"):
        if not archivo_hosts.exists():
            crear_directorios()
        lineas = archivo_hosts.read_text(encoding="utf-8").splitlines()
        hosts = [l.strip() for l in lineas if l.strip() and not l.strip().startswith("#")]
        if not hosts:
            print("[-] El archivo hosts.txt esta vacio.")
            pausa()
            return
        print(f"\n[OK] Cargados {len(hosts)} host(s) desde {archivo_hosts.name}: {', '.join(hosts)}")
    else:
        entrada = input("[+] Ingresa los hosts separados por comas: ").strip()
        if not entrada:
            print("[-] Debes ingresar al menos un host.")
            pausa()
            return

        hosts = [h.strip() for h in entrada.split(",") if h.strip()]
        if not hosts:
            print("[-] No se detectaron hosts validos.")
            pausa()
            return

    try:
        intervalo = int(input("[+] Intervalo entre pings en segundos (por defecto 2): ").strip() or "2")
        if intervalo < 1:
            intervalo = 1
    except ValueError:
        intervalo = 2

    crear_directorios()

    # Crear CSVs para cada host
    archivos_csv = {}
    for host in hosts:
        nombre = generar_nombre_csv(host)
        ruta = REGISTROS_DIR / nombre
        escribir_cabecera_csv(ruta)
        archivos_csv[host] = ruta

    print(f"\n[*] Monitoreando {len(hosts)} host(s) cada {intervalo} segundo(s)")
    print("[*] Presiona Ctrl+C para detener\n")

    contadores = {host: {"total": 0, "perdidos": 0, "latencias": []} for host in hosts}

    try:
        while True:
            with ThreadPoolExecutor(max_workers=len(hosts)) as executor:
                futuros = {executor.submit(ejecutar_ping, host): host for host in hosts}
                resultados = {}
                for futuro in as_completed(futuros):
                    host = futuros[futuro]
                    try:
                        resultados[host] = futuro.result()
                    except Exception:
                        resultados[host] = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "host": host, "latency_ms": None,
                            "packet_loss": 1, "status": "ERROR",
                        }

            # Mostrar y registrar
            limpiar_pantalla()
            print(SEPARADOR)
            print("  MONITOREO MULTIPLE EN TIEMPO REAL")
            print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(SEPARADOR)
            print()
            print(f"  {'Host':<30} {'Latencia':<12} {'Estado':<10} {'Perdida%':<10} {'Prom.':<10}")
            print(f"  {'-' * 72}")

            for host in hosts:
                res = resultados.get(host, {})
                c = contadores[host]
                c["total"] += 1
                if res.get("packet_loss", 1) == 1:
                    c["perdidos"] += 1
                if res.get("latency_ms") is not None:
                    c["latencias"].append(res["latency_ms"])

                escribir_fila_csv(archivos_csv[host], res)

                porc = round((c["perdidos"] / c["total"]) * 100, 1) if c["total"] > 0 else 0
                prom = round(statistics.mean(c["latencias"]), 2) if c["latencias"] else "-"
                lat_str = f"{res.get('latency_ms', '-')} ms" if res.get("latency_ms") is not None else "---"
                estado = res.get("status", "ERROR")

                print(f"  {host:<30} {lat_str:<12} {estado:<10} {porc:<10} {prom:<10}")

            print(f"\n  [*] Total pings por host: {contadores[hosts[0]]['total']}")
            print("  [*] Ctrl+C para detener")

            time.sleep(intervalo)

    except KeyboardInterrupt:
        print(f"\n\n[OK] Monitoreo detenido.")
        for host in hosts:
            print(f"  [*] {host} -> {archivos_csv[host].name}")
        pausa()


# ==============================================================================
# Opcion 4: Deteccion de microcortes
# ==============================================================================
def deteccion_microcortes():
    """Detecta microcortes: solo registra cuando hay perdida o latencia alta."""
    mostrar_encabezado("Deteccion de microcortes")

    host = input("[+] Ingresa el host o IP a monitorear: ").strip()
    if not host:
        print("[-] Debes ingresar un host valido.")
        pausa()
        return

    try:
        umbral = float(input("[+] Umbral de latencia en ms para alerta (por defecto 100): ").strip() or "100")
    except ValueError:
        umbral = 100.0

    crear_directorios()
    nombre_csv = generar_nombre_csv(host)
    ruta_csv = REGISTROS_DIR / nombre_csv
    escribir_cabecera_csv(ruta_csv)

    print(f"\n[*] Monitoreando microcortes en: {host}")
    print(f"[*] Umbral de latencia: {umbral} ms")
    print(f"[*] Intervalo: 1 segundo")
    print(f"[*] Registro: {ruta_csv.name}")
    print("[*] Solo se mostraran alertas cuando haya problemas")
    print("[*] Presiona Ctrl+C para detener\n")

    pings_total = 0
    eventos = 0

    try:
        while True:
            resultado = ejecutar_ping(host)
            pings_total += 1

            es_alerta = False
            motivo = ""

            if resultado["packet_loss"] == 1:
                es_alerta = True
                motivo = "PERDIDA DE PAQUETE"
            elif resultado["latency_ms"] is not None and resultado["latency_ms"] > umbral:
                es_alerta = True
                motivo = f"LATENCIA ALTA ({resultado['latency_ms']} ms > {umbral} ms)"

            if es_alerta:
                eventos += 1
                escribir_fila_csv(ruta_csv, resultado)
                hora = resultado["timestamp"].split(" ")[1]
                print(f"  [!] {hora} | {motivo} | Eventos: {eventos} / {pings_total} pings")
            else:
                # Mostrar estado cada 30 pings para confirmar que sigue activo
                if pings_total % 30 == 0:
                    print(f"  [OK] {pings_total} pings sin problemas... ({datetime.now().strftime('%H:%M:%S')})")

            time.sleep(1)

    except KeyboardInterrupt:
        print(f"\n\n[OK] Deteccion detenida.")
        print(f"[*] Total pings: {pings_total}")
        print(f"[*] Eventos detectados: {eventos}")
        if pings_total > 0:
            print(f"[*] Tasa de eventos: {round((eventos / pings_total) * 100, 2)}%")
        print(f"[*] Registro: {ruta_csv}")
        pausa()


# ==============================================================================
# Opcion 5: Ver estadisticas de un registro CSV
# ==============================================================================
def ver_estadisticas():
    """Carga un CSV existente y muestra estadisticas detalladas."""
    mostrar_encabezado("Estadisticas de registro CSV")

    crear_directorios()
    archivos = sorted(REGISTROS_DIR.glob("ping_*.csv"))

    if not archivos:
        print("[-] No se encontraron archivos CSV en la carpeta registros/")
        pausa()
        return

    print("[*] Archivos disponibles:\n")
    for i, archivo in enumerate(archivos, 1):
        tamano = archivo.stat().st_size
        tamano_str = f"{tamano / 1024:.1f} KB" if tamano > 1024 else f"{tamano} B"
        print(f"  {i}. {archivo.name}  ({tamano_str})")

    print()
    try:
        seleccion = int(input("[+] Selecciona un archivo (numero): ").strip())
        if seleccion < 1 or seleccion > len(archivos):
            print("[-] Seleccion fuera de rango.")
            pausa()
            return
    except ValueError:
        print("[-] Entrada invalida.")
        pausa()
        return

    ruta = archivos[seleccion - 1]
    registros = leer_csv(ruta)

    if not registros:
        print("[-] El archivo esta vacio o no tiene datos.")
        pausa()
        return

    stats = calcular_estadisticas(registros)

    print(f"\n{SEPARADOR}")
    print(f"  ESTADISTICAS: {ruta.name}")
    print(SEPARADOR)
    print()
    print(f"  Total de pings:            {stats['total_pings']}")
    print(f"  Paquetes perdidos:         {stats['paquetes_perdidos']}")
    print(f"  Paquetes exitosos:         {stats['paquetes_exitosos']}")
    print(f"  Porcentaje de perdida:     {stats['porcentaje_perdida']}%")
    print(f"  Disponibilidad (uptime):   {stats['porcentaje_disponibilidad']}%")
    print()

    if stats["latencia_promedio"] is not None:
        print(f"  Latencia promedio:         {stats['latencia_promedio']} ms")
        print(f"  Latencia minima:           {stats['latencia_min']} ms")
        print(f"  Latencia maxima:           {stats['latencia_max']} ms")
        print(f"  Latencia P95:              {stats['latencia_p95']} ms")
        print(f"  Desviacion estandar:       {stats['desviacion_estandar']} ms")
    else:
        print("  [!] No hay datos de latencia disponibles.")

    print(f"\n  Mayor ventana de caida:    {stats['mayor_ventana_caida']} pings consecutivos")

    # Rango de tiempo
    if registros:
        primer_ts = registros[0].get("timestamp", "")
        ultimo_ts = registros[-1].get("timestamp", "")
        print(f"\n  Primer registro:           {primer_ts}")
        print(f"  Ultimo registro:           {ultimo_ts}")

    pausa()


# ==============================================================================
# Opcion 6: Generar reporte de disponibilidad
# ==============================================================================
def generar_reporte():
    """Analiza un CSV y genera un reporte de texto con desglose por hora."""
    mostrar_encabezado("Reporte de disponibilidad")

    crear_directorios()
    archivos = sorted(REGISTROS_DIR.glob("ping_*.csv"))

    if not archivos:
        print("[-] No se encontraron archivos CSV en la carpeta registros/")
        pausa()
        return

    print("[*] Archivos disponibles:\n")
    for i, archivo in enumerate(archivos, 1):
        print(f"  {i}. {archivo.name}")

    print()
    try:
        seleccion = int(input("[+] Selecciona un archivo (numero): ").strip())
        if seleccion < 1 or seleccion > len(archivos):
            print("[-] Seleccion fuera de rango.")
            pausa()
            return
    except ValueError:
        print("[-] Entrada invalida.")
        pausa()
        return

    ruta = archivos[seleccion - 1]
    registros = leer_csv(ruta)

    if not registros:
        print("[-] El archivo esta vacio.")
        pausa()
        return

    stats = calcular_estadisticas(registros)

    # Agrupar por hora
    por_hora = defaultdict(list)
    for r in registros:
        ts = r.get("timestamp", "")
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            clave_hora = dt.strftime("%Y-%m-%d %H:00")
            por_hora[clave_hora].append(r)
        except ValueError:
            pass

    # Generar reporte
    lineas = []
    lineas.append("=" * 60)
    lineas.append("  REPORTE DE DISPONIBILIDAD DE RED")
    lineas.append("=" * 60)
    lineas.append(f"  Archivo: {ruta.name}")
    lineas.append(f"  Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lineas.append("")
    lineas.append("-" * 60)
    lineas.append("  RESUMEN GENERAL")
    lineas.append("-" * 60)
    lineas.append(f"  Total de pings:            {stats['total_pings']}")
    lineas.append(f"  Paquetes perdidos:         {stats['paquetes_perdidos']}")
    lineas.append(f"  Disponibilidad:            {stats['porcentaje_disponibilidad']}%")
    lineas.append(f"  Perdida de paquetes:       {stats['porcentaje_perdida']}%")

    if stats["latencia_promedio"] is not None:
        lineas.append(f"  Latencia promedio:         {stats['latencia_promedio']} ms")
        lineas.append(f"  Latencia minima:           {stats['latencia_min']} ms")
        lineas.append(f"  Latencia maxima:           {stats['latencia_max']} ms")
        lineas.append(f"  Latencia P95:              {stats['latencia_p95']} ms")

    lineas.append(f"  Mayor ventana de caida:    {stats['mayor_ventana_caida']} pings")
    lineas.append("")
    lineas.append("-" * 60)
    lineas.append("  DESGLOSE POR HORA")
    lineas.append("-" * 60)
    lineas.append(f"  {'Hora':<20} {'Pings':<8} {'Perd.':<8} {'Disp.%':<10} {'Lat.Prom':<10}")
    lineas.append(f"  {'-' * 56}")

    for hora in sorted(por_hora.keys()):
        regs = por_hora[hora]
        total_h = len(regs)
        perdidos_h = sum(1 for r in regs if r["packet_loss"] == "1" or r["packet_loss"] == 1)
        disp_h = round(((total_h - perdidos_h) / total_h) * 100, 1) if total_h > 0 else 0

        lats_h = []
        for r in regs:
            lat = r.get("latency_ms", "")
            if lat and lat != "" and lat != "None":
                try:
                    lats_h.append(float(lat))
                except ValueError:
                    pass
        prom_h = round(statistics.mean(lats_h), 1) if lats_h else "-"

        lineas.append(f"  {hora:<20} {total_h:<8} {perdidos_h:<8} {disp_h:<10} {prom_h:<10}")

    lineas.append("")
    lineas.append("=" * 60)
    lineas.append("  FIN DEL REPORTE")
    lineas.append("=" * 60)

    reporte_texto = "\n".join(lineas)

    # Guardar reporte
    nombre_reporte = f"reporte_{ruta.stem}.txt"
    ruta_reporte = REGISTROS_DIR / nombre_reporte
    with open(ruta_reporte, "w", encoding="utf-8") as f:
        f.write(reporte_texto)

    print(f"\n{reporte_texto}")
    print(f"\n[OK] Reporte guardado en: {ruta_reporte}")
    pausa()


# ==============================================================================
# Opcion 7: Traceroute
# ==============================================================================
def traceroute():
    """Ejecuta traceroute/tracert hacia un host y muestra los resultados."""
    mostrar_encabezado("Traceroute")

    host = input("[+] Ingresa el host o IP: ").strip()
    if not host:
        print("[-] Debes ingresar un host valido.")
        pausa()
        return

    if SISTEMA == "windows":
        cmd = ["tracert", "-d", host]
    else:
        cmd = ["traceroute", host]

    print(f"\n[*] Ejecutando traceroute hacia {host}...")
    print("[*] Esto puede tomar un momento...\n")

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        print(proc.stdout)
        if proc.stderr:
            print(proc.stderr)
    except subprocess.TimeoutExpired:
        print("[-] El comando excedio el tiempo limite (120s).")
    except FileNotFoundError:
        print("[-] Comando de traceroute no encontrado en el sistema.")
    except Exception as e:
        print(f"[-] Error: {e}")

    pausa()


# ==============================================================================
# Opcion 8: Resolucion DNS
# ==============================================================================
def resolver_dns():
    """Resuelve un dominio y muestra todas las IPs, midiendo el tiempo."""
    mostrar_encabezado("Resolucion DNS")

    dominio = input("[+] Ingresa el dominio a resolver: ").strip()
    if not dominio:
        print("[-] Debes ingresar un dominio.")
        pausa()
        return

    print(f"\n[*] Resolviendo: {dominio}\n")

    try:
        inicio = time.perf_counter()
        resultados = socket.getaddrinfo(dominio, None)
        fin = time.perf_counter()
        tiempo_ms = round((fin - inicio) * 1000, 2)

        # Extraer IPs unicas con familia
        ips_vistas = set()
        ips_info = []
        for res in resultados:
            familia, tipo, proto, canon, direccion = res
            ip = direccion[0]
            if ip not in ips_vistas:
                ips_vistas.add(ip)
                familia_str = "IPv4" if familia == socket.AF_INET else "IPv6" if familia == socket.AF_INET6 else "Otro"
                ips_info.append((ip, familia_str))

        print(f"  Dominio:              {dominio}")
        print(f"  Tiempo de resolucion: {tiempo_ms} ms")
        print(f"  Direcciones encontradas: {len(ips_info)}")
        print()

        for ip, familia in ips_info:
            print(f"    [{familia}] {ip}")

        # Intentar resolucion inversa
        print(f"\n  Resolucion inversa:")
        for ip, familia in ips_info:
            try:
                hostname, _, _ = socket.gethostbyaddr(ip)
                print(f"    {ip} -> {hostname}")
            except socket.herror:
                print(f"    {ip} -> (sin registro inverso)")
            except Exception:
                print(f"    {ip} -> (error en resolucion inversa)")

    except socket.gaierror as e:
        print(f"  [-] No se pudo resolver el dominio: {e}")
    except Exception as e:
        print(f"  [-] Error: {e}")

    pausa()


# ==============================================================================
# Opcion 9: Interfaz Streamlit
# ==============================================================================
def iniciar_streamlit():
    """Lanza la interfaz web con Streamlit."""
    mostrar_encabezado("Interfaz interactiva (Web)")

    script_path = Path(__file__).resolve()
    print("[*] Iniciando interfaz web...")
    print("[*] Se abrira una ventana del navegador automaticamente.")
    print("[*] Para detener, cierra esta ventana o presiona Ctrl+C.\n")

    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(script_path),
             "--", "--streamlit"],
            cwd=str(BASE_DIR),
        )
    except FileNotFoundError:
        print("[-] Streamlit no esta instalado.")
        print("[*] Instala con: pip install streamlit")
        pausa()
    except KeyboardInterrupt:
        print("\n[OK] Interfaz web detenida.")
        pausa()


# ==============================================================================
# Interfaz Streamlit
# ==============================================================================
def interfaz_streamlit():
    """Interfaz web completa con Streamlit."""
    import streamlit as st
    import pandas as pd

    crear_directorios()

    st.set_page_config(
        page_title="Ping Logger",
        page_icon="[*]",
        layout="wide",
    )

    st.title("Ping Logger - Monitor de Red")
    st.markdown("---")

    # Sidebar de configuracion
    st.sidebar.header("Configuracion")
    hosts_input = st.sidebar.text_input(
        "Host(s) (separados por comas)", value="8.8.8.8"
    )
    intervalo = st.sidebar.slider(
        "Intervalo entre pings (segundos)", min_value=1, max_value=30, value=2
    )
    umbral_alerta = st.sidebar.number_input(
        "Umbral de alerta de latencia (ms)", min_value=10, max_value=5000, value=100
    )
    max_pings = st.sidebar.number_input(
        "Cantidad de pings a realizar", min_value=1, max_value=1000, value=20
    )

    tab_monitor, tab_stats, tab_historial = st.tabs([
        "Monitor", "Estadisticas de CSV", "Historial de registros"
    ])

    # ---------- Tab Monitor ----------
    with tab_monitor:
        st.subheader("Monitoreo de hosts")

        col_btn1, col_btn2 = st.columns(2)
        iniciar = col_btn1.button("Iniciar monitoreo", type="primary")
        detener = col_btn2.button("Detener")

        if iniciar and not detener:
            hosts = [h.strip() for h in hosts_input.split(",") if h.strip()]
            if not hosts:
                st.error("Debes ingresar al menos un host.")
            else:
                # Preparar CSVs
                archivos_csv = {}
                for host in hosts:
                    nombre = generar_nombre_csv(host)
                    ruta = REGISTROS_DIR / nombre
                    escribir_cabecera_csv(ruta)
                    archivos_csv[host] = ruta

                # Placeholders para actualizacion en tiempo real
                placeholder_grafico = st.empty()
                placeholder_metricas = st.empty()
                placeholder_tabla = st.empty()
                placeholder_estado = st.empty()

                datos_grafico = {host: [] for host in hosts}
                todos_resultados = []

                barra_progreso = st.progress(0)

                for i in range(int(max_pings)):
                    if detener:
                        break

                    for host in hosts:
                        resultado = ejecutar_ping(host)
                        escribir_fila_csv(archivos_csv[host], resultado)
                        todos_resultados.append(resultado)

                        lat = resultado["latency_ms"] if resultado["latency_ms"] is not None else 0
                        datos_grafico[host].append(lat)

                        # Alerta si supera umbral
                        if resultado["latency_ms"] is not None and resultado["latency_ms"] > umbral_alerta:
                            placeholder_estado.warning(
                                f"[!] Latencia alta en {host}: {resultado['latency_ms']} ms"
                            )
                        elif resultado["packet_loss"] == 1:
                            placeholder_estado.error(
                                f"[!] Perdida de paquete en {host}"
                            )

                    # Actualizar grafico
                    df_grafico = pd.DataFrame(datos_grafico)
                    placeholder_grafico.line_chart(df_grafico)

                    # Actualizar metricas
                    with placeholder_metricas.container():
                        cols = st.columns(len(hosts))
                        for idx, host in enumerate(hosts):
                            with cols[idx]:
                                st.markdown(f"**{host}**")
                                datos_h = datos_grafico[host]
                                lats_validas = [d for d in datos_h if d > 0]
                                regs_host = [r for r in todos_resultados if r["host"] == host]
                                total_h = len(regs_host)
                                perdidos_h = sum(1 for r in regs_host if r["packet_loss"] == 1)

                                prom = round(statistics.mean(lats_validas), 2) if lats_validas else 0
                                porc_perdida = round((perdidos_h / total_h) * 100, 1) if total_h > 0 else 0
                                disp = round(100 - porc_perdida, 1)

                                st.metric("Latencia promedio", f"{prom} ms")
                                st.metric("Perdida de paquetes", f"{porc_perdida}%")
                                st.metric("Disponibilidad", f"{disp}%")

                    # Actualizar tabla de pings recientes
                    df_tabla = pd.DataFrame(todos_resultados[-20:])
                    placeholder_tabla.dataframe(df_tabla, use_container_width=True)

                    barra_progreso.progress((i + 1) / int(max_pings))
                    time.sleep(intervalo)

                barra_progreso.empty()
                st.success(f"[OK] Monitoreo completado: {int(max_pings)} rondas de pings.")

                # Boton de descarga
                for host in hosts:
                    ruta = archivos_csv[host]
                    with open(ruta, "r", encoding="utf-8") as f:
                        contenido = f.read()
                    st.download_button(
                        label=f"Descargar CSV de {host}",
                        data=contenido,
                        file_name=ruta.name,
                        mime="text/csv",
                    )

    # ---------- Tab Estadisticas ----------
    with tab_stats:
        st.subheader("Estadisticas de un registro CSV")

        archivos = sorted(REGISTROS_DIR.glob("ping_*.csv"))
        if not archivos:
            st.info("No hay archivos CSV disponibles en la carpeta registros/")
        else:
            nombres_archivos = [a.name for a in archivos]
            seleccion = st.selectbox("Selecciona un archivo CSV", nombres_archivos)

            if seleccion:
                ruta_sel = REGISTROS_DIR / seleccion
                registros = leer_csv(ruta_sel)

                if registros:
                    stats = calcular_estadisticas(registros)

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total pings", stats["total_pings"])
                    col2.metric("Perdidos", stats["paquetes_perdidos"])
                    col3.metric("Disponibilidad", f"{stats['porcentaje_disponibilidad']}%")
                    col4.metric("Mayor caida", f"{stats['mayor_ventana_caida']} pings")

                    if stats["latencia_promedio"] is not None:
                        col5, col6, col7, col8 = st.columns(4)
                        col5.metric("Lat. promedio", f"{stats['latencia_promedio']} ms")
                        col6.metric("Lat. minima", f"{stats['latencia_min']} ms")
                        col7.metric("Lat. maxima", f"{stats['latencia_max']} ms")
                        col8.metric("Lat. P95", f"{stats['latencia_p95']} ms")

                    # Grafico de latencia
                    df = pd.DataFrame(registros)
                    if "latency_ms" in df.columns:
                        df["latency_ms"] = pd.to_numeric(df["latency_ms"], errors="coerce")
                        st.line_chart(df["latency_ms"].dropna())

                    st.dataframe(df, use_container_width=True)

                    # Boton descarga
                    with open(ruta_sel, "r", encoding="utf-8") as f:
                        contenido_csv = f.read()
                    st.download_button(
                        label="Descargar CSV",
                        data=contenido_csv,
                        file_name=seleccion,
                        mime="text/csv",
                    )
                else:
                    st.warning("El archivo seleccionado esta vacio.")

    # ---------- Tab Historial ----------
    with tab_historial:
        st.subheader("Historial de registros")

        archivos = sorted(REGISTROS_DIR.glob("ping_*.csv"), reverse=True)
        if not archivos:
            st.info("No hay registros disponibles.")
        else:
            for archivo in archivos:
                tamano = archivo.stat().st_size
                tamano_str = f"{tamano / 1024:.1f} KB" if tamano > 1024 else f"{tamano} B"
                mod_time = datetime.fromtimestamp(archivo.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                st.text(f"  {archivo.name}  |  {tamano_str}  |  {mod_time}")


# ==============================================================================
# Menu principal CLI
# ==============================================================================
def menu_principal():
    """Menu principal del programa."""
    crear_directorios()

    while True:
        mostrar_encabezado("Menu Principal")

        print("  1. Monitoreo continuo de un solo host")
        print("  2. Prueba rapida de conectividad")
        print("  3. Monitorear multiples hosts simultaneamente")
        print("  4. Deteccion de microcortes")
        print("  5. Ver estadisticas de un registro CSV")
        print("  6. Generar reporte de disponibilidad")
        print("  7. Traceroute a un host")
        print("  8. Resolver DNS de un dominio")
        print("  9. Interfaz interactiva (Web)")
        print("  0. Salir")
        print()

        opcion = input("[+] Selecciona una opcion: ").strip()

        if opcion == "1":
            monitoreo_continuo()
        elif opcion == "2":
            prueba_rapida()
        elif opcion == "3":
            monitoreo_multiple()
        elif opcion == "4":
            deteccion_microcortes()
        elif opcion == "5":
            ver_estadisticas()
        elif opcion == "6":
            generar_reporte()
        elif opcion == "7":
            traceroute()
        elif opcion == "8":
            resolver_dns()
        elif opcion == "9":
            iniciar_streamlit()
        elif opcion == "0":
            limpiar_pantalla()
            print("[OK] Hasta luego!")
            sys.exit(0)
        else:
            print("[-] Opcion no valida.")
            pausa()


# ==============================================================================
# Punto de entrada
# ==============================================================================
if __name__ == "__main__":
    if "--streamlit" in sys.argv:
        interfaz_streamlit()
    else:
        menu_principal()
