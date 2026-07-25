# 🎵 AudioDucker para Windows

**AudioDucker** es una aplicación en Python que ajusta dinámicamente el volumen de tu reproductor de música (**Spotify** por defecto) cuando detecta que otras aplicaciones (**Discord**, **Chrome**, **Firefox**, **Zoom**, **Telegram**, etc.) están **emitiendo sonido**.

A diferencia de otros programas sencillos, AudioDucker utiliza las APIs de sonido nativas de Windows (WASAPI / PyCAW) para medir los **picos de volumen reales**. Si Chrome o Discord están abiertos pero en silencio, el volumen de Spotify NO bajará. Solo bajará en el instante exacto en que comiencen a reproducir audio (mensajes de voz, llamadas, vídeos, ChatGPT hablado, etc.).

---

## 📁 Estructura del Proyecto

```
AudioDucker/
├── main.py                  # Bucle principal y orquestador del servicio
├── detector.py              # Medición de picos de audio de procesos activos
├── volume_controller.py     # Control y transiciones de volumen de la app objetivo
├── config.json              # Configuración de aplicaciones, volúmenes y tiempos
├── requirements.txt         # Dependencias de Python necesarias
└── README.md                # Guía de uso e instalación
```

---

## 🚀 Requisitos e Instalación

1. Asegúrate de tener Python 3.8 o superior instalado en Windows.
2. Abre la consola de comandos o PowerShell en la carpeta del proyecto (`C:\Users\kelvi\Downloads\AudioDucker`):

```bash
cd C:\Users\kelvi\Downloads\AudioDucker
pip install -r requirements.txt
```

---

## 🎮 Ejecución

Para iniciar el programa, ejecuta:

```bash
python main.py
```

---

## ⚙️ Configuración (`config.json`)

El archivo `config.json` se crea automáticamente la primera vez que ejecutas el programa. Puedes modificarlo con cualquier editor de texto (como Bloc de notas o VS Code).

```json
{
  "target_app": "spotify.exe",
  "default_volume": 1.0,
  "default_duck_volume": 0.20,
  "trigger_apps": {
    "discord.exe": 0.25,
    "chrome.exe": 0.35,
    "msedge.exe": 0.35,
    "firefox.exe": 0.35,
    "brave.exe": 0.35,
    "telegram.exe": 0.25,
    "zoom.exe": 0.15,
    "obs64.exe": 0.30
  },
  "transition_duration_seconds": 0.4,
  "release_delay_seconds": 1.0,
  "audio_peak_threshold": 0.005,
  "check_interval_seconds": 0.05,
  "verbose_logging": true
}
```

### Explicación de Opciones:

- **`target_app`**: Proceso ejecutable de la aplicación que se atenúa (ej. `"spotify.exe"`).
- **`default_volume`**: Volumen normal de la app objetivo cuando nadie está hablando (`1.0` = 100%).
- **`default_duck_volume`**: Volumen por defecto (`0.20` = 20%) para apps que no estén registradas específicamente en `trigger_apps`.
- **`trigger_apps`**: Diccionario con los nombres del ejecutable en minúsculas y el porcentaje de volumen objetivo. **¡Puedes agregar cualquier aplicación de Windows aquí!**
  - Ejemplo: `"vlc.exe": 0.20`, `"league of legends.exe": 0.10`.
- **`transition_duration_seconds`**:
  - `0`: Cambio **INSTANTÁNEO** y de golpe (sin transición).
  - `0.3`, `0.5`, `1.0`: Duración del desvanecimiento suave (fade in / fade out) en segundos.
- **`release_delay_seconds`**: Tiempo de espera (en segundos) tras silenciarse el audio antes de restaurar Spotify al 100%. Evita altibajos molestos entre frases o palabras.
- **`audio_peak_threshold`**: Umbral mínimo del medidor de picos (de `0.0` a `1.0`) para considerar que una app está emitiendo sonido. Ignora ruido blanco.
- **`check_interval_seconds`**: Frecuencia de escaneo en segundos (`0.05` = 20 revisiones por segundo).

---

## 📦 Cómo convertirlo en un `.exe` e iniciarlo con Windows

Si quieres que AudioDucker se ejecute en segundo plano sin mostrar la consola y se inicie automáticamente al encender la computadora:

### 1. Compilar a `.exe` con PyInstaller
Ejecuta los siguientes comandos en tu terminal:

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name "AudioDucker" main.py
```

Encontrarás el ejecutable listo en la carpeta `dist/AudioDucker.exe`.

### 2. Copiar `config.json` junto al ejecutable
Copia `config.json` a la misma carpeta donde esté `AudioDucker.exe`.

### 3. Iniciar automáticamente con Windows (Startup)
1. Presiona `Win + R`, escribe `shell:startup` y presiona **Enter**.
2. Copia un acceso directo de `AudioDucker.exe` dentro de esa carpeta.
3. ¡Listo! Cada vez que enciendas tu PC, AudioDucker se ejecutará en segundo plano.
