import json
import logging
import os
import sys
import threading
from typing import Dict, Any, Set
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pystray
from PIL import Image

from detector import AudioDetector

logger = logging.getLogger("AudioDucker.GUI")

def resolve_exe_name(filepath: str) -> str:
    filepath = filepath.strip()
    
    if filepath.lower().endswith(".lnk"):
        target_name = None

        try:
            import win32com.client
            folder_path = os.path.dirname(os.path.abspath(filepath))
            file_name = os.path.basename(filepath)
            shell = win32com.client.Dispatch("Shell.Application")
            folder = shell.NameSpace(folder_path)
            item = folder.ParseName(file_name)
            if item and item.IsLink:
                link = item.GetLink
                if link and link.Target:
                    t_path = str(link.Target.Path)
                    t_name = str(link.Target.Name)

                    if t_path.lower().endswith(".exe"):
                        return os.path.basename(t_path).lower()

                    if t_name and t_name.strip():
                        target_name = t_name.strip().lower()
                    elif t_path:
                        parts = t_path.split("!")
                        target_name = parts[-1].split(".")[-1].lower()
        except Exception as e:
            logger.debug(f"Error resolviendo acceso directo con Shell.Application: {e}")

        if not target_name:
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortcut(filepath)
                target = shortcut.TargetPath
                if target and target.lower().endswith(".exe"):
                    return os.path.basename(target).lower()
            except Exception as e:
                logger.debug(f"Error resolviendo acceso directo con WScript.Shell: {e}")

        if target_name:
            target_name = target_name.replace(" - acceso directo", "").replace(" - shortcut", "").strip()
            target_clean = target_name.replace(" ", "")
            if not target_clean.endswith(".exe"):
                target_clean += ".exe"
            return target_clean

    filename = os.path.basename(filepath).lower().strip()
    filename = filename.replace(" - acceso directo.lnk", ".exe").replace(" - acceso directo", "")
    if filename.endswith(".lnk"):
        filename = filename.replace(".lnk", "")
    if not filename.endswith(".exe"):
        filename += ".exe"
    
    return filename.replace(" ", "")

def disable_slider_mousewheel(slider: ctk.CTkSlider):
    try:
        slider.unbind("<MouseWheel>")
        slider.unbind("<Button-4>")
        slider.unbind("<Button-5>")
        if hasattr(slider, "_canvas"):
            slider._canvas.unbind("<MouseWheel>")
            slider._canvas.unbind("<Button-4>")
            slider._canvas.unbind("<Button-5>")
            slider._canvas.bind("<MouseWheel>", lambda e: "break")
            slider._canvas.bind("<Button-4>", lambda e: "break")
            slider._canvas.bind("<Button-5>", lambda e: "break")
    except Exception:
        pass


