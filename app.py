import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageOps, ImageFilter

APP_TITLE = "OX Image Render Tool"
APP_VERSION = "1.0.0"


class RenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_TITLE} {APP_VERSION}")
        self.root.geometry("1080x760")
        self.root.minsize(980, 700)

        self.image = None
        self.preview_image = None
        self.output_image = None
        self.current_path = None

        self.size_var = tk.IntVar(value=100)
        self.padding_var = tk.IntVar(value=6)
        self.bg_var = tk.StringVar(value="transparent")
        self.sharpen_var = tk.BooleanVar(value=True)
        self.contain_var = tk.BooleanVar(value=True)

        self.build_ui()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="y", padx=(0, 12))

        right = ttk.Frame(main)
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(left, text="OX Inventory Render Tool", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))

        ttk.Button(left, text="Wczytaj obraz", command=self.load_image).pack(fill="x", pady=4)
        ttk.Button(left, text="Zapisz render", command=self.save_image).pack(fill="x", pady=4)
        ttk.Button(left, text="Batch render folderu", command=self.batch_render).pack(fill="x", pady=4)

        ttk.Separator(left).pack(fill="x", pady=10)

        ttk.Label(left, text="Rozmiar końcowy (px)").pack(anchor="w")
        size_box = ttk.Combobox(left, textvariable=self.size_var, values=[64, 100, 128, 256, 512], state="readonly")
        size_box.pack(fill="x", pady=(4, 8))
        size_box.bind("<<ComboboxSelected>>", lambda e: self.update_preview())

        ttk.Label(left, text="Padding").pack(anchor="w")
        padding_scale = ttk.Scale(left, from_=0, to=40, orient="horizontal", command=self._on_padding_change)
        padding_scale.set(self.padding_var.get())
        padding_scale.pack(fill="x", pady=(4, 2))

        self.padding_label = ttk.Label(left, text=f"{self.padding_var.get()} px")
        self.padding_label.pack(anchor="w", pady=(0, 8))

        ttk.Label(left, text="Tło").pack(anchor="w")
        bg_box = ttk.Combobox(left, textvariable=self.bg_var, values=["transparent", "white", "black"], state="readonly")
        bg_box.pack(fill="x", pady=(4, 8))
        bg_box.bind("<<ComboboxSelected>>", lambda e: self.update_preview())

        ttk.Checkbutton(left, text="Wyostrz obraz", variable=self.sharpen_var, command=self.update_preview).pack(anchor="w", pady=4)
        ttk.Checkbutton(left, text="Dopasuj bez ucinania", variable=self.contain_var, command=self.update_preview).pack(anchor="w", pady=4)

        ttk.Separator(left).pack(fill="x", pady=10)

        info = (
            "Program do robienia renderów PNG pod OX Inventory.\n\n"
            "Funkcje:\n"
            "- pojedynczy render\n"
            "- batch render całego folderu\n"
            "- przezroczyste tło\n"
            "- automatyczne centrowanie\n"
            "- eksport do PNG"
        )
        ttk.Label(left, text=info, justify="left").pack(anchor="w", pady=4)

        ttk.Label(right, text="Podgląd renderu", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))

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

    def set_status(self, text):
        self.status.config(text=text)
        self.root.update_idletasks()

    def load_image(self):
        path = filedialog.askopenfilename(
            title="Wybierz obraz",
            filetypes=[
                ("Obrazy", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("Wszystkie pliki", "*.*")
            ]
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

    def render_image(self, img):
        final_size = self.size_var.get()
        padding = self.padding_var.get()
        usable = max(1, final_size - padding * 2)

        if self.contain_var.get():
            rendered = ImageOps.contain(img, (usable, usable), method=Image.LANCZOS)
        else:
            rendered = ImageOps.fit(img, (usable, usable), method=Image.LANCZOS)

        if self.sharpen_var.get():
            rendered = rendered.filter(ImageFilter.SHARPEN)

        bg_mode = self.bg_var.get()
        if bg_mode == "transparent":
            canvas = Image.new("RGBA", (final_size, final_size), (0, 0, 0, 0))
        elif bg_mode == "white":
            canvas = Image.new("RGBA", (final_size, final_size), (255, 255, 255, 255))
        else:
            canvas = Image.new("RGBA", (final_size, final_size), (0, 0, 0, 255))

        x = (final_size - rendered.width) // 2
        y = (final_size - rendered.height) // 2
        canvas.alpha_composite(rendered, (x, y))
        return canvas

    def update_preview(self):
        if self.image is None:
            return

        self.output_image = self.render_image(self.image)
        preview_size = 480
        preview = self.output_image.copy().resize((preview_size, preview_size), Image.NEAREST)

        checker = self.make_checkerboard(preview_size, preview_size)
        checker.alpha_composite(preview)

        self.preview_image = ImageTk.PhotoImage(checker)
        self.preview_label.configure(image=self.preview_image)

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
        if self.output_image is None:
            messagebox.showwarning("Brak obrazu", "Najpierw wczytaj obraz.")
            return

        original_name = "render"
        if self.current_path:
            original_name = os.path.splitext(os.path.basename(self.current_path))[0]

        path = filedialog.asksaveasfilename(
            title="Zapisz render",
            defaultextension=".png",
            initialfile=f"{original_name}_{self.size_var.get()}x{self.size_var.get()}.png",
            filetypes=[("PNG", "*.png")]
        )
        if not path:
            return

        try:
            self.output_image.save(path, "PNG")
            self.set_status(f"Zapisano: {path}")
            messagebox.showinfo("Sukces", "Render zapisany poprawnie.")
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się zapisać pliku.\n\n{e}")

    def batch_render(self):
        input_dir = filedialog.askdirectory(title="Wybierz folder z obrazami")
        if not input_dir:
            return

        output_dir = filedialog.askdirectory(title="Wybierz folder zapisu renderów")
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
                out = self.render_image(img)
                stem = os.path.splitext(name)[0]
                dst = os.path.join(output_dir, f"{stem}_{self.size_var.get()}x{self.size_var.get()}.png")
                out.save(dst, "PNG")
                done += 1
                self.set_status(f"Przetworzono {done}/{len(files)}")
            except Exception:
                pass

        self.set_status(f"Batch render zakończony. Gotowe: {done}/{len(files)}")
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
