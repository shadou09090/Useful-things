# 🛠️ Programas Útiles (Python Utility Toolkit)

Una colección completa y modular de scripts y herramientas en Python diseñadas para **auditoría de ciberseguridad**, **automatización de tareas cotidianas**, **procesamiento de medios y documentos**, y **simulaciones algorítmicas**.

---

## 📁 Estructura del Repositorio

```text
Programas_utiles/
├── ciberseguridad/
│   ├── Puertos/
│   │   ├── ruta_a_escanear                # Archivo auxiliar de objetivo para escaneo
│   │   └── SpectraScan.py                 # Escáner de red, puertos y auditoría web
│   ├── Cifrador_de_mensajes.py            # Cifrado y descifrado simétrico por XOR
│   ├── Hash_fuerza_bruta.py               # Cracker de hashes SHA-256 por diccionario
│   └── limpiador_de_metadatos.py          # Extractor y sanitizador de metadatos EXIF (GPS, cámara)
├── Kit_herramientas/
│   ├── Compresor_removedor_fondos/
│   │   ├── Compresor_removedor_fondos.py  # Optimizador de PDFs/imágenes y recorte de fondos por IA
│   │   └── new images/                    # Carpeta de salida predeterminada
│   ├── Juntador_pdf/
│   │   └── Juntador_pdfs.py               # Fusión y unión secuencial de documentos PDF
│   ├── Descargar_videos_youtube.py        # Descarga de videos individuales y playlists de YouTube
│   ├── Escribir_mensajes.py               # Automatización de escritura por teclado (Auto-Typer)
│   ├── Generador_de_QR_por_link.py        # Generación de códigos QR personalizados
│   ├── Genera_y_poner_audio_por_texto.py  # Conversión de texto a voz (TTS) y reproducción automática
│   └── smart_organizer.py                 # Organizador inteligente de directorios (CLI y Web UI)
├── Programas_para_curiosidad/
│   └── Simulador_de_vida_cow.py           # Autómata celular del Juego de la Vida de Conway
├── requirements.txt                       # Lista estructurada de dependencias externas
├── instalar_dependencias.py               # Menú interactivo para instalar dependencias selectivas o totales
├── LICENSE                                # Licencia del proyecto
└── README.md                              # Documentación completa y guía de uso
```

---

## ⚙️ Instalación y Gestión de Dependencias

Para facilitar la preparación del entorno, el repositorio incluye un programa interactivo en Python y el archivo estándar `requirements.txt`.

### Opción 1: Instalador Interactivo (Recomendado)

Ejecuta el script de instalación interactivo:

```bash
python instalar_dependencias.py
```

Al iniciarse, se desplegará un menú interactivo en la terminal:
- **Opción `[1]`**: Instala **todas** las dependencias del proyecto completo en una sola operación.
- **Opciones `[2]` en adelante**: Permiten seleccionar un programa específico e instalar **únicamente** las librerías que ese programa necesita, evitando descargas innecesarias.
- **Programas con biblioteca estándar**: Si eliges un programa que no necesita librerías externas (como `SpectraScan.py` o `Cifrador_de_mensajes.py`), el instalador te informará que está listo para ejecutarse sin instalar nada adicional.

### Opción 2: Instalación Tradicional con Pip

Si prefieres instalar todas las librerías de una sola vez mediante `pip`:

```bash
pip install -r requirements.txt
```

---

## 📖 Catálogo Detallado de Programas

A continuación se detalla cada programa incluido en la suite, explicando su funcionamiento técnico, su utilidad práctica, sus dependencias y cómo ejecutarlo.

---

### 🛡️ Ciberseguridad y Auditoría

#### 1. Cifrador de Mensajes (XOR)
* **Archivo:** [`ciberseguridad/Cifrador_de_mensajes.py`](ciberseguridad/Cifrador_de_mensajes.py)
* **Dependencias:** Ninguna (Biblioteca estándar de Python).
* **¿Qué hace?**  
  Implementa un algoritmo de cifrado y descifrado simétrico byte a byte aplicando la operación lógica XOR entre los datos del mensaje y una clave secreta arbitraria. La salida cifrada se codifica en hexadecimal para garantizar que pueda copiarse y transportarse como texto sin perder caracteres especiales ni bytes no imprimibles. Dispone de un menú para cifrado manual, descifrado y prueba automatizada.
