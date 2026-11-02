import glob
import os
import shutil

import yt_dlp as youtube_dl


def obtener_ruta_ffmpeg():
    if shutil.which('ffmpeg'):
        return None

    patrones_winget = [
        os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\WinGet\Packages\yt-dlp.FFmpeg_*\*\bin'),
        os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\*\bin'),
    ]
    for patron in patrones_winget:
        coincidencias = glob.glob(patron)
        if coincidencias and os.path.isdir(coincidencias[0]):
            return coincidencias[0]

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass

    return None


def obtener_js_runtimes():
    if shutil.which('node'):
        return {'node': {}}
    if shutil.which('deno'):
        return {'deno': {}}
    return None


def descargar(url, es_playlist=False):
    carpeta_base = os.path.dirname(os.path.abspath(__file__))
    carpeta_descargas = os.path.join(carpeta_base, 'videos_descargado')
    os.makedirs(carpeta_descargas, exist_ok=True)

    if es_playlist:
        plantilla_salida = os.path.join(
            carpeta_descargas,
            '%(playlist_title)s',
            '%(playlist_index)s - %(title)s.%(ext)s',
        )
    else:
        plantilla_salida = os.path.join(carpeta_descargas, '%(title)s.%(ext)s')

    opciones = {
        'outtmpl': plantilla_salida,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'noplaylist': not es_playlist,
        'ignoreerrors': es_playlist,
        'windowsfilenames': True,
    }

    ruta_ffmpeg = obtener_ruta_ffmpeg()
    if ruta_ffmpeg:
        opciones['ffmpeg_location'] = ruta_ffmpeg

    js_runtimes = obtener_js_runtimes()
    if js_runtimes:
        opciones['js_runtimes'] = js_runtimes

    with youtube_dl.YoutubeDL(opciones) as ydl:
        ydl.download([url])


if __name__ == '__main__':
    url = input("Ingrese la URL de YouTube: ").strip()
    if url:
        modo = input("¿Descargar [1] Solo un video o [2] Playlist completa?: ").strip()
        descargar(url, es_playlist=(modo == '2'))