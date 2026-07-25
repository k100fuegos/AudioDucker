import logging
import time
from typing import Dict, Any, Optional, List
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
import psutil

logger = logging.getLogger("AudioDucker.VolumeController")

class SingleAppVolumeControl:
    def __init__(self, app_name: str):
        self.app_name = app_name.lower()

    def _get_interfaces() -> List[ISimpleAudioVolume]:
        interfaces = []
        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process:
                    try:
                        proc_name = session.Process.name().lower()
                        if proc_name == self.app_name:
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
                    iface.SetMasterVolume(target_volume, None)
                return True

            current_vol = interfaces[0].GetMasterVolume()
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
                iface.SetMasterVolume(target_volume, None)
            return True
        except Exception as e:
            logger.debug(f"Error ajustando volumen de {self.app_name}: {e}")
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
        """
        Ajusta de forma simultánea todas las aplicaciones objetivo habilitadas (enabled=True).
        """
        duration = duration_seconds if duration_seconds is not None else self.transition_duration

        for app_name, app_info in target_apps_config.items():
            if not isinstance(app_info, dict):
                continue
            
            # Verificar si esta app objetivo está habilitada (ON)
            if not app_info.get("enabled", True):
                continue

            app_control = SingleAppVolumeControl(app_name)
            
            if is_ducked:
                # Usar el volumen de atenuación de la app o el menor exigido
                app_duck_vol = float(app_info.get("duck_volume", 0.20))
                target_vol = min(app_duck_vol, trigger_lowest_ratio)
            else:
                # Restaurar a su volumen por defecto
                target_vol = float(app_info.get("default_volume", 1.0))

            app_control.set_volume(target_vol, duration_seconds=duration)
