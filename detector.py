import logging
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, Set, Tuple, List, Any, Union
import psutil

from volume_controller import (
    IS_WINDOWS,
    IS_LINUX,
    expand_process_aliases,
    resolve_linux_sink_input_names,
)

if IS_WINDOWS:
    from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
    from comtypes import CLSCTX_ALL
    try:
        import pythoncom
    except ImportError:
        pythoncom = None
else:
    AudioUtilities = None
    IAudioMeterInformation = None
    CLSCTX_ALL = None
    pythoncom = None

if IS_LINUX:
    try:
        import pulsectl
    except ImportError:
        pulsectl = None
else:
    pulsectl = None

logger = logging.getLogger("AudioDucker.Detector")


class AudioDetector:
    """
    Escanea las sesiones de audio activas y micrófonos de forma multiplataforma:
    - Windows: WASAPI / PyCAW (IAudioMeterInformation).
    - Linux: PipeWire / PulseAudio mediante pulsectl (PA_STREAM_PEAK_DETECT) y fallback pactl.
    """

    def __init__(self, audio_peak_threshold: float = 0.005):
        self.threshold = audio_peak_threshold

    def _ensure_com(self):
        if IS_WINDOWS and pythoncom:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # DETECCIÓN DE PROCESOS DE AUDIO (WINDOWS & LINUX)
    # ------------------------------------------------------------------
    def _get_active_audio_processes_windows(self) -> Dict[str, float]:
        self._ensure_com()
        active_processes: Dict[str, float] = {}
        if AudioUtilities is None:
            return active_processes

        try:
            sessions = AudioUtilities.GetAllSessions()
        except Exception as e:
            logger.debug(f"Error al obtener sesiones de audio WASAPI: {e}")
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
                peak_value = float(meter.GetPeakValue())

                if proc_name in active_processes:
                    active_processes[proc_name] = max(active_processes[proc_name], peak_value)
                else:
                    active_processes[proc_name] = peak_value

            except Exception:
                continue

        return active_processes

    def _get_primary_linux_proc_name(self, proplist: Dict[str, str]) -> str:
        """Determina el nombre principal legible del proceso de un sink-input en Linux."""
        all_candidates = resolve_linux_sink_input_names(proplist)
        # Si alguno de los candidatos coincide con un grupo conocido (ej. discord, firefox, spotify), preferir ese nombre base
        known_bases = [
            "discord", "spotify", "firefox", "chrome", "chromium", "brave",
            "msedge", "telegram", "zoom", "obs", "vlc", "cider"
        ]
        for kb in known_bases:
            if kb in all_candidates or f"{kb}.exe" in all_candidates:
                return kb

        bin_name = proplist.get("application.process.binary", "").strip().lower()
        if bin_name:
            return os.path.basename(bin_name)

        pid_str = proplist.get("application.process.id", "")
        if pid_str:
            try:
                return psutil.Process(int(pid_str)).name().lower().strip()
            except Exception:
                pass

        app_name = proplist.get("application.name", "").strip().lower()
        if app_name:
            return app_name

        return ""

    def _get_active_audio_processes_linux(self) -> Dict[str, float]:
        active_processes: Dict[str, float] = {}

        if pulsectl is not None:
            try:
                with pulsectl.Pulse("audioducker-detector") as pulse:
                    sinks = {s.index: s for s in pulse.sink_list()}
                    default_sink_name = pulse.server_info().default_sink_name
                    default_monitor = f"{default_sink_name}.monitor" if default_sink_name else None

                    for si in pulse.sink_input_list():
                        try:
                            proc_name = self._get_primary_linux_proc_name(si.proplist)
                            if not proc_name:
                                continue

                            is_corked = bool(getattr(si, "corked", 0))
                            is_muted = bool(getattr(si, "mute", 0))

                            if is_corked or is_muted:
                                peak_val = 0.0
                            else:
                                sink_obj = sinks.get(si.sink)
                                monitor_source = getattr(sink_obj, "monitor_source_name", None) or default_monitor
                                peak_val = 0.0
                                if monitor_source:
                                    try:
                                        peak_val = float(
                                            pulse.get_peak_sample(
                                                monitor_source,
                                                timeout=0.018,
                                                stream_idx=si.index
                                            )
                                        )
                                    except Exception:
                                        peak_val = 0.0

                                # En ciertas configuraciones de PipeWire donde stream_idx monitor devuelve 0.0
                                # para un stream activo (uncorked), medir el monitor del sink como respaldo
                                if peak_val <= 0.0 and monitor_source:
                                    try:
                                        sink_peak = float(pulse.get_peak_sample(monitor_source, timeout=0.012))
                                        vol_flat = float(getattr(si.volume, "value_flat", 1.0))
                                        peak_val = min(1.0, sink_peak * max(0.2, vol_flat))
                                    except Exception:
                                        pass

                            # Registrar el pico tanto en el nombre primario como en todos los alias del stream
                            for candidate in resolve_linux_sink_input_names(si.proplist) | {proc_name}:
                                if candidate.endswith(".exe"):
                                    continue
                                active_processes[candidate] = max(active_processes.get(candidate, 0.0), peak_val)
                        except Exception:
                            continue
                return active_processes
            except Exception as e:
                logger.debug(f"Error al escanear sesiones con pulsectl: {e}")

        # Fallback por CLI con pactl
        if shutil.which("pactl"):
            try:
                res = subprocess.run(
                    ["pactl", "list", "sink-inputs"],
                    capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0:
                    blocks = res.stdout.split("Sink Input #")
                    for block in blocks[1:]:
                        proplist: Dict[str, str] = {}
                        corked = False
                        muted = False
                        vol_pct = 100
                        for line in block.splitlines():
                            sline = line.strip()
                            if sline.startswith("Corked:"):
                                corked = "yes" in sline.lower()
                            elif sline.startswith("Mute:"):
                                muted = "yes" in sline.lower()
                            elif sline.startswith("Volume:"):
                                m = re.search(r"(\d+)%", sline)
                                if m:
                                    vol_pct = int(m.group(1))
                            elif "=" in sline:
                                k, v = sline.split("=", 1)
                                proplist[k.strip()] = v.strip().strip('"')

                        proc_name = self._get_primary_linux_proc_name(proplist)
                        if proc_name:
                            peak = 0.0 if (corked or muted or vol_pct == 0) else min(1.0, vol_pct / 100.0)
                            active_processes[proc_name] = max(active_processes.get(proc_name, 0.0), peak)
            except Exception as e:
                logger.debug(f"Error en fallback pactl: {e}")

        return active_processes

    def get_active_audio_processes(self) -> Dict[str, float]:
        if IS_WINDOWS:
            return self._get_active_audio_processes_windows()
        elif IS_LINUX:
            return self._get_active_audio_processes_linux()
        return {}

    # ------------------------------------------------------------------
    # DETECCIÓN Y MEDICIÓN DE MICRÓFONOS (WINDOWS & LINUX)
    # ------------------------------------------------------------------
    def _is_active_capture_device(self, dev) -> bool:
        if not (dev.id and dev.id.startswith("{0.0.1.")):
            return False
        state = getattr(dev, "state", None)
        if state is None:
            return True
        state_val = getattr(state, "value", state)
        return state_val == 1 or "Active" in str(state)

    def get_available_microphones(self) -> List[str]:
        mics = ["Default"]

        if IS_WINDOWS and AudioUtilities is not None:
            self._ensure_com()
            try:
                devices = AudioUtilities.GetAllDevices()
                for dev in devices:
                    if self._is_active_capture_device(dev):
                        name = dev.FriendlyName
                        if name and name not in mics:
                            mics.append(name)
            except Exception as e:
                logger.debug(f"Error al listar micrófonos en Windows: {e}")
            return mics

        if IS_LINUX:
            if pulsectl is not None:
                try:
                    with pulsectl.Pulse("audioducker-mics") as pulse:
                        for src in pulse.source_list():
                            if src.name and not src.name.endswith(".monitor"):
                                desc = (src.description or src.name).strip()
                                if desc and desc not in mics:
                                    mics.append(desc)
                    return mics
                except Exception as e:
                    logger.debug(f"Error al listar micrófonos con pulsectl: {e}")

            if shutil.which("pactl"):
                try:
                    res = subprocess.run(["pactl", "list", "sources"], capture_output=True, text=True, timeout=2)
                    if res.returncode == 0:
                        for block in res.stdout.split("Source #")[1:]:
                            name = ""
                            desc = ""
                            for line in block.splitlines():
                                sline = line.strip()
                                if sline.startswith("Name:"):
                                    name = sline.split(":", 1)[1].strip()
                                elif sline.startswith("Description:"):
                                    desc = sline.split(":", 1)[1].strip()
                            if name and not name.endswith(".monitor"):
                                label = desc or name
                                if label not in mics:
                                    mics.append(label)
                except Exception:
                    pass

        return mics

    def get_microphone_peak(self, mic_name: str = "Default") -> float:
        if IS_WINDOWS and AudioUtilities is not None:
            self._ensure_com()
            try:
                if mic_name == "Default" or not mic_name:
                    mic_dev = AudioUtilities.GetMicrophone()
                    if mic_dev:
                        raw_dev = getattr(mic_dev, "_dev", mic_dev)
                        meter = raw_dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None).QueryInterface(IAudioMeterInformation)
                        return float(meter.GetPeakValue())
                else:
                    devices = AudioUtilities.GetAllDevices()
                    for dev in devices:
                        if self._is_active_capture_device(dev) and dev.FriendlyName == mic_name:
                            try:
                                meter = dev._dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None).QueryInterface(IAudioMeterInformation)
                                return float(meter.GetPeakValue())
                            except Exception:
                                continue
            except Exception as e:
                logger.debug(f"Error leyendo pico del micrófono '{mic_name}' en Windows: {e}")
            return 0.0

        if IS_LINUX and pulsectl is not None:
            try:
                with pulsectl.Pulse("audioducker-mic-peak") as pulse:
                    target_source_name = None
                    if mic_name == "Default" or not mic_name:
                        default_src = pulse.server_info().default_source_name
                        if default_src and not default_src.endswith(".monitor"):
                            target_source_name = default_src
                        else:
                            for src in pulse.source_list():
                                if src.name and not src.name.endswith(".monitor"):
                                    target_source_name = src.name
                                    break
                    else:
                        for src in pulse.source_list():
                            if src.name and not src.name.endswith(".monitor"):
                                if src.description == mic_name or src.name == mic_name:
                                    target_source_name = src.name
                                    break

                    if target_source_name:
                        return float(pulse.get_peak_sample(target_source_name, timeout=0.02))
            except Exception as e:
                logger.debug(f"Error leyendo pico del micrófono '{mic_name}' en Linux: {e}")

        return 0.0

    # ------------------------------------------------------------------
    # VERIFICACIÓN DE ACTIVADORES (TRIGGERS)
    # ------------------------------------------------------------------
    def get_peak_for_app(self, app_name: str, active_procs: Dict[str, float]) -> float:
        """Obtiene el pico máximo actual para una aplicación considerando sus alias en Windows y Linux."""
        aliases = expand_process_aliases(app_name)
        peak = 0.0
        for proc_k, proc_peak in active_procs.items():
            pk_clean = proc_k.lower().strip()
            pk_no_ext = pk_clean[:-4] if pk_clean.endswith(".exe") else pk_clean
            if pk_clean in aliases or pk_no_ext in aliases:
                peak = max(peak, proc_peak)
        return peak

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

            if not is_enabled:
                continue

            peak = self.get_peak_for_app(k_clean, active_procs)
            if peak >= req_thresh:
                speaking_triggers.add(k_clean)
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
