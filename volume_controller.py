import logging
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Dict, Any, Optional, List, Set, Tuple
import psutil

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"

if IS_WINDOWS:
    from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
    try:
        import pythoncom
    except ImportError:
        pythoncom = None
else:
    AudioUtilities = None
    ISimpleAudioVolume = None
    pythoncom = None

if IS_LINUX:
    try:
        import pulsectl
    except ImportError:
        pulsectl = None
else:
    pulsectl = None

logger = logging.getLogger("AudioDucker.VolumeController")

# Mapeo de grupos de procesos vinculados multiplataforma (Windows + Linux + macOS)
APP_PROCESS_GROUPS: Dict[str, List[str]] = {
    "applemusic.exe": [
        "applemusic.exe", "ampapp.exe", "amplibraryagent.exe",
        "applemusicaudiohost.exe", "apple.music.exe", "cider", "cider.exe", "music"
    ],
    "spotify.exe": ["spotify.exe", "spotify", ".spotify-wrapped", "spotifyd"],
    "vlc.exe": ["vlc.exe", "vlc"],
    "chrome.exe": [
        "chrome.exe", "chrome", "google-chrome", "google-chrome-stable",
        "chromium", "chromium-browser"
    ],
    "msedge.exe": [
        "msedge.exe", "edge.exe", "msedge", "microsoft-edge",
        "microsoft-edge-stable", "microsoft-edge-beta", "microsoft-edge-dev"
    ],
    "firefox.exe": [
        "firefox.exe", "firefox", "firefox-esr", "firefox-bin", "librewolf"
    ],
    "brave.exe": ["brave.exe", "brave", "brave-browser", "brave-browser-stable"],
    "discord.exe": [
        "discord.exe", "discord", "discordptb", "discordcanary",
        "vesktop", "vesktop.bin", "webcord", "armcord"
    ],
    "telegram.exe": ["telegram.exe", "telegram", "telegram-desktop"],
    "zoom.exe": ["zoom.exe", "zoom", "zoom.real"],
    "obs64.exe": ["obs64.exe", "obs32.exe", "obs", "obs-studio"]
}


def expand_process_aliases(app_name: str) -> Set[str]:
    """Devuelve todos los posibles nombres de proceso (con y sin .exe) asociados a una app."""
    clean = app_name.lower().strip()
    no_ext = clean[:-4] if clean.endswith(".exe") else clean
    with_exe = f"{no_ext}.exe"

    aliases: Set[str] = {clean, no_ext, with_exe}
    for main_app, group in APP_PROCESS_GROUPS.items():
        group_lower = [g.lower().strip() for g in group]
        if clean in group_lower or with_exe in group_lower or no_ext in group_lower or main_app == clean:
            for item in group_lower:
                aliases.add(item)
                if item.endswith(".exe"):
                    aliases.add(item[:-4])
                else:
                    aliases.add(f"{item}.exe")
    return aliases


def resolve_linux_sink_input_names(sink_input_proplist: Dict[str, str]) -> Set[str]:
    """
    Extrae todos los nombres de proceso candidatos de un sink-input de PulseAudio/PipeWire,
    incluyendo el binario directo, el nombre de aplicación y los procesos padre vía psutil
    (indispensable para Discord, navegadores Chromium y Electron en Linux).
    """
    names: Set[str] = set()
    if not sink_input_proplist:
        return names

    for prop_key in ("application.process.binary", "application.name", "node.name", "media.name"):
        val = sink_input_proplist.get(prop_key)
        if val:
            v_clean = str(val).lower().strip()
            names.add(v_clean)
            names.add(os.path.basename(v_clean) if "/" in v_clean else v_clean)

    pid_str = sink_input_proplist.get("application.process.id")
    if pid_str:
        try:
            pid = int(pid_str)
            proc = psutil.Process(pid)
            pname = proc.name().lower().strip()
            names.add(pname)
            try:
                cmdline = proc.cmdline()
                if cmdline:
                    exe_base = cmdline[0].split("/")[-1].lower().strip()
                    if exe_base:
                        names.add(exe_base)
            except (psutil.Error, IndexError):
                pass

            # Revisar hasta 3 niveles de procesos padre (ej. WebRTC/Chromium hijo de Discord o Firefox)
            for parent in proc.parents()[:3]:
                try:
                    parent_name = parent.name().lower().strip()
                    if parent_name not in ("systemd", "init", "bash", "sh", "zsh", "fish", "flatpak-session-helper", "bwrap"):
                        names.add(parent_name)
                except psutil.Error:
                    continue
        except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    expanded: Set[str] = set()
    for n in names:
        if not n:
            continue
        expanded.add(n)
        if n.endswith(".exe"):
            expanded.add(n[:-4])
        else:
            expanded.add(f"{n}.exe")
    return expanded


import os

