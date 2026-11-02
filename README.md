# 🛠️ Programas Útiles (Python Utility Toolkit)

Una colección completa y modular de scripts y herramientas en Python diseñadas para **auditoría de ciberseguridad**, **automatización de tareas cotidianas**, **gestión de procesos y redes**, **procesamiento de medios y documentos**, y **simulaciones algorítmicas**.

Cada herramienta cuenta con su propia terminal interactiva de consola con menús de opciones y una **interfaz gráfica interactiva (Web)** lista para usar. Además, las herramientas que procesan o generan ficheros disponen de carpetas dedicadas para leer archivos de entrada y almacenar los resultados generados.

---

## 📁 Estructura del Repositorio

```text
Programas_utiles/
├── ciberseguridad/
│   ├── Puertos/
│   │   ├── ruta_a_escanear                    # Archivo auxiliar de objetivo para escaneo
│   │   └── SpectraScan.py                     # Escáner de red, puertos y auditoría web
│   ├── Cifrador_de_mensajes.py                # Cifrado y descifrado simétrico por XOR
│   ├── Hash_fuerza_bruta.py                   # Cracker de hashes SHA-256 por diccionario
│   └── limpiador_de_metadatos.py              # Extractor y sanitizador de metadatos EXIF (GPS, cámara)
├── Kit_herramientas/
│   ├── Auditor_procesos_puertos/
│   │   ├── reportes/                          # Carpeta donde se generan reportes JSON
│   │   └── Auditor_procesos_puertos.py        # Auditor de procesos, puertos y terminación con psutil
│   ├── Compresor_removedor_fondos/
│   │   ├── new images/                        # Carpeta de salida predeterminada
│   │   └── Compresor_removedor_fondos.py      # Optimizador de PDFs/imágenes y recorte de fondos por IA
│   ├── Convertidor_tablas/
│   │   ├── tablas_entrada/                    # Carpeta para colocar archivos CSV, Excel o PDF a leer
│   │   ├── tablas_generadas/                  # Carpeta donde se generan las tablas LaTeX y Markdown
│   │   └── Convertidor_tablas.py              # Conversor de tablas a LaTeX y Markdown
│   ├── Juntador_pdf/
│   │   └── Juntador_pdfs.py                   # Fusión y unión secuencial de documentos PDF
│   ├── Ping_Logger/
│   │   ├── hosts_entrada/                     # Carpeta de lectura con archivo hosts.txt
│   │   ├── registros/                         # Carpeta donde se generan logs CSV y reportes
│   │   └── Ping_Logger.py                     # Monitor continuo de latencia, pérdidas y microcortes
│   ├── Respaldos_incrementales/
│   │   ├── archivos_a_respaldar/              # Carpeta de lectura para colocar archivos a respaldar
│   │   ├── respaldos/                         # Carpeta donde se generan los respaldos .zip / .tar.gz
│   │   └── Respaldos_incrementales.py         # Copias de seguridad completas e incrementales por mtime
│   ├── Descargar_videos_youtube.py            # Descarga de videos individuales y playlists de YouTube
│   ├── Escribir_mensajes.py                   # Automatización de escritura por teclado (Auto-Typer)
│   ├── Generador_de_QR_por_link.py            # Generación de códigos QR personalizados
│   ├── Genera_y_poner_audio_por_texto.py      # Conversión de texto a voz (TTS) y reproducción automática
│   └── smart_organizer.py                     # Organizador inteligente de directorios (CLI y Web UI)
├── Programas_para_curiosidad/
│   └── Simulador_de_vida_cow.py               # Autómata celular del Juego de la Vida de Conway
├── requirements.txt                           # Lista estructurada de dependencias externas
├── instalar_dependencias.py                   # Menú interactivo para instalar dependencias selectivas o totales
├── LICENSE                                    # Licencia del proyecto
└── README.md                                  # Documentación completa y guía de uso
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
- **Opción `[ 1]`**: Instala **todas** las dependencias del proyecto completo en una sola operación.
- **Opciones `[ 2]` a `[13]`**: Permiten seleccionar un programa específico e instalar **únicamente** las librerías que ese programa necesita, evitando descargas innecesarias.
- **Opciones `[14]` a `[17]`**: Si eliges un programa que no necesita librerías externas (como `SpectraScan.py` o `Cifrador_de_mensajes.py`), el instalador te informará que funciona al 100% con la biblioteca estándar sin descargas.

### Opción 2: Instalación Tradicional con Pip

Si prefieres instalar todas las librerías de una sola vez mediante `pip`:

```bash
pip install -r requirements.txt
```

---

## 📖 Catálogo Detallado de Programas

A continuación se detalla cada programa incluido en la suite, explicando su funcionamiento técnico, su utilidad práctica, sus carpetas de lectura/generación, dependencias y cómo ejecutarlo.

---

### 🧰 Kit de Herramientas y Productividad

#### 1. Convertidor de Tablas PDF / CSV / Excel a LaTeX o Markdown
* **Archivo:** [`Kit_herramientas/Convertidor_tablas/Convertidor_tablas.py`](Kit_herramientas/Convertidor_tablas/Convertidor_tablas.py)
* **Carpetas del programa:**
  - 📥 **Lectura:** `tablas_entrada/` (donde colocas los archivos CSV, Excel o PDF a procesar).
  - 📤 **Generación:** `tablas_generadas/` (donde se guardan los archivos `.tex` y `.md` generados).
* **Dependencias:** `pandas`, `openpyxl`, `pymupdf`, `tabulate`, `streamlit`
* **¿Qué hace?**  
  Extrae tablas contenidas en archivos CSV (con autodetección de delimitador: coma, punto y coma, tabulación o barra vertical), libros de cálculo Excel (`.xlsx`) y documentos PDF (mediante el motor de análisis de tablas de PyMuPDF). Convierte la estructura tabular automáticamente a:
  - **Bloques LaTeX:** Con formato estándar (`\begin{tabular}{|c|c|...}`) o estilo académico `booktabs` (`\toprule`, `\midrule`, `\bottomrule`), aplicando escape preventivo de caracteres reservados de LaTeX (`&`, `%`, `$`, `#`, `_`, `{`, `}`, `~`, `^`).
  - **Tablas Markdown:** Formato compatible con GitHub Flavored Markdown (`|` y filas alineadas).
  - **Modo Lote:** Procesa todos los archivos dentro de `tablas_entrada/` y exporta versiones en ambos formatos.
  - **Vista Previa en Terminal:** Muestra la tabla formateada en consola usando `tabulate`.
  - **Interfaz Interactiva (Web):** Carga interactiva mediante navegador con previsualización, selector de estilo, código copiable y botón de descarga directa.