* **¿Qué utilidad tiene?**  
  - Comprender los conceptos esenciales de la criptografía simétrica y el funcionamiento de operaciones a nivel de bits.
  - Ofuscar rápidamente cadenas de texto sensibles, contraseñas temporales o notas privadas antes de transmitirlas por canales inseguros.
* **Ejecución:**
  ```bash
  python ciberseguridad/Cifrador_de_mensajes.py
  ```

---

#### 2. Cracker de Hashes SHA-256 por Fuerza Bruta / Diccionario
* **Archivo:** [`ciberseguridad/Hash_fuerza_bruta.py`](ciberseguridad/Hash_fuerza_bruta.py)
* **Dependencias:** Ninguna (Biblioteca estándar: `hashlib`, `time`, `typing`).
* **¿Qué hace?**  
  Toma una cadena resumen (hash SHA-256 de 64 caracteres hexadecimales) y un conjunto de palabras candidatas (diccionario). Itera sobre cada candidato generando su digest SHA-256 en tiempo real hasta dar con la coincidencia. Mide con precisión de microsegundos el tiempo invertido, el total de intentos y la tasa de velocidad de cómputo (*hashrate* en Hashes por segundo).
* **¿Qué utilidad tiene?**  
  - Auditoría de seguridad y concienciación sobre la debilidad de contraseñas cortas o predecibles frente a ataques de diccionario.
  - Demostración práctica de por qué los hashes simples sin funciones de derivación lentas ni sal (*salt*) son susceptibles a ataques de reversión rápida.
* **Ejecución:**
  ```bash
  python ciberseguridad/Hash_fuerza_bruta.py
  ```

---

#### 3. Extractor y Limpiador de Metadatos EXIF
* **Archivo:** [`ciberseguridad/limpiador_de_metadatos.py`](ciberseguridad/limpiador_de_metadatos.py)
* **Dependencias:** `Pillow`
* **¿Qué hace?**  
  Inspecciona los metadatos EXIF incrustados en archivos fotográficos. Extrae información sensible como el fabricante y modelo de la cámara o smartphone, versión de software, fecha y hora exacta de captura, y coordenadas GPS de latitud/longitud (convirtiéndolas a grados decimales y generando un enlace directo a Google Maps). Adicionalmente, cuenta con una función de sanitización que crea una copia de la imagen reescribiendo únicamente la matriz de píxeles, eliminando por completo cualquier metadato.
* **¿Qué utilidad tiene?**  
  - **Privacidad y Seguridad Personal (Anti-Doxxing / OSINT):** Evita revelar inadvertidamente tu ubicación geográfica exacta, tu rutina o el modelo de tus dispositivos al compartir fotos en internet o redes sociales.
  - Análisis forense digital para verificar el origen y autenticidad temporal de una captura fotográfica.
* **Ejecución:**
  ```bash
  python ciberseguridad/limpiador_de_metadatos.py
  ```

---

#### 4. SpectraScan / NetRecon v3.0 (Escáner de Red y Auditor Web)
* **Archivo:** [`ciberseguridad/Puertos/SpectraScan.py`](ciberseguridad/Puertos/SpectraScan.py)
* **Dependencias:** Ninguna (Biblioteca estándar: `socket`, `ssl`, `concurrent.futures`, `urllib`).
* **¿Qué hace?**  
  Herramienta avanzada de reconocimiento de red y auditoría de seguridad perimetral para servidores y aplicaciones web:
  - **Escaneo de Puertos Multihilo:** Comprueba puertos TCP concurrentemente con medición de latencia en milisegundos y captura de banners de bienvenida o cabeceras de servidor. Incluye perfiles para infraestructura básica, desarrollo web, bases de datos o rangos manuales (ej. `20-100,443,8080`).
  - **Auditoría TLS/SSL:** Extrae el certificado de seguridad del host, nombres alternativos (SANs), emisor, período de validez y suite de cifrado activa.
  - **Auditoría de Cabeceras HTTP:** Revisa cabeceras de protección defensiva (`HSTS`, `CSP`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, etc.).
  - **Auditoría de Cookies y CORS:** Analiza la permisividad de orígenes cruzados (`Access-Control-Allow-Origin`) y comprueba que las cookies tengan las directivas de seguridad `Secure`, `HttpOnly` y `SameSite`.
  - **Gobernanza Web y Métodos:** Valida la redirección obligatoria de HTTP a HTTPS, detecta métodos HTTP habilitados (`OPTIONS`) y comprueba la disponibilidad de archivos públicos como `robots.txt`, `security.txt` y `sitemap.xml`.
  - **Exportación:** Permite guardar reportes consolidados en formato JSON estructurado.
