import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox


BG = "#f5f7fb"
CARD = "#ffffff"
BORDER = "#e5e7eb"
TEXT = "#111827"
MUTED = "#6b7280"
ACCENT = "#2563eb"
ACCENT_DARK = "#1d4ed8"
DISABLED = "#cbd5e1"

APP_VERSION = "1.0.0"


def human_size(num_bytes: float) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} ПБ"


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin() -> None:
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)


def env_path(*parts: str) -> str:
    return os.path.join(*[part for part in parts if part])


LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
WINDIR = os.environ.get("WINDIR", r"C:\Windows")


def build_categories():
    return [
        {
            "key": "user_temp",
            "title": "Временные файлы пользователя",
            "subtitle": "%TEMP%",
            "admin": False,
            "paths": [tempfile.gettempdir()],
        },
        {
            "key": "win_temp",
            "title": "Системные временные файлы",
            "subtitle": r"Windows\Temp",
            "admin": True,
            "paths": [env_path(WINDIR, "Temp")],
        },
        {
            "key": "prefetch",
            "title": "Кэш Prefetch",
            "subtitle": "Ускорительные данные запуска приложений",
            "admin": True,
            "paths": [env_path(WINDIR, "Prefetch")],
        },
        {
            "key": "win_update",
            "title": "Кэш обновлений Windows",
            "subtitle": "Скачанные временные файлы обновлений",
            "admin": True,
            "paths": [env_path(WINDIR, "SoftwareDistribution", "Download")],
        },
        {
            "key": "thumbnails",
            "title": "Кэш миниатюр",
            "subtitle": "Превью изображений и видео",
            "admin": False,
            "paths": [env_path(LOCALAPPDATA, "Microsoft", "Windows", "Explorer")],
            "only_ext": (".db",),
        },
        {
            "key": "crash_dumps",
            "title": "Отчёты об ошибках и дампы",
            "subtitle": "Логи падений приложений",
            "admin": False,
            "paths": [
                env_path(LOCALAPPDATA, "CrashDumps"),
                env_path(LOCALAPPDATA, "Microsoft", "Windows", "WER"),
            ],
        },
        {
            "key": "chrome",
            "title": "Кэш Google Chrome",
            "subtitle": "Закрой браузер перед очисткой для лучшего результата",
            "admin": False,
            "paths": [
                env_path(LOCALAPPDATA, "Google", "Chrome", "User Data", "Default", "Cache"),
                env_path(LOCALAPPDATA, "Google", "Chrome", "User Data", "Default", "Code Cache"),
            ],
        },
        {
            "key": "edge",
            "title": "Кэш Microsoft Edge",
            "subtitle": "Временные файлы браузера",
            "admin": False,
            "paths": [
                env_path(LOCALAPPDATA, "Microsoft", "Edge", "User Data", "Default", "Cache"),
                env_path(LOCALAPPDATA, "Microsoft", "Edge", "User Data", "Default", "Code Cache"),
            ],
        },
        {
            "key": "firefox",
            "title": "Кэш Mozilla Firefox",
            "subtitle": "Временные файлы профилей Firefox",
            "admin": False,
            "paths": [env_path(LOCALAPPDATA, "Mozilla", "Firefox", "Profiles")],
            "recursive_glob": "cache2",
        },
        {
            "key": "recycle_bin",
            "title": "Корзина",
            "subtitle": "Полная очистка корзины",
            "admin": False,
            "special": "recycle_bin",
        },
        {
            "key": "dns",
            "title": "Сброс кэша DNS",
            "subtitle": "Небольшая сетевая оптимизация",
            "admin": False,
            "special": "dns",
        },
    ]


def iter_targets(cat):
    targets = []
    for base in cat.get("paths", []):
        if not base or not os.path.exists(base):
            continue
        glob_name = cat.get("recursive_glob")
        if glob_name:
            for root, dirs, _ in os.walk(base):
                for dirname in dirs:
                    if dirname.lower() == glob_name.lower():
                        targets.append(os.path.join(root, dirname))
        else:
            targets.append(base)
    return targets


