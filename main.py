import json
import logging
import os
import sys
import threading
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
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level, format=log_format, datefmt="%H:%M:%S")

def load_config(config_path: str) -> Dict[str, Any]:
    default_config = {
        "target_app": "spotify.exe",
        "default_volume": 1.0,
        "default_duck_volume": 0.20,
        "duck_on_microphone": False,
        "selected_microphone": "Default",
        "mic_duck_volume": 0.20,
        "mic_peak_threshold": 0.01,
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
        except Exception:
            pass
        return default_config

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            if "trigger_apps" in config and isinstance(config["trigger_apps"], dict):
                config["trigger_apps"] = {k.lower(): float(v) for k, v in config["trigger_apps"].items()}
            return {**default_config, **config}
    except Exception:
        return default_config

class AudioDuckerEngine:
    """
    Motor de monitoreo y atenuación de audio que corre en un hilo secundario.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

    def update_config(self, new_config: Dict[str, Any]):
        with self.lock:
            self.config = new_config

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _run_loop(self):
        if pythoncom:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

        logger = logging.getLogger("AudioDucker.Engine")
        detector = AudioDetector()

        is_ducked = False
        current_duck_target = None
        silence_start_time = None
        last_active_triggers = set()

        while self.running:
            with self.lock:
                target_app = self.config["target_app"].lower()
                default_volume = float(self.config["default_volume"])
                default_duck_volume = float(self.config["default_duck_volume"])
                trigger_apps = self.config["trigger_apps"]
                transition_duration = float(self.config["transition_duration_seconds"])
                release_delay = float(self.config["release_delay_seconds"])
                peak_threshold = float(self.config["audio_peak_threshold"])
                check_interval = float(self.config["check_interval_seconds"])

                duck_on_mic = bool(self.config.get("duck_on_microphone", False))
                selected_mic = str(self.config.get("selected_microphone", "Default"))
                mic_duck_vol = float(self.config.get("mic_duck_volume", 0.20))
                mic_peak_thresh = float(self.config.get("mic_peak_threshold", 0.01))

            detector.threshold = peak_threshold
            controller = VolumeController(target_app_name=target_app, transition_duration_seconds=transition_duration)

            is_triggered, required_volume, active_triggers = detector.check_triggers(
                trigger_apps=trigger_apps,
                default_duck_vol=default_duck_volume,
                duck_on_microphone=duck_on_mic,
                selected_microphone=selected_mic,
                mic_duck_volume=mic_duck_vol,
                mic_peak_threshold=mic_peak_thresh
            )

            if is_triggered:
                silence_start_time = None
                if not is_ducked or (current_duck_target is not None and required_volume < current_duck_target) or active_triggers != last_active_triggers:
                    logger.info(f"🔊 Sonido/Voz detectado en: {', '.join(active_triggers)} ➔ Atenuando {target_app} a {required_volume * 100:.0f}%")
                    controller.set_volume(required_volume, duration_seconds=transition_duration)
                    is_ducked = True
                    current_duck_target = required_volume
                    last_active_triggers = active_triggers

            else:
                if is_ducked:
                    if silence_start_time is None:
                        silence_start_time = time.time()
                    elif time.time() - silence_start_time >= release_delay:
                        logger.info(f"🔇 Silencio ➔ Restaurando {target_app} al {default_volume * 100:.0f}%")
                        controller.set_volume(default_volume, duration_seconds=transition_duration)
                        is_ducked = False
                        current_duck_target = None
                        silence_start_time = None
                        last_active_triggers = set()

            time.sleep(check_interval)

        if pythoncom:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

def main():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    config_file = os.path.join(base_dir, "config.json")
    config = load_config(config_file)
    setup_logging(config.get("verbose_logging", True))

    # Iniciar motor de atenuación en segundo plano
    engine = AudioDuckerEngine(config)
    engine.start()

    # Si se pasa --cli o --no-gui, correr en consola de fondo
    if "--cli" in sys.argv or "--no-gui" in sys.argv:
        print("[+] AudioDucker ejecutándose en modo consola sin GUI. Presiona Ctrl+C para salir.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            engine.stop()
            sys.exit(0)

    # Iniciar Interfaz Gráfica (GUI)
    from gui import launch_gui
    launch_gui(config_file, on_config_updated_callback=engine.update_config)
    engine.stop()

if __name__ == "__main__":
    main()
