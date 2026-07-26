![AudioDucker Banner](assets/banner.png)

# 🎵 AudioDucker v2.01 para Windows (Windows 10 / Windows 11)

**AudioDucker** es una aplicación inteligente diseñada específicamente para **Windows 10 y Windows 11** que atenúa automáticamente el volumen de tus reproductores de música y multimedia (**Spotify**, **Apple Music**, **VLC**, navegadores, etc.) **de forma simultánea** cuando detecta que otras aplicaciones (**Discord**, **Chrome**, **Firefox**, **Zoom**, **Telegram**, **OBS**, etc.) o tu **Micrófono** están **emitiendo sonido**.

A diferencia de otros programas convencionales, AudioDucker utiliza las APIs de sonido nativas de Windows (WASAPI / PyCAW) para medir los **picos de volumen reales**. Si Chrome o Discord están abiertos pero en silencio, las aplicaciones no bajarán de volumen. Solo se atenuarán en el instante exacto en que comiencen a reproducir audio por encima del umbral configurado o cuando hables por tu micrófono.

---

## ✨ Novedades y Características en la Versión 2.01

- 🗂️ **Navegación con Barra Lateral (Sidebar UI)**: Interfaz oscura moderna dividida en pestañas claras:
  - 🎯 **Apps Objetivo**: Elige qué programas (Spotify, Apple Music, VLC, etc.) sufrirán la bajada de volumen simultánea.
  - 📱 **Apps Activadoras**: Asigna el nivel de bajada y el umbral de sensibilidad para Discord, Chrome, Zoom, etc.
  - 🎤 **Micrófono**: Activa/desactiva la atenuación por voz con calibrador de ruido en tiempo real.
  - ⚙️ **Transición & Tiempos**: Ajusta la velocidad del desvanecimiento (fade in/out) y los tiempos de liberación tras el silencio.
- 🎚️ **Sensibilidad / Umbral de Activación Individual (`trigger_threshold`)**: Configura para cada app activadora qué tanto volumen debe emitir para activar la bajada. Permite ignorar sonidos pequeños o notificaciones bajas y activarse solo cuando haya audios fuertes.
- 📂 **Menú Desplegable (Acordeón) para Apps Activadoras**: Vista compacta de 1 fila por app con botón `⚙️ Opciones 🔻` para expandir/ocultar suavemente los sliders y controles.
- 🔊 **Medidores de Intensidad en Tiempo Real**: Barras dinámicas de picos (`Sonido actual: X%`) con indicadores de estado (🟢 Superando umbral, 🟠 Sonido bajo - no activa, ⚪ En silencio).
- 📌 **Minimizado a la Bandeja de Sistema (Iconos Ocultos / System Tray)**: Al cerrar o minimizar, el programa se oculta de la barra de tareas y sigue funcionando en segundo plano junto al reloj de Windows.
- 🍏 **Soporte UWP y Sub-Procesos (Apple Music / Microsoft Store)**: Mapeo automático `Shell.Application` de accesos directos `.lnk` a `.exe` reales y control agrupado para aplicaciones con sub-procesos secundarios (como `ampapp.exe` o `amplibraryagent.exe` en Apple Music).
- 🔄 **Herramientas de Servicio Rápido**:
  - `🔄 Reiniciar Servicio`: Recarga la configuración e reinicia el motor sin reiniciar la ventana.
  - `🔍 Escanear Sonidos`: Abre una ventana en vivo que detecta qué programas están sonando en tu PC para agregarlos con 1 clic.
- 🚫 **Sliders Protegidos contra Scroll**: Las barras de volumen (`CTkSlider`) no cambian accidentalmente al usar la rueda del ratón.

---

## 💡 Tips para Utilizar el Detector de Audio y Resolver Problemas

### 1. 🎚️ Cómo Calibrar la Sensibilidad de Sonido (Evitar activaciones por sonidos pequeños)
- Ve a la pestaña **`📱 Apps Activadoras`** y despliega **`⚙️ Opciones 🔻`** en la app deseada (ej. Discord).
- Mientras hablas o suena el audio de esa app, observa la barra **`Sonido actual: X%`**.
- Ajusta la **Sensibilidad / Umbral (`Activar si sonido > X%`)**:
  - Si fijas el umbral en **10%** y Discord produce un sonido suave de 3%, el estado mostrará `🟠 SONIDO BAJO - NO ACTIVA` y tu música **no se bajará**.
  - Cuando alguien hable fuerte y supere el 10%, el estado cambiará a `🟢 SUPERANDO UMBRAL` y la música **se atenuará de inmediato**.

