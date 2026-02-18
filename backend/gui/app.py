import customtkinter as ctk
from gui.frames.welcome_frame import WelcomeFrame
from gui.frames.input_frame import InputFrame
from gui.frames.confirmation_frame import ConfirmationFrame
from gui.frames.processing_frame import ProcessingFrame
from gui.frames.results_frame import ResultsFrame


class App(ctk.CTk):
    """Main application window controller."""

    FRAME_CLASSES = {
        "WelcomeFrame": WelcomeFrame,
        "InputFrame": InputFrame,
        "ConfirmationFrame": ConfirmationFrame,
        "ProcessingFrame": ProcessingFrame,
        "ResultsFrame": ResultsFrame,
    }

    def __init__(self):
        super().__init__()

        self.title("Calor Systems – Riconciliazione Demo")
        self.geometry("900x650")
        self.minsize(750, 500)

        # Grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Shared state between frames
        self.shared_data: dict = {}

        # Frame cache
        self._frames: dict[str, ctk.CTkFrame] = {}
        self._current_frame_name: str | None = None

        # Show first screen
        self.show_frame("WelcomeFrame")

    # ------------------------------------------------------------------ #
    def show_frame(self, name: str, **kwargs):
        """Switch the visible frame.  *kwargs* are forwarded to
        ``on_show()`` if the frame defines it."""

        # Hide current
        for f in self._frames.values():
            f.grid_remove()

        # Create on first use
        if name not in self._frames:
            cls = self.FRAME_CLASSES.get(name)
            if cls is None:
                raise ValueError(f"Unknown frame: {name}")
            frame = cls(parent=self, controller=self)
            self._frames[name] = frame

        frame = self._frames[name]
        frame.grid(row=0, column=0, sticky="nsew")
        frame.tkraise()
        self._current_frame_name = name

        # Let the frame know it is now visible
        if hasattr(frame, "on_show"):
            frame.on_show(**kwargs)
