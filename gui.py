import json
import logging
import os
import sys
from typing import Dict, Any, Callable
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from detector import AudioDetector

logger = logging.getLogger("AudioDucker.GUI")

def unbind_mouse_wheel(widget):
    """
    Evita que el slider se mueva al desplazarse con la rueda del ratón.
    """
    try:
        widget.bind("<MouseWheel>", lambda e: "break")
        widget.bind("<Button-4>", lambda e: "break")
        widget.bind("<Button-5>", lambda e: "break")
    except Exception:
        pass


class AudioDuckerGUI(ctk.CTk):
    def __init__(self, config_path: str, on_config_updated_callback=None):
        super().__init__()

        self.config_path = config_path
        self.on_config_updated_callback = on_config_updated_callback
        self.detector = AudioDetector()
        self.config_data = self.load_config()

        # Configuración de ventana
        self.title("AudioDucker v2.01 - Control de Volumen Inteligente")
        self.geometry("860x780")
        self.resizable(True, True)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            
        icon_path = os.path.join(base_dir, "assets", "logo.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self._build_ui(base_dir)

    def load_config(self) -> Dict[str, Any]:
        default_config = {
            "version": "2.01",
            "target_apps": {
                "spotify.exe": {
                    "enabled": True,
                    "default_volume": 1.0,
                    "duck_volume": 0.20
                }
            },
            "trigger_apps": {
                "discord.exe": {"enabled": True, "duck_volume": 0.25},
                "chrome.exe": {"enabled": True, "duck_volume": 0.35},
                "msedge.exe": {"enabled": True, "duck_volume": 0.35},
                "firefox.exe": {"enabled": True, "duck_volume": 0.35},
                "brave.exe": {"enabled": True, "duck_volume": 0.35},
                "telegram.exe": {"enabled": True, "duck_volume": 0.25},
                "zoom.exe": {"enabled": True, "duck_volume": 0.15},
                "obs64.exe": {"enabled": True, "duck_volume": 0.30}
            },
            "duck_on_microphone": False,
            "selected_microphone": "Default",
            "mic_duck_volume": 0.20,
            "mic_peak_threshold": 0.01,
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
                        data["target_apps"] = {
                            target_single: {
                                "enabled": True,
                                "default_volume": float(data.get("default_volume", 1.0)),
                                "duck_volume": float(data.get("default_duck_volume", 0.20))
                            }
                        }
                    
                    if "trigger_apps" in data and isinstance(data["trigger_apps"], dict):
                        new_triggers = {}
                        for app_k, app_v in data["trigger_apps"].items():
                            app_k_clean = str(app_k).lower()
                            if isinstance(app_v, dict):
                                new_triggers[app_k_clean] = {
                                    "enabled": bool(app_v.get("enabled", True)),
                                    "duck_volume": float(app_v.get("duck_volume", 0.25))
                                }
                            else:
                                new_triggers[app_k_clean] = {
                                    "enabled": True,
                                    "duck_volume": float(app_v)
                                }
                        data["trigger_apps"] = new_triggers

                    return {**default_config, **data}
            except Exception:
                pass
        return default_config

    def save_config(self):
        try:
            self.config_data["version"] = "2.01"
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            if self.on_config_updated_callback:
                self.on_config_updated_callback(self.config_data)
            messagebox.showinfo("Éxito", "¡Configuración guardada correctamente!")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la configuración: {e}")

    def _build_ui(self, base_dir: str):
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            title_frame,
            text="🎵 AudioDucker v2.01",
            font=("Segoe UI", 20, "bold"),
            text_color="#1E88E5"
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text="Control inteligente multi-aplicación y voz",
            font=("Segoe UI", 12, "italic"),
            text_color="#9E9E9E"
        ).pack(side="left", padx=10)

        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Panel de Control General")
        self.scroll_frame.pack(padx=15, pady=10, fill="both", expand=True)

        # ----------------------------------------------------
        # Sección 1: Aplicaciones Objetivo (Las que se atenuarán simultáneamente)
        # ----------------------------------------------------
        target_frame = ctk.CTkFrame(self.scroll_frame)
        target_frame.pack(fill="x", pady=8, padx=5)

        target_title_frame = ctk.CTkFrame(target_frame, fg_color="transparent")
        target_title_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            target_title_frame,
            text="🎯 Aplicaciones Objetivo (A las que se les BAJARÁ el volumen simultáneamente)",
            font=("Segoe UI", 13, "bold"),
            text_color="#81C784"
        ).pack(side="left")

        btn_add_target = ctk.CTkButton(
            target_title_frame,
            text="📁 Agregar App Objetivo (.exe)",
            width=180,
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            command=self._browse_and_add_target_exe
        )
        btn_add_target.pack(side="right", padx=5)

        self.targets_container = ctk.CTkFrame(target_frame, fg_color="transparent")
        self.targets_container.pack(fill="x", padx=10, pady=5)
        self._refresh_targets_list()

        # ----------------------------------------------------
        # Sección 2: Aplicaciones Activadoras (Las que provocan la bajada)
        # ----------------------------------------------------
        trigger_frame = ctk.CTkFrame(self.scroll_frame)
        trigger_frame.pack(fill="x", pady=8, padx=5)

        trigger_title_frame = ctk.CTkFrame(trigger_frame, fg_color="transparent")
        trigger_title_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            trigger_title_frame,
            text="📱 Aplicaciones Activadoras (Las que PROVOCAN la bajada de volumen)",
            font=("Segoe UI", 13, "bold"),
            text_color="#64B5F6"
        ).pack(side="left")

        btn_add_trigger = ctk.CTkButton(
            trigger_title_frame,
            text="📁 Agregar App Activadora (.exe)",
            width=190,
            fg_color="#1565C0",
            hover_color="#0D47A1",
            command=self._browse_and_add_trigger_exe
        )
        btn_add_trigger.pack(side="right", padx=5)

        self.triggers_container = ctk.CTkFrame(trigger_frame, fg_color="transparent")
        self.triggers_container.pack(fill="x", padx=10, pady=5)
        self._refresh_triggers_list()

        # ----------------------------------------------------
        # Sección 3: Detección por Micrófono (ON / OFF)
        # ----------------------------------------------------
        mic_frame = ctk.CTkFrame(self.scroll_frame)
        mic_frame.pack(fill="x", pady=8, padx=5)

        ctk.CTkLabel(mic_frame, text="🎤 Atenuación por Voz / Micrófono", font=("Segoe UI", 13, "bold"), text_color="#BA68C8").pack(anchor="w", padx=10, pady=5)

        self.mic_switch_var = ctk.BooleanVar(value=self.config_data.get("duck_on_microphone", False))
        self.mic_switch = ctk.CTkSwitch(
            mic_frame,
            text="Activar atenuación por voz cuando TÚ hables por el micrófono (ON/OFF)",
            variable=self.mic_switch_var,
            command=self._on_mic_switch_toggle,
            font=("Segoe UI", 12, "bold")
        )
        self.mic_switch.pack(anchor="w", padx=15, pady=5)

        mic_select_subframe = ctk.CTkFrame(mic_frame, fg_color="transparent")
        mic_select_subframe.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(mic_select_subframe, text="Seleccionar Micrófono del sistema:").pack(side="left", padx=5)
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

        # Mic Vol Subframe con Botones +, - y Entry
        mic_vol_row = ctk.CTkFrame(mic_frame, fg_color="transparent")
        mic_vol_row.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(mic_vol_row, text="Volumen al hablar por mic:").pack(side="left", padx=5)

        init_mic_pct = int(self.config_data.get("mic_duck_volume", 0.20) * 100)

        btn_mic_sub = ctk.CTkButton(mic_vol_row, text="-", width=30, command=lambda: self._step_mic_vol(-5))
        btn_mic_sub.pack(side="left", padx=2)

        self.mic_entry = ctk.CTkEntry(mic_vol_row, width=50, justify="center")
        self.mic_entry.insert(0, str(init_mic_pct))
        self.mic_entry.pack(side="left", padx=2)
        self.mic_entry.bind("<FocusOut>", lambda e: self._on_mic_entry_validate())
        self.mic_entry.bind("<Return>", lambda e: self._on_mic_entry_validate())

        ctk.CTkLabel(mic_vol_row, text="%").pack(side="left", padx=1)

        btn_mic_add = ctk.CTkButton(mic_vol_row, text="+", width=30, command=lambda: self._step_mic_vol(5))
        btn_mic_add.pack(side="left", padx=2)

        self.mic_vol_slider = ctk.CTkSlider(
            mic_vol_row,
            from_=0.0,
            to=1.0,
            number_of_steps=100,
            command=self._on_mic_vol_slider_change
        )
        self.mic_vol_slider.set(self.config_data.get("mic_duck_volume", 0.20))
        self.mic_vol_slider.pack(side="right", fill="x", expand=True, padx=10)
        unbind_mouse_wheel(self.mic_vol_slider)

        # ----------------------------------------------------
        # Sección 4: Parámetros de Transición y Tiempos
        # ----------------------------------------------------
        gen_frame = ctk.CTkFrame(self.scroll_frame)
        gen_frame.pack(fill="x", pady=8, padx=5)

        ctk.CTkLabel(gen_frame, text="⚙️ Transición y Tiempos de Restauración", font=("Segoe UI", 13, "bold"), text_color="#FFB74D").pack(anchor="w", padx=10, pady=5)

        trans_subframe = ctk.CTkFrame(gen_frame, fg_color="transparent")
        trans_subframe.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(trans_subframe, text="Duración de Transición (segundos):").pack(side="left", padx=5)
        self.trans_val_label = ctk.CTkLabel(trans_subframe, text=f"{self.config_data.get('transition_duration_seconds', 0.4):.2f}s", font=("Segoe UI", 12, "bold"))
        self.trans_val_label.pack(side="right", padx=5)

        self.trans_slider = ctk.CTkSlider(
            gen_frame,
            from_=0.0,
            to=2.0,
            number_of_steps=20,
            command=self._on_trans_slider_change
        )
        self.trans_slider.set(self.config_data.get("transition_duration_seconds", 0.4))
        self.trans_slider.pack(fill="x", padx=15, pady=(0, 5))
        unbind_mouse_wheel(self.trans_slider)

        self.trans_mode_label = ctk.CTkLabel(
            gen_frame,
            text="💡 Modo: Instantáneo (de golpe)" if self.config_data.get("transition_duration_seconds", 0.4) <= 0 else "💡 Modo: Transición Suave (fade in / fade out)",
            font=("Segoe UI", 11, "italic"),
            text_color="#3B8ED0" if self.config_data.get("transition_duration_seconds", 0.4) > 0 else "#E57373"
        )
        self.trans_mode_label.pack(anchor="w", padx=15, pady=(0, 10))

        delay_subframe = ctk.CTkFrame(gen_frame, fg_color="transparent")
        delay_subframe.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(delay_subframe, text="Tiempo de espera tras silencio (Release Delay):").pack(side="left", padx=5)
        self.delay_val_label = ctk.CTkLabel(delay_subframe, text=f"{self.config_data.get('release_delay_seconds', 1.0):.1f}s", font=("Segoe UI", 12, "bold"))
        self.delay_val_label.pack(side="right", padx=5)

        self.delay_slider = ctk.CTkSlider(
            gen_frame,
            from_=0.2,
            to=5.0,
            number_of_steps=48,
            command=self._on_delay_slider_change
        )
        self.delay_slider.set(self.config_data.get("release_delay_seconds", 1.0))
        self.delay_slider.pack(fill="x", padx=15, pady=(0, 10))
        unbind_mouse_wheel(self.delay_slider)

        # ----------------------------------------------------
        # Barra Inferior de Acciones
        # ----------------------------------------------------
        action_frame = ctk.CTkFrame(self)
        action_frame.pack(fill="x", padx=15, pady=10)

        btn_save = ctk.CTkButton(
            action_frame,
            text="💾 Guardar Configuración",
            fg_color="#1565C0",
            hover_color="#0D47A1",
            font=("Segoe UI", 13, "bold"),
            command=self._save_all
        )
        btn_save.pack(side="left", padx=10, pady=10, expand=True, fill="x")

        btn_startup = ctk.CTkButton(
            action_frame,
            text="🚀 Activar en Inicio de Windows",
            fg_color="#6A1B9A",
            hover_color="#4A148C",
            font=("Segoe UI", 13, "bold"),
            command=self._install_startup
        )
        btn_startup.pack(side="right", padx=10, pady=10, expand=True, fill="x")

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

    def _on_mic_switch_toggle(self):
        self.config_data["duck_on_microphone"] = self.mic_switch_var.get()

    def _on_mic_selected(self, choice: str):
        self.config_data["selected_microphone"] = choice

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

    # --- Métodos para APPS OBJETIVO ---
    def _browse_and_add_target_exe(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar Ejecutable de Aplicación Objetivo",
            filetypes=[("Archivos Ejecutables (*.exe)", "*.exe"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            filename = os.path.basename(filepath).lower()
            if "target_apps" not in self.config_data:
                self.config_data["target_apps"] = {}
            if filename not in self.config_data["target_apps"]:
                self.config_data["target_apps"][filename] = {
                    "enabled": True,
                    "default_volume": 1.0,
                    "duck_volume": 0.20
                }
                self._refresh_targets_list()
                messagebox.showinfo("App Objetivo Agregada", f"Se agregó '{filename}' a las aplicaciones que bajarán de volumen.")

    def _delete_target_app(self, app_name: str):
        if app_name in self.config_data["target_apps"]:
            del self.config_data["target_apps"][app_name]
            self._refresh_targets_list()

    def _refresh_targets_list(self):
        for w in self.targets_container.winfo_children():
            w.destroy()

        targets = self.config_data.get("target_apps", {})
        if not targets:
            ctk.CTkLabel(self.targets_container, text="No hay aplicaciones objetivo. Agrega una con el botón de arriba.").pack(pady=5)
            return

        for app_name, app_info in list(targets.items()):
            row = ctk.CTkFrame(self.targets_container)
            row.pack(fill="x", pady=4, padx=2)

            sw_var = ctk.BooleanVar(value=app_info.get("enabled", True))
            sw = ctk.CTkSwitch(
                row,
                text=f"🎯 {app_name}",
                variable=sw_var,
                width=160,
                command=lambda name=app_name, var=sw_var: self._toggle_target_enabled(name, var.get())
            )
            sw.pack(side="left", padx=5)

            # Botones -, Entry, +
            duck_pct = int(app_info.get("duck_volume", 0.20) * 100)

            btn_del = ctk.CTkButton(
                row,
                text="❌",
                width=35,
                fg_color="#D32F2F",
                hover_color="#B71C1C",
                command=lambda name=app_name: self._delete_target_app(name)
            )
            btn_del.pack(side="right", padx=5)

            btn_add = ctk.CTkButton(row, text="+", width=28, command=lambda name=app_name: self._step_target_vol(name, 5))
            btn_add.pack(side="right", padx=2)

            ctk.CTkLabel(row, text="%").pack(side="right", padx=1)

            entry = ctk.CTkEntry(row, width=45, justify="center")
            entry.insert(0, str(duck_pct))
            entry.pack(side="right", padx=2)

            btn_sub = ctk.CTkButton(row, text="-", width=28, command=lambda name=app_name: self._step_target_vol(name, -5))
            btn_sub.pack(side="right", padx=2)

            ctk.CTkLabel(row, text="Bajar a:").pack(side="right", padx=2)

            slider = ctk.CTkSlider(
                row,
                from_=0.0,
                to=1.0,
                number_of_steps=100,
                command=lambda val, name=app_name, ent=entry: self._on_target_slider_change(name, val, ent)
            )
            slider.set(app_info.get("duck_volume", 0.20))
            slider.pack(side="right", fill="x", expand=True, padx=8)
            unbind_mouse_wheel(slider)

            entry.bind("<FocusOut>", lambda e, name=app_name, ent=entry, s=slider: self._validate_target_entry(name, ent, s))
            entry.bind("<Return>", lambda e, name=app_name, ent=entry, s=slider: self._validate_target_entry(name, ent, s))

    def _toggle_target_enabled(self, app_name: str, enabled: bool):
        if app_name in self.config_data["target_apps"]:
            self.config_data["target_apps"][app_name]["enabled"] = enabled

    def _on_target_slider_change(self, app_name: str, val: float, entry_widget: ctk.CTkEntry):
        pct = max(0, min(100, int(round(val * 100))))
        entry_widget.delete(0, "end")
        entry_widget.insert(0, str(pct))
        if app_name in self.config_data["target_apps"]:
            self.config_data["target_apps"][app_name]["duck_volume"] = pct / 100.0

    def _step_target_vol(self, app_name: str, delta: int):
        if app_name in self.config_data["target_apps"]:
            curr = int(self.config_data["target_apps"][app_name].get("duck_volume", 0.20) * 100)
            new_val = max(0, min(100, curr + delta))
            self.config_data["target_apps"][app_name]["duck_volume"] = new_val / 100.0
            self._refresh_targets_list()

    def _validate_target_entry(self, app_name: str, entry_widget: ctk.CTkEntry, slider_widget: ctk.CTkSlider):
        try:
            val = int(entry_widget.get().strip())
            val = max(0, min(100, val))
        except Exception:
            val = 20
        entry_widget.delete(0, "end")
        entry_widget.insert(0, str(val))
        slider_widget.set(val / 100.0)
        if app_name in self.config_data["target_apps"]:
            self.config_data["target_apps"][app_name]["duck_volume"] = val / 100.0

    # --- Métodos para APPS ACTIVADORAS ---
    def _browse_and_add_trigger_exe(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar Ejecutable de Aplicación Activadora",
            filetypes=[("Archivos Ejecutables (*.exe)", "*.exe"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            filename = os.path.basename(filepath).lower()
            if "trigger_apps" not in self.config_data:
                self.config_data["trigger_apps"] = {}
            if filename not in self.config_data["trigger_apps"]:
                self.config_data["trigger_apps"][filename] = {
                    "enabled": True,
                    "duck_volume": 0.30
                }
                self._refresh_triggers_list()
                messagebox.showinfo("App Activadora Agregada", f"Se agregó '{filename}' a las aplicaciones activadoras.")

    def _delete_trigger_app(self, app_name: str):
        if app_name in self.config_data["trigger_apps"]:
            del self.config_data["trigger_apps"][app_name]
            self._refresh_triggers_list()

    def _refresh_triggers_list(self):
        for w in self.triggers_container.winfo_children():
            w.destroy()

        triggers = self.config_data.get("trigger_apps", {})
        if not triggers:
            ctk.CTkLabel(self.triggers_container, text="No hay aplicaciones activadoras configuradas.").pack(pady=5)
            return

        for app_name, app_info in list(triggers.items()):
            row = ctk.CTkFrame(self.triggers_container)
            row.pack(fill="x", pady=4, padx=2)

            is_enabled = app_info.get("enabled", True) if isinstance(app_info, dict) else True
            duck_vol = app_info.get("duck_volume", 0.25) if isinstance(app_info, dict) else float(app_info)
            duck_pct = int(duck_vol * 100)

            sw_var = ctk.BooleanVar(value=is_enabled)
            sw = ctk.CTkSwitch(
                row,
                text=f"📱 {app_name}",
                variable=sw_var,
                width=160,
                command=lambda name=app_name, var=sw_var: self._toggle_trigger_enabled(name, var.get())
            )
            sw.pack(side="left", padx=5)

            btn_del = ctk.CTkButton(
                row,
                text="❌",
                width=35,
                fg_color="#D32F2F",
                hover_color="#B71C1C",
                command=lambda name=app_name: self._delete_trigger_app(name)
            )
            btn_del.pack(side="right", padx=5)

            btn_add = ctk.CTkButton(row, text="+", width=28, command=lambda name=app_name: self._step_trigger_vol(name, 5))
            btn_add.pack(side="right", padx=2)

            ctk.CTkLabel(row, text="%").pack(side="right", padx=1)

            entry = ctk.CTkEntry(row, width=45, justify="center")
            entry.insert(0, str(duck_pct))
            entry.pack(side="right", padx=2)

            btn_sub = ctk.CTkButton(row, text="-", width=28, command=lambda name=app_name: self._step_trigger_vol(name, -5))
            btn_sub.pack(side="right", padx=2)

            ctk.CTkLabel(row, text="Fuerza:").pack(side="right", padx=2)

            slider = ctk.CTkSlider(
                row,
                from_=0.0,
                to=1.0,
                number_of_steps=100,
                command=lambda val, name=app_name, ent=entry: self._on_trigger_slider_change(name, val, ent)
            )
            slider.set(duck_vol)
            slider.pack(side="right", fill="x", expand=True, padx=8)
            unbind_mouse_wheel(slider)

            entry.bind("<FocusOut>", lambda e, name=app_name, ent=entry, s=slider: self._validate_trigger_entry(name, ent, s))
            entry.bind("<Return>", lambda e, name=app_name, ent=entry, s=slider: self._validate_trigger_entry(name, ent, s))

    def _toggle_trigger_enabled(self, app_name: str, enabled: bool):
        if app_name in self.config_data["trigger_apps"]:
            if isinstance(self.config_data["trigger_apps"][app_name], dict):
                self.config_data["trigger_apps"][app_name]["enabled"] = enabled
            else:
                vol = float(self.config_data["trigger_apps"][app_name])
                self.config_data["trigger_apps"][app_name] = {"enabled": enabled, "duck_volume": vol}

    def _on_trigger_slider_change(self, app_name: str, val: float, entry_widget: ctk.CTkEntry):
        pct = max(0, min(100, int(round(val * 100))))
        entry_widget.delete(0, "end")
        entry_widget.insert(0, str(pct))
        if app_name in self.config_data["trigger_apps"]:
            if isinstance(self.config_data["trigger_apps"][app_name], dict):
                self.config_data["trigger_apps"][app_name]["duck_volume"] = pct / 100.0
            else:
                self.config_data["trigger_apps"][app_name] = {"enabled": True, "duck_volume": pct / 100.0}

    def _step_trigger_vol(self, app_name: str, delta: int):
        if app_name in self.config_data["trigger_apps"]:
            app_info = self.config_data["trigger_apps"][app_name]
            curr = int((app_info.get("duck_volume", 0.25) if isinstance(app_info, dict) else float(app_info)) * 100)
            new_val = max(0, min(100, curr + delta))
            if isinstance(app_info, dict):
                self.config_data["trigger_apps"][app_name]["duck_volume"] = new_val / 100.0
            else:
                self.config_data["trigger_apps"][app_name] = {"enabled": True, "duck_volume": new_val / 100.0}
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
                self.config_data["trigger_apps"][app_name] = {"enabled": True, "duck_volume": val / 100.0}

    def _save_all(self):
        self.save_config()

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

def launch_gui(config_path: str, on_config_updated_callback=None):
    app = AudioDuckerGUI(config_path, on_config_updated_callback)
    app.mainloop()

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(base_dir, "config.json")
    launch_gui(config_file)
