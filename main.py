"""Mój Kopacz — automatyczne kopanie na stoniarkach w wielu oknach Minecrafta."""
import customtkinter as ctk

from gui import App


def main() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    App().mainloop()


if __name__ == "__main__":
    main()