* **¿Qué utilidad tiene?**  
  Ahorra horas de trabajo manual al redactar tesis, reportes técnicos, papers académicos o documentación en Markdown/LaTeX a partir de datos exportados en hojas de cálculo o tablas incrustadas en PDFs.
* **Ejecución en consola (CLI):**
  ```bash
  python Kit_herramientas/Convertidor_tablas/Convertidor_tablas.py
  ```
* **Ejecución en interfaz web:**
  ```bash
  python Kit_herramientas/Convertidor_tablas/Convertidor_tablas.py
  # Selecciona la opción [9] Interfaz interactiva (Web)
  ```

---

#### 2. Auditor de Procesos y Puertos Locales
* **Archivo:** [`Kit_herramientas/Auditor_procesos_puertos/Auditor_procesos_puertos.py`](Kit_herramientas/Auditor_procesos_puertos/Auditor_procesos_puertos.py)
* **Carpetas del programa:**
  - 📤 **Generación:** `reportes/` (donde se exportan los reportes completos del estado de red en formato JSON).
* **Dependencias:** `psutil`, `pandas`, `altair`, `streamlit`
* **¿Qué hace?**  
  Herramienta de diagnóstico de sistema y red local basada en `psutil`:
  - **Listado Completo:** Muestra todas las conexiones activas con protocolo (TCP/UDP), IP local, puerto, estado (`LISTEN`, `ESTABLISHED`), PID, nombre del proceso ejecutable, memoria RAM consumida y porcentaje de CPU.
  - **Consulta Específica:** Ingresa un número de puerto (ej. 3000, 5173, 5432, 8080) y localiza al instante el proceso exacto que lo bloquea.
  - **Escaneo de Puertos de Desarrollo:** Revisa en bloque los puertos más comunes (React, Vite, Angular, Flask, Django, PostgreSQL, Redis, Mongo, Tomcat).
  - **Top Consumo:** Rankings del Top 15 de procesos que más RAM y CPU están utilizando en tiempo real.
  - **Terminación de Procesos (Kill):** Permite finalizar procesos directamente por PID o liberar un puerto ocupado con confirmación de seguridad.
  - **Modo Vigilante:** Monitoreo dinámico continuo en terminal que refresca cada N segundos.
  - **Exportación JSON:** Guarda un informe con fecha y hora en la carpeta `reportes/`.
  - **Interfaz Interactiva (Web):** Panel de control web con filtros, gráficos de barras de consumo, semáforos de disponibilidad de puertos de desarrollo y botones para matar procesos.
