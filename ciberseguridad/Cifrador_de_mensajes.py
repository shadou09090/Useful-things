def xor_cipher(data: bytes, key: bytes) -> bytes:
    """Aplica XOR simétrico byte a byte."""
    key_len = len(key)
    return bytes([b ^ key[i % key_len] for i, b in enumerate(data)])


def cifrar(mensaje_original: str, llave_secreta: str) -> None:
    data = mensaje_original.encode("utf-8")
    key = llave_secreta.encode("utf-8")

    cifrado_bytes = xor_cipher(data, key)
    cifrado_hex = cifrado_bytes.hex()

    print(f"📝 Original:   {mensaje_original}")
    print(f"🔒 Cifrado (Hex): {cifrado_hex}")
    print(f"🔑 Clave:      {llave_secreta}")


def descifrar(mensaje_cifrado_hex: str, llave_secreta: str) -> None:
    try:
        cifrado_bytes = bytes.fromhex(mensaje_cifrado_hex.strip())
    except ValueError:
        print("❌ Error: La cadena cifrada no es un hexadecimal válido.")
        return

    key = llave_secreta.encode("utf-8")
    descifrado_bytes = xor_cipher(cifrado_bytes, key)

    try:
        mensaje_descifrado = descifrado_bytes.decode("utf-8")
        print(f"🔓 Descifrado: {mensaje_descifrado}")
    except UnicodeDecodeError:
        print(
            "❌ Error de decodificación: La clave es incorrecta o los datos están corruptos."
        )


def main():
    menu = """
Seleccione una opción:
1) Automática (prueba predefinida)
2) Cifrar mensaje manualmente
3) Descifrar mensaje cifrado (en formato Hex)
"""
    print(menu)
    opcion = input("Ingrese su opción: ").strip()

    if opcion == "1":
        mensaje = "MensajeDePrueba"
        llave = "ClaveSecreta"
        cifrar(mensaje, llave)
    elif opcion == "2":
        mensaje = input("Ingrese el mensaje a cifrar: ")
        llave = input("Ingrese la llave secreta: ")
        if not llave:
            print("❌ La clave no puede estar vacía.")
            return
        cifrar(mensaje, llave)
    elif opcion == "3":
        cifrado_hex = input("Ingrese el mensaje cifrado (hex): ")
        llave = input("Ingrese la llave secreta: ")
        if not llave:
            print("❌ La clave no puede estar vacía.")
            return
        descifrar(cifrado_hex, llave)
    else:
        print("Opción inválida.")


if __name__ == "__main__":
    main()