class SingleAppVolumeControl:
    def __init__(self, app_name: str):
        self.app_name = app_name.lower().strip()
        self.target_names: Set[str] = expand_process_aliases(self.app_name)

    def _get_windows_interfaces(self) -> List[ Any ]:
        interfaces = []
        if not IS_WINDOWS or AudioUtilities is None:
            return interfaces

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
                        proc_no_ext = proc_name[:-4] if proc_name.endswith(".exe") else proc_name
                        if proc_name in self.target_names or proc_no_ext in self.target_names:
                            interfaces.append(session._ctl.QueryInterface(ISimpleAudioVolume))
                    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                        continue
        except Exception as e:
            logger.debug(f"Error buscando sesión WASAPI para {self.app_name}: {e}")
        return interfaces

    def _set_volume_windows(self, target_volume: float, duration_seconds: float) -> bool:
        interfaces = self._get_windows_interfaces()
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
            logger.debug(f"Excepción en _set_volume_windows para {self.app_name}: {e}")
            return False

    def _set_volume_linux_pulsectl(self, target_volume: float, duration_seconds: float) -> bool:
        if pulsectl is None:
            return False

        try:
            with pulsectl.Pulse("audioducker-vol") as pulse:
                matching_inputs = []
                for si in pulse.sink_input_list():
                    candidate_names = resolve_linux_sink_input_names(si.proplist)
                    if candidate_names & self.target_names:
                        matching_inputs.append(si)

                if not matching_inputs:
                    return False

                if duration_seconds <= 0:
                    for si in matching_inputs:
                        try:
                            pulse.volume_set_all_chans(si, target_volume)
                        except Exception:
                            pass
                    return True

                try:
                    current_vol = float(matching_inputs[0].volume.value_flat)
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
                    for si in matching_inputs:
                        try:
                            pulse.volume_set_all_chans(si, new_vol)
                        except Exception:
                            pass
                    time.sleep(step_time)

                for si in matching_inputs:
                    try:
                        pulse.volume_set_all_chans(si, target_volume)
                    except Exception:
                        pass
                return True
        except Exception as e:
            logger.debug(f"Excepción en _set_volume_linux_pulsectl para {self.app_name}: {e}")
            return False

    def _get_linux_pactl_matching_indices(self) -> List[Tuple[int, float]]:
        """Fallback usando `pactl list sink-inputs` si pulsectl no está disponible."""
        if not shutil.which("pactl"):
            return []
        try:
            res = subprocess.run(
                ["pactl", "list", "sink-inputs"],
                capture_output=True, text=True, timeout=2
            )
            if res.returncode != 0:
                return []

            matches = []
            blocks = res.stdout.split("Sink Input #")
            for block in blocks[1:]:
                lines = block.splitlines()
                if not lines:
                    continue
                try:
                    idx = int(lines[0].strip())
                except ValueError:
                    continue

                proplist: Dict[str, str] = {}
                curr_vol = 1.0
                for line in lines[1:]:
                    sline = line.strip()
                    if sline.startswith("Volume:"):
                        m = re.search(r"(\d+)%", sline)
                        if m:
                            curr_vol = int(m.group(1)) / 100.0
                    elif "=" in sline:
                        parts = sline.split("=", 1)
                        k = parts[0].strip()
                        v = parts[1].strip().strip('"')
                        proplist[k] = v

                candidate_names = resolve_linux_sink_input_names(proplist)
                if candidate_names & self.target_names:
                    matches.append((idx, curr_vol))
            return matches
        except Exception:
            return []

    def _set_volume_linux_pactl(self, target_volume: float, duration_seconds: float) -> bool:
        matches = self._get_linux_pactl_matching_indices()
        if not matches:
            return False

        indices = [m[0] for m in matches]
        current_vol = matches[0][1]
        target_pct = int(round(target_volume * 100))

        if duration_seconds <= 0 or abs(current_vol - target_volume) < 0.01:
            for idx in indices:
                subprocess.run(["pactl", "set-sink-input-volume", str(idx), f"{target_pct}%"], capture_output=True)
            return True

        steps = max(3, min(12, int(duration_seconds / 0.04)))
        step_time = duration_seconds / steps
        vol_diff = target_volume - current_vol
        step_size = vol_diff / steps

        for i in range(1, steps + 1):
            new_pct = int(round(max(0.0, min(1.0, current_vol + (step_size * i))) * 100))
            for idx in indices:
                subprocess.run(["pactl", "set-sink-input-volume", str(idx), f"{new_pct}%"], capture_output=True)
            time.sleep(step_time)

        for idx in indices:
            subprocess.run(["pactl", "set-sink-input-volume", str(idx), f"{target_pct}%"], capture_output=True)
        return True

    def set_volume(self, target_volume: float, duration_seconds: float = 0.4) -> bool:
        target_volume = max(0.0, min(1.0, float(target_volume)))
        if IS_WINDOWS:
            return self._set_volume_windows(target_volume, duration_seconds)
        elif IS_LINUX:
            if pulsectl is not None:
                if self._set_volume_linux_pulsectl(target_volume, duration_seconds):
                    return True
            return self._set_volume_linux_pactl(target_volume, duration_seconds)
        return False


class MultiVolumeController:
    """
    Controla el volumen de MÚLTIPLES aplicaciones objetivo de forma simultánea
    (en paralelo mediante hilos para que la transición sea simultánea en todas las apps).
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
        target_vol = max(0.0, min(1.0, trigger_lowest_ratio)) if is_ducked else 1.0

        threads = []
        for app_name, app_info in target_apps_config.items():
            is_enabled = True
            if isinstance(app_info, dict):
                is_enabled = app_info.get("enabled", True)

            if not is_enabled:
                continue

            app_control = SingleAppVolumeControl(app_name)
            t = threading.Thread(
                target=app_control.set_volume,
                args=(target_vol, duration),
                daemon=True
            )
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=max(0.5, duration + 0.5))
