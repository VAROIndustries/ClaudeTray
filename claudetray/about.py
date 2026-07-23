"""About dialog: version info and links to varo.industries. Not unit-tested (UI)."""
import threading
import webbrowser

from . import __version__

TOOL_URL = "https://varo.industries/apps#github"
GITHUB_URL = "https://github.com/VAROIndustries/ClaudeTray"

BG = "#1a1a2e"
FG = "#e0e0e0"
FG_DIM = "#888888"
LINK = "#7aa2f7"


def _build(root):
    import tkinter as tk

    root.title("About ClaudeTray")
    root.configure(bg=BG)
    root.attributes("-topmost", True)
    root.resizable(False, False)

    pad = tk.Frame(root, bg=BG, padx=28, pady=20)
    pad.pack()

    tk.Label(pad, text="ClaudeTray", bg=BG, fg=FG,
             font=("Segoe UI", 16, "bold")).pack()
    tk.Label(pad, text=f"Version {__version__}", bg=BG, fg=FG_DIM).pack(pady=(2, 0))
    tk.Label(pad, text="Claude Code usage, right in your system tray.",
             bg=BG, fg=FG).pack(pady=(6, 12))

    def _link(text, url):
        lbl = tk.Label(pad, text=text, bg=BG, fg=LINK, cursor="hand2",
                       font=("Segoe UI", 9, "underline"))
        lbl.pack()
        lbl.bind("<Button-1>", lambda e: webbrowser.open(url))

    _link("varo.industries", TOOL_URL)
    _link("github.com/VAROIndustries/ClaudeTray", GITHUB_URL)

    tk.Label(pad, text="© 2026 VARØ Industries", bg=BG, fg=FG_DIM).pack(pady=(12, 10))
    tk.Button(pad, text="Close", width=10, command=root.destroy).pack()


def _run():
    import tkinter as tk

    root = tk.Tk()
    _build(root)
    root.mainloop()


def show_about():
    """Show the About window in its own thread so it doesn't block the tray."""
    threading.Thread(target=_run, daemon=True).start()