def folder_size(path, only_ext=None) -> int:
    total = 0
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    for root, _, files in os.walk(path):
        for filename in files:
            if only_ext and not filename.lower().endswith(only_ext):
                continue
            full_path = os.path.join(root, filename)
            try:
                total += os.path.getsize(full_path)
            except OSError:
                pass
    return total


def scan_category(cat) -> int:
    if cat.get("special") == "recycle_bin":
        return recycle_bin_size()
    if cat.get("special") == "dns":
        return 0
    return sum(folder_size(target, cat.get("only_ext")) for target in iter_targets(cat))


def clean_category(cat):
    if cat.get("special") == "recycle_bin":
        freed = recycle_bin_size()
        empty_recycle_bin()
        return freed, 1
    if cat.get("special") == "dns":
        flush_dns()
        return 0, 1

    freed = 0
    removed = 0
    only_ext = cat.get("only_ext")
    for target in iter_targets(cat):
        if os.path.isfile(target):
            size, count = remove_path(target, only_ext)
            freed += size
            removed += count
            continue
        try:
            entries = os.listdir(target)
        except OSError:
            continue
        for name in entries:
            size, count = remove_path(os.path.join(target, name), only_ext)
            freed += size
            removed += count
    return freed, removed


def remove_path(path, only_ext=None):
    try:
        if os.path.isfile(path) or os.path.islink(path):
            if only_ext and not path.lower().endswith(only_ext):
                return 0, 0
            size = os.path.getsize(path)
            os.chmod(path, 0o777)
            os.remove(path)
            return size, 1
        if os.path.isdir(path):
            if only_ext:
                freed = 0
                removed = 0
                for root, _, files in os.walk(path):
                    for filename in files:
                        if not filename.lower().endswith(only_ext):
                            continue
                        full_path = os.path.join(root, filename)
                        try:
                            freed += os.path.getsize(full_path)
                            os.remove(full_path)
                            removed += 1
                        except OSError:
                            pass
                return freed, removed
            size = folder_size(path)
            shutil.rmtree(path, ignore_errors=True)
            return (size, 1) if not os.path.exists(path) else (0, 0)
    except (OSError, PermissionError):
        pass
    return 0, 0


class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("i64Size", ctypes.c_longlong),
        ("i64NumItems", ctypes.c_longlong),
    ]


def recycle_bin_size() -> int:
    info = SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
    try:
        if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) == 0:
            return int(info.i64Size)
    except Exception:
        pass
    return 0


def empty_recycle_bin() -> None:
    flags = 0x00000001 | 0x00000002 | 0x00000004
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
    except Exception:
        pass


def flush_dns() -> None:
    try:
        subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass


