import logging
from typing import Dict, Set, Tuple
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
import comtypes
import psutil

logger = logging.getLogger("AudioDucker.Detector")

class AudioDetector:
    """
    Escanea las sesiones de audio activas en Windows y mide el nivel de pico (Peak Value)
    de cada aplicación registrada.
    """

    def __init__(self, audio_peak_threshold: float = 0.005):
        self.threshold = audio_peak_threshold

    def get_active_audio_processes(self) -> Dict[str, float]:
        """
        Retorna un diccionario {nombre_proceso: peak_value} para todos los procesos
        que estén emitiendo sonido en este instante.
        """
        active_processes: Dict[str, float] = {}

        try:
            sessions = AudioUtilities.GetAllSessions()
        except Exception as e:
            logger.debug(f"Error al obtener sesiones de audio: {e}")
            return active_processes

        for session in sessions:
            try:
                proc_name = None
                if session.Process:
                    try:
                        proc_name = session.Process.name().lower()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                        pass

                if not proc_name and session.DisplayName:
                    proc_name = session.DisplayName.lower()

                if not proc_name:
                    continue

                # Consultar la interfaz IAudioMeterInformation para leer el nivel de audio (0.0 a 1.0)
                meter = session._ctl.QueryInterface(IAudioMeterInformation)
                peak_value = meter.GetPeakValue()

                # Si hay múltiples instancias del mismo proceso (ej. múltiples pestañas de Chrome),
                # guardamos el pico máximo detectado entre todas ellas.
                if proc_name in active_processes:
                    active_processes[proc_name] = max(active_processes[proc_name], peak_value)
                else:
                    active_processes[proc_name] = peak_value

            except Exception as e:
                # Ignorar sesiones cerradas, sin permisos o temporales
                continue

        return active_processes

    def check_triggers(self, trigger_apps: Dict[str, float], default_duck_vol: float) -> Tuple[bool, float, Set[str]]:
        """
        Analiza si alguna de las aplicaciones trigger está reproduciendo sonido por encima del umbral.
        
        Retorna:
            - is_triggered (bool): True si al menos una app trigger está hablando.
            - target_volume (float): El porcentaje de volumen más bajo exigido por las apps activas.
            - active_trigger_names (Set[str]): Nombres de las apps que están activando la bajada de volumen.
        """
        active_procs = self.get_active_audio_processes()
        speaking_triggers = set()
        lowest_volume = 1.0

        for proc_name, peak in active_procs.items():
            if peak >= self.threshold:
                # Verificar si esta app está en la lista de triggers configuradas
                if proc_name in trigger_apps:
                    speaking_triggers.add(proc_name)
                    required_vol = trigger_apps[proc_name]
                    if required_vol < lowest_volume:
                        lowest_volume = required_vol

        if speaking_triggers:
            return True, lowest_volume, speaking_triggers
        
        return False, 1.0, set()
