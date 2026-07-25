import json
import logging
import os
import sys
import threading
import time
from typing import Dict, Any
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from detector import AudioDetector
from volume_controller import VolumeController

logger = logging.getLogger("AudioDucker.GUI")

class AudioDuckerGUI(ctk.CTk):
    def __init__(self, config_path: str, on_config_updated_callback=None):
        super().__init__()

        self.config_path = config_path
        self.on_config_updated_callback = on_config_updated_callback
        self.detector = AudioDetector()
        
        # Cargar configuración
        self.config_data = self.load_config()

        # Configuración de ventana
        self.title("AudioDucker v2.0 - Control de Volumen Inteligente")
        self.geometry("780x740")
        self.resizable(True, True)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Establecer icono de ventana si existe en assets
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
            "target_app": "spotify.exe",
            "default_volume": 1.0,
            "default_duck_volume": 0.20,
            "duck_on_microphone": False,
            "selected_microphone": "Default",
            "mic_duck_volume": 0.20,
            "mic_peak_threshold": 0.01,
            "trigger_apps": {
                "discord.exe": 0.25,
                "chrome.exe": 0.35,
                "msedge.exe": 0.35,
                "firefox.exe": 0.35,
                "brave.exe": 0.35,
                "telegram.exe": 0.25,
                "zoom.exe": 0.15,
                "obs64.exe": 0.30
            },
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
                    return {**default_config, **data}
            except Exception:
                pass
        return default_config

    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            if self.on_config_updated_callback:
                self.on_config_updated_callback(self.config_data)
            messagebox.showinfo("Éxito", "¡Configuración guardada correctamente!")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la configuración: {e}")

    def _build_ui(self, base_dir: str):
        # 1. Header Banner
        banner_path = os.path.join(base_dir, "assets", "banner.png")
        if os.path.exists(banner_path):
            try:
                pil_img = Image.open(banner_path)
                # Escalar manteniento aspecto
                banner_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(740, 140))
                banner_label = ctk.CTkLabel(self, image=banner_img, text="")
                banner_label.pack(pady=(10, 5), padx=15, fill="x")
            except Exception as e:
                logger.debug(f"Error cargando banner: {e}")

        # 2. Main Scrollable Container
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Configuración de AudioDucker")
        self.scroll_frame.pack(padx=15, pady=10, fill="both", expand=True)

        # ----------------------------------------------------
        # Sección A: Configuración General y Transiciones
        # ----------------------------------------------------
        gen_frame = ctk.CTkFrame(self.scroll_frame)
        gen_frame.pack(fill="x", pady=8, padx=5)

        ctk.CTkLabel(gen_frame, text="⚙️ Parámetros de Transición y Tiempos", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=10, pady=5)

        # Transición Suave vs Instantánea
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

        self.trans_mode_label = ctk.CTkLabel(
            gen_frame,
            text="💡 Modo: Instantáneo (de golpe)" if self.config_data.get("transition_duration_seconds", 0.4) <= 0 else "💡 Modo: Transición Suave (fade in / fade out)",
            font=("Segoe UI", 11, "italic"),
            text_color="#3B8ED0" if self.config_data.get("transition_duration_seconds", 0.4) > 0 else "#E57373"
        )
        self.trans_mode_label.pack(anchor="w", padx=15, pady=(0, 10))

        # Release Delay
        delay_subframe = ctk.CTkFrame(gen_frame, fg_color="transparent")
        delay_subframe.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(delay_subframe, text="Tiempo de espera antes de restaurar volumen (Release Delay):").pack(side="left", padx=5)
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

        # ----------------------------------------------------
        # Sección B: Detección por Micrófono (ON / OFF)
        # ----------------------------------------------------
        mic_frame = ctk.CTkFrame(self.scroll_frame)
        mic_frame.pack(fill="x", pady=8, padx=5)

        ctk.CTkLabel(mic_frame, text="🎤 Atenuación por Voz / Micrófono", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=10, pady=5)

        # Switch ON/OFF
        self.mic_switch_var = ctk.BooleanVar(value=self.config_data.get("duck_on_microphone", False))
        self.mic_switch = ctk.CTkSwitch(
            mic_frame,
            text="Activar atenuación cuando TÚ hables por el micrófono (ON/OFF)",
            variable=self.mic_switch_var,
            command=self._on_mic_switch_toggle,
            font=("Segoe UI", 12, "bold")
        )
        self.mic_switch.pack(anchor="w", padx=15, pady=5)

        # Selector de micrófono
        mic_select_subframe = ctk.CTkFrame(mic_frame, fg_color="transparent")
        mic_select_subframe.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(mic_select_subframe, text="Seleccionar Micrófono:").pack(side="left", padx=5)
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

        # Mic Duck Volume Slider
        mic_vol_subframe = ctk.CTkFrame(mic_frame, fg_color="transparent")
        mic_vol_subframe.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(mic_vol_subframe, text="Volumen de Spotify cuando hablas:").pack(side="left", padx=5)
        self.mic_vol_label = ctk.CTkLabel(mic_vol_subframe, text=f"{int(self.config_data.get('mic_duck_volume', 0.20)*100)}%", font=("Segoe UI", 12, "bold"))
        self.mic_vol_label.pack(side="right", padx=5)

        self.mic_vol_slider = ctk.CTkSlider(
            mic_frame,
            from_=0.0,
            to=1.0,
            number_of_steps=20,
            command=self._on_mic_vol_slider_change
        )
        self.mic_vol_slider.set(self.config_data.get("mic_duck_volume", 0.20))
        self.mic_vol_slider.pack(fill="x", padx=15, pady=(0, 10))

        # ----------------------------------------------------
        # Sección C: Gestor de Aplicaciones Activadoras
        # ----------------------------------------------------
        app_frame = ctk.CTkFrame(self.scroll_frame)
        app_frame.pack(fill="x", pady=8, padx=5)

        app_title_frame = ctk.CTkFrame(app_frame, fg_color="transparent")
        app_title_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(app_title_frame, text="💻 Aplicaciones Activadoras (Discord, Chrome, etc.)", font=("Segoe UI", 14, "bold")).pack(side="left")

        # Botón para buscar .exe con explorador nativo
        btn_add_exe = ctk.CTkButton(
            app_title_frame,
            text="📁 Agregar (.exe)",
            width=130,
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            command=self._browse_and_add_exe
        )
        btn_add_exe.pack(side="right", padx=5)

        self.apps_container = ctk.CTkFrame(app_frame, fg_color="transparent")
        self.apps_container.pack(fill="x", padx=10, pady=5)

        self._refresh_apps_list()

        # ----------------------------------------------------
        # Sección D: Botones de Acción Infobar
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
        is_on = self.mic_switch_var.get()
        self.config_data["duck_on_microphone"] = is_on

    def _on_mic_selected(self, choice: str):
        self.config_data["selected_microphone"] = choice

    def _on_mic_vol_slider_change(self, val: float):
        val = round(val, 2)
        self.mic_vol_label.configure(text=f"{int(val*100)}%")
        self.config_data["mic_duck_volume"] = val

    def _browse_and_add_exe(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar Ejecutable de Aplicación",
            filetypes=[("Archivos Ejecutables (*.exe)", "*.exe"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            filename = os.path.basename(filepath).lower()
            if filename not in self.config_data["trigger_apps"]:
                self.config_data["trigger_apps"][filename] = 0.30
                self._refresh_apps_list()
                messagebox.showinfo("Aplicación Agregada", f"Se agregó '{filename}' con volumen objetivo de 30%.")

    def _delete_app(self, app_name: str):
        if app_name in self.config_data["trigger_apps"]:
            del self.config_data["trigger_apps"][app_name]
            self._refresh_apps_list()

    def _on_app_vol_change(self, app_name: str, val: float, label_widget: ctk.CTkLabel):
        val = round(val, 2)
        label_widget.configure(text=f"{int(val*100)}%")
        self.config_data["trigger_apps"][app_name] = val

    def _refresh_apps_list(self):
        for widget in self.apps_container.winfo_children():
            widget.destroy()

        trigger_apps = self.config_data.get("trigger_apps", {})
        if not trigger_apps:
            ctk.CTkLabel(self.apps_container, text="No hay aplicaciones configuradas. Usa el botón 'Agregar (.exe)'.").pack(pady=10)
            return

        for app_name, target_vol in list(trigger_apps.items()):
            row = ctk.CTkFrame(self.apps_container)
            row.pack(fill="x", pady=4, padx=2)

            ctk.CTkLabel(row, text=f"📱 {app_name}", font=("Segoe UI", 12, "bold"), width=160, anchor="w").pack(side="left", padx=5)

            vol_label = ctk.CTkLabel(row, text=f"{int(target_vol*100)}%", width=45)
            vol_label.pack(side="right", padx=5)

            btn_del = ctk.CTkButton(
                row,
                text="❌",
                width=35,
                fg_color="#D32F2F",
                hover_color="#B71C1C",
                command=lambda name=app_name: self._delete_app(name)
            )
            btn_del.pack(side="right", padx=5)

            slider = ctk.CTkSlider(
                row,
                from_=0.0,
                to=1.0,
                number_of_steps=20,
                command=lambda val, name=app_name, lbl=vol_label: self._on_app_vol_change(name, val, lbl)
            )
            slider.set(target_vol)
            slider.pack(side="right", fill="x", expand=True, padx=10)

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
