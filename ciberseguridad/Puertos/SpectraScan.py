from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
import socket
import ssl
import time
from typing import Dict, List
import urllib.error
import urllib.request

ARCHIVO_RUTA = "ruta_a_escanear.txt"

PERFILES_PUERTOS: Dict[str, List[int]] = {
    "1": [21, 22, 25, 53, 80, 110, 143, 443, 3306, 5432, 6379, 8080, 8443],
    "2": [80, 81, 443, 3000, 4200, 5000, 5173, 8000, 8080, 8443, 8888, 9000],
    "3": [1433, 1521, 3306, 5432, 6379, 9200, 27017],
}


@dataclass
class ResultadoPuerto:
    puerto: int
    estado: str
    servicio: str
    latencia_ms: float
    banner: str = ""


def limpiar_objetivo(entrada: str) -> str:
    limpio = entrada.strip().replace("https://", "").replace("http://", "")
    return limpio.split("/")[0].split(":")[0]


def cargar_objetivo_desde_txt() -> str:
    base_dir = Path(__file__).resolve().parent
    candidatos = [base_dir / ARCHIVO_RUTA, base_dir / "ruta_a_escanear"]

    for ruta in candidatos:
        if ruta.exists() and ruta.is_file():
            contenido = ruta.read_text(encoding="utf-8").strip()
            if contenido:
                primera_linea = contenido.splitlines()[0]
                return limpiar_objetivo(primera_linea)

    ruta_default = base_dir / ARCHIVO_RUTA
    objetivo_default = "smart-trip-planner-ivory.vercel.app"
    ruta_default.write_text(objetivo_default + "\n", encoding="utf-8")
    return objetivo_default


def guardar_objetivo_en_txt(nuevo_objetivo: str) -> str:
    base_dir = Path(__file__).resolve().parent
    ruta = base_dir / ARCHIVO_RUTA
    limpio = limpiar_objetivo(nuevo_objetivo)
    ruta.write_text(limpio + "\n", encoding="utf-8")
    return limpio


def obtener_nombre_servicio(puerto: int) -> str:
    try:
        return socket.getservbyport(puerto, "tcp").upper()
    except OSError:
        return "DESCONOCIDO"


def capturar_banner(sock: socket.socket, host: str, puerto: int) -> str:
    try:
        if puerto in (80, 8080, 8000, 3000, 5000):
            payload = f"HEAD / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
            sock.sendall(payload.encode("utf-8"))
            respuesta = sock.recv(1024).decode("utf-8", errors="ignore")
            primera_linea = respuesta.splitlines()[0] if respuesta else ""
            servidor = ""
            for linea in respuesta.splitlines():
                if linea.lower().startswith("server:"):
                    servidor = linea.strip()
                    break
            return f"{primera_linea} | {servidor}".strip(" |")

        elif puerto in (443, 8443):
            contexto = ssl.create_default_context()
            with contexto.wrap_socket(sock, server_hostname=host) as ssock:
                version_tls = ssock.version()
                cipher = ssock.cipher()[0]
                return f"{version_tls} ({cipher})"

        else:
            datos = sock.recv(512).decode("utf-8", errors="ignore").strip()
            return datos.splitlines()[0] if datos else "Sin banner visible"
    except Exception:
        return "Sin respuesta de aplicación"


def escanear_puerto(
    ip: str, host: str, puerto: int, timeout: float
) -> ResultadoPuerto:
    inicio = time.perf_counter()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        resultado = s.connect_ex((ip, puerto))
        latencia = round((time.perf_counter() - inicio) * 1000, 2)

        if resultado == 0:
            servicio = obtener_nombre_servicio(puerto)
            banner = capturar_banner(s, host, puerto)
            return ResultadoPuerto(
                puerto, "ABIERTO", servicio, latencia, banner
            )
        else:
            return ResultadoPuerto(puerto, "CERRADO", "-", latencia)