* **¿Qué utilidad tiene?**  
  - Reconocimiento pasivo y activo en fases tempranas de pruebas de penetración (*pentesting*).
  - Verificación de políticas de seguridad en despliegues de producción y detección rápida de servicios expuestos por error.
* **Ejecución:**
  ```bash
  python ciberseguridad/Puertos/SpectraScan.py
  ```

---

### 🧰 Kit de Herramientas y Productividad

#### 5. Descargador de Videos y Playlists de YouTube
* **Archivo:** [`Kit_herramientas/Descargar_videos_youtube.py`](Kit_herramientas/Descargar_videos_youtube.py)
* **Dependencias:** `yt-dlp`, `imageio-ffmpeg`
* **¿Qué hace?**  
  Descarga videos individuales o listas de reproducción (*playlists*) completas de YouTube con la máxima calidad disponible de video y audio combinados en un contenedor `.mp4`. Detecta de forma inteligente ejecutables de `ffmpeg` instalados en el sistema (incluyendo instalaciones de WinGet y el paquete `imageio-ffmpeg`) y entornos de ejecución JavaScript (Node.js o Deno) para resolver las restricciones de YouTube.
* **¿Qué utilidad tiene?**  
  - Creación de respaldos offline de conferencias, material de estudio, cursos o tutoriales para acceder a ellos sin conexión a internet ni interrupciones publicitarias.
* **Ejecución:**
  ```bash
  python Kit_herramientas/Descargar_videos_youtube.py
  ```

---

#### 6. Escritor Automatizado de Mensajes (Auto-Typer)
* **Archivo:** [`Kit_herramientas/Escribir_mensajes.py`](Kit_herramientas/Escribir_mensajes.py)
* **Dependencias:** `pyautogui`
* **¿Qué hace?**  
  Espera 5 segundos para que el usuario coloque el cursor y el foco en el campo de texto o aplicación deseada. A continuación, simula pulsaciones de teclado automáticas escribiendo ráfagas de mensajes numerados y enviándolos mediante la tecla *Enter* con pausas controladas.
* **¿Qué utilidad tiene?**  
  - Automatización de pruebas de estrés en campos de entrada de formularios o aplicaciones de chat.
  - Envío secuencial y masivo de mensajes o comandos repetitivos sin intervención manual continua.
* **Ejecución:**
  ```bash
  python Kit_herramientas/Escribir_mensajes.py
  ```

---

#### 7. Generador de Códigos QR por Enlace
* **Archivo:** [`Kit_herramientas/Generador_de_QR_por_link.py`](Kit_herramientas/Generador_de_QR_por_link.py)
* **Dependencias:** `qrcode`, `Pillow`
* **¿Qué hace?**  
  Recibe cualquier enlace web o cadena de texto y genera una imagen PNG nítida con un código QR configurable con factores de corrección de error y colores corporativos (relleno naranja y fondo blanco).
* **¿Qué utilidad tiene?**  
  - Compartir de forma instantánea enlaces a sitios web, cartas y menús digitales, accesos a redes Wi-Fi o datos de contacto para ser leídos rápidamente con la cámara de cualquier teléfono móvil.
* **Ejecución:**
  ```bash
  python Kit_herramientas/Generador_de_QR_por_link.py
  ```

---

#### 8. Conversor de Texto a Voz (TTS con gTTS)
* **Archivo:** [`Kit_herramientas/Genera_y_poner_audio_por_texto.py`](Kit_herramientas/Genera_y_poner_audio_por_texto.py)
* **Dependencias:** `gTTS`
* **¿Qué hace?**  
  Convierte texto escrito en español a voz sintetizada natural usando la API de Google Text-to-Speech (gTTS). Genera un archivo `.mp3` con marca de tiempo en el nombre y lo reproduce de inmediato en el reproductor multimedia predeterminado del sistema operativo.
