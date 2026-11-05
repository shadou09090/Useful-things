import ctypes
from ctypes import wintypes
import time
import keyboard

user32 = ctypes.WinDLL('user32', use_last_error=True)

INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_RETURN = 0x0D


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong)
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("padding", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]


def construir_lote_memoria_c(texto_bloque):
    eventos = []
    for char in texto_bloque:
        if char == '\n':
            eventos.append(INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(
                ki=KEYBDINPUT(wVk=VK_RETURN, wScan=0, dwFlags=0, time=0, dwExtraInfo=0))))
            eventos.append(INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(
                ki=KEYBDINPUT(wVk=VK_RETURN, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0))))
        else:
            code = ord(char)
            eventos.append(INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(
                ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0))))
            eventos.append(INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(
                ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0))))

    ArrayType = INPUT * len(eventos)
    return ArrayType(*eventos), len(eventos)


CANTIDAD_MAXIMA = 100000

frase = input("¿Qué frase quieres poner?: ").strip()
if not frase:
    frase = "busca trabajo"

cantidad_str = input(f"¿Cuántas veces quieres repetirla? (Enter para la máxima: {CANTIDAD_MAXIMA}): ").strip()
try:
    TOTAL_LINEAS = int(cantidad_str) if cantidad_str else CANTIDAD_MAXIMA
    if TOTAL_LINEAS <= 0:
        TOTAL_LINEAS = CANTIDAD_MAXIMA
except ValueError:
    TOTAL_LINEAS = CANTIDAD_MAXIMA

tiempo_str = input("¿Cuántos segundos de espera antes de comenzar? (Enter para 5): ").strip()
try:
    tiempo_espera = float(tiempo_str) if tiempo_str else 5.0
except ValueError:
    tiempo_espera = 5.0

resp_numeros = input("¿Quieres números al lado de la frase? (s/n): ").strip().lower()
incluir_numeros = resp_numeros in ("s", "si", "sí", "y", "yes")

TAMANO_RAFAGA = 100

print(f"Pre-compilando {TOTAL_LINEAS} líneas en paquetes de memoria C...")
lotes_preparados = []

for inicio_lote in range(1, TOTAL_LINEAS + 1, TAMANO_RAFAGA):
    fin_lote = min(inicio_lote + TAMANO_RAFAGA, TOTAL_LINEAS + 1)
    if incluir_numeros:
        texto_rafaga = "".join(f"{i} {frase}\n" for i in range(inicio_lote, fin_lote))
    else:
        texto_rafaga = "".join(f"{frase}\n" for _ in range(inicio_lote, fin_lote))
    arreglo_c, num_eventos = construir_lote_memoria_c(texto_rafaga)
    lotes_preparados.append((arreglo_c, num_eventos))

print(f"Listo. Tienes {tiempo_espera} segundos para poner el cursor donde quieras...")
print("Presiona 'ESC' para detener.")
time.sleep(tiempo_espera)

t0 = time.perf_counter()
tamano_struct = ctypes.sizeof(INPUT)

for idx, (arreglo_c, num_eventos) in enumerate(lotes_preparados):
    if keyboard.is_pressed('esc'):
        print(f"\n[!] Abortado por el usuario en la ráfaga {idx + 1}.")
        break

    user32.SendInput(num_eventos, ctypes.byref(arreglo_c), tamano_struct)

t1 = time.perf_counter()
print(f"Inyección al kernel terminada en: {(t1 - t0) * 1000:.2f} milisegundos.")