### 2. 🔍 Usar el Escáner de Audio en Vivo (`🔍 Escanear Sonidos`)
Si tienes una aplicación abierta (como Apple Music, WhatsApp o un juego) y no estás seguro de cuál es el archivo ejecutable `.exe` real que emite el sonido:
1. Pon a reproducir música o sonido en la aplicación.
2. En AudioDucker, haz clic en **`🔍 Escanear Sonidos`** en el menú lateral izquierdo.
3. Se abrirá una ventana que mostrará en tiempo real todos los procesos que están generando audio en Windows en ese instante.
4. Haz clic en **`🎯 Asignar Objetivo`** o **`📱 Asignar Activadora`** al lado del proceso detectado para añadirlo automáticamente a tu lista.

### 3. 📁 Cómo agregar accesos directos de la Tienda de Windows (`shell:AppsFolder`)
Si deseas agregar accesos directos del Escritorio o apps de la Microsoft Store:
1. Presiona la combinación de teclas **`Win` + `R`** en tu teclado.
2. Escribe el comando **`shell:AppsFolder`** y presiona **Enter**.
3. Se abrirá la carpeta con todas tus aplicaciones de Windows.
4. Haz clic derecho sobre la aplicación deseada (ej. Spotify, Apple Music o WhatsApp) y elige 👉 **Crear acceso directo** *(en el Escritorio)*.
5. En AudioDucker, haz clic en **`📁 Agregar App (.exe)`** y selecciona el acceso directo `.lnk` del Escritorio. ¡AudioDucker identificará automáticamente el archivo `.exe` interno!

### 4. 📌 Dejar AudioDucker en los Iconos Ocultos
- Para evitar ocupar espacio en tu barra de tareas, haz clic en **`📌 Minimizar a Bandeja`** o simplemente presiona la `X` de cerrar la ventana.
- AudioDucker continuará funcionando en segundo plano en la bandeja de iconos ocultos junto al reloj de Windows. Para abrir la ventana nuevamente, haz doble clic en el ícono de AudioDucker o haz clic derecho y selecciona **`🎵 Mostrar AudioDucker`**.

---

## 📁 Estructura del Proyecto

```
AudioDucker/
├── assets/                  # Iconos y recursos gráficos (banner.png, logo.ico, logo.png)
├── AudioDucker.exe          # Ejecutable v2.01 listo para usar sin consola
├── main.py                  # Punto de entrada y motor multihilo v2.01
├── gui.py                   # Interfaz gráfica de usuario con Sidebar y System Tray
├── detector.py              # Medición de picos de sonido de procesos y micrófonos WASAPI
├── volume_controller.py     # Controlador multihilo simultáneo con agrupación de procesos
├── config.json              # Configuración persistente v2.01
├── create_startup_shortcut.ps1 # Script de inicio automático en Windows
├── requirements.txt         # Dependencias de Python (customtkinter, pycaw, pystray, Pillow)
└── README.md                # Documentación en GitHub
```

---

## 🤖 Desarrollo con Inteligencia Artificial

Este proyecto fue concebido, diseñado y desarrollado en par-programming utilizando tecnologías avanzadas de Inteligencia Artificial:

- **Modelo de IA**: **Google Antigravity AI (Gemini 3.6 Flash / Pro)** desarrollado por Google DeepMind.
- **Áreas de automatización**: Integración WASAPI de Windows, resolución de accesos directos UWP mediante `Shell.Application`, arquitectura multi-target asíncrona, medidores de pico en vivo, interfaz CustomTkinter y empaquetado autónomo con PyInstaller.

---

## 📦 Compilación a `.exe`

Para volver a generar el ejecutable `.exe` independiente con icono personalizado:

```bash
pip install pyinstaller pystray Pillow customtkinter pycaw psutil pywin32
python -m PyInstaller --noconsole --onefile --icon=assets/logo.ico --name "AudioDucker" main.py
```