class AudioDuckerGUI(ctk.CTk):
    def __init__(self, config_path: str, on_config_updated_callback=None, on_restart_service_callback=None):
        super().__init__()

        self.config_path = config_path
        self.on_config_updated_callback = on_config_updated_callback
        self.on_restart_service_callback = on_restart_service_callback
        self.detector = AudioDetector()
        self.config_data = self.load_config()
        self.trigger_live_widgets = {}
        self.expanded_trigger_cards: Set[str] = set()

        # Configuración de ventana
        self.title("AudioDucker v2.01 - Control de Volumen Inteligente")
        self.geometry("960x720")
        self.minsize(880, 620)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            
        self.icon_path = os.path.join(base_dir, "assets", "logo.ico")
        if os.path.exists(self.icon_path):
            try:
                self.iconbitmap(self.icon_path)
            except Exception:
                pass

        self.active_tab = "targets"
        self._build_sidebar_layout()

        # Configuración de bandeja de sistema (System Tray / Iconos Ocultos)
        self.tray_icon = None
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self._init_system_tray()

        self.after(200, self._update_live_meters)

    def _init_system_tray(self):
        try:
            if os.path.exists(self.icon_path):
                img = Image.open(self.icon_path)
            else:
                img = Image.new('RGB', (64, 64), color=(30, 136, 229))

            menu = pystray.Menu(
                pystray.MenuItem("🎵 Mostrar AudioDucker", lambda icon, item: self.after(0, self.show_window_from_tray), default=True),
                pystray.MenuItem("🔄 Reiniciar Servicio", lambda icon, item: self.after(0, self._restart_service)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("❌ Salir Completamente", lambda icon, item: self.after(0, self.quit_app_from_tray))
            )

            self.tray_icon = pystray.Icon("AudioDucker", img, "AudioDucker v2.01", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            logger.debug(f"Error inicializando bandeja de sistema: {e}")

    def hide_to_tray(self):
        self.withdraw()
        if self.tray_icon:
            try:
                self.tray_icon.notify("AudioDucker continúa ejecutándose en segundo plano (Iconos Ocultos).", "AudioDucker Minimizado")
            except Exception:
                pass

    def show_window_from_tray(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def quit_app_from_tray(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.destroy()

    def load_config(self) -> Dict[str, Any]:
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

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    if "target_app" in data and "target_apps" not in data:
                        target_single = str(data["target_app"]).lower()
                        data["target_apps"] = {target_single: {"enabled": True}}
                    
                    if "target_apps" in data and isinstance(data["target_apps"], dict):
                        clean_targets = {}
                        for tk_name, tv_info in data["target_apps"].items():
                            clean_k = str(tk_name).lower()
                            if isinstance(tv_info, dict):
                                clean_targets[clean_k] = {"enabled": bool(tv_info.get("enabled", True))}
                            else:
                                clean_targets[clean_k] = {"enabled": True}
                        data["target_apps"] = clean_targets

                    if "trigger_apps" in data and isinstance(data["trigger_apps"], dict):
                        clean_triggers = {}
                        for app_k, app_v in data["trigger_apps"].items():
                            app_k_clean = str(app_k).lower()
                            if isinstance(app_v, dict):
                                clean_triggers[app_k_clean] = {
                                    "enabled": bool(app_v.get("enabled", True)),
                                    "duck_volume": float(app_v.get("duck_volume", 0.25)),
                                    "trigger_threshold": float(app_v.get("trigger_threshold", 0.05))
                                }
                            else:
                                clean_triggers[app_k_clean] = {
                                    "enabled": True,
                                    "duck_volume": float(app_v),
                                    "trigger_threshold": 0.05
                                }
                        data["trigger_apps"] = clean_triggers

                    return {**default_config, **data}
            except Exception:
                pass
        return default_config

    def save_config(self, show_msg: bool = True):
        try:
            self.config_data["version"] = "2.01"
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            if self.on_config_updated_callback:
                self.on_config_updated_callback(self.config_data)
            if show_msg:
                messagebox.showinfo("Éxito", "¡Configuración guardada correctamente!")
        except Exception as e:
            if show_msg:
                messagebox.showerror("Error", f"No se pudo guardar la configuración: {e}")

    def _restart_service(self):
        self.save_config(show_msg=False)
        if self.on_restart_service_callback:
            self.on_restart_service_callback()
        messagebox.showinfo("Reinicio de Servicio", "¡El servicio de AudioDucker ha sido reiniciado correctamente!")

    def _build_sidebar_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="🎵 AudioDucker\nVersion 2.01",
            font=("Segoe UI", 16, "bold"),
            text_color="#1E88E5"
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 20))

        self.btn_nav_targets = ctk.CTkButton(
            self.sidebar_frame,
            text="🎯 Apps Objetivo",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
            height=40,
            command=lambda: self._select_tab("targets")
        )
        self.btn_nav_targets.grid(row=1, column=0, padx=15, pady=6, sticky="ew")

        self.btn_nav_triggers = ctk.CTkButton(
            self.sidebar_frame,
            text="📱 Apps Activadoras",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
            height=40,
            command=lambda: self._select_tab("triggers")
        )
        self.btn_nav_triggers.grid(row=2, column=0, padx=15, pady=6, sticky="ew")

        self.btn_nav_mic = ctk.CTkButton(
            self.sidebar_frame,
            text="🎤 Micrófono",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
            height=40,
            command=lambda: self._select_tab("mic")
        )
        self.btn_nav_mic.grid(row=3, column=0, padx=15, pady=6, sticky="ew")

        self.btn_nav_settings = ctk.CTkButton(
            self.sidebar_frame,
            text="⚙️ Transición & Tiempos",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
            height=40,
            command=lambda: self._select_tab("settings")
        )
        self.btn_nav_settings.grid(row=4, column=0, padx=15, pady=6, sticky="ew")

        btn_detect_live = ctk.CTkButton(
            self.sidebar_frame,
            text="🔍 Escanear Sonidos",
            fg_color="#00897B",
            hover_color="#00695C",
            font=("Segoe UI", 12, "bold"),
            command=self._show_live_processes_modal
        )
        btn_detect_live.grid(row=6, column=0, padx=15, pady=(10, 4), sticky="ew")

        btn_restart = ctk.CTkButton(
            self.sidebar_frame,
            text="🔄 Reiniciar Servicio",
            fg_color="#D81B60",
            hover_color="#AD1457",
            font=("Segoe UI", 12, "bold"),
            command=self._restart_service
        )
        btn_restart.grid(row=7, column=0, padx=15, pady=4, sticky="ew")

        btn_tray = ctk.CTkButton(
            self.sidebar_frame,
            text="📌 Minimizar a Bandeja",
            fg_color="#455A64",
            hover_color="#37474F",
            font=("Segoe UI", 12, "bold"),
            command=self.hide_to_tray
        )
        btn_tray.grid(row=8, column=0, padx=15, pady=4, sticky="ew")

        btn_save = ctk.CTkButton(
            self.sidebar_frame,
            text="💾 Guardar Cambios",
            fg_color="#1565C0",
            hover_color="#0D47A1",
            font=("Segoe UI", 12, "bold"),
            command=self.save_config
        )
        btn_save.grid(row=9, column=0, padx=15, pady=4, sticky="ew")

        btn_startup = ctk.CTkButton(
            self.sidebar_frame,
            text="🚀 Inicio en Windows",
            fg_color="#6A1B9A",
            hover_color="#4A148C",
            font=("Segoe UI", 12, "bold"),
            command=self._install_startup
        )
        btn_startup.grid(row=10, column=0, padx=15, pady=(4, 20), sticky="ew")

        self.main_content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content_frame.grid(row=0, column=1, padx=15, pady=15, sticky="nsew")

        self._create_targets_view()
        self._create_triggers_view()
        self._create_mic_view()
        self._create_settings_view()

        self._select_tab("targets")

    def _select_tab(self, tab_name: str):
        self.active_tab = tab_name

        self.btn_nav_targets.configure(fg_color=["#3B8ED0", "#1F6AA5"] if tab_name == "targets" else "transparent")
        self.btn_nav_triggers.configure(fg_color=["#3B8ED0", "#1F6AA5"] if tab_name == "triggers" else "transparent")
        self.btn_nav_mic.configure(fg_color=["#3B8ED0", "#1F6AA5"] if tab_name == "mic" else "transparent")
        self.btn_nav_settings.configure(fg_color=["#3B8ED0", "#1F6AA5"] if tab_name == "settings" else "transparent")

        self.targets_view.pack_forget()
        self.triggers_view.pack_forget()
        self.mic_view.pack_forget()
        self.settings_view.pack_forget()

        if tab_name == "targets":
            self.targets_view.pack(fill="both", expand=True)
        elif tab_name == "triggers":
            self.triggers_view.pack(fill="both", expand=True)
        elif tab_name == "mic":
            self.mic_view.pack(fill="both", expand=True)
        elif tab_name == "settings":
            self.settings_view.pack(fill="both", expand=True)

    # MODAL DE PROCESOS ACTIVOS EN TIEMPO REAL
    def _show_live_processes_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("🔍 Escáner de Procesos de Audio en Vivo")
        modal.geometry("540x450")
        modal.grab_set()

        ctk.CTkLabel(
            modal,
            text="Procesos de Audio Registrados en Windows",
            font=("Segoe UI", 14, "bold"),
            text_color="#00BFA5"
        ).pack(pady=10, padx=15, anchor="w")

        ctk.CTkLabel(
            modal,
            text="Haz clic en cualquier programa detectado para agregarlo directamente a tu lista:",
            font=("Segoe UI", 11, "italic"),
            text_color="#B0BEC5"
        ).pack(pady=(0, 10), padx=15, anchor="w")

        scroll = ctk.CTkScrollableFrame(modal)
        scroll.pack(fill="both", expand=True, padx=15, pady=10)

        procs = self.detector.get_active_audio_processes()
        if not procs:
            ctk.CTkLabel(scroll, text="No hay programas emitiendo audio en este instante.").pack(pady=20)
        else:
            for proc_name, peak in procs.items():
                if proc_name.startswith("@"):
                    continue
                row = ctk.CTkFrame(scroll)
                row.pack(fill="x", pady=4, padx=2)

                peak_pct = int(peak * 100)
                ctk.CTkLabel(row, text=f"🔊 {proc_name} ({peak_pct}%)", font=("Segoe UI", 12, "bold")).pack(side="left", padx=10, pady=8)

                btn_add_t = ctk.CTkButton(
                    row,
                    text="🎯 Asignar Objetivo",
                    width=130,
                    fg_color="#2E7D32",
                    hover_color="#1B5E20",
                    command=lambda p=proc_name: self._add_proc_from_scanner(p, is_target=True, modal_win=modal)
                )
                btn_add_t.pack(side="right", padx=5)

                btn_add_tr = ctk.CTkButton(
                    row,
                    text="📱 Asignar Activadora",
                    width=135,
                    fg_color="#1565C0",
                    hover_color="#0D47A1",
                    command=lambda p=proc_name: self._add_proc_from_scanner(p, is_target=False, modal_win=modal)
                )
                btn_add_tr.pack(side="right", padx=5)

    def _add_proc_from_scanner(self, proc_name: str, is_target: bool, modal_win: ctk.CTkToplevel):
        proc_clean = proc_name.lower().strip()
        if is_target:
            if "target_apps" not in self.config_data:
                self.config_data["target_apps"] = {}
            self.config_data["target_apps"][proc_clean] = {"enabled": True}
            self.save_config(show_msg=False)
            self._refresh_targets_list()
            messagebox.showinfo("Proceso Agregado", f"Se agregó '{proc_clean}' como App Objetivo.")
        else:
            if "trigger_apps" not in self.config_data:
                self.config_data["trigger_apps"] = {}
            self.config_data["trigger_apps"][proc_clean] = {"enabled": True, "duck_volume": 0.30, "trigger_threshold": 0.05}
            self.save_config(show_msg=False)
            self._refresh_triggers_list()
            messagebox.showinfo("Proceso Agregado", f"Se agregó '{proc_clean}' como App Activadora.")
        modal_win.destroy()

    # VISTA 1: APPS OBJETIVO
    def _create_targets_view(self):
        self.targets_view = ctk.CTkFrame(self.main_content_frame, fg_color="transparent")

        header = ctk.CTkFrame(self.targets_view, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            header,
            text="🎯 Aplicaciones Objetivo (A las que se les BAJARÁ el volumen)",
            font=("Segoe UI", 16, "bold"),
            text_color="#81C784"
        ).pack(side="left")

        btn_add = ctk.CTkButton(
            header,
            text="📁 Agregar App Objetivo (.exe)",
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            font=("Segoe UI", 12, "bold"),
            command=self._browse_and_add_target_exe
        )
        btn_add.pack(side="right")

        ctk.CTkLabel(
            self.targets_view,
            text="💡 Nota: El nivel de bajada de volumen se define en las Apps Activadoras o Micrófono.",
            font=("Segoe UI", 11, "italic"),
            text_color="#B0BEC5"
        ).pack(anchor="w", pady=(0, 10))

        self.targets_scroll = ctk.CTkScrollableFrame(self.targets_view)
        self.targets_scroll.pack(fill="both", expand=True)
        self._refresh_targets_list()

    def _refresh_targets_list(self):
        for w in self.targets_scroll.winfo_children():
            w.destroy()

        targets = self.config_data.get("target_apps", {})
        if not targets:
            ctk.CTkLabel(self.targets_scroll, text="No hay aplicaciones objetivo. Agrega una con el botón 'Agregar App Objetivo (.exe)'.").pack(pady=20)
            return

        for app_name, app_info in list(targets.items()):
            row = ctk.CTkFrame(self.targets_scroll)
            row.pack(fill="x", pady=5, padx=5)

            is_enabled = app_info.get("enabled", True) if isinstance(app_info, dict) else True
            sw_var = ctk.BooleanVar(value=is_enabled)

            sw = ctk.CTkSwitch(
                row,
                text=f"🎯 {app_name}",
                variable=sw_var,
                font=("Segoe UI", 13, "bold"),
                command=lambda name=app_name, var=sw_var: self._toggle_target_enabled(name, var.get())
            )
            sw.pack(side="left", padx=10, pady=10)

            status_lbl = ctk.CTkLabel(
                row,
                text="[ACTIVADO: Bajará volumen si hay sonido]" if is_enabled else "[DESACTIVADO: No se tocará volumen]",
                font=("Segoe UI", 11, "italic"),
                text_color="#81C784" if is_enabled else "#E57373"
            )
            status_lbl.pack(side="left", padx=15)

            btn_del = ctk.CTkButton(
                row,
                text="❌ Eliminar",
                width=80,
                fg_color="#D32F2F",
                hover_color="#B71C1C",
                command=lambda name=app_name: self._delete_target_app(name)
            )
            btn_del.pack(side="right", padx=10)

    def _toggle_target_enabled(self, app_name: str, enabled: bool):
        if app_name in self.config_data["target_apps"]:
            self.config_data["target_apps"][app_name]["enabled"] = enabled
            self.save_config(show_msg=False)
            self._refresh_targets_list()

    def _browse_and_add_target_exe(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar Ejecutable o Acceso Directo de Aplicación Objetivo",
            filetypes=[("Archivos Ejecutables o Accesos directos", "*.exe;*.lnk"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            filename = resolve_exe_name(filepath)
            if "target_apps" not in self.config_data:
                self.config_data["target_apps"] = {}
            self.config_data["target_apps"][filename] = {"enabled": True}
            self.save_config(show_msg=False)
            self._refresh_targets_list()
            messagebox.showinfo("App Objetivo Agregada", f"Se detectó e identificó '{filename}'. Se agregó a las aplicaciones objetivo activadas.")

    def _delete_target_app(self, app_name: str):
        if app_name in self.config_data["target_apps"]:
            del self.config_data["target_apps"][app_name]
            self.save_config(show_msg=False)
            self._refresh_targets_list()

    # VISTA 2: APPS ACTIVADORAS
    def _create_triggers_view(self):
        self.triggers_view = ctk.CTkFrame(self.main_content_frame, fg_color="transparent")

        header = ctk.CTkFrame(self.triggers_view, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            header,
            text="📱 Aplicaciones Activadoras (Las que PROVOCAN la bajada)",
            font=("Segoe UI", 16, "bold"),
            text_color="#64B5F6"
        ).pack(side="left")

        btn_add = ctk.CTkButton(
            header,
            text="📁 Agregar App Activadora (.exe)",
            fg_color="#1565C0",
            hover_color="#0D47A1",
            font=("Segoe UI", 12, "bold"),
            command=self._browse_and_add_trigger_exe
        )
        btn_add.pack(side="right")

        ctk.CTkLabel(
            self.triggers_view,
            text="💡 Haz clic en '⚙️ Opciones' en cualquier app para desplegar y ajustar sus controles.",
            font=("Segoe UI", 11, "italic"),
            text_color="#B0BEC5"
        ).pack(anchor="w", pady=(0, 10))

        self.triggers_scroll = ctk.CTkScrollableFrame(self.triggers_view)
        self.triggers_scroll.pack(fill="both", expand=True)
        self._refresh_triggers_list()

    def _refresh_triggers_list(self):
        for w in self.triggers_scroll.winfo_children():
            w.destroy()

        self.trigger_live_widgets = {}

        triggers = self.config_data.get("trigger_apps", {})
        if not triggers:
            ctk.CTkLabel(self.triggers_scroll, text="No hay aplicaciones activadoras configuradas.").pack(pady=20)
            return

        for app_name, app_info in list(triggers.items()):
            card = ctk.CTkFrame(self.triggers_scroll)
            card.pack(fill="x", pady=6, padx=5)

            is_enabled = app_info.get("enabled", True) if isinstance(app_info, dict) else True
            duck_vol = app_info.get("duck_volume", 0.25) if isinstance(app_info, dict) else float(app_info)
            trig_thresh = app_info.get("trigger_threshold", 0.05) if isinstance(app_info, dict) else 0.05
            
            duck_pct = int(duck_vol * 100)
            thresh_pct = int(trig_thresh * 100)

            # -------------------------------------------------------------
            # HEADER BAR (Siempre Visible)
            # -------------------------------------------------------------
            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=8)

            sw_var = ctk.BooleanVar(value=is_enabled)
            sw = ctk.CTkSwitch(
                top_row,
                text=f"📱 {app_name}",
                variable=sw_var,
                font=("Segoe UI", 13, "bold"),
                width=170,
                command=lambda name=app_name, var=sw_var: self._toggle_trigger_enabled(name, var.get())
            )
            sw.pack(side="left", padx=(0, 10))

            summary_lbl = ctk.CTkLabel(
                top_row,
                text=f"Bajar a: {duck_pct}%  ·  Umbral: {thresh_pct}%",
                font=("Segoe UI", 11, "italic"),
                text_color="#90A4AE"
            )
            summary_lbl.pack(side="left", padx=10)

            btn_del = ctk.CTkButton(
                top_row,
                text="❌",
                width=36,
                fg_color="#D32F2F",
                hover_color="#B71C1C",
                command=lambda name=app_name: self._delete_trigger_app(name)
            )
            btn_del.pack(side="right", padx=(5, 0))

            # Contenedor desplegable (Collapsible Body)
            body_frame = ctk.CTkFrame(card, fg_color="#1A1A1A", corner_radius=6)

            # Botón Desplegable (Acordeón)
            is_open = app_name in self.expanded_trigger_cards
            btn_expand = ctk.CTkButton(
                top_row,
                text="⚙️ Opciones 🔺" if is_open else "⚙️ Opciones 🔻",
                width=115,
                fg_color="#1E88E5" if is_open else "#37474F",
                hover_color="#1565C0" if is_open else "#455A64",
                font=("Segoe UI", 11, "bold"),
                command=lambda name=app_name, body=body_frame, btn=None: self._toggle_trigger_card_expand(name, body, btn)
            )
            # Re-vincular para pasar el propio botón
            btn_expand.configure(command=lambda name=app_name, body=body_frame, btn=btn_expand: self._toggle_trigger_card_expand(name, body, btn))
            btn_expand.pack(side="right", padx=5)

            # -------------------------------------------------------------
            # CUERPO DESPLEGABLE (Opciones Configurables)
            # -------------------------------------------------------------

            # Medidor en Vivo
            meter_frame = ctk.CTkFrame(body_frame, fg_color="#252525")
            meter_frame.pack(fill="x", padx=12, pady=(10, 6))

            pbar = ctk.CTkProgressBar(meter_frame, height=10)
            pbar.set(0.0)
            pbar.pack(fill="x", padx=8, pady=(6, 2))

            status_lbl = ctk.CTkLabel(
                meter_frame,
                text=f"Sonido actual: 0% | ⚪ En silencio (Umbral: {thresh_pct}%)",
                font=("Segoe UI", 10, "italic"),
                text_color="#9E9E9E"
            )
            status_lbl.pack(anchor="w", padx=8, pady=(0, 4))
            self.trigger_live_widgets[app_name] = (pbar, status_lbl)

            # Fila 1: Nivel de Atenuación (Duck Volume)
            vol_row = ctk.CTkFrame(body_frame, fg_color="transparent")
            vol_row.pack(fill="x", padx=12, pady=6)

            ctk.CTkLabel(vol_row, text="Bajar objetivo a:", font=("Segoe UI", 11)).pack(side="left")

            btn_v_sub = ctk.CTkButton(vol_row, text="-", width=26, command=lambda name=app_name: self._step_trigger_vol(name, -5))
            btn_v_sub.pack(side="left", padx=4)

            entry_vol = ctk.CTkEntry(vol_row, width=42, justify="center")
            entry_vol.insert(0, str(duck_pct))
            entry_vol.pack(side="left", padx=2)

            ctk.CTkLabel(vol_row, text="%").pack(side="left", padx=1)

            btn_v_add = ctk.CTkButton(vol_row, text="+", width=26, command=lambda name=app_name: self._step_trigger_vol(name, 5))
            btn_v_add.pack(side="left", padx=4)

            slider_vol = ctk.CTkSlider(
                vol_row,
                from_=0.0,
                to=1.0,
                number_of_steps=100,
                command=lambda val, name=app_name, ent=entry_vol: self._on_trigger_slider_change(name, val, ent)
            )
            slider_vol.set(duck_vol)
            slider_vol.pack(side="right", fill="x", expand=True, padx=8)
            disable_slider_mousewheel(slider_vol)

            entry_vol.bind("<FocusOut>", lambda e, name=app_name, ent=entry_vol, s=slider_vol: self._validate_trigger_entry(name, ent, s))
            entry_vol.bind("<Return>", lambda e, name=app_name, ent=entry_vol, s=slider_vol: self._validate_trigger_entry(name, ent, s))

            # Fila 2: Umbral Mínimo de Sonido / Sensibilidad (Trigger Threshold)
            thresh_row = ctk.CTkFrame(body_frame, fg_color="transparent")
            thresh_row.pack(fill="x", padx=12, pady=(2, 10))

            ctk.CTkLabel(thresh_row, text="Activar si sonido >", font=("Segoe UI", 11, "bold"), text_color="#FFB74D").pack(side="left")

            btn_t_sub = ctk.CTkButton(thresh_row, text="-", width=26, command=lambda name=app_name: self._step_trigger_thresh(name, -1))
            btn_t_sub.pack(side="left", padx=4)

            entry_thresh = ctk.CTkEntry(thresh_row, width=42, justify="center")
            entry_thresh.insert(0, str(thresh_pct))
            entry_thresh.pack(side="left", padx=2)

            ctk.CTkLabel(thresh_row, text="%").pack(side="left", padx=1)

            btn_t_add = ctk.CTkButton(thresh_row, text="+", width=26, command=lambda name=app_name: self._step_trigger_thresh(name, 1))
            btn_t_add.pack(side="left", padx=4)

            slider_thresh = ctk.CTkSlider(
                thresh_row,
                from_=0.01,
                to=1.0,
                number_of_steps=99,
                command=lambda val, name=app_name, ent=entry_thresh: self._on_trigger_thresh_slider_change(name, val, ent)
            )
            slider_thresh.set(trig_thresh)
            slider_thresh.pack(side="right", fill="x", expand=True, padx=8)
            disable_slider_mousewheel(slider_thresh)

            entry_thresh.bind("<FocusOut>", lambda e, name=app_name, ent=entry_thresh, s=slider_thresh: self._validate_trigger_thresh_entry(name, ent, s))
            entry_thresh.bind("<Return>", lambda e, name=app_name, ent=entry_thresh, s=slider_thresh: self._validate_trigger_thresh_entry(name, ent, s))

            # Mostrar u ocultar cuerpo según estado guardado
            if is_open:
                body_frame.pack(fill="x", padx=8, pady=(0, 8))
            else:
                body_frame.pack_forget()

    def _toggle_trigger_card_expand(self, app_name: str, body_frame: ctk.CTkFrame, btn_expand: ctk.CTkButton):
        if app_name in self.expanded_trigger_cards:
            self.expanded_trigger_cards.remove(app_name)
            body_frame.pack_forget()
            if btn_expand:
                btn_expand.configure(text="⚙️ Opciones 🔻", fg_color="#37474F")
        else:
            self.expanded_trigger_cards.add(app_name)
            body_frame.pack(fill="x", padx=8, pady=(0, 8))
            if btn_expand:
                btn_expand.configure(text="⚙️ Opciones 🔺", fg_color="#1E88E5")

    def _toggle_trigger_enabled(self, app_name: str, enabled: bool):
        if app_name in self.config_data["trigger_apps"]:
            if isinstance(self.config_data["trigger_apps"][app_name], dict):
                self.config_data["trigger_apps"][app_name]["enabled"] = enabled
            else:
                vol = float(self.config_data["trigger_apps"][app_name])
                self.config_data["trigger_apps"][app_name] = {"enabled": enabled, "duck_volume": vol, "trigger_threshold": 0.05}
            self.save_config(show_msg=False)

    def _browse_and_add_trigger_exe(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar Ejecutable o Acceso Directo de Aplicación Activadora",
            filetypes=[("Archivos Ejecutables o Accesos directos", "*.exe;*.lnk"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            filename = resolve_exe_name(filepath)
            if "trigger_apps" not in self.config_data:
                self.config_data["trigger_apps"] = {}
            self.config_data["trigger_apps"][filename] = {"enabled": True, "duck_volume": 0.30, "trigger_threshold": 0.05}
            self.expanded_trigger_cards.add(filename)
            self.save_config(show_msg=False)
            self._refresh_triggers_list()
            messagebox.showinfo("App Activadora Agregada", f"Se detectó e identificó '{filename}'. Se agregó a las aplicaciones activadoras.")

    def _delete_trigger_app(self, app_name: str):
        if app_name in self.config_data["trigger_apps"]:
            del self.config_data["trigger_apps"][app_name]
            if app_name in self.expanded_trigger_cards:
                self.expanded_trigger_cards.remove(app_name)
            self.save_config(show_msg=False)
            self._refresh_triggers_list()

    def _on_trigger_slider_change(self, app_name: str, val: float, entry_widget: ctk.CTkEntry):
        pct = max(0, min(100, int(round(val * 100))))
        entry_widget.delete(0, "end")
        entry_widget.insert(0, str(pct))
        if app_name in self.config_data["trigger_apps"]:
            if isinstance(self.config_data["trigger_apps"][app_name], dict):
                self.config_data["trigger_apps"][app_name]["duck_volume"] = pct / 100.0
            else:
                self.config_data["trigger_apps"][app_name] = {"enabled": True, "duck_volume": pct / 100.0, "trigger_threshold": 0.05}

    def _step_trigger_vol(self, app_name: str, delta: int):
        if app_name in self.config_data["trigger_apps"]:
            app_info = self.config_data["trigger_apps"][app_name]
            curr = int((app_info.get("duck_volume", 0.25) if isinstance(app_info, dict) else float(app_info)) * 100)
            new_val = max(0, min(100, curr + delta))
            if isinstance(app_info, dict):
                self.config_data["trigger_apps"][app_name]["duck_volume"] = new_val / 100.0
            else:
                self.config_data["trigger_apps"][app_name] = {"enabled": True, "duck_volume": new_val / 100.0, "trigger_threshold": 0.05}
            self._refresh_triggers_list()

    def _validate_trigger_entry(self, app_name: str, entry_widget: ctk.CTkEntry, slider_widget: ctk.CTkSlider):
        try:
            val = int(entry_widget.get().strip())
            val = max(0, min(100, val))
        except Exception:
            val = 25
        entry_widget.delete(0, "end")
        entry_widget.insert(0, str(val))
        slider_widget.set(val / 100.0)
        if app_name in self.config_data["trigger_apps"]:
            if isinstance(self.config_data["trigger_apps"][app_name], dict):
                self.config_data["trigger_apps"][app_name]["duck_volume"] = val / 100.0
            else:
                self.config_data["trigger_apps"][app_name] = {"enabled": True, "duck_volume": val / 100.0, "trigger_threshold": 0.05}

    def _on_trigger_thresh_slider_change(self, app_name: str, val: float, entry_widget: ctk.CTkEntry):
        pct = max(1, min(100, int(round(val * 100))))
        entry_widget.delete(0, "end")
        entry_widget.insert(0, str(pct))
        if app_name in self.config_data["trigger_apps"]:
            if isinstance(self.config_data["trigger_apps"][app_name], dict):
                self.config_data["trigger_apps"][app_name]["trigger_threshold"] = pct / 100.0
            else:
                self.config_data["trigger_apps"][app_name] = {"enabled": True, "duck_volume": 0.25, "trigger_threshold": pct / 100.0}

    def _step_trigger_thresh(self, app_name: str, delta: int):
        if app_name in self.config_data["trigger_apps"]:
            app_info = self.config_data["trigger_apps"][app_name]
            curr = int((app_info.get("trigger_threshold", 0.05) if isinstance(app_info, dict) else 0.05) * 100)
            new_val = max(1, min(100, curr + delta))
            if isinstance(app_info, dict):
                self.config_data["trigger_apps"][app_name]["trigger_threshold"] = new_val / 100.0
            else:
                self.config_data["trigger_apps"][app_name] = {"enabled": True, "duck_volume": 0.25, "trigger_threshold": new_val / 100.0}
            self._refresh_triggers_list()

    def _validate_trigger_thresh_entry(self, app_name: str, entry_widget: ctk.CTkEntry, slider_widget: ctk.CTkSlider):
        try:
            val = int(entry_widget.get().strip())
            val = max(1, min(100, val))
        except Exception:
            val = 5
        entry_widget.delete(0, "end")
        entry_widget.insert(0, str(val))
        slider_widget.set(val / 100.0)
        if app_name in self.config_data["trigger_apps"]:
            if isinstance(self.config_data["trigger_apps"][app_name], dict):
                self.config_data["trigger_apps"][app_name]["trigger_threshold"] = val / 100.0
            else:
                self.config_data["trigger_apps"][app_name] = {"enabled": True, "duck_volume": 0.25, "trigger_threshold": val / 100.0}

    # VISTA 3: MICRÓFONO
    def _create_mic_view(self):
        self.mic_view = ctk.CTkFrame(self.main_content_frame, fg_color="transparent")

        ctk.CTkLabel(
            self.mic_view,
            text="🎤 Atenuación por Voz / Micrófono",
            font=("Segoe UI", 16, "bold"),
            text_color="#BA68C8"
        ).pack(anchor="w", pady=(0, 10))

        mic_card = ctk.CTkFrame(self.mic_view)
        mic_card.pack(fill="x", pady=10, padx=5)

        self.mic_switch_var = ctk.BooleanVar(value=self.config_data.get("duck_on_microphone", False))
        self.mic_switch = ctk.CTkSwitch(
            mic_card,
            text="Activar atenuación cuando TÚ hables por el micrófono (ON/OFF)",
            variable=self.mic_switch_var,
            command=self._on_mic_switch_toggle,
            font=("Segoe UI", 12, "bold")
        )
        self.mic_switch.pack(anchor="w", padx=15, pady=15)

        mic_select_subframe = ctk.CTkFrame(mic_card, fg_color="transparent")
        mic_select_subframe.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(mic_select_subframe, text="Seleccionar Micrófono del sistema:").pack(side="left")
        available_mics = self.detector.get_available_microphones()
        self.mic_dropdown = ctk.CTkOptionMenu(
            mic_select_subframe,
            values=available_mics,
            command=self._on_mic_selected
        )
        current_mic = self.config_data.get("selected_microphone", "Default")
        if current_mic in available_mics:
            self.mic_dropdown.set(current_mic)
        else:
            self.mic_dropdown.set("Default")
        self.mic_dropdown.pack(side="right", padx=5, fill="x", expand=True)

        meter_frame = ctk.CTkFrame(mic_card, fg_color="#1E1E1E")
        meter_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(meter_frame, text="🔊 Medidor de voz en vivo:", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(5, 2))
        
        self.mic_progress = ctk.CTkProgressBar(meter_frame, height=14)
        self.mic_progress.set(0.0)
        self.mic_progress.pack(fill="x", padx=10, pady=5)

        self.mic_status_lbl = ctk.CTkLabel(
            meter_frame,
            text="Pico actual: 0% | Estado: Esperando voz...",
            font=("Segoe UI", 11, "italic"),
            text_color="#9E9E9E"
        )
        self.mic_status_lbl.pack(anchor="w", padx=10, pady=(0, 5))

        thresh_row = ctk.CTkFrame(mic_card, fg_color="transparent")
        thresh_row.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(thresh_row, text="Sensibilidad / Umbral de activación (Ruido de fondo):").pack(side="left")

        init_thresh_pct = int(self.config_data.get("mic_peak_threshold", 0.05) * 100)

        btn_t_sub = ctk.CTkButton(thresh_row, text="-", width=28, command=lambda: self._step_mic_thresh(-1))
        btn_t_sub.pack(side="left", padx=4)

        self.mic_thresh_entry = ctk.CTkEntry(thresh_row, width=45, justify="center")
        self.mic_thresh_entry.insert(0, str(init_thresh_pct))
        self.mic_thresh_entry.pack(side="left", padx=2)
        self.mic_thresh_entry.bind("<FocusOut>", lambda e: self._on_mic_thresh_validate())
        self.mic_thresh_entry.bind("<Return>", lambda e: self._on_mic_thresh_validate())

        ctk.CTkLabel(thresh_row, text="%").pack(side="left", padx=1)

        btn_t_add = ctk.CTkButton(thresh_row, text="+", width=28, command=lambda: self._step_mic_thresh(1))
        btn_t_add.pack(side="left", padx=4)

        self.mic_thresh_slider = ctk.CTkSlider(
            thresh_row,
            from_=0.01,
            to=0.30,
            number_of_steps=29,
            command=self._on_mic_thresh_slider_change
        )
        self.mic_thresh_slider.set(self.config_data.get("mic_peak_threshold", 0.05))
        self.mic_thresh_slider.pack(side="right", fill="x", expand=True, padx=8)
        disable_slider_mousewheel(self.mic_thresh_slider)

        mic_vol_row = ctk.CTkFrame(mic_card, fg_color="transparent")
        mic_vol_row.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(mic_vol_row, text="Nivel de atenuación al hablar por mic:").pack(side="left")

        init_mic_pct = int(self.config_data.get("mic_duck_volume", 0.20) * 100)

        btn_mic_sub = ctk.CTkButton(mic_vol_row, text="-", width=30, command=lambda: self._step_mic_vol(-5))
        btn_mic_sub.pack(side="left", padx=4)

        self.mic_entry = ctk.CTkEntry(mic_vol_row, width=50, justify="center")
        self.mic_entry.insert(0, str(init_mic_pct))
        self.mic_entry.pack(side="left", padx=2)
        self.mic_entry.bind("<FocusOut>", lambda e: self._on_mic_entry_validate())
        self.mic_entry.bind("<Return>", lambda e: self._on_mic_entry_validate())

        ctk.CTkLabel(mic_vol_row, text="%").pack(side="left", padx=1)

        btn_mic_add = ctk.CTkButton(mic_vol_row, text="+", width=30, command=lambda: self._step_mic_vol(5))
        btn_mic_add.pack(side="left", padx=4)

        self.mic_vol_slider = ctk.CTkSlider(
            mic_vol_row,
            from_=0.0,
            to=1.0,
            number_of_steps=100,
            command=self._on_mic_vol_slider_change
        )
        self.mic_vol_slider.set(self.config_data.get("mic_duck_volume", 0.20))
        self.mic_vol_slider.pack(side="right", fill="x", expand=True, padx=10)
        disable_slider_mousewheel(self.mic_vol_slider)

    def _on_mic_switch_toggle(self):
        self.config_data["duck_on_microphone"] = self.mic_switch_var.get()
        self.save_config(show_msg=False)

    def _on_mic_selected(self, choice: str):
        self.config_data["selected_microphone"] = choice
        self.save_config(show_msg=False)

    def _on_mic_vol_slider_change(self, val: float):
        pct = max(0, min(100, int(round(val * 100))))
        self.mic_entry.delete(0, "end")
        self.mic_entry.insert(0, str(pct))
        self.config_data["mic_duck_volume"] = pct / 100.0

    def _step_mic_vol(self, delta: int):
        try:
            curr = int(self.mic_entry.get().strip())
        except Exception:
            curr = int(self.config_data.get("mic_duck_volume", 0.20) * 100)
        new_val = max(0, min(100, curr + delta))
        self.mic_entry.delete(0, "end")
        self.mic_entry.insert(0, str(new_val))
        self.mic_vol_slider.set(new_val / 100.0)
        self.config_data["mic_duck_volume"] = new_val / 100.0

    def _on_mic_entry_validate(self):
        try:
            val = int(self.mic_entry.get().strip())
            val = max(0, min(100, val))
        except Exception:
            val = int(self.config_data.get("mic_duck_volume", 0.20) * 100)
        self.mic_entry.delete(0, "end")
        self.mic_entry.insert(0, str(val))
        self.mic_vol_slider.set(val / 100.0)
        self.config_data["mic_duck_volume"] = val / 100.0

    def _on_mic_thresh_slider_change(self, val: float):
        pct = max(1, min(30, int(round(val * 100))))
        self.mic_thresh_entry.delete(0, "end")
        self.mic_thresh_entry.insert(0, str(pct))
        self.config_data["mic_peak_threshold"] = pct / 100.0

    def _step_mic_thresh(self, delta: int):
        try:
            curr = int(self.mic_thresh_entry.get().strip())
        except Exception:
            curr = int(self.config_data.get("mic_peak_threshold", 0.05) * 100)
        new_val = max(1, min(30, curr + delta))
        self.mic_thresh_entry.delete(0, "end")
        self.mic_thresh_entry.insert(0, str(new_val))
        self.mic_thresh_slider.set(new_val / 100.0)
        self.config_data["mic_peak_threshold"] = new_val / 100.0

    def _on_mic_thresh_validate(self):
        try:
            val = int(self.mic_thresh_entry.get().strip())
            val = max(1, min(30, val))
        except Exception:
            val = int(self.config_data.get("mic_peak_threshold", 0.05) * 100)
        self.mic_thresh_entry.delete(0, "end")
        self.mic_thresh_entry.insert(0, str(val))
        self.mic_thresh_slider.set(val / 100.0)
        self.config_data["mic_peak_threshold"] = val / 100.0

    def _update_live_meters(self):
        if self.active_tab == "mic" and hasattr(self, "mic_progress"):
            try:
                selected_mic = self.config_data.get("selected_microphone", "Default")
                peak = self.detector.get_microphone_peak(selected_mic)
                thresh = float(self.config_data.get("mic_peak_threshold", 0.05))

                self.mic_progress.set(min(1.0, peak))
                peak_pct = int(peak * 100)
                thresh_pct = int(thresh * 100)

                if peak >= thresh:
                    self.mic_progress.configure(progress_color="#2E7D32")
                    self.mic_status_lbl.configure(
                        text=f"Pico actual: {peak_pct}% | 🟢 SUPERANDO UMBRAL DE ACTIVACIÓN ({thresh_pct}%)",
                        text_color="#81C784"
                    )
                else:
                    self.mic_progress.configure(progress_color="#1E88E5")
                    self.mic_status_lbl.configure(
                        text=f"Pico actual: {peak_pct}% | ⚪ Silencio / Ruido de fondo (Umbral: {thresh_pct}%)",
                        text_color="#9E9E9E"
                    )
            except Exception:
                pass

        elif self.active_tab == "triggers" and hasattr(self, "trigger_live_widgets"):
            try:
                active_procs = self.detector.get_active_audio_processes()
                for app_name, (pbar, lbl) in list(self.trigger_live_widgets.items()):
                    app_clean = app_name.lower().strip()
                    p_no_ext = app_clean.replace(".exe", "")
                    peak = 0.0
                    for proc_k, proc_peak in active_procs.items():
                        pk_clean = proc_k.lower().strip()
                        if pk_clean in (app_clean, p_no_ext) or pk_clean.replace(".exe", "") == p_no_ext:
                            peak = max(peak, proc_peak)

                    app_info = self.config_data.get("trigger_apps", {}).get(app_name, {})
                    thresh = float(app_info.get("trigger_threshold", 0.05)) if isinstance(app_info, dict) else 0.05

                    pbar.set(min(1.0, peak))
                    peak_pct = int(peak * 100)
                    thresh_pct = int(thresh * 100)

                    if peak >= thresh:
                        pbar.configure(progress_color="#2E7D32")
                        lbl.configure(
                            text=f"Sonido actual: {peak_pct}% | 🟢 SUPERANDO UMBRAL DE ACTIVACIÓN ({thresh_pct}%)",
                            text_color="#81C784"
                        )
                    elif peak > 0:
                        pbar.configure(progress_color="#F57C00")
                        lbl.configure(
                            text=f"Sonido actual: {peak_pct}% | 🟠 SONIDO BAJO - NO ACTIVA (< {thresh_pct}%)",
                            text_color="#FFB74D"
                        )
                    else:
                        pbar.configure(progress_color="#1E88E5")
                        lbl.configure(
                            text=f"Sonido actual: 0% | ⚪ En silencio (Umbral: {thresh_pct}%)",
                            text_color="#9E9E9E"
                        )
            except Exception:
                pass

        self.after(150, self._update_live_meters)

    # VISTA 4: CONFIGURACIÓN Y TIEMPOS
    def _create_settings_view(self):
        self.settings_view = ctk.CTkFrame(self.main_content_frame, fg_color="transparent")

        ctk.CTkLabel(
            self.settings_view,
            text="⚙️ Transición y Tiempos de Restauración",
            font=("Segoe UI", 16, "bold"),
            text_color="#FFB74D"
        ).pack(anchor="w", pady=(0, 10))

        card = ctk.CTkFrame(self.settings_view)
        card.pack(fill="x", pady=10, padx=5)

        trans_subframe = ctk.CTkFrame(card, fg_color="transparent")
        trans_subframe.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(trans_subframe, text="Duración de Transición (segundos):").pack(side="left")
        self.trans_val_label = ctk.CTkLabel(trans_subframe, text=f"{self.config_data.get('transition_duration_seconds', 0.4):.2f}s", font=("Segoe UI", 12, "bold"))
        self.trans_val_label.pack(side="right")

        self.trans_slider = ctk.CTkSlider(
            card,
            from_=0.0,
            to=2.0,
            number_of_steps=20,
            command=self._on_trans_slider_change
        )
        self.trans_slider.set(self.config_data.get("transition_duration_seconds", 0.4))
        self.trans_slider.pack(fill="x", padx=15, pady=(0, 5))
        disable_slider_mousewheel(self.trans_slider)

        self.trans_mode_label = ctk.CTkLabel(
            card,
            text="💡 Modo: Instantáneo (de golpe)" if self.config_data.get("transition_duration_seconds", 0.4) <= 0 else "💡 Modo: Transición Suave (fade in / fade out)",
            font=("Segoe UI", 11, "italic"),
            text_color="#3B8ED0" if self.config_data.get("transition_duration_seconds", 0.4) > 0 else "#E57373"
        )
        self.trans_mode_label.pack(anchor="w", padx=15, pady=(0, 15))

        delay_subframe = ctk.CTkFrame(card, fg_color="transparent")
        delay_subframe.pack(fill="x", padx=15, pady=(5, 5))

        ctk.CTkLabel(delay_subframe, text="Tiempo de espera tras silencio (Release Delay):").pack(side="left")
        self.delay_val_label = ctk.CTkLabel(delay_subframe, text=f"{self.config_data.get('release_delay_seconds', 1.0):.1f}s", font=("Segoe UI", 12, "bold"))
        self.delay_val_label.pack(side="right")

        self.delay_slider = ctk.CTkSlider(
            card,
            from_=0.2,
            to=5.0,
            number_of_steps=48,
            command=self._on_delay_slider_change
        )
        self.delay_slider.set(self.config_data.get("release_delay_seconds", 1.0))
        self.delay_slider.pack(fill="x", padx=15, pady=(0, 15))
        disable_slider_mousewheel(self.delay_slider)

    def _on_trans_slider_change(self, val: float):
        val = round(val, 2)
        self.trans_val_label.configure(text=f"{val:.2f}s")
        self.config_data["transition_duration_seconds"] = val
        if val <= 0:
            self.trans_mode_label.configure(text="💡 Modo: Instantáneo (de golpe)", text_color="#E57373")
        else:
            self.trans_mode_label.configure(text="💡 Modo: Transición Suave (fade in / fade out)", text_color="#3B8ED0")

    def _on_delay_slider_change(self, val: float):
        val = round(val, 1)
        self.delay_val_label.configure(text=f"{val:.1f}s")
        self.config_data["release_delay_seconds"] = val

    def _install_startup(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        ps_script = os.path.join(base_dir, "create_startup_shortcut.ps1")
        if os.path.exists(ps_script):
            try:
                os.system(f'powershell -ExecutionPolicy Bypass -File "{ps_script}"')
                messagebox.showinfo("Inicio de Windows", "¡Acceso directo a la carpeta de Inicio de Windows actualizado!")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo configurar inicio automático: {e}")
        else:
            messagebox.showerror("Error", "No se encontró el script create_startup_shortcut.ps1")

def launch_gui(config_path: str, on_config_updated_callback=None, on_restart_service_callback=None):
    app = AudioDuckerGUI(config_path, on_config_updated_callback, on_restart_service_callback)
    app.mainloop()

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(base_dir, "config.json")
    launch_gui(config_file)
