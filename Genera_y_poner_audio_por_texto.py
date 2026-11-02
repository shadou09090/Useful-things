import os
from pathlib import Path
from datetime import datetime
from gtts import gTTS, gTTSError

def main():
    texto = input("escribe:\n").strip()

    if not texto:
        print("Debes escribir algún texto.")
        return

    nombre = f"audio_{datetime.now():%Y%m%d_%H%M%S}.mp3"
    archivo = Path(__file__).resolve().parent / nombre

    try:
        audio = gTTS(text=texto, lang="es", slow=False)
        audio.save(str(archivo))

        print(f"Audio guardado en: {archivo}")
        os.startfile(str(archivo))
    except (gTTSError, OSError) as error:
        print(f"No se pudo generar o reproducir el audio: {error}")

if __name__ == "__main__":
    main()