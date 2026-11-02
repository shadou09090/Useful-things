import os
import time
import random

# Configuramos el tamaño de nuestro "universo"
FILAS = 20
COLUMNAS = 40


def limpiar_pantalla():
    # Detecta tu sistema operativo para usar el comando correcto ('clear' en Linux, 'cls' en Windows)
    os.system('clear' if os.name == 'posix' else 'cls')


def imprimir_tablero(tablero):
    limpiar_pantalla()
    for fila in tablero:
        # Imprime un bloque blanco si está vivo, o espacio vacío si está muerto
        print("".join(["██" if celda else "  " for celda in fila]))
    print("\n[ Presiona Ctrl+C para detener la simulación ]")


def contar_vecinos(tablero, x, y):
    vecinos = 0
    # Revisamos la cuadrícula de 3x3 alrededor de la célula
    for i in [-1, 0, 1]:
        for j in [-1, 0, 1]:
            if i == 0 and j == 0:
                continue  # No nos contamos a nosotros mismos

            # Verificamos que los vecinos no estén fuera de los bordes de la matriz
            if 0 <= x + i < FILAS and 0 <= y + j < COLUMNAS:
                vecinos += tablero[x + i][y + j]
    return vecinos


def siguiente_generacion(tablero):
    # Creamos un tablero nuevo lleno de ceros
    nuevo_tablero = [[0 for _ in range(COLUMNAS)] for _ in range(FILAS)]

    for i in range(FILAS):
        for j in range(COLUMNAS):
            vecinos = contar_vecinos(tablero, i, j)

            # Aplicamos las reglas de Conway
            if tablero[i][j] == 1 and (vecinos == 2 or vecinos == 3):
                nuevo_tablero[i][j] = 1  # Sobrevive
            elif tablero[i][j] == 0 and vecinos == 3:
                nuevo_tablero[i][j] = 1  # Nace
            # Cualquier otro caso, la célula muere (se queda en 0 en el nuevo tablero)

    return nuevo_tablero


# --- Inicio del simulador ---
# 1. Creamos un universo inicial arrojando 0s y 1s al azar
universo = [[random.choice([0, 1]) for _ in range(COLUMNAS)] for _ in range(FILAS)]

try:
    while True:
        imprimir_tablero(universo)
        universo = siguiente_generacion(universo)
        time.sleep(0.15)  # Pausa de 150ms para que alcancemos a ver la animación
except KeyboardInterrupt:
    print("\nSimulación terminada.")