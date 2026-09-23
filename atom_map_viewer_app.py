"""
Atom-map viewer applet.

Paste a list of SMILES / SMIRKS / reaction-SMILES strings (one per line) into
the text box and click "Render". Each line is drawn as its own image with
atom-map numbers shown as side annotations; use the Previous/Next buttons
(or Left/Right arrow keys) to step through them.

Run with:
    python atom_map_viewer_app.py
"""

import io
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageTk

from show_atom_map import render_mapped_smiles

CANVAS_SIZE = 500


class AtomMapViewerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Atom Map Viewer")
        self.root.geometry("900x800")

        self.entries: list[str] = []
        self.images: list[ImageTk.PhotoImage] = []
        self.current_index = 0

        self._build_widgets()

    def _build_widgets(self) -> None:
        # --- input area ---
        input_frame = ttk.Frame(self.root, padding=10)
        input_frame.pack(fill=tk.BOTH, expand=False)

        ttk.Label(
            input_frame,
            text="Paste SMILES / SMIRKS / reaction-SMILES, one per line:",
        ).pack(anchor="w")

        self.text_box = tk.Text(input_frame, height=8, wrap="none")
        self.text_box.pack(fill=tk.BOTH, expand=True, pady=(4, 4))

        button_row = ttk.Frame(input_frame)
        button_row.pack(fill=tk.X)

        self.render_button = ttk.Button(button_row, text="Render", command=self.render_all)
        self.render_button.pack(side=tk.LEFT)

        self.status_label = ttk.Label(button_row, text="")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # --- image display area ---
        display_frame = ttk.Frame(self.root, padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True)

        self.image_label = ttk.Label(display_frame, anchor="center")
        self.image_label.pack(fill=tk.BOTH, expand=True)

        # --- navigation controls ---
        nav_frame = ttk.Frame(self.root, padding=10)
        nav_frame.pack(fill=tk.X)

        self.prev_button = ttk.Button(nav_frame, text="< Previous", command=self.show_previous)
        self.prev_button.pack(side=tk.LEFT)

        self.position_label = ttk.Label(nav_frame, text="", anchor="center")
        self.position_label.pack(side=tk.LEFT, expand=True)

        self.next_button = ttk.Button(nav_frame, text="Next >", command=self.show_next)
        self.next_button.pack(side=tk.RIGHT)

        self.smiles_label = ttk.Label(self.root, text="", padding=(10, 0, 10, 10), wraplength=880)
        self.smiles_label.pack(fill=tk.X)

        self.root.bind("<Left>", lambda _event: self.show_previous())
        self.root.bind("<Right>", lambda _event: self.show_next())

    def render_all(self) -> None:
        raw_lines = self.text_box.get("1.0", tk.END).splitlines()
        lines = [line.strip() for line in raw_lines if line.strip()]

        if not lines:
            messagebox.showinfo("Nothing to render", "Paste at least one SMILES/SMIRKS string first.")
            return

        images: list[ImageTk.PhotoImage] = []
        entries: list[str] = []
        errors: list[str] = []

        for line in lines:
            try:
                png_bytes = render_mapped_smiles(line, CANVAS_SIZE)
                pil_image = Image.open(io.BytesIO(png_bytes))
                images.append(ImageTk.PhotoImage(pil_image))
                entries.append(line)
            except Exception as exc:
                errors.append(f"Line skipped ({exc}): {line}")

        if not images:
            messagebox.showerror("Nothing rendered", "\n".join(errors) or "No valid structures found.")
            return

        self.images = images
        self.entries = entries
        self.current_index = 0
        self._show_current()

        if errors:
            self.status_label.config(text=f"{len(errors)} line(s) skipped (see console).")
            print("\n".join(errors))
        else:
            self.status_label.config(text=f"Rendered {len(images)} structure(s).")

    def _show_current(self) -> None:
        if not self.images:
            return
        image = self.images[self.current_index]
        self.image_label.config(image=image)
        self.image_label.image = image  # keep a reference alive
        self.position_label.config(text=f"{self.current_index + 1} / {len(self.images)}")
        self.smiles_label.config(text=self.entries[self.current_index])

    def show_previous(self) -> None:
        if not self.images:
            return
        self.current_index = (self.current_index - 1) % len(self.images)
        self._show_current()

    def show_next(self) -> None:
        if not self.images:
            return
        self.current_index = (self.current_index + 1) % len(self.images)
        self._show_current()


def main() -> None:
    root = tk.Tk()
    AtomMapViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
