import io
import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import requests
from PIL import Image, ImageTk, ImageFilter, ImageOps

APP_TITLE = "OX RemoveBG Tool"
APP_VERSION = "1.1.0"
CONFIG_PATH = Path("config.json")


def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {"api_key": ""}


def save_config(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def crop_transparent(img):
    bbox = img.getbbox()
    if bbox:
        return img.crop(bbox)
    return img


def fit_to_canvas(img, final_size=100, padding=4, sharpen=True):
    usable = max(1, final_size - padding * 2)
    contained = ImageOps.contain(img, (usable, usable), method=Image.LANCZOS)
    if sharpen:
        contained = contained.filter(ImageFilter.SHARPEN)

    canvas = Image.new("RGBA", (final_size, final_size), (0, 0, 0, 0))
    x = (final_size - contained.width) // 2
    y = (final_size - contained.height) // 2
    canvas.alpha_composite(contained, (x, y))
    return canvas


def checkerboard(width, height, block=20):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    px = img.load()
    c1 = (70, 70, 70, 255)
    c2 = (100, 100, 100, 255)
    for y in range(height):
        for x in range(width):
            px[x, y] = c1 if ((x // block) + (y // block)) % 2 == 0 else c2
    return img


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_TITLE} {APP_VERSION}")
        self.root.geometry("1120x780")
        self.root.minsize(1000, 720)

        self.config = load_config()
        self.current_path = None
        self.original_image = None
        self.removed_bg_image = None
        self.final_image = None
        self.preview_image = None

        self.api_key_var = tk.StringVar(value=self.config.get("api_key", ""))
        self.size_var = tk.IntVar(value=100)
        self.padding_var = tk.IntVar(value=4)
        self.crop_var = tk.BooleanVar(value=True)
        self.sharpen_var = tk.BooleanVar(value=True)

        self.build_ui()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="y", padx=(0, 12))

        right = ttk.Frame(main)
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(left, text="OX RemoveBG Tool", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))

        ttk.Label(left, text="API key remove.bg").pack(anchor="w")
        ttk.Entry(left, textvariable=self.api_key_var, show="*", width=38).pack(fill="x", pady=(4, 8))
        ttk.Button(left, text="Zapisz klucz do config.json", command=self.save_api_key).pack(fill="x", pady=4)

        ttk.Separator(left).pack(fill="x", pady=10)

        ttk.Button(left, text="Wczytaj obraz", command=self.load_image).pack(fill="x", pady=4)
        ttk.Button(left, text="Usuń tło przez remove.bg", command=self.remove_background).pack(fill="x", pady=4)
        ttk.Button(left, text="Zapisz finalny PNG", command=self.save_image).pack(fill="x", pady=4)
        ttk.Button(left, text="Batch render folderu", command=self.batch_render).pack(fill="x", pady=4)

        ttk.Separator(left).pack(fill="x", pady=10)

        ttk.Label(left, text="Rozmiar końcowy (px)").pack(anchor="w")
        size_box = ttk.Combobox(left, textvariable=self.size_var, values=[64, 100, 128, 256, 512], state="readonly")
        size_box.pack(fill="x", pady=(4, 8))
        size_box.bind("<<ComboboxSelected>>", lambda e: self.rebuild_final())

        ttk.Label(left, text="Padding").pack(anchor="w")
        pad = ttk.Scale(left, from_=0, to=20, orient="horizontal", command=self._on_padding)
        pad.set(self.padding_var.get())
        pad.pack(fill="x", pady=(4, 2))
        self.pad_label = ttk.Label(left, text=f"{self.padding_var.get()} px")
        self.pad_label.pack(anchor="w", pady=(0, 8))

        ttk.Checkbutton(left, text="Przytnij puste brzegi", variable=self.crop_var, command=self.rebuild_final).pack(anchor="w", pady=4)
        ttk.Checkbutton(left, text="Wyostrz", variable=self.sharpen_var, command=self.rebuild_final).pack(anchor="w", pady=4)

        ttk.Separator(left).pack(fill="x", pady=10)

        info = (
            "Program zapisuje klucz API lokalnie w config.json.\n\n"
            "Workflow:\n"
            "1. Wpisz klucz API\n"
            "2. Zapisz go do config.json\n"
            "3. Wczytaj obraz\n"
            "4. Usuń tło przez remove.bg\n"
            "5. Zapisz PNG pod OX Inventory"
        )
        ttk.Label(left, text=info, justify="left").pack(anchor="w", pady=4)

        ttk.Label(right, text="Podgląd", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))
        self.preview_frame = tk.Frame(right, bg="#1e1e1e", bd=1, relief="solid")
        self.preview_frame.pack(fill="both", expand=True)
        self.preview_label = tk.Label(self.preview_frame, bg="#1e1e1e")
        self.preview_label.pack(expand=True)

        self.status = ttk.Label(self.root, text="Gotowe")
        self.status.pack(fill="x", padx=12, pady=(0, 10))

    def _on_padding(self, value):
        self.padding_var.set(int(float(value)))
        self.pad_label.config(text=f"{self.padding_var.get()} px")
        self.rebuild_final()

    def set_status(self, text):
        self.status.config(text=text)
        self.root.update_idletasks()

    def save_api_key(self):
        api_key = self.api_key_var.get().strip()
        self.config["api_key"] = api_key
        save_config(self.config)
        messagebox.showinfo("OK", "Klucz zapisany do config.json")

    def load_image(self):
        path = filedialog.askopenfilename(
            title="Wybierz obraz",
            filetypes=[("Obrazy", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Wszystkie pliki", "*.*")]
        )
        if not path:
            return
        try:
            self.current_path = path
            self.original_image = Image.open(path).convert("RGBA")
            self.removed_bg_image = None
            self.final_image = None
            self.set_status(f"Wczytano: {os.path.basename(path)}")
            self.show_preview(self.original_image)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się wczytać obrazu.\n\n{e}")

    def call_removebg(self, path):
        api_key = self.api_key_var.get().strip() or self.config.get("api_key", "").strip()
        if not api_key:
            raise RuntimeError("Brak API key remove.bg")

        with open(path, "rb") as f:
            response = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                files={"image_file": f},
                data={"size": "auto", "format": "png", "crop": "false"},
                headers={"X-Api-Key": api_key},
                timeout=120
            )

        if response.status_code != 200:
            try:
                details = response.json()
            except Exception:
                details = response.text
            raise RuntimeError(f"remove.bg error {response.status_code}: {details}")

        return Image.open(io.BytesIO(response.content)).convert("RGBA")

    def remove_background(self):
        if not self.current_path:
            messagebox.showwarning("Brak obrazu", "Najpierw wczytaj obraz.")
            return

        try:
            self.set_status("Wysyłanie obrazu do remove.bg...")
            self.removed_bg_image = self.call_removebg(self.current_path)
            self.set_status("Tło usunięte. Składam finalny PNG...")
            self.rebuild_final()
        except Exception as e:
            self.set_status("Błąd")
            messagebox.showerror("Błąd API", str(e))

    def rebuild_final(self):
        if self.removed_bg_image is None:
            return

        img = self.removed_bg_image.copy()
        if self.crop_var.get():
            img = crop_transparent(img)

        self.final_image = fit_to_canvas(
            img,
            final_size=self.size_var.get(),
            padding=self.padding_var.get(),
            sharpen=self.sharpen_var.get()
        )
        self.show_preview(self.final_image)
        self.set_status("Gotowe")

    def show_preview(self, img):
        preview_size = 520
        base = checkerboard(preview_size, preview_size)
        scaled = img.copy().resize((preview_size, preview_size), Image.NEAREST)
        base.alpha_composite(scaled)
        self.preview_image = ImageTk.PhotoImage(base)
        self.preview_label.configure(image=self.preview_image)

    def save_image(self):
        if self.final_image is None:
            messagebox.showwarning("Brak renderu", "Najpierw usuń tło.")
            return

        original_name = "render"
        if self.current_path:
            original_name = Path(self.current_path).stem

        path = filedialog.asksaveasfilename(
            title="Zapisz PNG",
            defaultextension=".png",
            initialfile=f"{original_name}_{self.size_var.get()}x{self.size_var.get()}.png",
            filetypes=[("PNG", "*.png")]
        )
        if not path:
            return

        try:
            self.final_image.save(path, "PNG")
            self.set_status(f"Zapisano: {path}")
            messagebox.showinfo("Sukces", "PNG zapisany poprawnie.")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def batch_render(self):
        input_dir = filedialog.askdirectory(title="Wybierz folder z obrazami")
        if not input_dir:
            return
        output_dir = filedialog.askdirectory(title="Wybierz folder zapisu")
        if not output_dir:
            return

        supported = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        files = [f for f in os.listdir(input_dir) if Path(f).suffix.lower() in supported]
        if not files:
            messagebox.showwarning("Brak plików", "W folderze nie ma obsługiwanych obrazów.")
            return

        done = 0
        failed = 0

        for name in files:
            src = os.path.join(input_dir, name)
            try:
                removed = self.call_removebg(src)
                if self.crop_var.get():
                    removed = crop_transparent(removed)
                final = fit_to_canvas(
                    removed,
                    final_size=self.size_var.get(),
                    padding=self.padding_var.get(),
                    sharpen=self.sharpen_var.get()
                )
                dst = os.path.join(output_dir, f"{Path(name).stem}_{self.size_var.get()}x{self.size_var.get()}.png")
                final.save(dst, "PNG")
                done += 1
            except Exception:
                failed += 1
            self.set_status(f"Przetworzono {done + failed}/{len(files)}")

        self.set_status(f"Gotowe. OK: {done}, błędy: {failed}")
        messagebox.showinfo("Batch zakończony", f"OK: {done}\nBłędy: {failed}")


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()