* **¿Qué utilidad tiene?**  
  Esencial para desarrolladores cuando un servidor local o base de datos falla al iniciar con el clásico error `EADDRINUSE: port already in use`, permitiendo identificar y cerrar el proceso bloqueador en segundos sin tener que buscar comandos manuales en el Administrador de Tareas.
* **Ejecución en consola (CLI):**
  ```bash
  python Kit_herramientas/Auditor_procesos_puertos/Auditor_procesos_puertos.py
  ```
* **Ejecución en interfaz web:**
  ```bash
  python Kit_herramientas/Auditor_procesos_puertos/Auditor_procesos_puertos.py
  # Selecciona la opción [11] Interfaz interactiva (Web)
  ```

---

#### 3. Automatizador de Respaldos Incrementales
* **Archivo:** [`Kit_herramientas/Respaldos_incrementales/Respaldos_incrementales.py`](Kit_herramientas/Respaldos_incrementales/Respaldos_incrementales.py)
* **Carpetas del programa:**
  - 📥 **Lectura:** `archivos_a_respaldar/` (carpeta predeterminada para depositar los archivos y carpetas a respaldar, con soporte también para rutas personalizadas).
  - 📤 **Generación:** `respaldos/` (donde se generan los archivos `.zip` o `.tar.gz`, el manifiesto `.backup_manifest.json` y la configuración).
* **Dependencias:** `streamlit` (módulos `zipfile`, `tarfile`, `json`, `hashlib` son estándar).
* **¿Qué hace?**  
  Sistema de copias de seguridad inteligente para directorios de trabajo:
  - **Respaldos Completos:** Empaqueta y comprime la totalidad de los archivos en formato `.zip` o `.tar.gz`.
  - **Respaldos Incrementales:** Compara la fecha y hora de modificación (`mtime`) de cada archivo contra un manifiesto persistente (`.backup_manifest.json`). Únicamente incluye en el nuevo archivo los ficheros modificados o añadidos desde la última copia, ahorrando tiempo y almacenamiento.
  - **Verificación de Integridad:** Comprueba la consistencia de cualquier archivo de respaldo, listando su estructura y tamaño total.
  - **Restauración:** Extrae respaldos completos o incrementales en el directorio indicado por el usuario.
  - **Exclusiones Configurables:** Filtra automáticamente carpetas pesadas prescindibles (`node_modules`, `__pycache__`, `.venv`, `.git`, archivos `.pyc`, `.env`).
  - **Rotación Automática:** Conserva los últimos *N* respaldos y purga los más antiguos para evitar que el disco se sature.
  - **Interfaz Interactiva (Web):** Interfaz visual para seleccionar rutas, elegir formato, ver el historial de backups y restaurar archivos.
* **¿Qué utilidad tiene?**  
  Protección contra pérdida de código, proyectos o documentos críticos mediante copias frecuentes y ligeras que no consumen espacio innecesario al respaldar sólo lo que ha cambiado.
* **Ejecución en consola (CLI):**
  ```bash
  python Kit_herramientas/Respaldos_incrementales/Respaldos_incrementales.py
  ```
* **Ejecución en interfaz web:**
  ```bash
  python Kit_herramientas/Respaldos_incrementales/Respaldos_incrementales.py
  # Selecciona la opción [10] Interfaz interactiva (Web)
  ```

---

