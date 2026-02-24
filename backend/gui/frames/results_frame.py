import customtkinter as ctk
import threading
from tkinter import simpledialog, messagebox
from core.ai_report import generate_report, get_saved_api_key, save_api_key


_STATUS_STYLE = {
    "QUADRATO":        ("✅ Quadrato",       "#2ecc71"),
    "QUADRATO_ARROT":  ("✅ Quadrato (≈)",   "#27ae60"),
    "ANOMALIA_LIEVE":  ("⚠️ Anomalia lieve", "#f39c12"),
    "ANOMALIA_GRAVE":  ("🔴 Anomalia grave", "#e74c3c"),
    "NON_TROVATO":     ("❓ Non trovato",     "#95a5a6"),
    "IN_ATTESA":       ("⏳ In attesa",       "#3498db"),
    "INCOMPLETO":      ("❓ Incompleto",      "#95a5a6"),
}


class ResultsFrame(ctk.CTkFrame):
    """Displays reconciliation results day by day."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)

        # ── Header ──
        ctk.CTkLabel(
            self, text="📊  Risultati Analisi",
            font=("Segoe UI", 22, "bold"),
        ).grid(row=0, column=0, pady=(20, 5), padx=20)

        self.summary_label = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 13), text_color="gray",
        )
        self.summary_label.grid(row=1, column=0, pady=(0, 10), padx=20)

        # ── Scrollable results ──
        self.cards = ctk.CTkScrollableFrame(
            self, label_text="Dettaglio giornaliero"
        )
        self.cards.grid(row=2, column=0, pady=5, padx=20, sticky="nsew")
        self.cards.grid_columnconfigure(0, weight=1)

        # ── Bottom ──
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=3, column=0, pady=20)

        ctk.CTkButton(
            self.bottom_frame, text="🏠  Torna",
            command=lambda: self.controller.show_frame("WelcomeFrame"),
            width=140, corner_radius=8,
        ).grid(row=0, column=0, padx=10)

        self.btn_ai = ctk.CTkButton(
            self.bottom_frame, text="🤖 Genera Report AI",
            command=self._generate_ai_report,
            width=160, corner_radius=8, fg_color="#8e44ad", hover_color="#9b59b6"
        )
        self.btn_ai.grid(row=0, column=1, padx=10)

        self.ai_provider = ctk.CTkOptionMenu(
            self.bottom_frame, values=["OpenRouter", "Gemini"],
            width=120, corner_radius=8
        )
        self.ai_provider.grid(row=0, column=2, padx=10)
        self.ai_provider.set("OpenRouter")

    # ── Lifecycle ──
    def on_show(self, **_):
        self._build()

    def _build(self):
        for w in self.cards.winfo_children():
            w.destroy()

        results = self.controller.shared_data.get("results", [])
        if not results:
            ctk.CTkLabel(
                self.cards, text="Nessun risultato disponibile.",
                font=("Segoe UI", 13), text_color="gray",
            ).pack(pady=30)
            self.summary_label.configure(text="")
            return

        # Summary counts
        ok = sum(1 for r in results if r.get("stato_globale") in ("QUADRATO",))
        warn = sum(1 for r in results if "ANOMALIA" in (r.get("stato_globale") or ""))
        self.summary_label.configure(
            text=f"{len(results)} giornate analizzate  —  "
                 f"✅ {ok} OK   ⚠ {warn} con anomalie"
        )

        for res in results:
            date_str = res.get("data", "N/A")
            gs = res.get("stato_globale", "UNKNOWN")
            gs_label, gs_colour = _STATUS_STYLE.get(gs, (gs, "gray"))

            # Day card
            card = ctk.CTkFrame(self.cards, fg_color="#2b2b2b", corner_radius=8)
            card.pack(fill="x", pady=4, padx=4)
            card.grid_columnconfigure(1, weight=1)

            # Date + global status
            ctk.CTkLabel(
                card, text=f"📅 {date_str}",
                font=("Segoe UI", 13, "bold"),
            ).grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")

            ctk.CTkLabel(
                card, text=gs_label,
                font=("Segoe UI", 13, "bold"), text_color=gs_colour,
            ).grid(row=0, column=1, padx=10, pady=(8, 2), sticky="e")

            # Category details
            row_i = 1
            for cat, det in res.get("risultati", {}).items():
                stato = det.get("stato", "")
                diff = det.get("differenza", 0)
                note = det.get("note", "")
                s_label, s_col = _STATUS_STYLE.get(stato, (stato, "gray"))

                line = f"  {cat}:  {s_label}  (diff €{diff:+.2f})"
                if note:
                    line += f"  — {note}"

                ctk.CTkLabel(
                    card, text=line,
                    font=("Segoe UI", 11), text_color=s_col, anchor="w",
                ).grid(row=row_i, column=0, columnspan=2, padx=18, pady=1, sticky="w")
                row_i += 1

            # Bottom padding inside card
            ctk.CTkLabel(card, text="").grid(row=row_i, column=0, pady=4)

    def _generate_ai_report(self):
        results = self.controller.shared_data.get("results", [])
        if not results:
            messagebox.showinfo("Niente da analizzare", "Non ci sono risultati da analizzare.")
            return

        provider = self.ai_provider.get()
        api_key = get_saved_api_key(provider)
        
        if not api_key:
            api_key = simpledialog.askstring(
                f"Chiave API {provider}",
                f"Inserisci la tua chiave API di {provider} per generare il report:",
                parent=self
            )
            if not api_key:
                return  # Canceled
            save_api_key(provider, api_key)

        self.btn_ai.configure(state="disabled", text="⏳ Generazione...")

        def _worker():
            try:
                report_text = generate_report(results, provider, api_key)
                self.after(0, lambda: self._show_report_window(report_text, provider))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore AI", str(e)))
            finally:
                self.after(0, lambda: self.btn_ai.configure(state="normal", text="🤖 Genera Report AI"))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_report_window(self, text: str, provider: str):
        win = ctk.CTkToplevel(self)
        win.title(f"Report Analisi AI ({provider})")
        win.geometry("700x500")
        win.attributes("-topmost", True)  # Fallback focus

        lbl = ctk.CTkLabel(win, text="🤖 Analisi Intelligente Risultati", font=("Segoe UI", 18, "bold"))
        lbl.pack(pady=10)

        txt = ctk.CTkTextbox(win, font=("Consolas", 13), corner_radius=10, wrap="word")
        txt.pack(expand=True, fill="both", padx=20, pady=10)
        txt.insert("1.0", text)
        txt.configure(state="disabled")

        btn = ctk.CTkButton(win, text="Chiudi", command=win.destroy)
        btn.pack(pady=10)

