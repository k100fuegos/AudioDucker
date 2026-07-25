![AudioDucker Banner](assets/banner.png)

# 🎵 AudioDucker v2.01 para Windows

**AudioDucker** es una aplicación inteligente para Windows que atenúa automáticamente el volumen de tus reproductores de música y multimedia (**Spotify**, **VLC**, navegadores, etc.) **de forma simultánea** cuando detecta que otras aplicaciones (**Discord**, **Chrome**, **Firefox**, **Zoom**, **Telegram**, etc.) o tu **Micrófono** están **emitiendo sonido**.

A diferencia de otros programas convencionales, AudioDucker utiliza las APIs de sonido nativas de Windows (WASAPI / PyCAW) para medir los **picos de volumen reales**. Si Chrome o Discord están abiertos pero en silencio, las aplicaciones no bajarán de volumen. Solo se atenuarán en el instante exacto en que comiencen a reproducir audio o cuando comiences a hablar por tu micrófono.

---

## ✨ Novedades en la Versión 2.01

- 🎯 **Atenuación Simultánea Multi-Target**: Puedes configurar **múltiples aplicaciones objetivo** (Spotify, VLC, YouTube Music, juegos, etc.) para que sufran la bajada de volumen al mismo tiempo.
- 🔘 **Switches ON/OFF Individuales**:
  - **En Aplicaciones Objetivo**: Interruptor independiente para activar o pausar la bajada de volumen en cada programa sin necesidad de borrarlo.
  - **En Aplicaciones Activadoras**: Interruptor independiente para elegir qué aplicaciones pueden provocar la bajada y cuáles deben ser ignoradas.
  - **En Micrófono**: Switch ON/OFF rápido para atenuación por voz.
- 🖥️ **Interfaz Gráfica Limpia (GUI v2.01)**: Interfaz compacta y directa sin distracciones internas.
- 📁 **Exploradores de Archivos `.exe`**: Botones de búsqueda nativos para agregar tanto apps objetivo como activadoras directamente desde el Explorador de Windows.
- 🎚️ **Control de Transiciones**: Elige entre cambios **Instantáneos (0s - de golpe)** o **Desvanecimientos Suaves (0.1s a 2.0s)**.
- 🚀 **Integración con Inicio de Windows**: Registra el ejecutable en la carpeta de Inicio de Windows (`shell:startup`).

---

## 📁 Estructura del Proyecto

```
AudioDucker/
├── assets/                  # Iconos y recursos gráficos (banner.png, logo.ico, logo.png)
├── AudioDucker.exe          # Ejecutable v2.01 listo para usar sin consola
├── main.py                  # Punto de entrada y motor multihilo v2.01
├── gui.py                   # Interfaz gráfica de usuario v2.01 con CustomTkinter
├── detector.py              # Medición de picos de sonido de procesos y micrófonos
├── volume_controller.py     # Controlador multihilo simultáneo (MultiVolumeController)
├── config.json              # Configuración persistente v2.01
├── create_startup_shortcut.ps1 # Script de inicio automático en Windows
├── requirements.txt         # Dependencias de Python
└── README.md                # Documentación en GitHub
```

---

## ⚙️ Configuración (`config.json` v2.01)

Toda la configuración se puede gestionar visualmente desde la GUI o editando `config.json`:

```json
{
  "version": "2.01",
  "target_apps": {
    "spotify.exe": {
      "enabled": true,
      "default_volume": 1.0,
      "duck_volume": 0.20
    },
    "vlc.exe": {
      "enabled": false,
      "default_volume": 1.0,
      "duck_volume": 0.15
    }
  },
  "trigger_apps": {
    "discord.exe": {
      "enabled": true,
      "duck_volume": 0.25
    },
    "chrome.exe": {
      "enabled": true,
      "duck_volume": 0.35
    }
  },
  "duck_on_microphone": false,
  "selected_microphone": "Default",
  "mic_duck_volume": 0.20,
  "transition_duration_seconds": 0.4,
  "release_delay_seconds": 1.0
}
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