def inspeccionar_ssl(host: str, puerto: int = 443) -> Dict[str, str]:
    contexto = ssl.create_default_context()
    try:
        with socket.create_connection((host, puerto), timeout=3.0) as sock:
            with contexto.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                sujeto = dict(x[0] for x in cert.get("subject", []))
                emisor = dict(x[0] for x in cert.get("issuer", []))
                san = [v for k, v in cert.get("subjectAltName", []) if k == "DNS"]
                return {
                    "Común (CN)": sujeto.get("commonName", "N/A"),
                    "Emisor": emisor.get("organizationName", "N/A"),
                    "Válido desde": cert.get("notBefore", "N/A"),
                    "Válido hasta": cert.get("notAfter", "N/A"),
                    "Protocolo": ssock.version() or "N/A",
                    "Cifrado": ssock.cipher()[0] if ssock.cipher() else "N/A",
                    "SANs": ", ".join(san[:5]) if san else "N/A",
                }
    except Exception as e:
        return {"Error SSL": str(e)}


def auditar_cabeceras_http(host: str) -> Dict[str, str]:
    url = f"https://{host}"
    req = urllib.request.Request(
        url, method="HEAD", headers={"User-Agent": "NetRecon/3.0"}
    )
    cabeceras_seguridad = [
        "Strict-Transport-Security",
        "Content-Security-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cross-Origin-Opener-Policy",
        "Server",
    ]
    resultado = {}
    try:
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            headers = dict(resp.info())
            resultado["Código HTTP"] = f"{resp.status} {resp.reason}"
            for h in cabeceras_seguridad:
                valor = next(
                    (v for k, v in headers.items() if k.lower() == h.lower()),
                    None,
                )
                resultado[h] = valor if valor else "AUSENTE"
    except Exception as e:
        resultado["Error HTTP"] = str(e)
    return resultado


def auditar_cors_y_cookies(host: str) -> Dict[str, str]:
    url = f"https://{host}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "NetRecon/3.0",
            "Origin": "https://auditoria-externa.example.com",
        },
    )
    resultado = {}
    try:
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            info = resp.info()
            acao = info.get("Access-Control-Allow-Origin")
            acac = info.get("Access-Control-Allow-Credentials")

            if acao == "*":
                resultado["Política CORS"] = "PERMISIVA (Access-Control-Allow-Origin: *)"
            elif acao:
                resultado["Política CORS"] = f"Refleja o restringe origen: {acao} (Credentials: {acac})"
            else:
                resultado["Política CORS"] = "Restringida / No expuesta por defecto (Seguro)"

            cookies = info.get_all("Set-Cookie") or []
            if not cookies:
                resultado["Cookies detectadas"] = "Ninguna en la ruta raíz"
            else:
                for idx, c in enumerate(cookies, 1):
                    c_low = c.lower()
                    nombre = c.split("=")[0].strip()
                    flags = []
                    flags.append("Secure: SI" if "secure" in c_low else "Secure: NO")
                    flags.append("HttpOnly: SI" if "httponly" in c_low else "HttpOnly: NO")
                    flags.append("SameSite: SI" if "samesite" in c_low else "SameSite: NO")
                    resultado[f"Cookie #{idx} ({nombre})"] = " | ".join(flags)
    except Exception as e:
        resultado["Error CORS/Cookies"] = str(e)
    return resultado


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def auditar_transporte_y_metodos(host: str) -> Dict[str, str]:
    resultado = {}
    opener = urllib.request.build_opener(SinRedireccion)

    try:
        req_http = urllib.request.Request(
            f"http://{host}", method="HEAD", headers={"User-Agent": "NetRecon/3.0"}
        )
        with opener.open(req_http, timeout=4.0) as resp:
            resultado["Redirección HTTP -> HTTPS"] = f"NO REDIRIGE (Responde {resp.status} en texto plano)"
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 307, 308):
            destino = e.headers.get("Location", "Desconocido")
            resultado["Redirección HTTP -> HTTPS"] = f"ACTIVA (Código {e.code} -> {destino})"
        else:
            resultado["Redirección HTTP -> HTTPS"] = f"Respuesta HTTP {e.code}"
    except Exception as e:
        resultado["Redirección HTTP -> HTTPS"] = f"No accesible por puerto 80 ({e})"

    try:
        req_opt = urllib.request.Request(
            f"https://{host}", method="OPTIONS", headers={"User-Agent": "NetRecon/3.0"}
        )
        with urllib.request.urlopen(req_opt, timeout=4.0) as resp:
            allow = resp.info().get("Allow") or resp.info().get("Access-Control-Allow-Methods")
            resultado["Métodos HTTP (OPTIONS)"] = allow if allow else "No reportados en cabecera Allow"
    except urllib.error.HTTPError as e:
        allow = e.headers.get("Allow") if e.headers else None
        resultado["Métodos HTTP (OPTIONS)"] = allow if allow else f"Método OPTIONS bloqueado ({e.code})"
    except Exception as e:
        resultado["Métodos HTTP (OPTIONS)"] = f"Error al consultar OPTIONS ({e})"

    return resultado