* **¿Qué utilidad tiene?**  
  - Accesibilidad digital para personas con dificultades visuales.
  - Creación rápida de pistas de narración o locución para videos, presentaciones o avisos audibles automáticos.
* **Ejecución:**
  ```bash
  python Kit_herramientas/Genera_y_poner_audio_por_texto.py
  ```

---

#### 9. Organizador Inteligente de Directorios (Smart Organizer)
* **Archivo:** [`Kit_herramientas/smart_organizer.py`](Kit_herramientas/smart_organizer.py)
* **Dependencias:** `streamlit` (requerido para la interfaz web)
* **¿Qué hace?**  
  Analiza cualquier directorio saturado (como la carpeta de *Descargas* o el *Escritorio*) y clasifica sus archivos automáticamente en subcarpetas según su extensión: Documentos, Imágenes, Comprimidos, Ejecutables, Código/Datos, Multimedia, Diseño CAD, Imágenes de Disco, etc.
  - **Modo Simulación (Dry Run):** Muestra qué archivos se moverían y a dónde sin alterar ningún fichero en el disco.
  - **Modo Centinela:** Monitorea en segundo plano el directorio cada ciertos segundos y organiza archivos nuevos automáticamente conforme van llegando.
  - **Función Deshacer (Undo):** Permite revertir la última organización en cualquier momento devolviendo los archivos a su lugar original gracias a un historial persistente en JSON.
  - **Doble Interfaz:** Dispone de un menú interactivo en consola CLI y una aplicación web moderna con gráficos y métricas desarrollada en **Streamlit**.
* **¿Qué utilidad tiene?**  
  - Elimina el desorden crónico en carpetas de descargas y escritorios sin riesgo de pérdida de datos ni sobreescritura accidental (gestiona colisiones de nombres automáticamente).
* **Ejecución en consola (CLI):**
  ```bash
  python Kit_herramientas/smart_organizer.py
  ```
* **Ejecución en interfaz Web (Streamlit):**
  ```bash
  streamlit run Kit_herramientas/smart_organizer.py
  ```

---

#### 10. Optimizador de PDFs e Imágenes y Removedor de Fondos por IA
* **Archivo:** [`Kit_herramientas/Compresor_removedor_fondos/Compresor_removedor_fondos.py`](Kit_herramientas/Compresor_removedor_fondos/Compresor_removedor_fondos.py)
* **Dependencias:** `pymupdf`, `Pillow`, `rembg`, `streamlit`
* **¿Qué hace?**  
  Suite completa de optimización visual y procesamiento de archivos multimedia:
  - **Compresión de PDFs:** Reescribe la estructura interna y reduce la resolución/peso de las imágenes del documento con 3 niveles seleccionables (Baja, Media y Alta compresión).
  - **Compresión de Imágenes:** Optimiza ficheros JPG, PNG y WEBP aplicando compresión progresiva y cuantización inteligente de colores sin pérdida notable de calidad visual.
  - **Recorte de Fondos por IA (Turbo):** Utiliza redes neuronales (modelo `u2netp` a través de `rembg`) para aislar el sujeto principal y remover el fondo de una imagen, generando un PNG transparente a alta velocidad.
  - **Procesamiento por Lotes:** Procesa directorios enteros de imágenes y PDFs calculando el porcentaje total de espacio ahorrado.
  - **Interfaz Web Interactiva:** Incluye soporte completo para ejecutarse como una aplicación web con Streamlit con carga interactiva, previsualizaciones antes/después y descarga en ZIP.
* **¿Qué utilidad tiene?**  
  - Reducir el peso de documentos o imágenes para cumplir con los límites de adjuntos en correos electrónicos o plataformas institucionales.
  - Preparar catálogos de comercio electrónico, fotos de perfil o recursos de diseño gráfico sin fondo de manera instantánea.
* **Ejecución en consola (CLI):**
  ```bash
  python Kit_herramientas/Compresor_removedor_fondos/Compresor_removedor_fondos.py
  ```
* **Ejecución en interfaz Web (Streamlit):**
  ```bash
  streamlit run Kit_herramientas/Compresor_removedor_fondos/Compresor_removedor_fondos.py -- --webui
  ```

