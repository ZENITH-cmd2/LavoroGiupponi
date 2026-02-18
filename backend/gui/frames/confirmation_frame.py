import customtkinter as ctk
import os
from core.file_classifier import FileClassifier

# Friendly labels and colours per type
_TYPE_META = {
    "FORTECH":   ("📊 Fortech (Master)",           "#3498db"),
    "AS400":     ("💰 AS400 (Contanti)",            "#f1c40f"),
    "NUMIA":     ("💳 Numia (Carte Bancarie)",      "#2ecc71"),
    "IP_CARTE":  ("⛽ iP Portal (Carte Petrolifere)", "#00bcd4"),
    "IP_BUONI":  ("🎫 iP Portal (Buoni)",           "#e74c3c"),
    "SATISPAY":  ("📱 Satispay",                    "#95a5a6"),
    "UNKNOWN":   ("❓ Non riconosciuto",             "#7f8c8d"),
}


class ConfirmationFrame(ctk.CTkFrame):
    """Shows classified files and lets the user confirm before processing."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)

        # ── Header ──
        ctk.CTkLabel(
            self, text="✅  Riepilogo File", font=("Segoe UI", 22, "bold"),
        ).grid(row=0, column=0, pady=(20, 5), padx=20)

        self.subtitle = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 13), text_color="gray",
        )
        self.subtitle.grid(row=1, column=0, pady=(0, 10), padx=20)

        # ── Scrollable card area ──
        self.cards = ctk.CTkScrollableFrame(self, label_text="Classificazione")
        self.cards.grid(row=2, column=0, pady=5, padx=20, sticky="nsew")
        self.cards.grid_columnconfigure(0, weight=1)

        # ── Status banner ──
        self.status = ctk.CTkLabel(self, text="", font=("Segoe UI", 14, "bold"))
        self.status.grid(row=3, column=0, pady=10)

        # ── Buttons ──
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=4, column=0, pady=(0, 20), padx=20, sticky="ew")
        btn_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row, text="← Indietro", command=lambda: controller.show_frame("InputFrame"),
            width=160, fg_color="gray", hover_color="#555555", corner_radius=8,
        ).grid(row=0, column=0, padx=8)

        self.btn_go = ctk.CTkButton(
            btn_row, text="▶  Procedi con l'analisi", command=self._proceed,
            width=220, corner_radius=8, state="disabled",
        )
        self.btn_go.grid(row=0, column=1, padx=8)

    # ── Lifecycle ──
    def on_show(self, **_):
        self._build()

    # ── Build ──
    def _build(self):
        for w in self.cards.winfo_children():
            w.destroy()

        files = self.controller.shared_data.get("files", [])
        if not files:
            self.subtitle.configure(text="Nessun file selezionato.")
            self.status.configure(text="")
            self.btn_go.configure(state="disabled")
            return

        classified = FileClassifier.classify_files(files)
        missing, is_valid = FileClassifier.validate_group(classified)

        self.subtitle.configure(
            text=f"{len(files)} file caricati — vedi sotto come sono stati classificati."
        )

        for ftype, paths in classified.items():
            label, colour = _TYPE_META.get(ftype, ("?", "gray"))
            card = ctk.CTkFrame(self.cards, fg_color="#2b2b2b", corner_radius=8)
            card.pack(fill="x", pady=4, padx=4)
            card.grid_columnconfigure(1, weight=1)

            # type badge
            ctk.CTkLabel(
                card, text=label, font=("Segoe UI", 13, "bold"),
                text_color=colour,
            ).grid(row=0, column=0, padx=10, pady=6, sticky="w")

            if paths:
                names = ", ".join(os.path.basename(p) for p in paths)
                ctk.CTkLabel(
                    card, text=names, font=("Segoe UI", 12), anchor="w",
                    text_color="#cccccc",
                ).grid(row=0, column=1, padx=6, pady=6, sticky="w")
            else:
                if ftype != "UNKNOWN":
                    ctk.CTkLabel(
                        card, text="⚠  MANCANTE", font=("Segoe UI", 12, "bold"),
                        text_color="#e74c3c",
                    ).grid(row=0, column=1, padx=6, pady=6, sticky="w")

        # Status
        if is_valid:
            self.status.configure(
                text="✅ Tutti i file necessari sono presenti!",
                text_color="#2ecc71",
            )
        elif missing:
            n = len(missing)
            self.status.configure(
                text=f"⚠  {n} tipo/i di file mancanti — puoi comunque procedere.",
                text_color="#f39c12",
            )
        self.btn_go.configure(state="normal")

    def _proceed(self):
        self.controller.show_frame("ProcessingFrame")
