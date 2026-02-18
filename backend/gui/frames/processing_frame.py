import customtkinter as ctk
import threading
import time
import os
import traceback
from core.database import Database
from core.importer import DataImporter
from core.analyzer import Analyzer


class ProcessingFrame(ctk.CTkFrame):
    """Runs import + analysis on a background thread with live feedback."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self._running = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=1)
        self.grid_rowconfigure(5, weight=0)

        # ── Header ──
        self.title_label = ctk.CTkLabel(
            self, text="⏳  Elaborazione in corso…",
            font=("Segoe UI", 22, "bold"),
        )
        self.title_label.grid(row=0, column=0, pady=(25, 5), padx=20)

        # ── Phase label ──
        self.phase_label = ctk.CTkLabel(
            self, text="Preparazione…",
            font=("Segoe UI", 14), text_color="#3498db",
        )
        self.phase_label.grid(row=1, column=0, pady=(0, 10))

        # ── Progress bar ──
        self.progress = ctk.CTkProgressBar(self, width=500, height=16, corner_radius=8)
        self.progress.grid(row=2, column=0, pady=5, padx=40, sticky="ew")
        self.progress.set(0)

        # ── Percentage label ──
        self.pct_label = ctk.CTkLabel(
            self, text="0 %", font=("Segoe UI", 13, "bold"),
        )
        self.pct_label.grid(row=3, column=0, pady=(2, 10))

        # ── Log area ──
        self.log_box = ctk.CTkTextbox(
            self, font=("Consolas", 11), state="disabled",
            fg_color="#1a1a1a", corner_radius=8,
        )
        self.log_box.grid(row=4, column=0, pady=5, padx=20, sticky="nsew")

        # ── Bottom buttons ──
        self.btn_row = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_row.grid(row=5, column=0, pady=(5, 20))

        self.btn_results = ctk.CTkButton(
            self.btn_row, text="📊  Vedi Risultati", command=self._go_results,
            width=200, corner_radius=8, state="disabled",
        )
        self.btn_results.grid(row=0, column=0, padx=8)

    # ── Lifecycle ----------------------------------------------------------
    def on_show(self, **_):
        if not self._running:
            self._start()

    # ── Thread-safe helpers ------------------------------------------------
    def _log(self, msg: str):
        """Append a line to the log textbox (thread-safe via after())."""
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}]  {msg}\n"

        def _do():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, _do)

    def _set_phase(self, text: str):
        self.after(0, lambda: self.phase_label.configure(text=text))

    def _set_progress(self, value: float):
        """value in 0..1"""
        self.after(0, lambda: self.progress.set(value))
        self.after(0, lambda: self.pct_label.configure(text=f"{int(value * 100)} %"))

    def _progress_cb(self, current, total, message):
        """Callback for importer / analyser."""
        pct = current / total if total > 0 else 0
        self._set_progress(pct)
        self._log(message)

    # ── Processing ---------------------------------------------------------
    def _start(self):
        self._running = True
        self.btn_results.configure(state="disabled")
        self.progress.set(0)

        # Clear log
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        self._set_phase("Preparazione…")
        self._log("Avvio elaborazione…")

        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            files = self.controller.shared_data.get("files", [])
            root_path = os.getcwd()

            # Phase 1 — Database
            self._set_phase("FASE 1/3 · Inizializzazione database…")
            self._log("Inizializzazione database in corso…")
            db = Database(root_path)
            ok = db.initialize()
            if not ok:
                self._log("❌  Inizializzazione database fallita!")
                self._set_phase("Errore.")
                self._running = False
                return
            self._log("✅  Database pronto.")
            self._set_progress(0.05)

            # Phase 2 — Import
            self._set_phase(f"FASE 2/3 · Importazione {len(files)} file…")
            self._log(f"Importazione di {len(files)} file…")

            importer = DataImporter(db)
            importer.import_files(files, progress_callback=self._progress_cb)
            self._log("✅  Importazione completata.")
            self._set_progress(0.6)

            # Phase 3 — Analysis
            self._set_phase("FASE 3/3 · Analisi riconciliazione…")
            self._log("Avvio analisi riconciliazione…")

            analyzer = Analyzer(db)
            results = analyzer.run_analysis(progress_callback=self._progress_cb)
            self._log(f"✅  Analisi completata — {len(results)} giornate elaborate.")
            self._set_progress(1.0)

            self.controller.shared_data["results"] = results

            # Done
            self._set_phase("✅  Elaborazione completata!")
            self.after(0, lambda: self.title_label.configure(
                text="✅  Elaborazione completata!"
            ))
            self.after(0, lambda: self.btn_results.configure(state="normal"))

        except Exception as exc:
            tb = traceback.format_exc()
            self._log(f"❌  ERRORE: {exc}")
            self._log(tb)
            self._set_phase("❌  Si è verificato un errore.")
        finally:
            self._running = False

    def _go_results(self):
        self.controller.show_frame("ResultsFrame")
