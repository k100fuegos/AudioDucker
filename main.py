import json
import logging
import os
import sys
import threading
import time
from typing import Dict, Any

try:
    import pythoncom
except ImportError:
    pythoncom = None

from detector import AudioDetector
from volume_controller import MultiVolumeController

def setup_logging(verbose: bool = True):
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level, format=log_format, datefmt="%H:%M:%S")

def load_config(config_path: str) -> Dict[str, Any]:
    default_config = {
        "version": "2.01",
        "target_apps": {
            "spotify.exe": {"enabled": True},
            "applemusic.exe": {"enabled": True},
            "vlc.exe": {"enabled": False}
        },
        "trigger_apps": {
            "discord.exe": {"enabled": True, "duck_volume": 0.25, "trigger_threshold": 0.05},
            "chrome.exe": {"enabled": True, "duck_volume": 0.35, "trigger_threshold": 0.05},
            "msedge.exe": {"enabled": True, "duck_volume": 0.35, "trigger_threshold": 0.05},
            "firefox.exe": {"enabled": True, "duck_volume": 0.35, "trigger_threshold": 0.05},
            "brave.exe": {"enabled": True, "duck_volume": 0.35, "trigger_threshold": 0.05},
            "telegram.exe": {"enabled": True, "duck_volume": 0.25, "trigger_threshold": 0.05},
            "zoom.exe": {"enabled": True, "duck_volume": 0.15, "trigger_threshold": 0.05},
            "obs64.exe": {"enabled": True, "duck_volume": 0.30, "trigger_threshold": 0.05}
        },
        "duck_on_microphone": False,
        "selected_microphone": "Default",
        "mic_duck_volume": 0.20,
        "mic_peak_threshold": 0.05,
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
            
            if "target_app" in config and "target_apps" not in config:
                target_single = str(config["target_app"]).lower()
                config["target_apps"] = {target_single: {"enabled": True}}

            if "trigger_apps" in config and isinstance(config["trigger_apps"], dict):
                clean_triggers = {}
                for k, v in config["trigger_apps"].items():
                    k_clean = str(k).lower()
                    if isinstance(v, dict):
                        clean_triggers[k_clean] = {
                            "enabled": bool(v.get("enabled", True)),
                            "duck_volume": float(v.get("duck_volume", 0.25)),
                            "trigger_threshold": float(v.get("trigger_threshold", 0.05))
                        }
                    else:
                        clean_triggers[k_clean] = {
                            "enabled": True,
                            "duck_volume": float(v),
                            "trigger_threshold": 0.05
                        }
                config["trigger_apps"] = clean_triggers

            return {**default_config, **config}
    except Exception:
        return default_config


class AudioDuckerEngine:
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
                target_apps = self.config.get("target_apps", {})
                trigger_apps = self.config.get("trigger_apps", {})
                transition_duration = float(self.config.get("transition_duration_seconds", 0.4))
                release_delay = float(self.config.get("release_delay_seconds", 1.0))
                peak_threshold = float(self.config.get("audio_peak_threshold", 0.005))
                check_interval = float(self.config.get("check_interval_seconds", 0.05))

                duck_on_mic = bool(self.config.get("duck_on_microphone", False))
                selected_mic = str(self.config.get("selected_microphone", "Default"))
                mic_duck_vol = float(self.config.get("mic_duck_volume", 0.20))
                mic_peak_thresh = float(self.config.get("mic_peak_threshold", 0.05))

            detector.threshold = peak_threshold
            controller = MultiVolumeController(transition_duration_seconds=transition_duration)

            is_triggered, required_volume, active_triggers = detector.check_triggers(
                trigger_apps=trigger_apps,
                default_duck_vol=0.20,
                duck_on_microphone=duck_on_mic,
                selected_microphone=selected_mic,
                mic_duck_volume=mic_duck_vol,
                mic_peak_threshold=mic_peak_thresh
            )

            if is_triggered:
                silence_start_time = None
                if not is_ducked or (current_duck_target is not None and required_volume < current_duck_target) or active_triggers != last_active_triggers:
                    logger.info(f"🔊 Sonido detectado en: {', '.join(active_triggers)} ➔ Atenuando aplicaciones objetivo activas.")
                    controller.apply_volume_state(
                        target_apps_config=target_apps,
                        is_ducked=True,
                        trigger_lowest_ratio=required_volume,
                        duration_seconds=transition_duration
                    )
                    is_ducked = True
                    current_duck_target = required_volume
                    last_active_triggers = active_triggers

            else:
                if is_ducked:
                    if silence_start_time is None:
                        silence_start_time = time.time()
                    elif time.time() - silence_start_time >= release_delay:
                        logger.info(f"🔇 Silencio ➔ Restaurando aplicaciones objetivo a su volumen normal.")
                        controller.apply_volume_state(
                            target_apps_config=target_apps,
                            is_ducked=False,
                            duration_seconds=transition_duration
                        )
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

    engine = AudioDuckerEngine(config)
    engine.start()

    def restart_service_callback():
        engine.stop()
        time.sleep(0.2)
        new_cfg = load_config(config_file)
        engine.update_config(new_cfg)
        engine.start()

    if "--cli" in sys.argv or "--no-gui" in sys.argv:
        print("[+] AudioDucker v2.01 ejecutándose en modo consola sin GUI. Presiona Ctrl+C para salir.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            engine.stop()
            sys.exit(0)

    from gui import launch_gui
    launch_gui(
        config_file,
        on_config_updated_callback=engine.update_config,
        on_restart_service_callback=restart_service_callback
    )
    engine.stop()

if __name__ == "__main__":
    main()
