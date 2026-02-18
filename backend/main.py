import sys
import os

# Ensure the working directory is the script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from gui.app import App

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = App()
    app.mainloop()
