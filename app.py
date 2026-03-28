import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageOps, ImageFilter

APP_TITLE = "OX Background Remover Tool"
APP_VERSION = "1.1.0"


def color_distance(c1, c2):
    return abs(c1[0] - c2[0]) + abs(c1[1] - c2[1]) + abs(c1[2] - c2[2])


def average_colors(colors):
    if not colors:
        return (255, 255, 255)
    r = sum(c[0] for c in colors) // len(colors)
    g = sum(c[1] for c in colors) // len(colors)
    b = sum(c[2] for c in colors) // len(colors)
    return (r, g, b)


def detect_background_color(img):
    w, h = img.size
    px = img.load()

    sample_points = []
    margin_x = max(1, w // 20)
    margin_y = max(1, h // 20)

    corners = [
        (0, 0),
        (w - 1, 0),
        (0, h - 1),
        (w - 1, h - 1),
    ]

    for cx, cy in corners:
        for dx in range(margin_x):
            for dy in range(margin_y):
                x = min(max(cx + (-dx if cx > 0 else dx), 0), w - 1)
                y = min(max(cy + (-dy if cy > 0 else dy), 0), h - 1)
                sample_points.append(px[x, y][:3])

    return average_colors(sample_points)


def remove_background_and_crop(img, tolerance=60, feather_alpha=True):
    img = img.convert("RGBA")
    bg = detect_background_color(img)
    px = img.load()
    w, h = img.size

    min_x, min_y = w, h
    max_x, max_y = 0, 0
    found = False

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            dist = color_distance((r, g, b), bg)

            if dist <= tolerance:
                if feather_alpha:
                    alpha = int(max(0, min(255, (dist / max(tolerance, 1)) * 255)))
                    px[x, y] = (r, g, b, alpha)
                else:
                    px[x, y] = (r, g, b, 0)
            else:
                found = True
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    if not found:
        return img, bg

    cropped = img.crop((min_x, min_y, max_x + 1, max_y + 1))
    return cropped, bg


class RenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_TITLE} {APP_VERSION}")
        self.root.geometry("1100x780")
        self.root.minsize(1000, 720)

        self.image = None
        self.processed_image = None
        self.preview_image = None
        self.current_path = None

        self.size_var = tk.IntVar(value=100)
        self.padding_var = tk.IntVar(value=4)
        self.tolerance_var = tk.IntVar(value=60)
        self.sharpen_var = tk.BooleanVar(value=True)
        self.auto_crop_var = tk.BooleanVar(value=True)
        self.feather_var = tk.BooleanVar(value=True)

        self.build_ui()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="y", padx=(0, 12))

        right = ttk.Frame(main)
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(left, text="OX Background Remover", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))

        ttk.Button(left, text="Wczytaj obraz", command=self.load_image).pack(fill="x", pady=4)
        ttk.Button(left, text="Zapisz PNG", command=self.save_image).pack(fill="x", pady=4)
        ttk.Button(left, text="Batch render folderu", command=self.batch_render).pack(fill="x", pady=4)

        ttk.Separator(left).pack(fill="x", pady=10)

        ttk.Label(left, text="Rozmiar końcowy (px)").pack(anchor="w")
        size_box = ttk.Combobox(left, textvariable=self.size_var, values=[64, 100, 128, 256, 512], state="readonly")
        size_box.pack(fill="x", pady=(4, 8))
        size_box.bind("<<ComboboxSelected>>", lambda e: self.update_preview())

        ttk.Label(left, text="Padding").pack(anchor="w")
        padding_scale = ttk.Scale(left, from_=0, to=20, orient="horizontal", command=self._on_padding_change)
        padding_scale.set(self.padding_var.get())
        padding_scale.pack(fill="x", pady=(4, 2))
        self.padding_label = ttk.Label(left, text=f"{self.padding_var.get()} px")
        self.padding_label.pack(anchor="w", pady=(0, 8))

        ttk.Label(left, text="Czułość usuwania tła").pack(anchor="w")
        tolerance_scale = ttk.Scale(left, from_=5, to=150, orient="horizontal", command=self._on_tolerance_change)
        tolerance_scale.set(self.tolerance_var.get())
        tolerance_scale.pack(fill="x", pady=(4, 2))
        self.tolerance_label = ttk.Label(left, text=str(self.tolerance_var.get()))
        self.tolerance_label.pack(anchor="w", pady=(0, 8))

        ttk.Checkbutton(left, text="Wyostrz obraz", variable=self.sharpen_var, command=self.update_preview).pack(anchor="w", pady=4)
        ttk.Checkbutton(left, text="Automatycznie przycinaj do obiektu", variable=self.auto_crop_var, command=self.update_preview).pack(anchor="w", pady=4)
        ttk.Checkbutton(left, text="Miękkie krawędzie alpha", variable=self.feather_var, command=self.update_preview).pack(anchor="w", pady=4)

        ttk.Separator(left).pack(fill="x", pady=10)

        info = (
            "Program:\n"
            "- wykrywa kolor tła z rogów\n"
            "- usuwa tło\n"
            "- przycina pustą przestrzeń\n"
            "- centruje obiekt\n"
            "- zapisuje PNG z przezroczystością\n\n"
            "Najlepsze dla obrazów z jednolitym tłem."
        )
        ttk.Label(left, text=info, justify="left").pack(anchor="w", pady=4)

        ttk.Label(right, text="Podgląd", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))
        self.preview_frame = tk.Frame(right, bg="#1e1e1e", bd=1, relief="solid")
        self.preview_frame.pack(fill="both", expand=True)

        self.preview_label = tk.Label(self.preview_frame, bg="#1e1e1e")
        self.preview_label.pack(expand=True)

        self.status = ttk.Label(self.root, text="Gotowe")
        self.status.pack(fill="x", padx=12, pady=(0, 10))

    def _on_padding_change(self, value):
        self.padding_var.set(int(float(value)))
        self.padding_label.config(text=f"{self.padding_var.get()} px")
        self.update_preview()

    def _on_tolerance_change(self, value):
        self.tolerance_var.set(int(float(value)))
        self.tolerance_label.config(text=str(self.tolerance_var.get()))
        self.update_preview()

    def set_status(self, text):
        self.status.config(text=text)
        self.root.update_idletasks()

    def load_image(self):
        path = filedialog.askopenfilename(
            title="Wybierz obraz",
            filetypes=[("Obrazy", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Wszystkie pliki", "*.*")]
        )
        if not path:
            return

        try:
            self.image = Image.open(path).convert("RGBA")
            self.current_path = path
            self.set_status(f"Wczytano: {os.path.basename(path)}")
            self.update_preview()
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się wczytać obrazu.\n\n{e}")

    def build_output_image(self, img):
        tolerance = self.tolerance_var.get()
        feather = self.feather_var.get()
        final_size = self.size_var.get()
        padding = self.padding_var.get()
        usable = max(1, final_size - padding * 2)

        processed = img.copy()
        if self.auto_crop_var.get():
            processed, _bg = remove_background_and_crop(processed, tolerance=tolerance, feather_alpha=feather)
        else:
            processed, _bg = remove_background_and_crop(processed, tolerance=tolerance, feather_alpha=feather)

        rendered = ImageOps.contain(processed, (usable, usable), method=Image.LANCZOS)

        if self.sharpen_var.get():
            rendered = rendered.filter(ImageFilter.SHARPEN)

        canvas = Image.new("RGBA", (final_size, final_size), (0, 0, 0, 0))
        x = (final_size - rendered.width) // 2
        y = (final_size - rendered.height) // 2
        canvas.alpha_composite(rendered, (x, y))
        return canvas

    def update_preview(self):
        if self.image is None:
            return

        self.processed_image = self.build_output_image(self.image)

        preview_size = 500
        preview = self.processed_image.copy().resize((preview_size, preview_size), Image.NEAREST)
        checker = self.make_checkerboard(preview_size, preview_size)
        checker.alpha_composite(preview)

        self.preview_image = ImageTk.PhotoImage(checker)
        self.preview_label.config(image=self.preview_image)

    def make_checkerboard(self, width, height, block=20):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
        px = img.load()
        c1 = (70, 70, 70, 255)
        c2 = (100, 100, 100, 255)
        for y in range(height):
            for x in range(width):
                px[x, y] = c1 if ((x // block) + (y // block)) % 2 == 0 else c2
        return img

    def save_image(self):
        if self.processed_image is None:
            messagebox.showwarning("Brak obrazu", "Najpierw wczytaj obraz.")
            return

        original_name = "render"
        if self.current_path:
            original_name = os.path.splitext(os.path.basename(self.current_path))[0]

        path = filedialog.asksaveasfilename(
            title="Zapisz PNG",
            defaultextension=".png",
            initialfile=f"{original_name}_cutout_{self.size_var.get()}x{self.size_var.get()}.png",
            filetypes=[("PNG", "*.png")]
        )
        if not path:
            return

        try:
            self.processed_image.save(path, "PNG")
            self.set_status(f"Zapisano: {path}")
            messagebox.showinfo("Sukces", "PNG zapisany poprawnie.")
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się zapisać pliku.\n\n{e}")

    def batch_render(self):
        input_dir = filedialog.askdirectory(title="Wybierz folder z obrazami")
        if not input_dir:
            return

        output_dir = filedialog.askdirectory(title="Wybierz folder zapisu")
        if not output_dir:
            return

        supported = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        files = [f for f in os.listdir(input_dir) if os.path.splitext(f)[1].lower() in supported]

        if not files:
            messagebox.showwarning("Brak plików", "W wybranym folderze nie ma obsługiwanych obrazów.")
            return

        done = 0
        for name in files:
            try:
                src = os.path.join(input_dir, name)
                img = Image.open(src).convert("RGBA")
                out = self.build_output_image(img)
                stem = os.path.splitext(name)[0]
                dst = os.path.join(output_dir, f"{stem}_cutout_{self.size_var.get()}x{self.size_var.get()}.png")
                out.save(dst, "PNG")
                done += 1
                self.set_status(f"Przetworzono {done}/{len(files)}")
            except Exception:
                pass

        self.set_status(f"Gotowe: {done}/{len(files)}")
        messagebox.showinfo("Gotowe", f"Zrobiono {done} renderów.")


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    RenderApp(root)
    root.mainloop()
