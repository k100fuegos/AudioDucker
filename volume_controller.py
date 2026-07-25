import logging
import time
from typing import Dict, Any, Optional, List
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
import psutil

try:
    import pythoncom
except ImportError:
    pythoncom = None

logger = logging.getLogger("AudioDucker.VolumeController")

class SingleAppVolumeControl:
    def __init__(self, app_name: str):
        self.app_name = app_name.lower().strip()
        self.app_no_ext = self.app_name.replace(".exe", "")
        self.app_with_exe = f"{self.app_no_ext}.exe"

    def _get_interfaces(self) -> List[ISimpleAudioVolume]:
        interfaces = []
        if pythoncom:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process:
                    try:
                        proc_name = session.Process.name().lower().strip()
                        proc_no_ext = proc_name.replace(".exe", "")
                        
                        # Coincidencia flexible de proceso
                        if proc_name in (self.app_name, self.app_with_exe, self.app_no_ext) or proc_no_ext == self.app_no_ext:
                            interfaces.append(session._ctl.QueryInterface(ISimpleAudioVolume))
                    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                        continue
        except Exception as e:
            logger.debug(f"Error buscando sesión para {self.app_name}: {e}")
        return interfaces

    def set_volume(self, target_volume: float, duration_seconds: float = 0.4) -> bool:
        target_volume = max(0.0, min(1.0, float(target_volume)))
        interfaces = self._get_interfaces()
        if not interfaces:
            return False

        try:
            if duration_seconds <= 0:
                for iface in interfaces:
                    try:
                        iface.SetMasterVolume(target_volume, None)
                    except Exception:
                        pass
                return True

            try:
                current_vol = interfaces[0].GetMasterVolume()
            except Exception:
                current_vol = 1.0

            if abs(current_vol - target_volume) < 0.005:
                return True

            steps = max(4, int(duration_seconds / 0.02))
            step_time = duration_seconds / steps
            vol_diff = target_volume - current_vol
            step_size = vol_diff / steps

            for i in range(1, steps + 1):
                new_vol = max(0.0, min(1.0, current_vol + (step_size * i)))
                for iface in interfaces:
                    try:
                        iface.SetMasterVolume(new_vol, None)
                    except Exception:
                        pass
                time.sleep(step_time)

            for iface in interfaces:
                try:
                    iface.SetMasterVolume(target_volume, None)
                except Exception:
                    pass
            return True

        except Exception as e:
            logger.debug(f"Excepción en set_volume para {self.app_name}: {e}")
            return False


class MultiVolumeController:
    """
    Controla el volumen de MÚLTIPLES aplicaciones objetivo de forma simultánea.
    """

    def __init__(self, transition_duration_seconds: float = 0.4):
        self.transition_duration = transition_duration_seconds

    def apply_volume_state(
        self,
        target_apps_config: Dict[str, Dict[str, Any]],
        is_ducked: bool,
        trigger_lowest_ratio: float = 1.0,
        duration_seconds: Optional[float] = None
    ):
        duration = duration_seconds if duration_seconds is not None else self.transition_duration

        for app_name, app_info in target_apps_config.items():
            is_enabled = True
            if isinstance(app_info, dict):
                is_enabled = app_info.get("enabled", True)

            if not is_enabled:
                continue

            app_control = SingleAppVolumeControl(app_name)
            
            if is_ducked:
                target_vol = max(0.0, min(1.0, trigger_lowest_ratio))
            else:
                target_vol = 1.0

            app_control.set_volume(target_vol, duration_seconds=duration)