#### 4. Monitor de Latencia y Caídas de Red (Ping Logger)
* **Archivo:** [`Kit_herramientas/Ping_Logger/Ping_Logger.py`](Kit_herramientas/Ping_Logger/Ping_Logger.py)
* **Carpetas del programa:**
  - 📥 **Lectura:** `hosts_entrada/` (contiene `hosts.txt` para cargar listas masivas de IPs o dominios a auditar).
  - 📤 **Generación:** `registros/` (donde se generan los ficheros `.csv` con cada ping registrado y los reportes de disponibilidad).
* **Dependencias:** `pandas`, `streamlit` (módulos `subprocess`, `csv`, `socket`, `concurrent.futures` son estándar).
* **¿Qué hace?**  
  Monitor continuo de calidad de conexión y diagnóstico de estabilidad de red:
  - **Monitoreo Continuo:** Envía paquetes ICMP regulares a un host y muestra en consola latencia actual, promedio acumulado, porcentaje de pérdida de paquetes y estado.
  - **Registro Histórico en CSV:** Guarda cada ping con marca de tiempo precisa (`YYYY-MM-DD HH:MM:SS`), latencia en ms, indicador de pérdida (0/1) y estado (`OK`/`TIMEOUT`/`ERROR`).
  - **Detección de Microcortes:** Modo centinela con umbral de latencia configurable que alerta sonoramente o por consola y aísla cada corte de internet ocurrido.
  - **Monitoreo Multihilo:** Audita múltiples servidores simultáneamente (Google DNS, Cloudflare, gateway local, etc.) leyendo la lista desde `hosts_entrada/hosts.txt`.
  - **Estadísticas y Análisis:** Calcula latencia mínima, media, máxima, percentil 95 (P95) y la ventana de caída más larga de cualquier CSV generado.
  - **Utilidades de Red:** Incluye *traceroute* y resolución DNS con medición de tiempo de respuesta.
  - **Interfaz Interactiva (Web):** Monitor web en tiempo real con gráficos de línea interactivos de latencia, tarjetas de métricas, visor del historial de registros y descarga de CSVs.
* **¿Qué utilidad tiene?**  
  Demostrar microcortes intermitentes ante proveedores de internet (ISP), verificar la estabilidad de conexiones para streaming o gaming, y auditar la latencia hacia servidores remotos.
* **Ejecución en consola (CLI):**
  ```bash
  python Kit_herramientas/Ping_Logger/Ping_Logger.py
  ```
* **Ejecución en interfaz web:**
  ```bash
  python Kit_herramientas/Ping_Logger/Ping_Logger.py
  # Selecciona la opción [9] Interfaz interactiva (Web)
  ```

---

#### 5. Descargador de Videos y Playlists de YouTube
* **Archivo:** [`Kit_herramientas/Descargar_videos_youtube.py`](Kit_herramientas/Descargar_videos_youtube.py)
* **Carpetas del programa:**
  - 📤 **Generación:** `videos_descargado/` (donde se descargan los videos MP4).
* **Dependencias:** `yt-dlp`, `imageio-ffmpeg`
* **¿Qué hace?**  
  Descarga videos individuales o listas de reproducción (*playlists*) completas de YouTube con la máxima calidad disponible de video y audio combinados en contenedor `.mp4`. Detecta de forma inteligente ejecutables de `ffmpeg` instalados en el sistema o vía `imageio-ffmpeg` y motores JS (Node.js o Deno).
* **¿Qué utilidad tiene?**  
  Respaldo sin conexión de conferencias, cursos o material educativo sin anuncios ni dependencia de internet.
* **Ejecución:**
  ```bash
  python Kit_herramientas/Descargar_videos_youtube.py
  ```

---

#### 6. Escritor Automatizado de Mensajes (Auto-Typer)
* **Archivo:** [`Kit_herramientas/Escribir_mensajes.py`](Kit_herramientas/Escribir_mensajes.py)
* **Dependencias:** `pyautogui`
* **¿Qué hace?**  
  Da un margen inicial de 5 segundos para situar el foco en la aplicación deseada y a continuación simula pulsaciones de teclado automáticas escribiendo y enviando secuencias de texto con pausas controladas.
* **¿Qué utilidad tiene?**  
  Automatización de pruebas de estrés en entradas de formularios o envío masivo y controlado de mensajes o comandos repetitivos.
* **Ejecución:**
  ```bash
  python Kit_herramientas/Escribir_mensajes.py
  ```

---