---

#### 11. Juntador de Archivos PDF
* **Archivo:** [`Kit_herramientas/Juntador_pdf/Juntador_pdfs.py`](Kit_herramientas/Juntador_pdf/Juntador_pdfs.py)
* **Dependencias:** `pypdf`
* **¿Qué hace?**  
  Examina el directorio donde se ejecuta, identifica todos los archivos con extensión `.pdf`, los ordena alfabéticamente y los fusiona página por página en un único documento maestro de salida (`power_BI.pdf`).
* **¿Qué utilidad tiene?**  
  - Agrupar reportes mensuales, facturas dispersas, capítulos de libros, recibos o escaneos individuales en un solo archivo PDF unificado y fácil de compartir o imprimir.
* **Ejecución:**
  ```bash
  python Kit_herramientas/Juntador_pdf/Juntador_pdfs.py
  ```

---

### 🧬 Curiosidades y Algoritmos

#### 12. Simulador del Juego de la Vida de Conway
* **Archivo:** [`Programas_para_curiosidad/Simulador_de_vida_cow.py`](Programas_para_curiosidad/Simulador_de_vida_cow.py)
* **Dependencias:** Ninguna (Biblioteca estándar: `os`, `time`, `random`).
* **¿Qué hace?**  
  Implementación en consola del célebre autómata celular creado por el matemático John Horton Conway. Crea una cuadrícula bidimensional de células vivas (`██`) y muertas, aplicando en cada iteración temporal las cuatro reglas clásicas de Conway:
  1. Cualquier célula viva con menos de 2 vecinos vivos muere (subpoblación).
  2. Cualquier célula viva con 2 o 3 vecinos vivos sobrevive para la siguiente generación.
  3. Cualquier célula viva con más de 3 vecinos vivos muere (sobrepoblación).
  4. Cualquier célula muerta con exactamente 3 vecinos vivos se convierte en una célula viva (reproducción).
* **¿Qué utilidad tiene?**  
  - Fines educativos, divulgación científica y exploración visual de la teoría del caos, la emergencia y los sistemas deterministas complejos a partir de reglas simples.
* **Ejecución:**
  ```bash
  python Programas_para_curiosidad/Simulador_de_vida_cow.py
  ```

---

## 📋 Resumen Rápido de Dependencias por Programa

| Programa | Ruta | Dependencias Externas |
| :--- | :--- | :--- |
| **Descargador de Videos YouTube** | `Kit_herramientas/Descargar_videos_youtube.py` | `yt-dlp`, `imageio-ffmpeg` |
| **Limpiador de Metadatos EXIF** | `ciberseguridad/limpiador_de_metadatos.py` | `Pillow` |
| **Escritor de Mensajes (Auto-Typer)** | `Kit_herramientas/Escribir_mensajes.py` | `pyautogui` |
| **Generador de Códigos QR** | `Kit_herramientas/Generador_de_QR_por_link.py` | `qrcode`, `Pillow` |
| **Generador de Audio (TTS)** | `Kit_herramientas/Genera_y_poner_audio_por_texto.py` | `gTTS` |
| **Organizador Inteligente** | `Kit_herramientas/smart_organizer.py` | `streamlit` |
| **Optimizador PDFs / Imágenes** | `Kit_herramientas/Compresor_removedor_fondos/...` | `pymupdf`, `Pillow`, `rembg`, `streamlit` |
| **Juntador de PDFs** | `Kit_herramientas/Juntador_pdf/Juntador_pdfs.py` | `pypdf` |
| **Cifrador de Mensajes (XOR)** | `ciberseguridad/Cifrador_de_mensajes.py` | *Ninguna (Estándar)* |
| **Cracker SHA-256** | `ciberseguridad/Hash_fuerza_bruta.py` | *Ninguna (Estándar)* |
| **SpectraScan / NetRecon** | `ciberseguridad/Puertos/SpectraScan.py` | *Ninguna (Estándar)* |
| **Juego de la Vida de Conway** | `Programas_para_curiosidad/Simulador_de_vida_cow.py` | *Ninguna (Estándar)* |

---

## 📄 Licencia

Este repositorio está protegido bajo los términos de la licencia [LICENSE](LICENSE) incluida en la raíz del proyecto.
