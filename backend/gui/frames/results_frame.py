import customtkinter as ctk


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
        ctk.CTkButton(
            self, text="🏠  Torna alla Home",
            command=lambda: self.controller.show_frame("WelcomeFrame"),
            width=200, corner_radius=8,
        ).grid(row=3, column=0, pady=20)

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
