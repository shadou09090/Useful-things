import qrcode

def generate_qr_code(url, filename="qrcode.png"):


    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=100,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

#abajo se cambian los colores del QR code, el fill_color es el color del QR y el back_color es el color de fondo
        img = qr.make_image(fill_color="#FFA300", back_color="#FFFFFF")
        img.save(filename)
        print(f"QR code generated successfully and saved as {filename}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":

    link = input("Enter the URL to generate a QR code for: ")
    if link:
        generate_qr_code(link)
    else:
        print("No URL entered. Exiting.")
