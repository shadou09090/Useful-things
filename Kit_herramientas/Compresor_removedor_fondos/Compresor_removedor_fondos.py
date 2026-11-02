import os
import sys
import io
import time
import zipfile
import subprocess
import pymupdf as fitz
from PIL import Image
from rembg import remove, new_session

CARPETA_SALIDA = "new images"
SESION_REMBG = None


def asegurar_carpeta():
    ruta = os.path.join(os.getcwd(), CARPETA_SALIDA)
    os.makedirs(ruta, exist_ok=True)
    return ruta


def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')


def obtener_tamano_legible(bytes_size):
    for unidad in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unidad}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def limpiar_ruta(ruta):
    return ruta.strip().strip('"').strip("'")


def obtener_sesion_rembg():
    global SESION_REMBG
    if SESION_REMBG is None:
        SESION_REMBG = new_session("u2netp")
    return SESION_REMBG


def obtener_config_nivel(nivel):
    niveles = {
        "1": {"calidad": 85, "dpi_max": 220, "colores_png": None},
        "2": {"calidad": 72, "dpi_max": 150, "colores_png": 256},
        "3": {"calidad": 55, "dpi_max": 100, "colores_png": 128}
    }
    return niveles.get(str(nivel), niveles["2"])


def seleccionar_nivel_cli():
    print("\nNiveles de compresion:")
    print("  [1] Baja   (Max. nitidez, reduccion ligera)")
    print("  [2] Media  (Recomendado: sin perdida visual notable)")
    print("  [3] Alta   (Maximo ahorro de peso para correo/web)")

    while True:
        opcion = input("\nSeleccione el nivel (1-3) [Por defecto 2]: ").strip()
        if opcion == "" or opcion in ["1", "2", "3"]:
            return obtener_config_nivel(opcion if opcion else "2")
        print("Opcion no valida. Ingrese 1, 2 o 3.")


def comprimir_imagen(ruta_entrada, ruta_salida, config):
    with Image.open(ruta_entrada) as img:
        formato_orig = img.format
        ext = os.path.splitext(ruta_salida)[1].lower()

        if ext in ['.jpg', '.jpeg'] or formato_orig == 'JPEG':
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            img.save(ruta_salida, 'JPEG', optimize=True, quality=config["calidad"], progressive=True)

        elif ext == '.png' or formato_orig == 'PNG':
            if config["colores_png"] and img.mode != 'P':
                img = img.quantize(colors=config["colores_png"], method=2)
            img.save(ruta_salida, 'PNG', optimize=True, compress_level=6)

        elif ext == '.webp' or formato_orig == 'WEBP':
            img.save(ruta_salida, 'WEBP', optimize=True, quality=config["calidad"])

        else:
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            ruta_salida = os.path.splitext(ruta_salida)[0] + ".jpg"
            img.save(ruta_salida, 'JPEG', optimize=True, quality=config["calidad"])

    return ruta_salida


def comprimir_pdf(ruta_entrada, ruta_salida, config):
    doc = fitz.open(ruta_entrada)

    if hasattr(doc, "rewrite_images"):
        doc.rewrite_images(
            dpi_threshold=config["dpi_max"] + 30,
            dpi_target=config["dpi_max"],
            quality=config["calidad"],
            lossy=True,
            bitonal=True,
            color=True,
            gray=True
        )

    doc.save(
        ruta_salida,
        garbage=4,
        deflate=True,
        clean=True,
        deflate_images=True,
        deflate_fonts=True
    )
    doc.close()
    return ruta_salida


def quitar_fondo_rapido(ruta_entrada, ruta_salida, sesion=None):
    if sesion is None:
        sesion = obtener_sesion_rembg()

    with Image.open(ruta_entrada) as img:
        img_rgba = img.convert("RGBA")
        ancho_orig, alto_orig = img_rgba.size

        max_dim = 1024
        if max(ancho_orig, alto_orig) > max_dim:
            escala = max_dim / float(max(ancho_orig, alto_orig))
            nuevo_tam = (int(ancho_orig * escala), int(alto_orig * escala))
            img_inferencia = img_rgba.resize(nuevo_tam, Image.Resampling.BILINEAR)
            mascara = remove(img_inferencia, session=sesion, only_mask=True)
            mascara = mascara.resize((ancho_orig, alto_orig), Image.Resampling.BILINEAR)
        else:
            mascara = remove(img_rgba, session=sesion, only_mask=True)

        img_rgba.putalpha(mascara)
        img_rgba.save(ruta_salida, 'PNG', compress_level=3)

    return ruta_salida


