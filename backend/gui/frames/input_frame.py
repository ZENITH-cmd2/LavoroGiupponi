import customtkinter as ctk
from tkinter import filedialog
import os


class InputFrame(ctk.CTkFrame):
    """File-selection screen: user picks one or more Excel files."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.selected_files: list[str] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)

        # ── Title ──
        ctk.CTkLabel(
            self, text="📂  Caricamento Dati", font=("Segoe UI", 22, "bold"),
        ).grid(row=0, column=0, pady=(20, 5), padx=20)

        ctk.CTkLabel(
            self,
            text="Seleziona i file Excel dei punti vendita che vuoi analizzare.",
            font=("Segoe UI", 13), text_color="gray",
        ).grid(row=1, column=0, pady=(0, 10), padx=20)

        # ── File list ──
        self.file_list = ctk.CTkScrollableFrame(
            self, label_text="File selezionati (0)"
        )
        self.file_list.grid(row=2, column=0, pady=5, padx=20, sticky="nsew")
        self.file_list.grid_columnconfigure(0, weight=1)

        # ── Empty-state placeholder ──
        self._placeholder = ctk.CTkLabel(
            self.file_list,
            text="Nessun file ancora selezionato.\nClicca «Aggiungi File» per iniziare.",
            text_color="#777777", font=("Segoe UI", 12),
        )
        self._placeholder.pack(pady=30)

        # ── Buttons row ──
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=3, column=0, pady=10, padx=20, sticky="ew")
        btn_row.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(
            btn_row, text="➕  Aggiungi File", command=self._add,
            width=170, corner_radius=8,
        ).grid(row=0, column=0, padx=6)

        ctk.CTkButton(
            btn_row, text="🗑  Svuota Lista", command=self._clear,
            width=170, corner_radius=8,
            fg_color="#c0392b", hover_color="#922b21",
        ).grid(row=0, column=1, padx=6)

        self.btn_next = ctk.CTkButton(
            btn_row, text="Avanti  ➡", command=self._next,
            width=170, corner_radius=8, state="disabled",
        )
        self.btn_next.grid(row=0, column=2, padx=6)

        # ── Back button ──
        ctk.CTkButton(
            self, text="← Indietro", command=lambda: controller.show_frame("WelcomeFrame"),
            width=100, fg_color="transparent", hover_color="#333333",
            text_color="gray", font=("Segoe UI", 12),
        ).grid(row=4, column=0, pady=(0, 15))

    # ── Actions ──
    def _add(self):
        paths = filedialog.askopenfilenames(
            title="Seleziona file Excel",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Tutti", "*.*")],
        )
        for p in paths:
            if p not in self.selected_files:
                self.selected_files.append(p)
        self._refresh()

    def _clear(self):
        self.selected_files.clear()
        self._refresh()

    def _next(self):
        self.controller.shared_data["files"] = list(self.selected_files)
        self.controller.show_frame("ConfirmationFrame")

    def _refresh(self):
        for w in self.file_list.winfo_children():
            w.destroy()

        if not self.selected_files:
            self._placeholder = ctk.CTkLabel(
                self.file_list,
                text="Nessun file ancora selezionato.\nClicca «Aggiungi File» per iniziare.",
                text_color="#777777", font=("Segoe UI", 12),
            )
            self._placeholder.pack(pady=30)
            self.file_list.configure(label_text="File selezionati (0)")
            self.btn_next.configure(state="disabled")
            return

        self.file_list.configure(label_text=f"File selezionati ({len(self.selected_files)})")
        for idx, fp in enumerate(self.selected_files, 1):
            row = ctk.CTkFrame(self.file_list, fg_color="#2b2b2b", corner_radius=6)
            row.pack(fill="x", pady=2, padx=4)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row, text=f" {idx}.", font=("Segoe UI", 12, "bold"), width=30,
            ).grid(row=0, column=0, padx=(8, 2), pady=4)

            ctk.CTkLabel(
                row, text=os.path.basename(fp), font=("Segoe UI", 12), anchor="w",
            ).grid(row=0, column=1, padx=4, pady=4, sticky="w")

        self.btn_next.configure(state="normal")
