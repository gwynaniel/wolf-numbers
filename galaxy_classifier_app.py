import csv
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk

from astroquery.simbad import Simbad


APP_TITLE = "Galaxy Classifier"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base_path) / relative_path


def extract_archive_if_needed(path, log):
    source = Path(path)

    if source.is_dir():
        return source

    if source.suffix.lower() == ".zip":
        extract_dir = source.with_suffix("")
        extract_dir.mkdir(exist_ok=True)
        log(f"Розпаковую архів: {source.name}")

        with zipfile.ZipFile(source, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        return extract_dir

    raise ValueError("Потрібно вибрати папку із зображеннями або .zip архів.")


def get_galaxy_name(filename):
    name = Path(filename).stem.upper()
    name = re.sub(r"^\d+[_\-\s]*", "", name)
    match = re.search(r"\b(NGC|IC|M)[_\-\s]*(\d+)\b", name)

    if not match:
        return None

    return f"{match.group(1)} {match.group(2)}"


def safe_folder_name(text):
    text = str(text).strip()
    for old, new in {
        "/": "-",
        "\\": "-",
        ":": "-",
        "*": "",
        "?": "",
        '"': "",
        "<": "",
        ">": "",
        "|": "",
    }.items():
        text = text.replace(old, new)
    return text or "Unknown"


def explain_type(morph_type):
    if morph_type is None:
        return "Невідомий тип"

    text = str(morph_type).strip()

    if text in ["", "--", "None"]:
        return "Невідомий тип"

    upper = text.upper()

    if upper.startswith("E"):
        return "Еліптична галактика"
    if "S0" in upper:
        return "Лінзоподібна галактика"
    if upper.startswith("SB"):
        return "Спіральна галактика з баром"
    if upper.startswith("SAB"):
        return "Перехідна спіральна галактика, слабкий бар"
    if upper.startswith("SA"):
        return "Спіральна галактика без бара"
    if "IRR" in upper or "IM" in upper:
        return "Неправильна галактика"
    if upper.startswith("S"):
        return "Спіральна галактика"

    return "Інший або змішаний морфологічний тип"


class MorphologyClient:
    def __init__(self):
        self._client = Simbad()
        self._client.add_votable_fields("otype", "morphtype")

    def query(self, name):
        try:
            result = self._client.query_object(name)

            if result is None:
                return None

            for column in ["morph_type", "MORPHTYPE", "Morph_type"]:
                if column in result.colnames:
                    value = result[column][0]
                    if value is not None and str(value).strip() not in ["", "--", "None"]:
                        return str(value).strip()

            return None
        except Exception:
            return None


def classify_images(input_path, output_path, progress, log, row_found):
    source_dir = extract_archive_if_needed(input_path, log)
    output_dir = Path(output_path)
    output_dir.mkdir(exist_ok=True)

    files = [
        file for file in source_dir.rglob("*")
        if file.suffix.lower() in IMAGE_EXTENSIONS
    ]

    if not files:
        raise ValueError("У вибраному місці не знайдено зображень .jpg, .jpeg, .png або .webp.")

    client = MorphologyClient()
    report = []
    total = len(files)

    log(f"Знайдено зображень: {total}")

    for index, file in enumerate(files, start=1):
        galaxy_name = get_galaxy_name(file.name)

        if galaxy_name:
            morph = client.query(galaxy_name)
            log(f"{index}/{total}: {file.name} -> {galaxy_name} -> {morph or 'Unknown'}")
        else:
            morph = None
            log(f"{index}/{total}: {file.name} -> назву галактики не розпізнано")

        folder = safe_folder_name(morph) if morph else "Unknown"
        description = explain_type(morph)
        target_folder = output_dir / folder
        target_folder.mkdir(exist_ok=True)
        shutil.copy2(file, target_folder / file.name)

        row = {
            "file": file.name,
            "galaxy_name": galaxy_name or "",
            "morphology": morph or "",
            "folder": folder,
            "description": description,
        }
        report.append(row)
        row_found(row)
        progress(index, total)

    report_path = output_dir / "classification_report.csv"
    with open(report_path, "w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["file", "galaxy_name", "morphology", "folder", "description"],
        )
        writer.writeheader()
        writer.writerows(report)

    log(f"Готово. Звіт збережено: {report_path}")
    return report_path


class GalaxyClassifierApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1060x720")
        self.minsize(920, 620)
        self.configure(bg="#111827")

        self.events = queue.Queue()
        self.worker = None
        self.output_path = tk.StringVar(value=str(Path.cwd() / "classified_galaxies"))
        self.input_path = tk.StringVar(value=str(Path.cwd() / "images"))
        self.status = tk.StringVar(value="Готово до класифікації")
        self.progress_text = tk.StringVar(value="0 / 0")

        self._setup_styles()
        self._build_ui()
        self.after(100, self._process_events)

    def _setup_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("Root.TFrame", background="#111827")
        self.style.configure("Panel.TFrame", background="#172033")
        self.style.configure("Soft.TFrame", background="#1f2937")
        self.style.configure("Title.TLabel", background="#111827", foreground="#f8fafc", font=("Segoe UI", 25, "bold"))
        self.style.configure("Subtitle.TLabel", background="#111827", foreground="#cbd5e1", font=("Segoe UI", 10))
        self.style.configure("Label.TLabel", background="#172033", foreground="#e5e7eb", font=("Segoe UI", 10, "bold"))
        self.style.configure("Muted.TLabel", background="#172033", foreground="#94a3b8", font=("Segoe UI", 9))
        self.style.configure("Status.TLabel", background="#111827", foreground="#cbd5e1", font=("Segoe UI", 10))
        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8), foreground="#07111f", background="#38bdf8")
        self.style.map("Accent.TButton", background=[("active", "#7dd3fc"), ("disabled", "#475569")])
        self.style.configure("Tool.TButton", font=("Segoe UI", 10), padding=(12, 7), foreground="#e5e7eb", background="#334155")
        self.style.map("Tool.TButton", background=[("active", "#475569")])
        self.style.configure("TEntry", fieldbackground="#0f172a", foreground="#f8fafc", insertcolor="#f8fafc", bordercolor="#334155", padding=8)
        self.style.configure("TProgressbar", troughcolor="#0f172a", background="#22c55e", bordercolor="#0f172a", lightcolor="#22c55e", darkcolor="#22c55e")
        self.style.configure("Treeview", background="#0f172a", fieldbackground="#0f172a", foreground="#e5e7eb", rowheight=28, borderwidth=0)
        self.style.configure("Treeview.Heading", background="#243244", foreground="#f8fafc", font=("Segoe UI", 9, "bold"))
        self.style.map("Treeview", background=[("selected", "#0369a1")])

    def _build_ui(self):
        root = ttk.Frame(self, style="Root.TFrame", padding=22)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, style="Root.TFrame")
        header.pack(fill="x")

        title_block = ttk.Frame(header, style="Root.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text="Galaxy Classifier", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_block,
            text="Класифікація зображень галактик за морфологічним типом SIMBAD",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        self.start_button = ttk.Button(header, text="Почати", style="Accent.TButton", command=self.start_classification)
        self.start_button.pack(side="right", padx=(12, 0))
        ttk.Button(header, text="Відкрити результат", style="Tool.TButton", command=self.open_output).pack(side="right")

        body = ttk.Frame(root, style="Root.TFrame")
        body.pack(fill="both", expand=True, pady=(20, 0))
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(1, weight=1)

        settings = ttk.Frame(body, style="Panel.TFrame", padding=16)
        settings.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="Зображення або ZIP", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
        ttk.Entry(settings, textvariable=self.input_path).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(settings, text="Папка", style="Tool.TButton", command=self.pick_input_folder).grid(row=0, column=2, padx=(10, 4), pady=6)
        ttk.Button(settings, text="ZIP", style="Tool.TButton", command=self.pick_input_zip).grid(row=0, column=3, pady=6)

        ttk.Label(settings, text="Папка результатів", style="Label.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=6)
        ttk.Entry(settings, textvariable=self.output_path).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(settings, text="Обрати", style="Tool.TButton", command=self.pick_output_folder).grid(row=1, column=2, columnspan=2, sticky="ew", padx=(10, 0), pady=6)

        results_panel = ttk.Frame(body, style="Panel.TFrame", padding=14)
        results_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        results_panel.rowconfigure(1, weight=1)
        results_panel.columnconfigure(0, weight=1)

        ttk.Label(results_panel, text="Результати", style="Label.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))

        columns = ("file", "name", "morph", "description")
        self.table = ttk.Treeview(results_panel, columns=columns, show="headings")
        self.table.heading("file", text="Файл")
        self.table.heading("name", text="Галактика")
        self.table.heading("morph", text="Тип")
        self.table.heading("description", text="Опис")
        self.table.column("file", width=180, minwidth=140)
        self.table.column("name", width=110, minwidth=90)
        self.table.column("morph", width=120, minwidth=80)
        self.table.column("description", width=270, minwidth=190)
        self.table.grid(row=1, column=0, sticky="nsew")

        table_scroll = ttk.Scrollbar(results_panel, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=table_scroll.set)
        table_scroll.grid(row=1, column=1, sticky="ns")

        side = ttk.Frame(body, style="Panel.TFrame", padding=14)
        side.grid(row=1, column=1, sticky="nsew")
        side.rowconfigure(3, weight=1)
        side.columnconfigure(0, weight=1)

        ttk.Label(side, text="Стан", style="Label.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(side, textvariable=self.status, style="Muted.TLabel", wraplength=340).grid(row=1, column=0, sticky="ew", pady=(4, 10))

        progress_line = ttk.Frame(side, style="Panel.TFrame")
        progress_line.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        progress_line.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(progress_line, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="ew")
        ttk.Label(progress_line, textvariable=self.progress_text, style="Muted.TLabel").grid(row=0, column=1, padx=(10, 0))

        log_frame = ttk.Frame(side, style="Soft.TFrame", padding=10)
        log_frame.grid(row=3, column=0, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_box = tk.Text(
            log_frame,
            bg="#0b1220",
            fg="#dbeafe",
            insertbackground="#dbeafe",
            relief="flat",
            wrap="word",
            font=("Consolas", 9),
            padx=10,
            pady=10,
        )
        self.log_box.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=log_scroll.set)
        log_scroll.grid(row=0, column=1, sticky="ns")

        footer = ttk.Frame(root, style="Root.TFrame")
        footer.pack(fill="x", pady=(12, 0))
        ttk.Label(footer, textvariable=self.status, style="Status.TLabel").pack(side="left")

    def pick_input_folder(self):
        value = filedialog.askdirectory(title="Оберіть папку із зображеннями")
        if value:
            self.input_path.set(value)

    def pick_input_zip(self):
        value = filedialog.askopenfilename(title="Оберіть ZIP архів", filetypes=[("ZIP archives", "*.zip")])
        if value:
            self.input_path.set(value)

    def pick_output_folder(self):
        value = filedialog.askdirectory(title="Оберіть папку для результатів")
        if value:
            self.output_path.set(value)

    def start_classification(self):
        if self.worker and self.worker.is_alive():
            return

        input_path = self.input_path.get().strip()
        output_path = self.output_path.get().strip()

        if not input_path or not Path(input_path).exists():
            messagebox.showerror(APP_TITLE, "Вкажіть наявну папку або ZIP архів із зображеннями.")
            return

        if not output_path:
            messagebox.showerror(APP_TITLE, "Вкажіть папку для результатів.")
            return

        for item in self.table.get_children():
            self.table.delete(item)

        self.log_box.delete("1.0", "end")
        self.progress.configure(value=0)
        self.progress_text.set("0 / 0")
        self.status.set("Класифікація виконується...")
        self.start_button.configure(state="disabled")

        self.worker = threading.Thread(
            target=self._worker_run,
            args=(input_path, output_path),
            daemon=True,
        )
        self.worker.start()

    def _worker_run(self, input_path, output_path):
        try:
            report_path = classify_images(
                input_path,
                output_path,
                lambda current, total: self.events.put(("progress", current, total)),
                lambda text: self.events.put(("log", text)),
                lambda row: self.events.put(("row", row)),
            )
            self.events.put(("done", str(report_path)))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _process_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]

                if kind == "log":
                    self.log_box.insert("end", event[1] + "\n")
                    self.log_box.see("end")
                elif kind == "row":
                    row = event[1]
                    self.table.insert(
                        "",
                        "end",
                        values=(row["file"], row["galaxy_name"], row["morphology"], row["description"]),
                    )
                elif kind == "progress":
                    current, total = event[1], event[2]
                    self.progress.configure(value=(current / total) * 100)
                    self.progress_text.set(f"{current} / {total}")
                elif kind == "done":
                    self.status.set(f"Готово: {event[1]}")
                    self.start_button.configure(state="normal")
                    messagebox.showinfo(APP_TITLE, "Класифікацію завершено.")
                elif kind == "error":
                    self.status.set("Помилка")
                    self.start_button.configure(state="normal")
                    messagebox.showerror(APP_TITLE, event[1])
        except queue.Empty:
            pass

        self.after(100, self._process_events)

    def open_output(self):
        path = Path(self.output_path.get().strip())
        path.mkdir(exist_ok=True)

        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Не вдалося відкрити папку: {exc}")


if __name__ == "__main__":
    app = GalaxyClassifierApp()
    app.mainloop()
