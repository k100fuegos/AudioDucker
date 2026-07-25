import logging
import time
from typing import Optional
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
import psutil

logger = logging.getLogger("AudioDucker.VolumeController")

class VolumeController:
    """
    Controla el volumen de la aplicación objetivo (ejemplo: Spotify)
    mediante la interfaz ISimpleAudioVolume de WASAPI.
    """

    def __init__(self, target_app_name: str, transition_duration_seconds: float = 0.4):
        self.target_app_name = target_app_name.lower()
        self.transition_duration = transition_duration_seconds
        self.last_applied_volume: Optional[float] = None

    def _get_target_session_interface(self) -> Optional[ISimpleAudioVolume]:
        """
        Busca dinámicamente la sesión de audio del proceso objetivo.
        """
        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process:
                    try:
                        proc_name = session.Process.name().lower()
                        if proc_name == self.target_app_name:
                            return session._ctl.QueryInterface(ISimpleAudioVolume)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                        continue
        except Exception as e:
            logger.debug(f"Error buscando sesión para {self.target_app_name}: {e}")
        
        return None

    def get_current_volume(self) -> Optional[float]:
        """
        Obtiene el volumen máster actual (0.0 a 1.0) de la app objetivo.
        """
        interface = self._get_target_session_interface()
        if interface:
            try:
                return interface.GetMasterVolume()
            except Exception as e:
                logger.debug(f"Error leyendo volumen actual: {e}")
        return None

    def set_volume(self, target_volume: float, duration_seconds: Optional[float] = None) -> bool:
        """
        Establece el volumen de la app objetivo.
        
        Si duration_seconds <= 0: Se aplica el cambio de volumen de forma INSTANTÁNEA (de golpe).
        Si duration_seconds > 0: Se realiza una transición SUAVE (fade in / fade out) durante ese tiempo.
        """
        target_volume = max(0.0, min(1.0, float(target_volume)))
        duration = duration_seconds if duration_seconds is not None else self.transition_duration

        interface = self._get_target_session_interface()
        if not interface:
            logger.debug(f"Proceso '{self.target_app_name}' no encontrado o no tiene sesión de audio activa.")
            self.last_applied_volume = None
            return False

        try:
            current_vol = interface.GetMasterVolume()
            
            # Evitar re-aplicar si el volumen ya es prácticamente idéntico
            if abs(current_vol - target_volume) < 0.005:
                self.last_applied_volume = target_volume
                return True

            # Caso 1: Transición INSTANTÁNEA (de repente) cuando duration <= 0
            if duration <= 0:
                interface.SetMasterVolume(target_volume, None)
                self.last_applied_volume = target_volume
                logger.info(f"Volumen de {self.target_app_name} cambiado instantáneamente a {target_volume * 100:.0f}%")
                return True

            # Caso 2: Transición SUAVE (fading) cuando duration > 0
            steps = max(4, int(duration / 0.02))  # Pasos cada ~20ms
            step_time = duration / steps
            vol_diff = target_volume - current_vol
            step_size = vol_diff / steps

            logger.info(f"Iniciando transición suave de {self.target_app_name}: {current_vol * 100:.0f}% ➔ {target_volume * 100:.0f}% ({duration}s)")
            
            for i in range(1, steps + 1):
                new_vol = current_vol + (step_size * i)
                new_vol = max(0.0, min(1.0, new_vol))
                try:
                    interface.SetMasterVolume(new_vol, None)
                except Exception:
                    break
                time.sleep(step_time)

            # Asegurar el valor exacto al final
            interface.SetMasterVolume(target_volume, None)
            self.last_applied_volume = target_volume
            return True

        except Exception as e:
            logger.warning(f"Error al cambiar volumen de {self.target_app_name}: {e}")
            return False