#### 7. Generador de Códigos QR por Enlace
* **Archivo:** [`Kit_herramientas/Generador_de_QR_por_link.py`](Kit_herramientas/Generador_de_QR_por_link.py)
* **Dependencias:** `qrcode`, `Pillow`
* **¿Qué hace?**  
  Recibe cualquier enlace web o cadena de texto y genera una imagen PNG nítida con un código QR configurable con colores personalizados y corrección de errores.
* **¿Qué utilidad tiene?**  
  Compartir de forma instantánea accesos Wi-Fi, menús digitales o enlaces para ser leídos con cámaras de teléfonos móviles.
* **Ejecución:**
  ```bash
  python Kit_herramientas/Generador_de_QR_por_link.py
  ```

---

#### 8. Conversor de Texto a Voz (TTS con gTTS)
* **Archivo:** [`Kit_herramientas/Genera_y_poner_audio_por_texto.py`](Kit_herramientas/Genera_y_poner_audio_por_texto.py)
* **Dependencias:** `gTTS`
* **¿Qué hace?**  
  Convierte texto escrito en español a voz sintetizada natural usando la API de Google Text-to-Speech (gTTS), guarda el audio `.mp3` con marca de tiempo y lo reproduce inmediatamente en el reproductor del sistema.
* **¿Qué utilidad tiene?**  
  Accesibilidad digital y creación rápida de pistas de narración o locución para videos y avisos sonoros.
* **Ejecución:**
  ```bash
  python Kit_herramientas/Genera_y_poner_audio_por_texto.py
  ```

---

#### 9. Organizador Inteligente de Directorios (Smart Organizer)
* **Archivo:** [`Kit_herramientas/smart_organizer.py`](Kit_herramientas/smart_organizer.py)
* **Dependencias:** `streamlit`
* **¿Qué hace?**  
  Clasifica archivos de carpetas caóticas (Descargas, Escritorio) en categorías (Documentos, Imágenes, Ejecutables, Código, etc.). Incluye modo simulación (*Dry Run*), modo centinela en tiempo real, función deshacer (*Undo*) e interfaz web en Streamlit.
* **¿Qué utilidad tiene?**  
  Mantener carpetas limpias y ordenadas automáticamente evitando la acumulación de ficheros sueltos.
* **Ejecución:**
  ```bash
  python Kit_herramientas/smart_organizer.py
  ```

---

#### 10. Optimizador de PDFs e Imágenes y Removedor de Fondos por IA
* **Archivo:** [`Kit_herramientas/Compresor_removedor_fondos/Compresor_removedor_fondos.py`](Kit_herramientas/Compresor_removedor_fondos/Compresor_removedor_fondos.py)
* **Carpetas del programa:**
  - 📤 **Generación:** `new images/`
* **Dependencias:** `pymupdf`, `Pillow`, `rembg`, `streamlit`
* **¿Qué hace?**  
  Comprime documentos PDF e imágenes (JPG, PNG, WEBP) reduciendo notablemente su tamaño, recorta fondos mediante IA con el modelo `u2netp`, permite procesamiento por lotes y ofrece interfaz web interactiva.
* **¿Qué utilidad tiene?**  
  Ajustar archivos pesados para envíos por correo electrónico y generar recursos gráficos transparentes para catálogos y diseño.
* **Ejecución:**
  ```bash
  python Kit_herramientas/Compresor_removedor_fondos/Compresor_removedor_fondos.py
  ```

---

#### 11. Juntador de Archivos PDF
* **Archivo:** [`Kit_herramientas/Juntador_pdf/Juntador_pdfs.py`](Kit_herramientas/Juntador_pdf/Juntador_pdfs.py)
* **Dependencias:** `pypdf`
* **¿Qué hace?**  
  Escanea todos los archivos `.pdf` de la carpeta, los ordena alfabéticamente y los fusiona en un único documento maestro (`power_BI.pdf`).
* **¿Qué utilidad tiene?**  
  Unificar reportes dispersos, facturas, comprobantes o capítulos en un único documento listo para imprimir o enviar.
* **Ejecución:**
  ```bash
  python Kit_herramientas/Juntador_pdf/Juntador_pdfs.py
  ```

---

### 🛡️ Ciberseguridad y Auditoría