def mostrar_resultado(ruta_orig, ruta_nueva, tiempo_seg):
    peso_orig = os.path.getsize(ruta_orig)
    peso_nuevo = os.path.getsize(ruta_nueva)
    ahorro = ((peso_orig - peso_nuevo) / peso_orig) * 100 if peso_orig > 0 else 0

    print("\n" + "-" * 55)
    print(f"Tiempo de proceso: {tiempo_seg:.2f} segundos")
    print(f"Archivo original : {obtener_tamano_legible(peso_orig)}")
    print(f"Archivo nuevo    : {obtener_tamano_legible(peso_nuevo)}")
    if ahorro > 0:
        print(f"Reduccion lograda: {ahorro:.1f}%")
    else:
        print("Nota             : Guardado en 'new images' sin reduccion adicional.")
    print(f"Guardado en      : {ruta_nueva}")
    print("-" * 55)


def procesar_individual_cli(tipo):
    ruta = limpiar_ruta(input("\nArrastre el archivo aqui o escriba la ruta: "))
    if not os.path.isfile(ruta):
        print("Error: El archivo no existe.")
        return

    carpeta_destino = asegurar_carpeta()
    nombre_base = os.path.basename(ruta)
    nombre, ext = os.path.splitext(nombre_base)

    try:
        if tipo == "nobg":
            sesion = obtener_sesion_rembg()
            print("\nEliminando fondo en modo rapido...")
            t_inicio = time.perf_counter()
            ruta_salida = os.path.join(carpeta_destino, f"{nombre}_sin_fondo.png")
            ruta_final = quitar_fondo_rapido(ruta, ruta_salida, sesion)
            t_total = time.perf_counter() - t_inicio

            print("\n" + "-" * 55)
            print("Fondo eliminado con exito.")
            print(f"Tiempo de proceso: {t_total:.2f} segundos")
            print(f"Peso final       : {obtener_tamano_legible(os.path.getsize(ruta_final))}")
            print(f"Guardado en      : {ruta_final}")
            print("-" * 55)
        else:
            config = seleccionar_nivel_cli()
            print("\nProcesando archivo...")
            t_inicio = time.perf_counter()
            ruta_salida = os.path.join(carpeta_destino, f"{nombre}_opt{ext}")
            if tipo == "pdf":
                ruta_final = comprimir_pdf(ruta, ruta_salida, config)
            else:
                ruta_final = comprimir_imagen(ruta, ruta_salida, config)
            t_total = time.perf_counter() - t_inicio
            mostrar_resultado(ruta, ruta_final, t_total)
    except Exception as e:
        print(f"Error al procesar el archivo: {e}")


def procesar_lote_cli():
    carpeta = limpiar_ruta(input("\nArrastre la carpeta de origen aqui o escriba la ruta: "))
    if not os.path.isdir(carpeta):
        print("Error: La carpeta no existe.")
        return

    config = seleccionar_nivel_cli()
    carpeta_salida = asegurar_carpeta()

    ext_validas = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}
    archivos = [
        f for f in os.listdir(carpeta)
        if os.path.splitext(f)[1].lower() in ext_validas
        and os.path.isfile(os.path.join(carpeta, f))
    ]

    if not archivos:
        print("\nNo se encontraron PDFs ni imagenes compatibles en la carpeta.")
        return

    peso_total_orig = 0
    peso_total_nuevo = 0
    procesados = 0
    t_inicio_lote = time.perf_counter()

    print(f"\nOptimizando {len(archivos)} archivos hacia '{CARPETA_SALIDA}'...\n")
    for archivo in archivos:
        ruta_in = os.path.join(carpeta, archivo)
        nombre, ext = os.path.splitext(archivo)
        ruta_out = os.path.join(carpeta_salida, f"{nombre}_opt{ext}")

        try:
            t_item = time.perf_counter()
            if ext.lower() == '.pdf':
                ruta_out = comprimir_pdf(ruta_in, ruta_out, config)
            else:
                ruta_out = comprimir_imagen(ruta_in, ruta_out, config)
            dt_item = time.perf_counter() - t_item

            p_orig = os.path.getsize(ruta_in)
            p_nuevo = os.path.getsize(ruta_out)

            peso_total_orig += p_orig
            peso_total_nuevo += p_nuevo
            procesados += 1
            ahorro = ((p_orig - p_nuevo) / p_orig) * 100
            print(f"[OK] {archivo} -> -{ahorro:.1f}% ({obtener_tamano_legible(p_nuevo)}) [{dt_item:.2f}s]")
        except Exception as e:
            print(f"[ERROR] {archivo}: {e}")

    t_total_lote = time.perf_counter() - t_inicio_lote
    if procesados > 0:
        ahorro_total = ((peso_total_orig - peso_total_nuevo) / peso_total_orig) * 100
        print("\n" + "=" * 55)
        print(f"Archivos procesados  : {procesados}/{len(archivos)}")
        print(f"Tiempo total         : {t_total_lote:.2f} segundos")
        print(f"Peso total original  : {obtener_tamano_legible(peso_total_orig)}")
        print(f"Peso total final     : {obtener_tamano_legible(peso_total_nuevo)}")
        print(f"Ahorro total         : {ahorro_total:.1f}%")
        print(f"Carpeta de destino   : {carpeta_salida}")
        print("=" * 55)