def verificar_archivos_gobernanza(host: str) -> Dict[str, str]:
    rutas = {
        "robots.txt": f"https://{host}/robots.txt",
        "security.txt": f"https://{host}/.well-known/security.txt",
        "sitemap.xml": f"https://{host}/sitemap.xml",
    }
    resultado = {}
    for nombre, url in rutas.items():
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "NetRecon/3.0"})
        try:
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                ctype = resp.info().get_content_type()
                tamano = len(resp.read(2048))
                resultado[nombre] = f"DISPONIBLE (HTTP {resp.status} | Tipo: {ctype} | Muestra: {tamano} bytes)"
        except urllib.error.HTTPError as e:
            resultado[nombre] = f"NO ENCONTRADO (HTTP {e.code})"
        except Exception as e:
            resultado[nombre] = f"ERROR ({e})"
    return resultado


def parsear_rango_puertos(entrada: str) -> List[int]:
    puertos = set()
    for parte in entrada.split(","):
        parte = parte.strip()
        if "-" in parte:
            inicio, fin = map(int, parte.split("-"))
            puertos.update(range(max(1, inicio), min(65535, fin) + 1))
        elif parte.isdigit():
            p = int(parte)
            if 1 <= p <= 65535:
                puertos.add(p)
    return sorted(puertos)


def ejecutar_escaneo(
    host: str,
    puertos: List[int],
    timeout: float = 1.0,
    workers: int = 50,
    mostrar_cerrados: bool = False,
):
    print(f"\n[*] Resolviendo DNS para '{host}'...")
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET)
        ips = sorted(list({info[4][0] for info in infos}))
        ip_principal = ips[0]
        try:
            rdns = socket.gethostbyaddr(ip_principal)[0]
        except socket.herror:
            rdns = "Sin registro PTR (Reverse DNS)"
    except socket.gaierror:
        print(f"[!] Error crítico: No se pudo resolver el host '{host}'.")
        return None

    print(f"[+] IP Principal : {ip_principal}")
    if len(ips) > 1:
        print(f"[+] IPs Alternas : {', '.join(ips[1:])}")
    print(f"[+] Reverse DNS  : {rdns}")
    print(
        f"[*] Escaneando {len(puertos)} puertos con {workers} hilos (Timeout: {timeout}s)...\n"
    )

    inicio_total = time.perf_counter()
    resultados: List[ResultadoPuerto] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {
            executor.submit(escanear_puerto, ip_principal, host, p, timeout): p
            for p in puertos
        }
        for futuro in as_completed(futuros):
            resultados.append(futuro.result())

    tiempo_total = round(time.perf_counter() - inicio_total, 3)
    resultados.sort(key=lambda x: x.puerto)

    print(
        f"{'PUERTO':<9} {'ESTADO':<10} {'SERVICIO':<14} {'LATENCIA':<12} {'BANNER / INFO'}"
    )
    print("-" * 85)
    abiertos = 0
    for r in resultados:
        if r.estado == "ABIERTO":
            abiertos += 1
            print(
                f"{r.puerto:<9} {'ABIERTO':<10} {r.servicio:<14} {f'{r.latencia_ms} ms':<12} {r.banner}"
            )
        elif mostrar_cerrados:
            print(
                f"{r.puerto:<9} {'CERRADO':<10} {r.servicio:<14} {f'{r.latencia_ms} ms':<12} -"
            )

    print("-" * 85)
    print(
        f"[✓] Escaneo finalizado en {tiempo_total}s | Abiertos: {abiertos} | Cerrados/Filtrados: {len(puertos) - abiertos}"
    )

    return {
        "objetivo": host,
        "ip": ip_principal,
        "ips_adicionales": ips[1:],
        "reverse_dns": rdns,
        "timestamp": datetime.now().isoformat(),
        "tiempo_segundos": tiempo_total,
        "puertos_abiertos": [
            asdict(r) for r in resultados if r.estado == "ABIERTO"
        ],
    }


