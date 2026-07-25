import json
import logging
import os
import sys
import time
from typing import Dict, Any

# Asegurar soporte de COM en Windows
try:
    import pythoncom
except ImportError:
    pythoncom = None

from detector import AudioDetector
from volume_controller import VolumeController

def setup_logging(verbose: bool = True):
    """Configura el formato y nivel de logs del programa."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level, format=log_format, datefmt="%H:%M:%S")

def load_config(config_path: str) -> Dict[str, Any]:
    """Carga la configuración desde config.json o usa valores por defecto."""
    default_config = {
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
        "verbose_logging": True
    }

    if not os.path.exists(config_path):
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            print(f"[+] Archivo de configuración por defecto creado en: {config_path}")
        except Exception as e:
            print(f"[!] No se pudo crear config.json: {e}")
        return default_config

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Asegurar minúsculas en nombres de procesos
            if "trigger_apps" in config and isinstance(config["trigger_apps"], dict):
                config["trigger_apps"] = {k.lower(): float(v) for k, v in config["trigger_apps"].items()}
            return {**default_config, **config}
    except Exception as e:
        print(f"[!] Error leyendo config.json ({e}). Usando valores por defecto.")
        return default_config

def main():
    # Obtener ruta absoluta del directorio del ejecutable/script
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    config_file = os.path.join(base_dir, "config.json")
    
    config = load_config(config_file)
    setup_logging(config.get("verbose_logging", True))
    logger = logging.getLogger("AudioDucker")

    # Inicializar COM en Windows
    if pythoncom:
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass

    target_app = config["target_app"].lower()
    default_volume = float(config["default_volume"])
    default_duck_volume = float(config["default_duck_volume"])
    trigger_apps = config["trigger_apps"]
    transition_duration = float(config["transition_duration_seconds"])
    release_delay = float(config["release_delay_seconds"])
    peak_threshold = float(config["audio_peak_threshold"])
    check_interval = float(config["check_interval_seconds"])

    print("======================================================")
    print("           🎵 AudioDucker para Windows 🎵             ")
    print("======================================================")
    print(f" App objetivo (atenuada) : {target_app}")
    print(f" Apps desencadenantes    : {', '.join(trigger_apps.keys())}")
    print(f" Duración de transición  : {transition_duration}s {'(INSTANTÁNEA)' if transition_duration <= 0 else '(SUAVE)'}")
    print(f" Retardo de liberación   : {release_delay}s")
    print("======================================================")
    print(" Presiona Ctrl+C para salir.\n")

    detector = AudioDetector(audio_peak_threshold=peak_threshold)
    controller = VolumeController(target_app_name=target_app, transition_duration_seconds=transition_duration)

    is_ducked = False
    current_duck_target = None
    silence_start_time = None
    last_active_triggers = set()

    try:
        while True:
            is_triggered, required_volume, active_triggers = detector.check_triggers(
                trigger_apps=trigger_apps,
                default_duck_vol=default_duck_volume
            )

            if is_triggered:
                silence_start_time = None
                
                # Si no estaba atenuado o si hay una app que exige un volumen aún menor
                if not is_ducked or (current_duck_target is not None and required_volume < current_duck_target) or active_triggers != last_active_triggers:
                    logger.info(f"🔊 Audio detectado en: {', '.join(active_triggers)} ➔ Atenuando {target_app} a {required_volume * 100:.0f}%")
                    controller.set_volume(required_volume, duration_seconds=transition_duration)
                    is_ducked = True
                    current_duck_target = required_volume
                    last_active_triggers = active_triggers

            else:
                # Nadie está hablando
                if is_ducked:
                    if silence_start_time is None:
                        silence_start_time = time.time()
                        logger.debug(f"Silencio detectado. Esperando {release_delay}s antes de restaurar volumen...")
                    elif time.time() - silence_start_time >= release_delay:
                        logger.info(f"🔇 Silencio finalizado ➔ Restaurando {target_app} al {default_volume * 100:.0f}%")
                        controller.set_volume(default_volume, duration_seconds=transition_duration)
                        is_ducked = False
                        current_duck_target = None
                        silence_start_time = None
                        last_active_triggers = set()

            time.sleep(check_interval)

    except KeyboardInterrupt:
        print("\n[!] Deteniendo AudioDucker...")
    finally:
        # Intentar restaurar volumen original antes de salir
        print(f"[*] Restaurando volumen de {target_app} al 100%...")
        controller.set_volume(default_volume, duration_seconds=0)
        if pythoncom:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        print("[+] ¡Hasta luego!")

if __name__ == "__main__":
    main()
