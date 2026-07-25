import logging
from typing import Dict, Set, Tuple, List, Any, Union
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
import comtypes
from comtypes import CLSCTX_ALL
import psutil

try:
    import pythoncom
except ImportError:
    pythoncom = None

logger = logging.getLogger("AudioDucker.Detector")

class AudioDetector:
    """
    Escanea las sesiones de audio activas y micrófonos en Windows,
    midiendo picos de audio (Peak Values) mediante WASAPI / PyCAW.
    """

    def __init__(self, audio_peak_threshold: float = 0.005):
        self.threshold = audio_peak_threshold

    def _ensure_com(self):
        if pythoncom:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

    def get_active_audio_processes(self) -> Dict[str, float]:
        self._ensure_com()
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

                meter = session._ctl.QueryInterface(IAudioMeterInformation)
                peak_value = meter.GetPeakValue()

                if proc_name in active_processes:
                    active_processes[proc_name] = max(active_processes[proc_name], peak_value)
                else:
                    active_processes[proc_name] = peak_value

            except Exception:
                continue

        return active_processes

    def get_available_microphones(self) -> List[str]:
        self._ensure_com()
        mics = ["Default"]
        try:
            devices = AudioUtilities.GetAllDevices()
            for dev in devices:
                if dev.id and dev.id.startswith("{0.0.1."):
                    name = dev.FriendlyName
                    if name and name not in mics:
                        mics.append(name)
        except Exception as e:
            logger.debug(f"Error al listar micrófonos: {e}")
        return mics

    def get_microphone_peak(self, mic_name: str = "Default") -> float:
        self._ensure_com()
        try:
            if mic_name == "Default" or not mic_name:
                mic_dev = AudioUtilities.GetMicrophone()
                if mic_dev:
                    meter = mic_dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None).QueryInterface(IAudioMeterInformation)
                    return meter.GetPeakValue()
            else:
                devices = AudioUtilities.GetAllDevices()
                for dev in devices:
                    if dev.id and dev.id.startswith("{0.0.1.") and dev.FriendlyName == mic_name:
                        meter = dev._dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None).QueryInterface(IAudioMeterInformation)
                        return meter.GetPeakValue()
        except Exception as e:
            logger.debug(f"Error leyendo pico del micrófono '{mic_name}': {e}")
        return 0.0

    def check_triggers(
        self,
        trigger_apps: Dict[str, Union[Dict[str, Any], float]],
        default_duck_vol: float,
        duck_on_microphone: bool = False,
        selected_microphone: str = "Default",
        mic_duck_volume: float = 0.20,
        mic_peak_threshold: float = 0.05
    ) -> Tuple[bool, float, Set[str]]:
        active_procs = self.get_active_audio_processes()
        speaking_triggers = set()
        lowest_volume = 1.0

        # Normalizar diccionario de activadores para búsqueda flexible
        # Tuple: (is_enabled, duck_volume, trigger_threshold)
        clean_triggers: Dict[str, Tuple[bool, float, float]] = {}
        for app_k, app_v in trigger_apps.items():
            k_clean = str(app_k).lower().strip()
            is_enabled = True
            req_vol = default_duck_vol
            req_thresh = self.threshold
            if isinstance(app_v, dict):
                is_enabled = bool(app_v.get("enabled", True))
                req_vol = float(app_v.get("duck_volume", default_duck_vol))
                req_thresh = float(app_v.get("trigger_threshold", 0.05))
            else:
                req_vol = float(app_v)
            clean_triggers[k_clean] = (is_enabled, req_vol, req_thresh)

        for proc_name, peak in active_procs.items():
            # Coincidencia flexible: proc_name, sin .exe o con .exe
            matched_key = None
            p_clean = proc_name.lower().strip()
            p_no_ext = p_clean.replace(".exe", "")
            p_with_exe = f"{p_no_ext}.exe"

            if p_clean in clean_triggers:
                matched_key = p_clean
            elif p_with_exe in clean_triggers:
                matched_key = p_with_exe
            elif p_no_ext in clean_triggers:
                matched_key = p_no_ext

            if matched_key:
                is_enabled, req_vol, req_thresh = clean_triggers[matched_key]
                # Se activa SOLO si la app está habilitada Y el sonido supera el umbral de sensibilidad de esa app
                if is_enabled and peak >= req_thresh:
                    speaking_triggers.add(matched_key)
                    if req_vol < lowest_volume:
                        lowest_volume = req_vol

        if duck_on_microphone:
            mic_peak = self.get_microphone_peak(selected_microphone)
            if mic_peak >= mic_peak_threshold:
                speaking_triggers.add(f"🎤 Micrófono ({selected_microphone})")
                if mic_duck_volume < lowest_volume:
                    lowest_volume = mic_duck_volume

        if speaking_triggers:
            return True, lowest_volume, speaking_triggers
        
        return False, 1.0, set()
