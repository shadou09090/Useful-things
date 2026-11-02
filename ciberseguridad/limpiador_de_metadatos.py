import os
import sys
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


def obtener_datos_exif(ruta_imagen):
    try:
        imagen = Image.open(ruta_imagen)
        exif_raw = imagen._getexif()
        if not exif_raw:
            return None

        datos_exif = {}
        for tag_id, valor in exif_raw.items():
            nombre_tag = TAGS.get(tag_id, tag_id)
            if nombre_tag == "GPSInfo":
                datos_gps = {}
                for gps_id in valor:
                    nombre_gps = GPSTAGS.get(gps_id, gps_id)
                    datos_gps[nombre_gps] = valor[gps_id]
                datos_exif[nombre_tag] = datos_gps
            else:
                datos_exif[nombre_tag] = valor
        return datos_exif
    except Exception as e:
        print(f"\n[!] Error al leer la imagen: {e}")
        return None


def a_grados_decimales(valor):
    d = float(valor[0])
    m = float(valor[1])
    s = float(valor[2])
    return d + (m / 60.0) + (s / 3600.0)


def extraer_coordenadas(gps_info):
    try:
        lat = a_grados_decimales(gps_info["GPSLatitude"])
        if gps_info.get("GPSLatitudeRef") != "N":
            lat = -lat

        lon = a_grados_decimales(gps_info["GPSLongitude"])
        if gps_info.get("GPSLongitudeRef") != "E":
            lon = -lon

        return lat, lon
    except KeyError:
        return None, None
    except Exception:
        return None, None


def mostrar_metadatos_sensibles(ruta):
    datos = obtener_datos_exif(ruta)
    if not datos:
        print("\n[-] No se encontraron metadatos EXIF en la imagen o el formato no los soporta.")
        return

    print("\n" + "=" * 45)
    print("        REPORTE DE METADATOS SENSIBLES")
    print("=" * 45)

    marca = datos.get("Make", "No registrado")
    modelo = datos.get("Model", "No registrado")
    software = datos.get("Software", "No registrado")
    fecha = datos.get("DateTimeOriginal", datos.get("DateTime", "No registrada"))

    print(f"[*] Marca del dispositivo  : {marca}")
    print(f"[*] Modelo del dispositivo : {modelo}")
    print(f"[*] Software / OS          : {software}")
    print(f"[*] Fecha de captura       : {fecha}")

    if "GPSInfo" in datos:
        lat, lon = extraer_coordenadas(datos["GPSInfo"])
        if lat is not None and lon is not None:
            print(f"[!] Coordenadas GPS        : {lat:.6f}, {lon:.6f}")
            print(f"[!] Enlace Google Maps     : https://www.google.com/maps?q={lat},{lon}")
        else:
            print("[*] Coordenadas GPS        : Datos GPS incompletos o corruptos")
    else:
        print("[*] Coordenadas GPS        : No encontradas")
    print("=" * 45)


def mostrar_todos_metadatos(ruta):
    datos = obtener_datos_exif(ruta)
    if not datos:
        print("\n[-] No se encontraron metadatos EXIF en la imagen.")
        return

    print("\n" + "=" * 45)
    print("          VOLCADO COMPLETO DE EXIF")
    print("=" * 45)
    for clave, valor in datos.items():
        if clave != "GPSInfo" and not isinstance(valor, bytes):
            print(f"{clave}: {valor}")
    print("=" * 45)


def sanitizar_imagen(ruta):
    try:
        imagen = Image.open(ruta)

        directorio, nombre_archivo = os.path.split(ruta)
        nombre_base, extension = os.path.splitext(nombre_archivo)
        nueva_ruta = os.path.join(directorio, f"{nombre_base}_sanitizada{extension}")

        imagen_limpia = Image.new(imagen.mode, imagen.size)
        imagen_limpia.putdata(list(imagen.getdata()))

        imagen_limpia.save(nueva_ruta, quality=95)
        print(f"\n[+] Imagen sanitizada guardada con éxito en:\n    -> {nueva_ruta}")
        return nueva_ruta
    except Exception as e:
        print(f"\n[!] Error al sanitizar la imagen: {e}")
        return None


def verificar_ruta():
    ruta = input("\nIngrese la ruta de la imagen: ").strip().strip('"').strip("'")
    if not os.path.isfile(ruta):
        print("\n[!] Error: El archivo especificado no existe.")
        return None
    return ruta


def menu():
    while True:
        print("\n" + "=" * 45)
        print("   EXTRACTOR Y LIMPIADOR DE METADATOS EXIF")
        print("=" * 45)
        print("1. Analizar metadatos sensibles (GPS, Dispositivo, Fecha)")
        print("2. Sanitizar imagen (Crear copia sin metadatos)")
        print("3. Flujo completo (Analizar, Sanitizar y Verificar)")
        print("4. Ver todos los metadatos EXIF crudos")
        print("5. Salir")
        print("=" * 45)

        opcion = input("Seleccione una opción (1-5): ").strip()

        if opcion == "1":
            ruta = verificar_ruta()
            if ruta:
                mostrar_metadatos_sensibles(ruta)
        elif opcion == "2":
            ruta = verificar_ruta()
            if ruta:
                sanitizar_imagen(ruta)
        elif opcion == "3":
            ruta = verificar_ruta()
            if ruta:
                mostrar_metadatos_sensibles(ruta)
                nueva_ruta = sanitizar_imagen(ruta)
                if nueva_ruta:
                    print("\n[*] Verificando el archivo generado...")
                    mostrar_metadatos_sensibles(nueva_ruta)
        elif opcion == "4":
            ruta = verificar_ruta()
            if ruta:
                mostrar_todos_metadatos(ruta)
        elif opcion == "5":
            print("\nSaliendo del programa.")
            sys.exit(0)
        else:
            print("\n[!] Opción inválida. Intente de nuevo.")


if __name__ == "__main__":
    menu()