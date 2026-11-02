import hashlib
import time
from typing import Iterable, Optional, Tuple


def crack_sha256(
    target_hex: str, candidates: Iterable[str]
) -> Tuple[Optional[str], int, float]:
    try:
        target_bytes = bytes.fromhex(target_hex.strip())
    except ValueError:
        raise ValueError("El hash objetivo no tiene un formato hexadecimal válido.")

    if len(target_bytes) != 32:
        raise ValueError("El hash objetivo no corresponde a SHA-256 (longitud incorrecta).")

    start_time = time.perf_counter()

    for attempts, word in enumerate(candidates, start=1):
        if hashlib.sha256(word.encode("utf-8")).digest() == target_bytes:
            elapsed = time.perf_counter() - start_time
            return word, attempts, elapsed
    else:
        elapsed = time.perf_counter() - start_time
        return None, attempts, elapsed


def main() -> None:
    hash_objetivo = "a00d52243f97dba5c7cd716d8a675cb4e1db62ca6f14c25ebee868bd17ec2bfc"
    diccionario = ["123456", "admin", "qwerty", "princesa", "dragon", "password123", "queso"]

    print(f"Hash objetivo: {hash_objetivo}")
    print(f"Candidatos cargados: {len(diccionario)}\n")

    password, attempts, elapsed = crack_sha256(hash_objetivo, diccionario)

    rate = attempts / elapsed if elapsed > 0 else 0.0

    if password is not None:
        print(f"[+] Contraseña encontrada: '{password}'")
    else:
        print("[-] Contraseña no encontrada en el conjunto de prueba.")

    print(f"[i] Intentos: {attempts}")
    print(f"[i] Tiempo:   {elapsed:.6f} s")
    print(f"[i] Hashrate: {rate:,.2f} H/s")


if __name__ == "__main__":
    main()