import customtkinter as ctk


class WelcomeFrame(ctk.CTkFrame):
    """Welcome / demo screen – first thing the user sees."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Center everything
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # ── Logo / icon area ──
        icon_label = ctk.CTkLabel(
            self, text="⚙️", font=("Segoe UI Emoji", 52)
        )
        icon_label.grid(row=1, column=0, pady=(0, 5))

        # ── Title ──
        ctk.CTkLabel(
            self,
            text="Calor Systems",
            font=("Segoe UI", 28, "bold"),
        ).grid(row=2, column=0, pady=(0, 5))

        # ── Subtitle / demo notice ──
        ctk.CTkLabel(
            self,
            text="Sistema di Riconciliazione Dati – DEMO",
            font=("Segoe UI", 15),
            text_color="gray",
        ).grid(row=3, column=0, pady=(0, 25))

        # ── Description ──
        desc = (
            "Questa è una versione dimostrativa del software.\n"
            "Premi il pulsante qui sotto per iniziare:\n"
            "caricherai i tuoi file Excel e il sistema\n"
            "verificherà automaticamente la quadratura dei conti."
        )
        ctk.CTkLabel(
            self, text=desc, font=("Segoe UI", 13), justify="center",
            text_color="#aaaaaa",
        ).grid(row=4, column=0, pady=(0, 20))

        # ── CTA button ──
        self.btn = ctk.CTkButton(
            self,
            text="▶  INIZIA IL TEST",
            command=self._go,
            width=260,
            height=48,
            font=("Segoe UI", 16, "bold"),
            corner_radius=12,
        )
        self.btn.grid(row=5, column=0, pady=(0, 40), sticky="n")

    def _go(self):
        self.controller.show_frame("InputFrame")
