![AudioDucker Banner](assets/banner.png)

# 🎵 AudioDucker v2.01 para Windows (Windows 10 / Windows 11)

**AudioDucker** es una aplicación inteligente diseñada específicamente para **Windows 10 y Windows 11** que atenúa automáticamente el volumen de tus reproductores de música y multimedia (**Spotify**, **VLC**, navegadores, etc.) **de forma simultánea** cuando detecta que otras aplicaciones (**Discord**, **Chrome**, **Firefox**, **Zoom**, **Telegram**, etc.) o tu **Micrófono** están **emitiendo sonido**.

A diferencia de otros programas convencionales, AudioDucker utiliza las APIs de sonido nativas de Windows (WASAPI / PyCAW) para medir los **picos de volumen reales**. Si Chrome o Discord están abiertos pero en silencio, las aplicaciones no bajarán de volumen. Solo se atenuarán en el instante exacto en que comiencen a reproducir audio o cuando comiences a hablar por tu micrófono.

---

## ✨ Novedades en la Versión 2.01

- 🗂️ **Diseño con Barra Lateral (Sidebar Navigation)**: Menú lateral izquierdo moderno e intuitivo para navegar rápidamente entre pestañas:
  - 🎯 **Apps Objetivo**: Elige qué programas (Spotify, VLC, etc.) sufrirán la bajada de volumen simultánea.
  - 📱 **Apps Activadoras**: Asigna la fuerza de atenuación deseada para Discord, Chrome, Zoom, etc.
  - 🎤 **Micrófono**: Activa/desactiva la atenuación cuando hables por tu micrófono.
  - ⚙️ **Transición & Tiempos**: Ajusta la duración del desvanecimiento y los tiempos de silencio.
- 🎯 **Apps Objetivo Simplificadas**: Únicamente cuentan con interruptores **ON/OFF**. El nivel de volumen lo define la app activadora o micrófono activo.
- 🚫 **Barras Protegidas contra Scroll**: Las barras de volumen (`CTkSlider`) ya no cambiarán accidentalmente al usar la rueda del ratón.
- 🎚️ **Entradas Numéricas Validadas + Botones `+` / `-`**: Ajusta los porcentajes escribiendo el número exacto (0-100%) o con clics rápidos.

---

## 💡 Tip: Cómo agregar accesos directos de la Tienda de Windows (`shell:AppsFolder`)

Si deseas agregar aplicaciones de la Microsoft Store (como la app de Spotify de la Store o WhatsApp Desktop) cuyo archivo `.exe` está oculto en la carpeta `WindowsApps`:

1. Presiona la combinación de teclas **`Win` + `R`** en tu teclado.
2. Escribe el siguiente comando y presiona **Enter**:
   ```text
   shell:AppsFolder
   ```
3. Se abrirá una carpeta especial de Windows con todas tus aplicaciones instaladas.
4. Haz clic derecho sobre la aplicación que deseas agregar (ej. Spotify o WhatsApp) y selecciona 👉 **Crear acceso directo** *(se creará un acceso directo en tu Escritorio)*.
5. Abre la ventana de AudioDucker, haz clic en **`📁 Agregar App (.exe)`** y selecciona el acceso directo que acabas de crear en tu escritorio. ¡AudioDucker detectará automáticamente el ejecutable!

---

## 📁 Estructura del Proyecto

```
AudioDucker/
├── assets/                  # Iconos y recursos gráficos (banner.png, logo.ico, logo.png)
├── AudioDucker.exe          # Ejecutable v2.01 listo para usar sin consola
├── main.py                  # Punto de entrada y motor multihilo v2.01
├── gui.py                   # Interfaz gráfica de usuario con barra lateral (Sidebar)
├── detector.py              # Medición de picos de sonido de procesos y micrófonos WASAPI
├── volume_controller.py     # Controlador multihilo simultáneo (MultiVolumeController)
├── config.json              # Configuración persistente v2.01
├── create_startup_shortcut.ps1 # Script de inicio automático en Windows
├── requirements.txt         # Dependencias de Python
└── README.md                # Documentación en GitHub
```

---

## 🤖 Desarrollo con Inteligencia Artificial

Este proyecto fue concebido, diseñado y desarrollado en par-programming utilizando tecnologías avanzadas de Inteligencia Artificial:

- **Modelo de IA**: **Google Antigravity AI (Gemini 3.6 Flash / Pro)** desarrollado por Google DeepMind.
- **Áreas de automatización**: Integración WASAPI de Windows, arquitectura multi-target asíncrona, diseño de GUI moderna y empaquetado autónomo.

---

## 📦 Compilación a `.exe`

Para volver a generar el ejecutable `.exe` independiente con icono personalizado:

```bash
pip install pyinstaller
python -m PyInstaller --noconsole --onefile --icon=assets/logo.ico --name "AudioDucker" main.py
```