#### 12. Cifrador de Mensajes (XOR)
* **Archivo:** [`ciberseguridad/Cifrador_de_mensajes.py`](ciberseguridad/Cifrador_de_mensajes.py)
* **Dependencias:** Ninguna (Biblioteca estándar).
* **¿Qué hace?** Cifra y descifra mensajes de texto mediante el algoritmo simétrico XOR con clave secreta y salida hexadecimal.
* **¿Qué utilidad tiene?** Comprensión práctica de operaciones a nivel de bit y ofuscación rápida de textos confidenciales.
* **Ejecución:** `python ciberseguridad/Cifrador_de_mensajes.py`

#### 13. Cracker de Hashes SHA-256 por Fuerza Bruta / Diccionario
* **Archivo:** [`ciberseguridad/Hash_fuerza_bruta.py`](ciberseguridad/Hash_fuerza_bruta.py)
* **Dependencias:** Ninguna (Biblioteca estándar: `hashlib`, `time`, `typing`).
* **¿Qué hace?** Aplica fuerza bruta y ataque de diccionario contra un hash SHA-256 calculando el tiempo de cómputo y hashrate exacto.
* **¿Qué utilidad tiene?** Auditoría de fortaleza de contraseñas y demostración didáctica de la necesidad de sales (*salts*).
* **Ejecución:** `python ciberseguridad/Hash_fuerza_bruta.py`

#### 14. Extractor y Limpiador de Metadatos EXIF
* **Archivo:** [`ciberseguridad/limpiador_de_metadatos.py`](ciberseguridad/limpiador_de_metadatos.py)
* **Dependencias:** `Pillow`
* **¿Qué hace?** Lee coordenadas GPS, modelo de dispositivo y fecha de captura en imágenes, y genera copias sanitizadas sin metadatos.
* **¿Qué utilidad tiene?** Protección de la privacidad personal antes de subir fotografías a internet (prevención de doxxing).
* **Ejecución:** `python ciberseguridad/limpiador_de_metadatos.py`

#### 15. SpectraScan / NetRecon v3.0 (Escáner de Red y Auditor Web)
* **Archivo:** [`ciberseguridad/Puertos/SpectraScan.py`](ciberseguridad/Puertos/SpectraScan.py)
* **Dependencias:** Ninguna (Biblioteca estándar: `socket`, `ssl`, `concurrent.futures`, `urllib`).
* **¿Qué hace?** Escáner multihilo de puertos TCP con detección de banners, análisis de certificados SSL/TLS, auditoría de cabeceras de seguridad HTTP, cookies, CORS y gobernanza web (`robots.txt`, `security.txt`).
* **¿Qué utilidad tiene?** Auditoría defensiva y reconocimiento de superficie de ataque en infraestructura y servidores web.
* **Ejecución:** `python ciberseguridad/Puertos/SpectraScan.py`

---

### 🧬 Curiosidades y Algoritmos

#### 16. Simulador del Juego de la Vida de Conway
* **Archivo:** [`Programas_para_curiosidad/Simulador_de_vida_cow.py`](Programas_para_curiosidad/Simulador_de_vida_cow.py)
* **Dependencias:** Ninguna (Biblioteca estándar: `os`, `time`, `random`).
* **¿Qué hace?** Ejecuta en consola el autómata celular de Conway sobre una matriz bidimensional animada en tiempo real.
* **¿Qué utilidad tiene?** Demostración visual de sistemas complejos, emergencia algorítmica y autoorganización.
* **Ejecución:** `python Programas_para_curiosidad/Simulador_de_vida_cow.py`

---

## 📋 Resumen de Dependencias por Programa

| Programa | Ubicación | Dependencias Externas |
| :--- | :--- | :--- |
| **Convertidor de Tablas** | `Kit_herramientas/Convertidor_tablas/...` | `pandas`, `openpyxl`, `pymupdf`, `tabulate`, `streamlit` |
| **Auditor de Procesos y Puertos** | `Kit_herramientas/Auditor_procesos_puertos/...` | `psutil`, `pandas`, `altair`, `streamlit` |
| **Respaldos Incrementales** | `Kit_herramientas/Respaldos_incrementales/...` | `streamlit` |
| **Monitor de Latencia (Ping Logger)** | `Kit_herramientas/Ping_Logger/...` | `pandas`, `streamlit` |
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
