#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auditor de Procesos y Puertos
=============================
Audita conexiones de red locales, muestra que procesos usan que puertos,
estadisticas de RAM/CPU y permite matar procesos.

Dependencias: psutil, streamlit
"""

import os
import sys
import json
import time
import signal
import datetime
import subprocess
from pathlib import Path

try:
    import psutil
except ImportError:
    print("\n[!] Error: Se requiere el modulo 'psutil'.")
    print("[*] Puedes instalarlo ejecutando: python instalar_dependencias.py")
    print("[*] O directamente con: pip install psutil pandas altair streamlit\n")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPORTES_DIR = SCRIPT_DIR / "reportes"

PUERTOS_DEV = [3000, 3001, 4200, 5000, 5173, 5432, 6379, 8000, 8080, 8443, 9000, 27017]

NOMBRES_PUERTOS_DEV = {
    3000: "React / Node",
    3001: "React (alt)",
    4200: "Angular",
    5000: "Flask / .NET",
    5173: "Vite",
    5432: "PostgreSQL",
    6379: "Redis",
    8000: "Django / Uvicorn",
    8080: "HTTP Alt / Tomcat",
    8443: "HTTPS Alt",
    9000: "SonarQube / PHP-FPM",
    27017: "MongoDB",
}

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def limpiar_pantalla():
    os.system("cls" if os.name == "nt" else "clear")


def pausar():
    input("\n[*] Presiona ENTER para continuar...")


def formatear_bytes(nbytes):
    """Convierte bytes a formato legible (KB, MB, GB)."""
    if nbytes is None:
        return "N/A"
    if nbytes < 1024:
        return f"{nbytes} B"
    elif nbytes < 1024 ** 2:
        return f"   {nbytes / 1024:.1f} KB"
    elif nbytes < 1024 ** 3:
        return f"{nbytes / 1024**2:.1f} MB"
    else:
        return f"{nbytes / 1024**3:.2f} GB"


def nombre_estado(status):
    """Traduce el estado de conexion."""
    traducciones = {
        "LISTEN": "ESCUCHANDO",
        "ESTABLISHED": "ESTABLECIDA",
        "CLOSE_WAIT": "ESPERA_CIERRE",
        "TIME_WAIT": "ESPERA_TIEMPO",
        "SYN_SENT": "SYN_ENVIADO",
        "SYN_RECV": "SYN_RECIBIDO",
        "FIN_WAIT1": "FIN_ESPERA1",
        "FIN_WAIT2": "FIN_ESPERA2",
        "LAST_ACK": "ULTIMO_ACK",
        "CLOSING": "CERRANDO",
        "NONE": "NINGUNO",
    }
    return traducciones.get(status, status)


def obtener_info_proceso(pid):
    """Obtiene nombre, RAM y CPU de un proceso dado su PID."""
    if pid is None or pid == 0:
        return ("Sistema", 0, 0.0)
    try:
        proc = psutil.Process(pid)
        nombre = proc.name()
        ram = proc.memory_info().rss
        cpu = proc.cpu_percent(interval=0)
        return (nombre, ram, cpu)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ("(acceso denegado)", 0, 0.0)


def obtener_conexiones():
    """Obtiene todas las conexiones de red con info de proceso."""
    conexiones = []
    try:
        conns = psutil.net_connections(kind="inet")
    except psutil.AccessDenied:
        print("[!] Error: Se requieren permisos de administrador para ver todas las conexiones.")
        print("[*] Algunas conexiones pueden no aparecer.")
        try:
            conns = psutil.net_connections(kind="inet")
        except Exception:
            conns = []

    for c in conns:
        protocolo = "TCP" if c.type == 1 else "UDP"  # SOCK_STREAM=1, SOCK_DGRAM=2
        ip_local = c.laddr.ip if c.laddr else ""
        puerto = c.laddr.port if c.laddr else 0
        estado = c.status if c.status else "NONE"
        pid = c.pid

        nombre, ram, cpu = obtener_info_proceso(pid)

        conexiones.append({
            "protocolo": protocolo,
            "ip_local": ip_local,
            "puerto": puerto,
            "estado": estado,
            "pid": pid if pid else 0,
            "proceso": nombre,
            "ram_bytes": ram,
            "ram": formatear_bytes(ram),
            "cpu": cpu,
        })

    return conexiones


def imprimir_tabla_conexiones(conexiones, titulo="Conexiones de red"):
    """Imprime una tabla formateada de conexiones."""
    if not conexiones:
        print("\n[*] No se encontraron conexiones.")
        return

    print(f"\n{'=' * 110}")
    print(f"  {titulo}")
    print(f"{'=' * 110}")
    encabezado = f"{'Proto':<6} {'IP Local':<18} {'Puerto':<7} {'Estado':<16} {'PID':<8} {'Proceso':<22} {'RAM':<10} {'CPU%':<6}"
    print(encabezado)
    print("-" * 110)

    for c in conexiones:
        linea = (
            f"{c['protocolo']:<6} "
            f"{c['ip_local']:<18} "
            f"{c['puerto']:<7} "
            f"{nombre_estado(c['estado']):<16} "
            f"{c['pid']:<8} "
            f"{c['proceso']:<22} "
            f"{c['ram']:<10} "
            f"{c['cpu']:<6.1f}"
        )
        print(linea)

    print("-" * 110)
    print(f"  Total: {len(conexiones)} conexiones")


# ---------------------------------------------------------------------------
# Funciones del menu
# ---------------------------------------------------------------------------

def listar_puertos():
    """Opcion 1: Listar todos los puertos en uso."""
    limpiar_pantalla()
    print("[*] Obteniendo conexiones de red...")
    conexiones = obtener_conexiones()
    conexiones.sort(key=lambda x: x["puerto"])
    imprimir_tabla_conexiones(conexiones, "Todos los puertos en uso")
    pausar()


def consultar_puerto():
    """Opcion 2: Consultar un puerto especifico."""
    limpiar_pantalla()
    try:
        puerto = int(input("[?] Ingresa el numero de puerto a consultar: "))
    except ValueError:
        print("[!] Numero de puerto invalido.")
        pausar()
        return

    print(f"\n[*] Buscando conexiones en el puerto {puerto}...")
    conexiones = obtener_conexiones()
    filtradas = [c for c in conexiones if c["puerto"] == puerto]

    if filtradas:
        imprimir_tabla_conexiones(filtradas, f"Conexiones en el puerto {puerto}")
    else:
        print(f"\n[+] El puerto {puerto} esta libre (no hay procesos usandolo).")

    pausar()


def escaneo_puertos_dev():
    """Opcion 3: Escaneo rapido de puertos de desarrollo."""
    limpiar_pantalla()
    print("[*] Escaneando puertos de desarrollo comunes...\n")

    conexiones = obtener_conexiones()
    puertos_ocupados = {}
    for c in conexiones:
        if c["puerto"] in PUERTOS_DEV:
            if c["puerto"] not in puertos_ocupados:
                puertos_ocupados[c["puerto"]] = []
            puertos_ocupados[c["puerto"]].append(c)

    print(f"{'Puerto':<8} {'Servicio comun':<20} {'Estado':<12} {'Proceso':<22} {'PID':<8}")
    print("-" * 80)

    for puerto in PUERTOS_DEV:
        servicio = NOMBRES_PUERTOS_DEV.get(puerto, "Desconocido")
        if puerto in puertos_ocupados:
            for c in puertos_ocupados[puerto]:
                estado = "[OCUPADO]"
                print(f"{puerto:<8} {servicio:<20} {estado:<12} {c['proceso']:<22} {c['pid']:<8}")
        else:
            print(f"{puerto:<8} {servicio:<20} {'[LIBRE]':<12} {'---':<22} {'---':<8}")

    ocupados = len(puertos_ocupados)
    libres = len(PUERTOS_DEV) - ocupados
    print(f"\n[*] Resumen: {ocupados} puertos ocupados, {libres} puertos libres de {len(PUERTOS_DEV)} escaneados.")
    pausar()


def buscar_por_proceso():
    """Opcion 4: Buscar puertos por nombre de proceso."""
    limpiar_pantalla()
    nombre = input("[?] Ingresa el nombre (parcial) del proceso: ").strip().lower()

    if not nombre:
        print("[!] Nombre vacio.")
        pausar()
        return

    print(f"\n[*] Buscando procesos que contengan '{nombre}'...")
    conexiones = obtener_conexiones()
    filtradas = [c for c in conexiones if nombre in c["proceso"].lower()]

    if filtradas:
        filtradas.sort(key=lambda x: x["proceso"].lower())
        imprimir_tabla_conexiones(filtradas, f"Puertos usados por procesos con '{nombre}'")
    else:
        print(f"\n[*] No se encontraron conexiones de procesos que contengan '{nombre}'.")

    pausar()


def top_ram():
    """Opcion 5: Top 15 procesos por consumo de RAM."""
    limpiar_pantalla()
    print("[*] Obteniendo procesos por consumo de RAM...\n")

    procesos = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = proc.info
            ram = info["memory_info"].rss if info["memory_info"] else 0
            procesos.append({
                "pid": info["pid"],
                "nombre": info["name"],
                "ram_bytes": ram,
                "ram": formatear_bytes(ram),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procesos.sort(key=lambda x: x["ram_bytes"], reverse=True)
    top = procesos[:15]

    print(f"{'#':<4} {'PID':<10} {'Proceso':<30} {'RAM':<15}")
    print("-" * 65)

    for i, p in enumerate(top, 1):
        print(f"{i:<4} {p['pid']:<10} {p['nombre']:<30} {p['ram']:<15}")

    print("-" * 65)
    pausar()


def top_cpu():
    """Opcion 6: Top 15 procesos por consumo de CPU."""
    limpiar_pantalla()
    print("[*] Midiendo uso de CPU durante 2 segundos... (por favor espera)")

    # Primera llamada para inicializar la medicion
    for proc in psutil.process_iter(["pid"]):
        try:
            proc.cpu_percent()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(2)

    procesos = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            info = proc.info
            cpu = proc.cpu_percent()
            procesos.append({
                "pid": info["pid"],
                "nombre": info["name"],
                "cpu": cpu,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procesos.sort(key=lambda x: x["cpu"], reverse=True)
    top = procesos[:15]

    print(f"\n{'#':<4} {'PID':<10} {'Proceso':<30} {'CPU %':<10}")
    print("-" * 60)

    for i, p in enumerate(top, 1):
        print(f"{i:<4} {p['pid']:<10} {p['nombre']:<30} {p['cpu']:<10.1f}")

    print("-" * 60)
    pausar()


def matar_proceso():
    """Opcion 7: Matar proceso por PID."""
    limpiar_pantalla()
    try:
        pid = int(input("[?] Ingresa el PID del proceso a terminar: "))
    except ValueError:
        print("[!] PID invalido.")
        pausar()
        return

    try:
        proc = psutil.Process(pid)
        nombre = proc.name()
        ram = formatear_bytes(proc.memory_info().rss)
    except psutil.NoSuchProcess:
        print(f"[!] No existe un proceso con PID {pid}.")
        pausar()
        return
    except psutil.AccessDenied:
        print(f"[!] Acceso denegado al proceso con PID {pid}.")
        pausar()
        return

    print(f"\n[!] Proceso encontrado:")
    print(f"    PID:     {pid}")
    print(f"    Nombre:  {nombre}")
    print(f"    RAM:     {ram}")

    confirmacion = input(f"\n[?] Confirmar terminar el proceso '{nombre}' (PID: {pid})? (s/n): ").strip().lower()

    if confirmacion == "s":
        try:
            proc.kill()
            print(f"\n[OK] Proceso '{nombre}' (PID: {pid}) terminado exitosamente.")
        except psutil.NoSuchProcess:
            print(f"\n[!] El proceso ya no existe.")
        except psutil.AccessDenied:
            print(f"\n[!] Acceso denegado. Intenta ejecutar como administrador.")
        except Exception as e:
            print(f"\n[!] Error al terminar el proceso: {e}")
    else:
        print("\n[-] Operacion cancelada.")

    pausar()


def liberar_puerto():
    """Opcion 8: Liberar un puerto ocupado."""
    limpiar_pantalla()
    try:
        puerto = int(input("[?] Ingresa el numero de puerto a liberar: "))
    except ValueError:
        print("[!] Numero de puerto invalido.")
        pausar()
        return

    print(f"\n[*] Buscando procesos que usan el puerto {puerto}...")
    conexiones = obtener_conexiones()
    filtradas = [c for c in conexiones if c["puerto"] == puerto]

    if not filtradas:
        print(f"\n[+] El puerto {puerto} ya esta libre.")
        pausar()
        return

    pids_vistos = set()
    for c in filtradas:
        pid = c["pid"]
        if pid == 0 or pid in pids_vistos:
            continue
        pids_vistos.add(pid)

        print(f"\n[!] Proceso usando el puerto {puerto}:")
        print(f"    PID:     {pid}")
        print(f"    Nombre:  {c['proceso']}")
        print(f"    Estado:  {nombre_estado(c['estado'])}")
        print(f"    RAM:     {c['ram']}")

        confirmacion = input(f"\n[?] Terminar proceso '{c['proceso']}' (PID: {pid}) para liberar el puerto? (s/n): ").strip().lower()

        if confirmacion == "s":
            try:
                proc = psutil.Process(pid)
                proc.kill()
                print(f"[OK] Proceso '{c['proceso']}' (PID: {pid}) terminado. Puerto {puerto} liberado.")
            except psutil.NoSuchProcess:
                print(f"[!] El proceso ya no existe.")
            except psutil.AccessDenied:
                print(f"[!] Acceso denegado. Intenta ejecutar como administrador.")
            except Exception as e:
                print(f"[!] Error: {e}")
        else:
            print("[-] Se omitio este proceso.")

    pausar()


def modo_vigilante():
    """Opcion 9: Modo vigilante (monitoreo en tiempo real)."""
    limpiar_pantalla()
    try:
        intervalo = int(input("[?] Intervalo de refresco en segundos (ej: 5): "))
        if intervalo < 1:
            intervalo = 5
    except ValueError:
        intervalo = 5

    print(f"\n[*] Modo vigilante activado. Refresco cada {intervalo} segundos.")
    print("[*] Presiona Ctrl+C para salir.\n")
    time.sleep(1)

    try:
        while True:
            limpiar_pantalla()
            ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[*] MODO VIGILANTE - Ultima actualizacion: {ahora}")
            print(f"[*] Refresco cada {intervalo}s | Ctrl+C para salir\n")

            conexiones = obtener_conexiones()
            filtradas = [c for c in conexiones if c["estado"] in ("LISTEN", "ESTABLISHED")]
            filtradas.sort(key=lambda x: (x["estado"], x["puerto"]))

            imprimir_tabla_conexiones(filtradas, "Conexiones LISTEN y ESTABLISHED")

            escuchando = len([c for c in filtradas if c["estado"] == "LISTEN"])
            establecidas = len([c for c in filtradas if c["estado"] == "ESTABLISHED"])
            print(f"\n  [*] LISTEN: {escuchando} | ESTABLISHED: {establecidas}")

            time.sleep(intervalo)

    except KeyboardInterrupt:
        print("\n\n[*] Modo vigilante desactivado.")
        pausar()


def exportar_json():
    """Opcion 10: Exportar reporte completo a JSON."""
    limpiar_pantalla()
    print("[*] Generando reporte completo...\n")

    REPORTES_DIR.mkdir(parents=True, exist_ok=True)

    conexiones = obtener_conexiones()
    conexiones.sort(key=lambda x: x["puerto"])

    # Top procesos por RAM
    procesos_ram = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = proc.info
            ram = info["memory_info"].rss if info["memory_info"] else 0
            procesos_ram.append({
                "pid": info["pid"],
                "nombre": info["name"],
                "ram_bytes": ram,
                "ram": formatear_bytes(ram),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procesos_ram.sort(key=lambda x: x["ram_bytes"], reverse=True)

    # Estado de puertos dev
    puertos_dev_estado = {}
    for puerto in PUERTOS_DEV:
        ocupantes = [c for c in conexiones if c["puerto"] == puerto]
        puertos_dev_estado[str(puerto)] = {
            "servicio": NOMBRES_PUERTOS_DEV.get(puerto, "Desconocido"),
            "estado": "OCUPADO" if ocupantes else "LIBRE",
            "procesos": ocupantes if ocupantes else [],
        }

    ahora = datetime.datetime.now()
    reporte = {
        "titulo": "Reporte de Auditoria de Procesos y Puertos",
        "fecha": ahora.strftime("%Y-%m-%d %H:%M:%S"),
        "sistema": {
            "plataforma": sys.platform,
            "cpu_count": psutil.cpu_count(),
            "ram_total": formatear_bytes(psutil.virtual_memory().total),
            "ram_usada": formatear_bytes(psutil.virtual_memory().used),
            "ram_porcentaje": psutil.virtual_memory().percent,
        },
        "total_conexiones": len(conexiones),
        "conexiones": conexiones,
        "top_15_ram": procesos_ram[:15],
        "puertos_desarrollo": puertos_dev_estado,
    }

    nombre_archivo = f"reporte_puertos_{ahora.strftime('%Y%m%d_%H%M%S')}.json"
    ruta_archivo = REPORTES_DIR / nombre_archivo

    with open(ruta_archivo, "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False, default=str)

    print(f"[OK] Reporte exportado exitosamente:")
    print(f"     {ruta_archivo}")
    print(f"     Total de conexiones registradas: {len(conexiones)}")
    pausar()


# ---------------------------------------------------------------------------
# Interfaz Streamlit
# ---------------------------------------------------------------------------

def interfaz_web():
    """Opcion 11: Lanzar interfaz web con Streamlit."""
    limpiar_pantalla()
    print("[*] Iniciando interfaz web interactiva...")
    print("[*] Se abrira una ventana en tu navegador.")
    print("[*] Para detenerla, cierra esta terminal o presiona Ctrl+C.\n")
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve()), "--", "--web"])
    except KeyboardInterrupt:
        print("\n[*] Interfaz interactiva detenida.")
        pausar()


def streamlit_app():
    """Aplicacion Streamlit completa."""
    import streamlit as st
    import pandas as pd

    st.set_page_config(
        page_title="Auditor de Procesos y Puertos",
        page_icon="[*]",
        layout="wide",
    )

    st.title("Auditor de Procesos y Puertos")
    st.caption("Monitoreo de conexiones de red, procesos y puertos del sistema")

    # --- Sidebar ---
    st.sidebar.header("Configuracion")
    auto_refresh = st.sidebar.toggle("Auto-refresco", value=False)
    if auto_refresh:
        intervalo_refresh = st.sidebar.slider("Intervalo (segundos)", 3, 30, 5)
        st.sidebar.info(f"Refrescando cada {intervalo_refresh} segundos")

    seccion = st.sidebar.radio("Seccion", [
        "Conexiones de red",
        "Puertos de desarrollo",
        "Top procesos (RAM)",
        "Top procesos (CPU)",
        "Gestionar procesos",
    ])

    # --- Funciones auxiliares Streamlit ---
    @st.cache_data(ttl=3)
    def cargar_conexiones():
        return obtener_conexiones()

    def df_conexiones(conexiones):
        if not conexiones:
            return pd.DataFrame()
        df = pd.DataFrame(conexiones)
        df = df[["protocolo", "ip_local", "puerto", "estado", "pid", "proceso", "ram", "cpu"]]
        df.columns = ["Protocolo", "IP Local", "Puerto", "Estado", "PID", "Proceso", "RAM", "CPU %"]
        return df

    # --- Secciones ---
    if seccion == "Conexiones de red":
        st.header("Conexiones de red activas")

        col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
        with col_filtro1:
            filtro_puerto = st.text_input("Filtrar por puerto", placeholder="Ej: 8080")
        with col_filtro2:
            filtro_proceso = st.text_input("Filtrar por proceso", placeholder="Ej: python")
        with col_filtro3:
            filtro_estado = st.multiselect("Filtrar por estado", [
                "LISTEN", "ESTABLISHED", "CLOSE_WAIT", "TIME_WAIT",
                "SYN_SENT", "FIN_WAIT1", "FIN_WAIT2", "NONE"
            ])

        conexiones = cargar_conexiones()
        df = df_conexiones(conexiones)

        if not df.empty:
            if filtro_puerto:
                try:
                    p = int(filtro_puerto)
                    df = df[df["Puerto"] == p]
                except ValueError:
                    st.warning("Ingresa un numero de puerto valido")

            if filtro_proceso:
                df = df[df["Proceso"].str.contains(filtro_proceso, case=False, na=False)]

            if filtro_estado:
                df = df[df["Estado"].isin(filtro_estado)]

            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(df)} conexiones")
        else:
            st.info("No se encontraron conexiones. Puede requerir permisos de administrador.")

    elif seccion == "Puertos de desarrollo":
        st.header("Estado de puertos de desarrollo")

        conexiones = cargar_conexiones()
        puertos_en_uso = set(c["puerto"] for c in conexiones)

        cols = st.columns(4)
        for i, puerto in enumerate(PUERTOS_DEV):
            col = cols[i % 4]
            servicio = NOMBRES_PUERTOS_DEV.get(puerto, "Desconocido")
            ocupado = puerto in puertos_en_uso

            with col:
                if ocupado:
                    procs = [c for c in conexiones if c["puerto"] == puerto]
                    nombres = ", ".join(set(c["proceso"] for c in procs))
                    st.error(f"**Puerto {puerto}** - {servicio}\n\nOCUPADO: {nombres}")
                else:
                    st.success(f"**Puerto {puerto}** - {servicio}\n\nLIBRE")

    elif seccion == "Top procesos (RAM)":
        st.header("Top 15 procesos por consumo de RAM")

        procesos = []
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                info = proc.info
                ram = info["memory_info"].rss if info["memory_info"] else 0
                procesos.append({
                    "PID": info["pid"],
                    "Proceso": info["name"],
                    "RAM (bytes)": ram,
                    "RAM": formatear_bytes(ram),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procesos.sort(key=lambda x: x["RAM (bytes)"], reverse=True)
        top15 = procesos[:15]

        if top15:
            df_ram = pd.DataFrame(top15)

            # Grafico de barras
            import altair as alt
            chart_data = pd.DataFrame({
                "Proceso": [f"{p['Proceso']} ({p['PID']})" for p in top15],
                "RAM (MB)": [p["RAM (bytes)"] / (1024**2) for p in top15],
            })
            chart = alt.Chart(chart_data).mark_bar(color="#e74c3c").encode(
                x=alt.X("RAM (MB):Q", title="RAM (MB)"),
                y=alt.Y("Proceso:N", sort="-x", title="Proceso"),
            ).properties(height=400)
            st.altair_chart(chart, use_container_width=True)

            st.dataframe(
                df_ram[["PID", "Proceso", "RAM"]],
                use_container_width=True,
                hide_index=True,
            )

    elif seccion == "Top procesos (CPU)":
        st.header("Top 15 procesos por consumo de CPU")

        if st.button("Medir CPU (espera ~2 segundos)"):
            with st.spinner("Midiendo uso de CPU durante 2 segundos..."):
                for proc in psutil.process_iter(["pid"]):
                    try:
                        proc.cpu_percent()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                time.sleep(2)

                procesos = []
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        info = proc.info
                        cpu = proc.cpu_percent()
                        procesos.append({
                            "PID": info["pid"],
                            "Proceso": info["name"],
                            "CPU %": cpu,
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                procesos.sort(key=lambda x: x["CPU %"], reverse=True)
                top15 = procesos[:15]

                if top15:
                    import altair as alt
                    df_cpu = pd.DataFrame(top15)
                    chart_data = pd.DataFrame({
                        "Proceso": [f"{p['Proceso']} ({p['PID']})" for p in top15],
                        "CPU %": [p["CPU %"] for p in top15],
                    })
                    chart = alt.Chart(chart_data).mark_bar(color="#3498db").encode(
                        x=alt.X("CPU %:Q", title="CPU %"),
                        y=alt.Y("Proceso:N", sort="-x", title="Proceso"),
                    ).properties(height=400)
                    st.altair_chart(chart, use_container_width=True)

                    st.dataframe(df_cpu, use_container_width=True, hide_index=True)
        else:
            st.info("Haz clic en el boton para medir el uso de CPU en tiempo real.")

    elif seccion == "Gestionar procesos":
        st.header("Gestionar procesos")

        tab_matar, tab_liberar = st.tabs(["Matar proceso por PID", "Liberar puerto"])

        with tab_matar:
            pid_input = st.number_input("PID del proceso", min_value=1, step=1, key="kill_pid")

            if st.button("Buscar proceso", key="btn_buscar_pid"):
                try:
                    proc = psutil.Process(int(pid_input))
                    nombre = proc.name()
                    ram = formatear_bytes(proc.memory_info().rss)
                    st.session_state["proc_encontrado"] = {
                        "pid": int(pid_input),
                        "nombre": nombre,
                        "ram": ram,
                    }
                except psutil.NoSuchProcess:
                    st.error(f"No existe un proceso con PID {int(pid_input)}")
                    st.session_state.pop("proc_encontrado", None)
                except psutil.AccessDenied:
                    st.error(f"Acceso denegado al proceso PID {int(pid_input)}")
                    st.session_state.pop("proc_encontrado", None)

            if "proc_encontrado" in st.session_state:
                info = st.session_state["proc_encontrado"]
                st.warning(
                    f"Proceso encontrado: **{info['nombre']}** (PID: {info['pid']}) - RAM: {info['ram']}"
                )
                if st.button("Confirmar: TERMINAR proceso", key="btn_confirmar_kill", type="primary"):
                    try:
                        proc = psutil.Process(info["pid"])
                        proc.kill()
                        st.success(f"Proceso '{info['nombre']}' (PID: {info['pid']}) terminado exitosamente.")
                        st.session_state.pop("proc_encontrado", None)
                    except psutil.NoSuchProcess:
                        st.error("El proceso ya no existe.")
                        st.session_state.pop("proc_encontrado", None)
                    except psutil.AccessDenied:
                        st.error("Acceso denegado. Ejecuta como administrador.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        with tab_liberar:
            puerto_input = st.number_input("Numero de puerto", min_value=1, max_value=65535, step=1, key="lib_puerto")

            if st.button("Buscar proceso en puerto", key="btn_buscar_puerto"):
                conexiones = obtener_conexiones()
                filtradas = [c for c in conexiones if c["puerto"] == int(puerto_input)]

                if filtradas:
                    st.session_state["procs_puerto"] = filtradas
                else:
                    st.success(f"El puerto {int(puerto_input)} esta libre.")
                    st.session_state.pop("procs_puerto", None)

            if "procs_puerto" in st.session_state:
                for c in st.session_state["procs_puerto"]:
                    if c["pid"] == 0:
                        continue
                    st.warning(
                        f"Puerto {c['puerto']} usado por **{c['proceso']}** "
                        f"(PID: {c['pid']}) - Estado: {c['estado']} - RAM: {c['ram']}"
                    )
                    if st.button(
                        f"Terminar {c['proceso']} (PID: {c['pid']})",
                        key=f"kill_port_{c['pid']}",
                        type="primary",
                    ):
                        try:
                            proc = psutil.Process(c["pid"])
                            proc.kill()
                            st.success(f"Proceso '{c['proceso']}' (PID: {c['pid']}) terminado.")
                            st.session_state.pop("procs_puerto", None)
                            st.rerun()
                        except psutil.NoSuchProcess:
                            st.error("El proceso ya no existe.")
                        except psutil.AccessDenied:
                            st.error("Acceso denegado. Ejecuta como administrador.")
                        except Exception as e:
                            st.error(f"Error: {e}")

    # --- Auto-refresh ---
    if auto_refresh:
        time.sleep(intervalo_refresh)
        st.rerun()


# ---------------------------------------------------------------------------
# Menu principal
# ---------------------------------------------------------------------------

def menu_principal():
    """Menu principal del programa."""
    while True:
        limpiar_pantalla()
        print("""
 ============================================================
       AUDITOR DE PROCESOS Y PUERTOS
 ============================================================

   [1]  Listar todos los puertos en uso
   [2]  Consultar un puerto especifico
   [3]  Escaneo rapido de puertos de desarrollo
   [4]  Buscar puertos por nombre de proceso
   [5]  Top 15 procesos por consumo de RAM
   [6]  Top 15 procesos por consumo de CPU
   [7]  Matar proceso por PID
   [8]  Liberar un puerto ocupado
   [9]  Modo vigilante (monitoreo en tiempo real)
  [10]  Exportar reporte completo a JSON
  [11]  Interfaz interactiva (Web)
   [0]  Salir

 ============================================================
""")
        opcion = input("  [?] Selecciona una opcion: ").strip()

        opciones = {
            "1": listar_puertos,
            "2": consultar_puerto,
            "3": escaneo_puertos_dev,
            "4": buscar_por_proceso,
            "5": top_ram,
            "6": top_cpu,
            "7": matar_proceso,
            "8": liberar_puerto,
            "9": modo_vigilante,
            "10": exportar_json,
            "11": interfaz_web,
        }

        if opcion == "0":
            limpiar_pantalla()
            print("\n[*] Hasta luego!\n")
            sys.exit(0)
        elif opcion in opciones:
            opciones[opcion]()
        else:
            print("\n[!] Opcion no valida.")
            pausar()


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--web" in sys.argv:
        streamlit_app()
    else:
        menu_principal()
