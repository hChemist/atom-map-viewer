"""
Atom-map viewer applet.

Paste a list of SMILES / SMIRKS / reaction-SMILES strings (one per line) into
the text box and click "Render". Each line is drawn as its own image with
atom-map numbers shown as side annotations, stacked in a scrollable page
below the text box so you can scroll through them like a webpage.

Run with:
    python atom_map_viewer_app.py
"""

import ctypes
import ctypes.wintypes
import io
import sys
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageTk

from show_atom_map import render_mapped_smiles

CANVAS_SIZE = 500


def get_usable_screen_size(widget: tk.Misc) -> tuple[int, int]:
    """
    The screen area actually available for windows, excluding the taskbar
    and similar OS chrome (on Windows, via the SPI_GETWORKAREA system
    setting). Falls back to the raw screen size elsewhere or if the query
    fails, and reserves a little extra margin for the window's own title bar.
    """
    title_bar_margin = 40

    if sys.platform == "win32":
        try:
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
            width = rect.right - rect.left
            height = rect.bottom - rect.top - title_bar_margin
            if width > 0 and height > 0:
                return width, height
        except Exception:
            pass

    return widget.winfo_screenwidth(), widget.winfo_screenheight() - title_bar_margin


class AtomMapViewerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Atom Map Viewer")
        self.root.geometry("900x800")

        self.pil_images: list[Image.Image] = []  # original, full-resolution renders
        self.tk_images: list[ImageTk.PhotoImage] = []  # keep references alive
        self.image_labels: list[ttk.Label] = []
        self._resize_after_id: str | None = None
        self._textbox_resize_start_y = 0
        self._textbox_resize_start_height = 0

        self._build_widgets()

    def _build_widgets(self) -> None:
        # --- input area ---
        input_frame = ttk.Frame(self.root, padding=10)
        input_frame.pack(fill=tk.BOTH, expand=False)

        ttk.Label(
            input_frame,
            text="Paste SMILES / SMIRKS / reaction-SMILES, one per line:",
        ).pack(anchor="w")

        text_box_frame = ttk.Frame(input_frame, height=140)
        text_box_frame.pack(fill=tk.X, pady=(4, 0))
        text_box_frame.pack_propagate(False)
        text_box_frame.grid_propagate(False)
        text_box_frame.rowconfigure(0, weight=1)
        text_box_frame.columnconfigure(0, weight=1)

        self.text_box = tk.Text(text_box_frame, wrap="none")
        text_v_scroll = ttk.Scrollbar(text_box_frame, orient="vertical", command=self.text_box.yview)
        text_h_scroll = ttk.Scrollbar(text_box_frame, orient="horizontal", command=self.text_box.xview)
        self.text_box.configure(yscrollcommand=text_v_scroll.set, xscrollcommand=text_h_scroll.set)

        self.text_box.grid(row=0, column=0, sticky="nsew")
        text_v_scroll.grid(row=0, column=1, sticky="ns")
        text_h_scroll.grid(row=1, column=0, sticky="ew")

        self._text_box_frame = text_box_frame

        grip = ttk.Frame(input_frame, height=8, cursor="sb_v_double_arrow")
        grip.pack(fill=tk.X, pady=(0, 4))
        ttk.Separator(grip, orient="horizontal").place(relx=0.5, rely=0.5, anchor="center", relwidth=1)

        grip.bind("<ButtonPress-1>", self._start_textbox_resize)
        grip.bind("<B1-Motion>", self._do_textbox_resize)

        button_row = ttk.Frame(input_frame)
        button_row.pack(fill=tk.X)

        self.render_button = ttk.Button(button_row, text="Render", command=self.render_all)
        self.render_button.pack(side=tk.LEFT)

        self.status_label = ttk.Label(button_row, text="")
        self.status_label.pack(side=tk.LEFT, padx=10)

        ttk.Label(input_frame, text="Click any rendered image to open it full-size.").pack(anchor="w", pady=(4, 0))

        # --- scrollable results page ---
        results_frame = ttk.Frame(self.root)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.results_canvas = tk.Canvas(results_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_canvas.yview)
        self.results_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.results_container = ttk.Frame(self.results_canvas)
        self.results_window = self.results_canvas.create_window(
            (0, 0), window=self.results_container, anchor="nw"
        )

        self.results_container.bind(
            "<Configure>",
            lambda _event: self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all")),
        )
        self.results_canvas.bind("<Configure>", self._on_canvas_resized)

        # mouse-wheel scrolling (Windows sends <MouseWheel> with event.delta in multiples of 120)
        self.results_canvas.bind("<Enter>", lambda _event: self._bind_mousewheel())
        self.results_canvas.bind("<Leave>", lambda _event: self._unbind_mousewheel())

    def _start_textbox_resize(self, event: tk.Event) -> None:
        self._textbox_resize_start_y = event.y_root
        self._textbox_resize_start_height = self._text_box_frame.winfo_height()

    def _do_textbox_resize(self, event: tk.Event) -> None:
        delta = event.y_root - self._textbox_resize_start_y
        new_height = max(self._textbox_resize_start_height + delta, 40)
        self._text_box_frame.configure(height=new_height)

    def _bind_mousewheel(self) -> None:
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self) -> None:
        self.root.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.results_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_canvas_resized(self, event: tk.Event) -> None:
        self.results_canvas.itemconfig(self.results_window, width=event.width)

        # Debounce: only rescale images after the user stops resizing for a moment.
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(150, lambda: self._rescale_images(event.width))

    def _rescale_images(self, available_width: int) -> None:
        self._resize_after_id = None
        max_width = max(available_width - 20, 50)  # small margin so it isn't flush with the scrollbar

        self.tk_images = []
        for pil_image, label in zip(self.pil_images, self.image_labels):
            if pil_image.width > max_width:
                scale = max_width / pil_image.width
                new_size = (max_width, max(int(pil_image.height * scale), 1))
                resized = pil_image.resize(new_size, Image.LANCZOS)
            else:
                resized = pil_image

            tk_image = ImageTk.PhotoImage(resized)
            self.tk_images.append(tk_image)  # keep a reference alive
            label.configure(image=tk_image)
            label.image = tk_image

    def _make_caption_widget(self, parent: tk.Widget, caption: str) -> tk.Text:
        """A read-only, auto-sized Text widget so SMILES/SMIRKS captions can be selected and copied."""
        style = ttk.Style()
        bg = style.lookup("TFrame", "background") or "SystemButtonFace"

        text_widget = tk.Text(
            parent,
            wrap="word",
            height=1,
            borderwidth=0,
            highlightthickness=0,
            background=bg,
            relief="flat",
            padx=0,
            pady=0,
            cursor="xterm",
        )
        text_widget.insert("1.0", caption)
        text_widget.tag_configure("center", justify="center")
        text_widget.tag_add("center", "1.0", "end")

        # Allow selection/copy but block editing: keep state "normal" (a
        # "disabled" Text widget blocks mouse-drag selection in Tk) and swallow
        # key presses instead, except the standard copy shortcuts.
        def block_edits(event: tk.Event) -> str | None:
            if event.state & 0x4 and event.keysym.lower() == "c":  # Ctrl+C
                return None
            return "break"

        def select_all(_event: tk.Event) -> str:
            text_widget.tag_add("sel", "1.0", "end")
            return "break"

        text_widget.bind("<Key>", block_edits)
        text_widget.bind("<Control-a>", select_all)

        # Grow the widget to fit the wrapped text instead of scrolling internally.
        def resize_to_content(_event=None) -> None:
            num_lines = int(text_widget.count("1.0", "end", "displaylines")[0])
            text_widget.configure(height=max(num_lines, 1))

        text_widget.bind("<Configure>", resize_to_content)

        return text_widget

    def _open_full_size(self, pil_image: Image.Image, caption: str) -> None:
        popup = tk.Toplevel(self.root)
        popup.title(caption[:80])
        popup.attributes("-topmost", True)
        popup.after(200, lambda: popup.attributes("-topmost", False))

        # The viewport is a fixed fraction of *this* screen's usable work area
        # (re-read fresh each time so it adapts to whichever monitor/laptop it
        # opens on, and excludes the taskbar/title bar so the window doesn't
        # get pushed off-screen or clipped by OS chrome) -- independent of the
        # image's own size, so scrolling is only offered, and only works, when
        # the image genuinely doesn't fit.
        screen_w, screen_h = get_usable_screen_size(popup)
        caption_budget = 90
        toolbar_budget = 36
        viewport_w = int(screen_w * 0.85)
        viewport_h = int(screen_h * 0.85) - caption_budget - toolbar_budget

        caption_box = self._make_caption_widget(popup, caption)
        caption_box.pack(fill=tk.X, padx=10, pady=(6, 0))

        # Zoom controls: start at 100% (native resolution); "Zoom to fit" scales
        # down just enough that the whole image is visible with no scrolling,
        # useful when the image is too big to see all at once.
        fit_scale = min(viewport_w / pil_image.width, viewport_h / pil_image.height, 1.0)
        zoom_state = {"scale": 1.0}

        toolbar = ttk.Frame(popup)
        toolbar.pack(fill=tk.X, padx=10, pady=(6, 0))

        zoom_label = ttk.Label(toolbar, text="100%")

        def redraw(new_scale: float) -> None:
            new_scale = max(0.05, min(new_scale, 4.0))
            zoom_state["scale"] = new_scale
            zoom_label.config(text=f"{round(new_scale * 100)}%")

            display_w = max(int(pil_image.width * new_scale), 1)
            display_h = max(int(pil_image.height * new_scale), 1)
            display_image = (
                pil_image if new_scale == 1.0 else pil_image.resize((display_w, display_h), Image.LANCZOS)
            )

            canvas_w = min(display_w, viewport_w)
            canvas_h = min(display_h, viewport_h)
            canvas.configure(width=canvas_w, height=canvas_h, scrollregion=(0, 0, display_w, display_h))

            v_scroll.grid_remove()
            h_scroll.grid_remove()
            if display_h > canvas_h:
                v_scroll.grid(row=0, column=1, sticky="ns")
            if display_w > canvas_w:
                h_scroll.grid(row=1, column=0, sticky="ew")

            tk_image = ImageTk.PhotoImage(display_image)
            canvas.delete("all")
            canvas.current_image = tk_image  # keep a reference alive
            canvas.create_image(0, 0, image=tk_image, anchor="nw")

            popup.update_idletasks()
            width = min(popup.winfo_reqwidth(), screen_w)
            height = min(popup.winfo_reqheight(), screen_h)
            x = max((screen_w - width) // 2, 0)
            y = max((screen_h - height) // 2, 0)
            popup.geometry(f"{width}x{height}+{x}+{y}")

        def zoom_in() -> None:
            redraw(zoom_state["scale"] * 1.25)

        def zoom_out() -> None:
            redraw(zoom_state["scale"] / 1.25)

        def zoom_to_fit() -> None:
            redraw(fit_scale)

        def zoom_actual_size() -> None:
            redraw(1.0)

        ttk.Button(toolbar, text="Zoom to Fit", command=zoom_to_fit).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="100%", command=zoom_actual_size).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(toolbar, text="-", width=2, command=zoom_out).pack(side=tk.LEFT, padx=(10, 0))
        zoom_label.pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="+", width=2, command=zoom_in).pack(side=tk.LEFT)

        canvas_frame = ttk.Frame(popup)
        canvas_frame.pack(padx=10, pady=10)

        canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        canvas.grid(row=0, column=0)
        v_scroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        h_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        def on_mousewheel(event: tk.Event) -> None:
            if event.state & 0x4:  # Ctrl+wheel zooms
                if event.delta > 0:
                    zoom_in()
                else:
                    zoom_out()
            elif event.state & 0x1:  # Shift+wheel scrolls horizontally
                canvas.xview_scroll(int(-event.delta / 120), "units")
            else:
                canvas.yview_scroll(int(-event.delta / 120), "units")

        canvas.bind("<MouseWheel>", on_mousewheel)

        redraw(1.0)

        # If the image doesn't fit natively, default to "zoom to fit" so the
        # whole structure is visible right away; the user can zoom in from there.
        if fit_scale < 1.0:
            zoom_to_fit()

    @staticmethod
    def _parse_entries(raw_text: str) -> list[tuple[str, str]]:
        """
        Parse pasted text into (smirks_to_render, caption) pairs.

        Handles plain one-per-line input as well as rows copied horizontally
        from a spreadsheet, where cells are tab-separated and each cell may be
        "<SMIRKS> <mapping annotation>" (only the SMIRKS part is rendered; the
        full cell text is kept as the caption).
        """
        entries: list[tuple[str, str]] = []
        for raw_line in raw_text.splitlines():
            for cell in raw_line.split("\t"):
                cell = cell.strip()
                if not cell:
                    continue
                smirks = cell.split(None, 1)[0]
                entries.append((smirks, cell))
        return entries

    def render_all(self) -> None:
        raw_text = self.text_box.get("1.0", tk.END)
        entries = self._parse_entries(raw_text)

        if not entries:
            messagebox.showinfo("Nothing to render", "Paste at least one SMILES/SMIRKS string first.")
            return

        # If any line contained tab-separated cells (e.g. a row copied
        # horizontally from a spreadsheet), rewrite the box to one cell per
        # line so it's clear how the paste was split up.
        if any("\t" in raw_line for raw_line in raw_text.splitlines()):
            self.text_box.delete("1.0", tk.END)
            self.text_box.insert("1.0", "\n".join(caption for _smirks, caption in entries))

        for child in self.results_container.winfo_children():
            child.destroy()
        self.pil_images = []
        self.tk_images = []
        self.image_labels = []

        errors: list[str] = []
        rendered_count = 0

        for smirks, caption in entries:
            try:
                png_bytes = render_mapped_smiles(smirks, CANVAS_SIZE)
                pil_image = Image.open(io.BytesIO(png_bytes))
                pil_image.load()  # detach from the BytesIO buffer
                tk_image = ImageTk.PhotoImage(pil_image)
            except Exception as exc:
                errors.append(f"Entry skipped ({exc}): {caption}")
                continue

            self.pil_images.append(pil_image)
            self.tk_images.append(tk_image)
            rendered_count += 1

            entry_frame = ttk.Frame(self.results_container, padding=(0, 10))
            entry_frame.pack(fill=tk.X)

            image_label = ttk.Label(entry_frame, image=tk_image, cursor="hand2")
            image_label.pack()
            image_label.bind("<Button-1>", lambda _event, img=pil_image, cap=caption: self._open_full_size(img, cap))
            self.image_labels.append(image_label)

            caption_box = self._make_caption_widget(entry_frame, caption)
            caption_box.pack(fill=tk.X, pady=(4, 0))
            ttk.Separator(entry_frame, orient="horizontal").pack(fill=tk.X, pady=(10, 0))

        self.results_canvas.yview_moveto(0)

        # fit the freshly rendered images to the current window width
        self._rescale_images(self.results_canvas.winfo_width())

        if rendered_count == 0:
            messagebox.showerror("Nothing rendered", "\n".join(errors) or "No valid structures found.")
            return

        if errors:
            self.status_label.config(text=f"Rendered {rendered_count}; {len(errors)} line(s) skipped (see console).")
            print("\n".join(errors))
        else:
            self.status_label.config(text=f"Rendered {rendered_count} structure(s).")


def main() -> None:
    root = tk.Tk()
    AtomMapViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
