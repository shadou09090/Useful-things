import os
from pypdf import PdfWriter, PdfReader


def unir_pdfs():
    archivos = [archivo for archivo in os.listdir('.') if archivo.endswith('.pdf')]

    archivos.sort()

    if not archivos:
        print("No se encontraron archivos PDF en esta carpeta.")
        return

    writer = PdfWriter()

    print("Iniciando la unión de archivos:")
    for archivo in archivos:
        reader = PdfReader(archivo)
        for page in reader.pages:
            writer.add_page(page)
        print(f" - Añadido: {archivo}")

    nombre_salida = "power_BI.pdf"
    with open(nombre_salida, 'wb') as f:
        writer.write(f)

    print(f"\n¡Éxito! El archivo se guardó como: {nombre_salida}")


if __name__ == '__main__':
    unir_pdfs()