def lanzar_streamlit():
    print("\nIniciando interfaz web en Streamlit...")
    print("Para volver al menu de terminal, presione Ctrl+C en esta consola.\n")
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        os.path.abspath(__file__),
        "--client.toolbarMode=minimal",
        "--", "--webui"
    ]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nInterfaz de Streamlit cerrada.")


def ejecutar_interfaz_streamlit():
    import streamlit as st

    st.set_page_config(
        page_title="Optimizador de PDFs e Imagenes",
        layout="centered",
        initial_sidebar_state="collapsed"
    )

    st.markdown("""
        <style>
            .stDeployButton {display: none !important;}
            [data-testid="stDeployButton"] {display: none !important;}
            [data-testid="stToolbar"] {visibility: hidden !important; height: 0% !important;}
            #MainMenu {visibility: hidden !important;}
            header {visibility: hidden !important;}
            footer {visibility: hidden !important;}
        </style>
    """, unsafe_allow_html=True)

    @st.cache_resource(show_spinner="Cargando motor ligero u2netp en memoria RAM...")
    def cargar_modelo_ia():
        return new_session("u2netp")

    sesion_ia = cargar_modelo_ia()
    carpeta_destino = asegurar_carpeta()

    st.title("Optimizador de PDFs e Imagenes")
    st.caption(f"Todos los archivos generados se guardan automaticamente en: `{carpeta_destino}`")

    tab_pdf, tab_img, tab_bg, tab_lote = st.tabs([
        "Comprimir PDF",
        "Comprimir Imagen",
        "Quitar Fondo (Turbo)",
        "Procesamiento por Lotes"
    ])

    mapa_niveles = {
        "Baja (Max. nitidez)": "1",
        "Media (Recomendado)": "2",
        "Alta (Max. ahorro)": "3"
    }

    with tab_pdf:
        st.subheader("Reducir peso de documento PDF")
        pdf_file = st.file_uploader("Suba su archivo PDF", type=["pdf"], key="u_pdf")
        nivel_pdf = st.select_slider(
            "Nivel de compresion",
            options=list(mapa_niveles.keys()),
            value="Media (Recomendado)",
            key="s_pdf"
        )

        if pdf_file and st.button("Comprimir PDF", type="primary", key="b_pdf"):
            with st.spinner("Optimizando estructura e imagenes del PDF..."):
                t0 = time.perf_counter()
                config = obtener_config_nivel(mapa_niveles[nivel_pdf])
                nombre, ext = os.path.splitext(pdf_file.name)
                ruta_temp = os.path.join(carpeta_destino, f"_temp_{pdf_file.name}")
                ruta_salida = os.path.join(carpeta_destino, f"{nombre}_opt{ext}")

                with open(ruta_temp, "wb") as f:
                    f.write(pdf_file.getbuffer())

                comprimir_pdf(ruta_temp, ruta_salida, config)
                dt = time.perf_counter() - t0
                p_orig = os.path.getsize(ruta_temp)
                p_nuevo = os.path.getsize(ruta_salida)
                os.remove(ruta_temp)

                ahorro = ((p_orig - p_nuevo) / p_orig) * 100 if p_orig > 0 else 0
                st.success(f"Guardado en `{ruta_salida}` en **{dt:.2f} s**")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Original", obtener_tamano_legible(p_orig))
                c2.metric("Optimizado", obtener_tamano_legible(p_nuevo))
                c3.metric("Reduccion", f"{ahorro:.1f}%")
                c4.metric("Tiempo", f"{dt:.2f} s")

                with open(ruta_salida, "rb") as f:
                    st.download_button(
                        "Descargar PDF Optimizado",
                        data=f.read(),
                        file_name=f"{nombre}_opt{ext}",
                        mime="application/pdf"
                    )

    with tab_img:
        st.subheader("Comprimir Imagen sin perdida visual")
        img_file = st.file_uploader("Suba su imagen", type=["jpg", "jpeg", "png", "webp"], key="u_img")
        nivel_img = st.select_slider(
            "Nivel de compresion",
            options=list(mapa_niveles.keys()),
            value="Media (Recomendado)",
            key="s_img"
        )

        if img_file and st.button("Comprimir Imagen", type="primary", key="b_img"):
            with st.spinner("Comprimiendo imagen..."):
                t0 = time.perf_counter()
                config = obtener_config_nivel(mapa_niveles[nivel_img])
                nombre, ext = os.path.splitext(img_file.name)
                ruta_temp = os.path.join(carpeta_destino, f"_temp_{img_file.name}")
                ruta_salida = os.path.join(carpeta_destino, f"{nombre}_opt{ext}")

                with open(ruta_temp, "wb") as f:
                    f.write(img_file.getbuffer())

                ruta_salida = comprimir_imagen(ruta_temp, ruta_salida, config)
                dt = time.perf_counter() - t0
                p_orig = os.path.getsize(ruta_temp)
                p_nuevo = os.path.getsize(ruta_salida)
                os.remove(ruta_temp)

                ahorro = ((p_orig - p_nuevo) / p_orig) * 100 if p_orig > 0 else 0
                st.success(f"Guardado en `{ruta_salida}` en **{dt:.2f} s**")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Original", obtener_tamano_legible(p_orig))
                c2.metric("Optimizado", obtener_tamano_legible(p_nuevo))
                c3.metric("Reduccion", f"{ahorro:.1f}%")
                c4.metric("Tiempo", f"{dt:.2f} s")

                st.image(ruta_salida, caption="Vista previa optimizada", use_container_width=True)

                with open(ruta_salida, "rb") as f:
                    st.download_button(
                        "Descargar Imagen Optimizada",
                        data=f.read(),
                        file_name=os.path.basename(ruta_salida)
                    )

    with tab_bg:
        st.subheader("Eliminar el fondo de una imagen (Motor Rapido)")
        bg_file = st.file_uploader("Suba su imagen", type=["jpg", "jpeg", "png", "webp"], key="u_bg")

        if bg_file and st.button("Quitar Fondo Ahora", type="primary", key="b_bg"):
            with st.spinner("Recortando fondo..."):
                t0 = time.perf_counter()
                nombre, _ = os.path.splitext(bg_file.name)
                ruta_temp = os.path.join(carpeta_destino, f"_temp_{bg_file.name}")
                ruta_salida = os.path.join(carpeta_destino, f"{nombre}_sin_fondo.png")

                with open(ruta_temp, "wb") as f:
                    f.write(bg_file.getbuffer())

                quitar_fondo_rapido(ruta_temp, ruta_salida, sesion_ia)
                dt = time.perf_counter() - t0
                p_final = os.path.getsize(ruta_salida)
                os.remove(ruta_temp)

                st.success(f"Recorte completado en **{dt:.2f} segundos** y guardado en `{ruta_salida}`")

                m1, m2 = st.columns(2)
                m1.metric("Tiempo de inferencia", f"{dt:.2f} s")
                m2.metric("Peso del PNG resultante", obtener_tamano_legible(p_final))

                col_a, col_b = st.columns(2)
                col_a.image(bg_file, caption="Original", use_container_width=True)
                col_b.image(ruta_salida, caption="Sin Fondo (PNG)", use_container_width=True)

                with open(ruta_salida, "rb") as f:
                    st.download_button(
                        "Descargar PNG sin fondo",
                        data=f.read(),
                        file_name=f"{nombre}_sin_fondo.png",
                        mime="image/png"
                    )

    with tab_lote:
        st.subheader("Optimizar multiples archivos a la vez")
        lote_files = st.file_uploader(
            "Seleccione multiples PDFs o Imagenes",
            type=["pdf", "jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="u_lote"
        )
        nivel_lote = st.select_slider(
            "Nivel de compresion",
            options=list(mapa_niveles.keys()),
            value="Media (Recomendado)",
            key="s_lote"
        )

        if lote_files and st.button("Procesar Lote", type="primary", key="b_lote"):
            t0_lote = time.perf_counter()
            config = obtener_config_nivel(mapa_niveles[nivel_lote])
            barra = st.progress(0)
            p_total_orig = 0
            p_total_nuevo = 0
            archivos_generados = []

            for idx, archivo in enumerate(lote_files):
                nombre, ext = os.path.splitext(archivo.name)
                ruta_temp = os.path.join(carpeta_destino, f"_temp_{archivo.name}")
                ruta_salida = os.path.join(carpeta_destino, f"{nombre}_opt{ext}")

                with open(ruta_temp, "wb") as f:
                    f.write(archivo.getbuffer())

                if ext.lower() == ".pdf":
                    ruta_salida = comprimir_pdf(ruta_temp, ruta_salida, config)
                else:
                    ruta_salida = comprimir_imagen(ruta_temp, ruta_salida, config)

                p_total_orig += os.path.getsize(ruta_temp)
                p_total_nuevo += os.path.getsize(ruta_salida)
                os.remove(ruta_temp)
                archivos_generados.append(ruta_salida)
                barra.progress((idx + 1) / len(lote_files))

            dt_lote = time.perf_counter() - t0_lote
            ahorro_total = ((p_total_orig - p_total_nuevo) / p_total_orig) * 100 if p_total_orig > 0 else 0
            st.success(f"Se guardaron {len(archivos_generados)} archivos en `{carpeta_destino}` en **{dt_lote:.2f} s**")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Original", obtener_tamano_legible(p_total_orig))
            c2.metric("Total Optimizado", obtener_tamano_legible(p_total_nuevo))
            c3.metric("Ahorro Total", f"{ahorro_total:.1f}%")
            c4.metric("Tiempo Total", f"{dt_lote:.2f} s")

            buffer_zip = io.BytesIO()
            with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                for ruta_f in archivos_generados:
                    zf.write(ruta_f, os.path.basename(ruta_f))

            st.download_button(
                "Descargar todos en ZIP",
                data=buffer_zip.getvalue(),
                file_name="new_images_optimizados.zip",
                mime="application/zip"
            )


def menu():
    asegurar_carpeta()
    while True:
        limpiar_pantalla()
        print("=======================================================")
        print("          OPTIMIZADOR DE PDFs E IMAGENES               ")
        print(f"      Carpeta de salida: ./{CARPETA_SALIDA}/            ")
        print("=======================================================")
        print("  [1] Comprimir un archivo PDF")
        print("  [2] Comprimir una Imagen (JPG, PNG, WEBP)")
        print("  [3] Quitar el fondo de una Imagen (Modo Turbo)")
        print("  [4] Comprimir carpeta completa por lotes")
        print("  [5] Abrir interfaz grafica interactiva (Streamlit)")
        print("  [6] Salir")
        print("=======================================================")

        opcion = input("Seleccione una opcion (1-6): ").strip()

        if opcion == "1":
            procesar_individual_cli("pdf")
            input("\nPresione Enter para continuar...")
        elif opcion == "2":
            procesar_individual_cli("img")
            input("\nPresione Enter para continuar...")
        elif opcion == "3":
            procesar_individual_cli("nobg")
            input("\nPresione Enter para continuar...")
        elif opcion == "4":
            procesar_lote_cli()
            input("\nPresione Enter para continuar...")
        elif opcion == "5":
            lanzar_streamlit()
        elif opcion == "6":
            sys.exit(0)


if __name__ == "__main__":
    if "--webui" in sys.argv:
        ejecutar_interfaz_streamlit()
    else:
        menu()