def imprimir_seccion(titulo: str, datos: Dict[str, str]):
    print(f"\n[*] {titulo}:")
    for k, v in datos.items():
        print(f"    • {k:<30}: {v}")


def menu_principal():
    objetivo_actual = cargar_objetivo_desde_txt()
    ultimo_reporte = None

    while True:
        print("\n" + "=" * 72)
        print(f" NETRECON v3.0 | Archivo: {ARCHIVO_RUTA} | Objetivo: {objetivo_actual}")
        print("=" * 72)
        print(" 1) Escaneo Rápido (Puertos críticos de infraestructura)")
        print(" 2) Escaneo Web & Desarrollo (80, 443, 3000, 5173, 8080...)")
        print(" 3) Escaneo de Bases de Datos (MySQL, PostgreSQL, Oracle, Mongo...)")
        print(" 4) Escaneo Personalizado (ej. 20-100, 443, 8000-8100)")
        print(" 5) Auditoría TLS/SSL y Cabeceras de Seguridad HTTP")
        print(" 6) Auditoría de Cookies, CORS, Redirección HTTPS y Métodos HTTP")
        print(" 7) Verificar archivos públicos (robots.txt, security.txt, sitemap.xml)")
        print(" 8) Ejecutar Auditoría Completa (Red + TLS + Web + Gobernanza)")
        print(" 9) Recargar o actualizar objetivo en ruta_a_escanear.txt")
        print(" 10) Exportar último reporte a JSON")
        print(" 0) Salir")
        print("=" * 72)

        opcion = input("Seleccione una acción: ").strip()

        if opcion in ("1", "2", "3"):
            mostrar_c = (
                input("¿Mostrar también puertos cerrados? (s/N): ")
                .strip()
                .lower()
                == "s"
            )
            ultimo_reporte = ejecutar_escaneo(
                objetivo_actual,
                PERFILES_PUERTOS[opcion],
                mostrar_cerrados=mostrar_c,
            )

        elif opcion == "4":
            rango_str = input("Ingrese puertos o rangos (ej. 22,80,443,8000-8050): ")
            try:
                lista_puertos = parsear_rango_puertos(rango_str)
                if not lista_puertos:
                    print("[!] No se ingresaron puertos válidos.")
                    continue
                ultimo_reporte = ejecutar_escaneo(objetivo_actual, lista_puertos)
            except ValueError:
                print("[!] Formato de rango inválido.")

        elif opcion == "5":
            ssl_info = inspeccionar_ssl(objetivo_actual)
            imprimir_seccion(f"Certificado TLS/SSL ({objetivo_actual})", ssl_info)

            http_info = auditar_cabeceras_http(objetivo_actual)
            imprimir_seccion(f"Cabeceras de Seguridad HTTP ({objetivo_actual})", http_info)

            if ultimo_reporte is None:
                ultimo_reporte = {"objetivo": objetivo_actual, "timestamp": datetime.now().isoformat()}
            ultimo_reporte["ssl"] = ssl_info
            ultimo_reporte["http_headers"] = http_info

        elif opcion == "6":
            cors_cookies = auditar_cors_y_cookies(objetivo_actual)
            imprimir_seccion("Política CORS y Seguridad de Cookies", cors_cookies)

            transporte = auditar_transporte_y_metodos(objetivo_actual)
            imprimir_seccion("Transporte HTTP->HTTPS y Métodos Habilitados", transporte)

            if ultimo_reporte is None:
                ultimo_reporte = {"objetivo": objetivo_actual, "timestamp": datetime.now().isoformat()}
            ultimo_reporte["cors_cookies"] = cors_cookies
            ultimo_reporte["transporte_metodos"] = transporte

        elif opcion == "7":
            archivos = verificar_archivos_gobernanza(objetivo_actual)
            imprimir_seccion("Archivos de Gobernanza y Metadatos Web", archivos)

            if ultimo_reporte is None:
                ultimo_reporte = {"objetivo": objetivo_actual, "timestamp": datetime.now().isoformat()}
            ultimo_reporte["archivos_gobernanza"] = archivos

        elif opcion == "8":
            ultimo_reporte = ejecutar_escaneo(objetivo_actual, PERFILES_PUERTOS["1"])
            if ultimo_reporte is not None:
                ssl_info = inspeccionar_ssl(objetivo_actual)
                imprimir_seccion("Certificado TLS/SSL", ssl_info)

                http_info = auditar_cabeceras_http(objetivo_actual)
                imprimir_seccion("Cabeceras de Seguridad HTTP", http_info)

                cors_cookies = auditar_cors_y_cookies(objetivo_actual)
                imprimir_seccion("Política CORS y Seguridad de Cookies", cors_cookies)

                transporte = auditar_transporte_y_metodos(objetivo_actual)
                imprimir_seccion("Transporte y Métodos HTTP", transporte)

                archivos = verificar_archivos_gobernanza(objetivo_actual)
                imprimir_seccion("Archivos de Gobernanza", archivos)

                ultimo_reporte["ssl"] = ssl_info
                ultimo_reporte["http_headers"] = http_info
                ultimo_reporte["cors_cookies"] = cors_cookies
                ultimo_reporte["transporte_metodos"] = transporte
                ultimo_reporte["archivos_gobernanza"] = archivos

        elif opcion == "9":
            sub = input("¿Desea (1) Recargar desde el archivo o (2) Escribir nueva ruta en el archivo?: ").strip()
            if sub == "1":
                objetivo_actual = cargar_objetivo_desde_txt()
                print(f"[✓] Objetivo recargado desde archivo: {objetivo_actual}")
            elif sub == "2":
                nuevo = input("Ingrese la nueva ruta o dominio: ").strip()
                if nuevo:
                    objetivo_actual = guardar_objetivo_en_txt(nuevo)
                    print(f"[✓] Archivo '{ARCHIVO_RUTA}' actualizado con: {objetivo_actual}")

        elif opcion == "10":
            if not ultimo_reporte:
                print("[!] Ejecuta primero algún módulo de escaneo o auditoría.")
                continue
            nombre_archivo = f"auditoria_{objetivo_actual.replace('.', '_')}.json"
            with open(nombre_archivo, "w", encoding="utf-8") as f:
                json.dump(ultimo_reporte, f, indent=4, ensure_ascii=False)
            print(f"[✓] Reporte guardado en '{nombre_archivo}'")

        elif opcion == "0":
            break
        else:
            print("[!] Opción no reconocida.")


if __name__ == "__main__":
    menu_principal()