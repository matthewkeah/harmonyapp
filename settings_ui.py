import customtkinter as ctk

from constants import (
    TIME_SIGNATURE_ORDER, DEFAULT_TIME_SIGNATURE, KEYS,
)


class SettingsModal(ctk.CTkToplevel):
    def __init__(self, parent, instruments_dict, current_key, current_tempo,
                 current_insts, current_vols, on_apply_callback,
                 current_time_sig=DEFAULT_TIME_SIGNATURE):
        super().__init__(parent)
        self.title("Composition Settings")
        self.geometry("460x760")
        self.attributes("-topmost", True)
        self.configure(fg_color="#F5F5DC")

        self.instruments = instruments_dict
        self.sorted_inst_names = sorted(list(self.instruments.keys()))
        self.on_apply = on_apply_callback

        ctk.CTkLabel(self, text="Key Signature", font=("Helvetica", 14, "bold"),
                     text_color="#008080").pack(pady=(20, 5))
        self.key_var = ctk.StringVar(value=current_key)
        # KEYS holds every major and minor key, including enharmonic
        # equivalents. The dropdown shows the full menu so the user
        # can choose whichever spelling they want.
        keys = list(KEYS.keys())
        ctk.CTkComboBox(self, variable=self.key_var, values=keys).pack(
            padx=20, fill="x")

        ctk.CTkLabel(self, text="Time Signature", font=("Helvetica", 14, "bold"),
                     text_color="#008080").pack(pady=(16, 5))
        self.time_sig_var = ctk.StringVar(value=current_time_sig)
        ctk.CTkComboBox(self, variable=self.time_sig_var,
                        values=TIME_SIGNATURE_ORDER).pack(padx=20, fill="x")

        ctk.CTkLabel(self, text="Tempo (BPM)", font=("Helvetica", 14, "bold"),
                     text_color="#008080").pack(pady=(16, 5))
        self.tempo_var = ctk.IntVar(value=current_tempo)
        self.tempo_slider = ctk.CTkSlider(
            self, from_=40, to=240, variable=self.tempo_var,
            command=self._update_tempo_label, fg_color="#CCCCCC", progress_color="#008080"
        )
        self.tempo_slider.pack(padx=20, fill="x")
        self.tempo_label = ctk.CTkLabel(self, text=f"{current_tempo} BPM", text_color="#333333")
        self.tempo_label.pack()

        ctk.CTkLabel(self, text="Orchestration & Volume", font=("Helvetica", 14, "bold"),
                     text_color="#008080").pack(pady=(20, 10))

        self.voice_vars = []
        self.vol_vars = []
        voices = ["Soprano", "Alto", "Tenor", "Bass"]

        voices_frame = ctk.CTkFrame(self, fg_color="transparent")
        voices_frame.pack(fill="x", padx=20, pady=5)

        for i, voice in enumerate(voices):
            ctk.CTkLabel(voices_frame, text=voice, width=60, anchor="w",
                         text_color="#333333").grid(row=i, column=0, pady=10)

            inst_var = ctk.StringVar(value=current_insts[i])
            self.voice_vars.append(inst_var)

            btn = ctk.CTkButton(
                voices_frame,
                text=current_insts[i],
                fg_color="#FFFFFF",
                text_color="#333333",
                border_width=1,
                border_color="#CCCCCC",
                hover_color="#E0E0E0"
            )
            btn.grid(row=i, column=1, padx=10, pady=10, sticky="ew")
            btn.configure(command=lambda v=inst_var, b=btn: self._open_search(v, b))

            vol_var = ctk.IntVar(value=current_vols[i])
            self.vol_vars.append(vol_var)
            vol_slider = ctk.CTkSlider(voices_frame, from_=0, to=127, variable=vol_var,
                                       width=100, fg_color="#CCCCCC", progress_color="#008080")
            vol_slider.grid(row=i, column=2, padx=5)

        ctk.CTkButton(self, text="Apply & Close", fg_color="#008080",
                      hover_color="#006666", command=self._apply_and_close).pack(pady=30)

    def _update_tempo_label(self, val):
        self.tempo_label.configure(text=f"{int(val)} BPM")

    def _open_search(self, target_var, target_button=None):
        search_win = ctk.CTkToplevel(self)
        search_win.title("Search Instrument")
        search_win.geometry("300x400")
        search_win.attributes("-topmost", True)
        search_win.configure(fg_color="#FFFFFF")

        search_var = ctk.StringVar()
        entry = ctk.CTkEntry(search_win, textvariable=search_var,
                             placeholder_text="Type to search...",
                             fg_color="#F5F5F5", text_color="#000000")
        entry.pack(padx=10, pady=10, fill="x")

        scroll = ctk.CTkScrollableFrame(search_win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        def choose_instrument(name):
            target_var.set(name)
            if target_button is not None:
                target_button.configure(text=name)
            search_win.destroy()

        def update_list(*args):
            for widget in scroll.winfo_children():
                widget.destroy()
            query = search_var.get().lower()
            for name in self.sorted_inst_names:
                if query in name.lower():
                    ctk.CTkButton(
                        scroll, text=name, fg_color="transparent",
                        text_color="#333333", anchor="w",
                        command=lambda n=name: choose_instrument(n)
                    ).pack(fill="x", pady=2)

        search_var.trace_add("write", update_list)
        update_list()

    def _apply_and_close(self):
        settings = {
            "key": self.key_var.get(),
            "time_sig": self.time_sig_var.get(),
            "tempo": self.tempo_var.get(),
            "instruments": [v.get() for v in self.voice_vars],
            "volumes": [v.get() for v in self.vol_vars],
        }
        self.on_apply(settings)
        self.destroy()