class ToggleCard(tk.Frame):
    def __init__(self, master, cat, selected=True, disabled=False, command=None):
        super().__init__(master, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        self.cat = cat
        self.disabled = disabled
        self.command = command
        self.var = tk.BooleanVar(value=selected and not disabled)
        self.size_var = tk.StringVar(value="—")

        self.grid_columnconfigure(1, weight=1)
        self.canvas = tk.Canvas(self, width=24, height=24, bg=CARD, highlightthickness=0)
        self.canvas.grid(row=0, column=0, rowspan=2, padx=(14, 10), pady=12, sticky="n")

        title = cat["title"] + ("  · нужны права администратора" if disabled else "")
        self.title_label = tk.Label(
            self, text=title, bg=CARD, fg=TEXT if not disabled else MUTED,
            font=("Segoe UI", 10, "bold"), anchor="w",
        )
        self.title_label.grid(row=0, column=1, padx=0, pady=(10, 0), sticky="ew")

        self.subtitle_label = tk.Label(
            self, text=cat.get("subtitle", ""), bg=CARD, fg=MUTED,
            font=("Segoe UI", 9), anchor="w",
        )
        self.subtitle_label.grid(row=1, column=1, padx=0, pady=(1, 10), sticky="ew")

        self.size_label = tk.Label(
            self, textvariable=self.size_var, bg=CARD, fg=MUTED,
            font=("Segoe UI", 10), width=10, anchor="e",
        )
        self.size_label.grid(row=0, column=2, rowspan=2, padx=(8, 14), pady=12, sticky="e")

        for widget in (self, self.canvas, self.title_label, self.subtitle_label, self.size_label):
            widget.bind("<Button-1>", self.toggle)
            widget.bind("<Enter>", self.hover_on)
            widget.bind("<Leave>", self.hover_off)
        self.draw()

    def hover_on(self, _event=None):
        if not self.disabled:
            self.configure(highlightbackground="#bfdbfe")

    def hover_off(self, _event=None):
        self.configure(highlightbackground=BORDER)

    def toggle(self, _event=None):
        if self.disabled:
            return
        self.var.set(not self.var.get())
        self.draw()
        if self.command:
            self.command()

    def draw(self):
        self.canvas.delete("all")
        checked = self.var.get()
        fill = ACCENT if checked else CARD
        outline = ACCENT if checked else DISABLED
        self.canvas.create_rectangle(3, 3, 21, 21, width=2, outline=outline, fill=fill)
        if checked:
            self.canvas.create_line(7, 12, 11, 16, 18, 8, width=3, fill="white", capstyle="round")

    def set_size(self, value: str):
        self.size_var.set(value)


class CleanerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Junk Cleaner")
        self.geometry("760x720")
        self.minsize(680, 620)
        self.configure(bg=BG)

        self.categories = build_categories()
        self.cards = {}
        self.busy = False
        self.total_size = 0

        self.build_ui()
        self.after(250, self.scan)

    def build_ui(self):
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True, padx=24, pady=22)

        top = tk.Frame(root, bg=BG)
        top.pack(fill="x")

        tk.Label(top, text="Junk Cleaner", bg=BG, fg=TEXT,
                 font=("Segoe UI", 24, "bold")).pack(anchor="w")
        mode = "режим администратора" if is_admin() else "обычный режим"
        tk.Label(
            top,
            text=f"Аккуратная очистка временных файлов и кэшей · {mode}",
            bg=BG, fg=MUTED, font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 0))

        summary = tk.Frame(root, bg=ACCENT, highlightthickness=0)
        summary.pack(fill="x", pady=(18, 14))
        self.summary_title = tk.Label(
            summary, text="Сканирование...", bg=ACCENT, fg="white",
            font=("Segoe UI", 16, "bold"),
        )
        self.summary_title.pack(anchor="w", padx=18, pady=(14, 0))
        self.summary_text = tk.Label(
            summary, text="Проверяю безопасные места для очистки",
            bg=ACCENT, fg="#dbeafe", font=("Segoe UI", 10),
        )
        self.summary_text.pack(anchor="w", padx=18, pady=(2, 14))

        list_box = tk.Frame(root, bg=BG)
        list_box.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(list_box, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(
            list_box, orient="vertical", command=self.canvas.yview,
            bg=BG, troughcolor=BG, activebackground=DISABLED,
        )
        self.list_frame = tk.Frame(self.canvas, bg=BG)
        self.window_id = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scroll.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.list_frame.bind("<Configure>", self.update_scroll_region)
        self.canvas.bind("<Configure>", self.resize_inner)
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        admin_locked = not is_admin()
        for cat in self.categories:
            disabled = cat.get("admin", False) and admin_locked
            card = ToggleCard(self.list_frame, cat, selected=not disabled, disabled=disabled)
            card.pack(fill="x", padx=(0, 8), pady=5)
            self.cards[cat["key"]] = card

        bottom = tk.Frame(root, bg=BG)
        bottom.pack(fill="x", pady=(14, 0))

        self.status = tk.Label(
            bottom, text="Готово", bg=BG, fg=MUTED, font=("Segoe UI", 10), anchor="w",
        )
        self.status.pack(fill="x", pady=(0, 8))

        buttons = tk.Frame(bottom, bg=BG)
        buttons.pack(fill="x")
        self.scan_btn = self.make_button(buttons, "Сканировать", self.scan, secondary=True)
        self.scan_btn.pack(side="left")
        self.clean_btn = self.make_button(buttons, "Очистить выбранное", self.clean)
        self.clean_btn.pack(side="left", padx=10)

        if not is_admin():
            self.admin_btn = self.make_button(
                buttons, "Запустить как администратор", self.elevate, secondary=True,
            )
            self.admin_btn.pack(side="right")

    def make_button(self, master, text, command, secondary=False):
        fg = ACCENT if secondary else "white"
        bg = CARD if secondary else ACCENT
        active = "#eff6ff" if secondary else ACCENT_DARK
        return tk.Button(
            master, text=text, command=command, bg=bg, fg=fg,
            activebackground=active, activeforeground=fg if secondary else "white",
            relief="flat", bd=0, padx=18, pady=10, cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            highlightthickness=1,
            highlightbackground="#dbeafe" if secondary else ACCENT,
        )

    def update_scroll_region(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def resize_inner(self, event):
        self.canvas.itemconfig(self.window_id, width=event.width)

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def elevate(self):
        relaunch_as_admin()
        self.destroy()

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.scan_btn.configure(state=state)
        self.clean_btn.configure(state=state)

    def scan(self):
        if self.busy:
            return
        self.set_busy(True)
        self.summary_title.configure(text="Сканирование...")
        self.summary_text.configure(text="Ищу временные файлы, кэши и безопасный мусор")
        self.status.configure(text="Пожалуйста, подождите")
        threading.Thread(target=self.scan_worker, daemon=True).start()

    def scan_worker(self):
        total = 0
        for cat in self.categories:
            try:
                size = scan_category(cat)
            except Exception:
                size = 0
            total += size
            self.after(0, self.set_card_size, cat, size)
        self.after(0, self.scan_done, total)

    def set_card_size(self, cat, size):
        if cat.get("special") == "dns":
            value = "опция"
        else:
            value = human_size(size) if size else "пусто"
        self.cards[cat["key"]].set_size(value)

    def scan_done(self, total):
        self.total_size = total
        self.summary_title.configure(text=f"Можно освободить {human_size(total)}")
        self.summary_text.configure(text="Выбери категории и нажми очистку")
        self.status.configure(text="Сканирование завершено")
        self.set_busy(False)

    def clean(self):
        if self.busy:
            return
        selected = [cat for cat in self.categories if self.cards[cat["key"]].var.get()]
        if not selected:
            messagebox.showinfo("Нечего чистить", "Выберите хотя бы одну категорию.")
            return
        ok = messagebox.askyesno(
            "Подтверждение",
            "Удалить выбранные временные файлы и кэши?\n\n"
            "Системные файлы не затрагиваются.",
        )
        if not ok:
            return
        self.set_busy(True)
        self.summary_title.configure(text="Очистка...")
        self.summary_text.configure(text="Занятые файлы будут пропущены автоматически")
        threading.Thread(target=self.clean_worker, args=(selected,), daemon=True).start()

    def clean_worker(self, selected):
        freed_total = 0
        items_total = 0
        for cat in selected:
            self.after(0, self.status.configure, {"text": f"Очищаю: {cat['title']}"})
            try:
                freed, items = clean_category(cat)
            except Exception:
                freed, items = 0, 0
            freed_total += freed
            items_total += items
            self.after(0, self.set_card_size, cat, 0)
        self.after(0, self.clean_done, freed_total, items_total)

    def clean_done(self, freed, items):
        self.summary_title.configure(text=f"Освобождено {human_size(freed)}")
        self.summary_text.configure(text=f"Обработано элементов: {items}")
        self.status.configure(text="Очистка завершена")
        self.set_busy(False)
        messagebox.showinfo(
            "Готово",
            f"Освобождено: {human_size(freed)}\nОбработано элементов: {items}",
        )


def main():
    if os.name != "nt":
        print("Это приложение предназначено для Windows.")
        return
    app = CleanerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
