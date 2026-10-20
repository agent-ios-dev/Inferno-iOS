"""Native Windows device buttons for the local Inferno QMP endpoint.

Closing this panel leaves the VM running. No reset, restore or force-off action.
Mappings come from Inferno's hw/input/buttons.c, including the F2 ringer toggle.
"""
import queue
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import ttk

from qmp import execute
import device_lifecycle as lifecycle


BUTTONS = (
    ("Питание / экран", "f5", 100),
    ("Домой", "f6", 100),
    ("Громкость −", "f3", 100),
    ("Громкость +", "f4", 100),
    ("Без звука ↔ со звуком", "f2", 100),
    ("Удержать питание", "f5", 2500),
)


class Controls:
    def __init__(self, root):
        self.root = root
        self.worker = ThreadPoolExecutor(max_workers=1)
        self.results = queue.Queue()
        self.pending = False
        self.closed = False
        self.next_status = 0
        root.title("iPhone — управление QEMU")
        root.geometry(f"360x610+{max(0, root.winfo_screenwidth()-390)}+60")
        root.minsize(340, 590)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.on_top = tk.BooleanVar(value=True)
        root.attributes("-topmost", True)
        style = ttk.Style(root)
        style.configure("Device.TButton", font=("Segoe UI", 11), padding=(10, 11))
        body = ttk.Frame(root, padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure((0, 1), weight=1)
        ttk.Label(body, text="Управление устройством", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.buttons = []
        launch = ttk.Frame(body)
        launch.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        launch.columnconfigure((0, 1), weight=1)
        for label, operation, row, column, span in (
                ("Запустить iOS", lifecycle.start, 0, 0, 2),
                ("Остановить", lifecycle.stop, 1, 0, 1),
                ("Перезапустить", lifecycle.restart, 1, 1, 1)):
            button = ttk.Button(launch, text=label, style="Device.TButton",
                                command=lambda op=operation: self.control_vm(op))
            button.grid(row=row, column=column, columnspan=span, sticky="ew", padx=3, pady=4)
            self.buttons.append(button)
        ttk.Separator(body).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        for index, (label, code, hold) in enumerate(BUTTONS):
            button = ttk.Button(body, text=label, style="Device.TButton",
                                command=lambda l=label, c=code, h=hold: self.press(l, c, h))
            if index < 4:
                button.grid(row=3+index//2, column=index % 2, sticky="ew", padx=3, pady=4)
            else:
                button.grid(row=index+1, column=0, columnspan=2, sticky="ew", padx=3, pady=4)
            self.buttons.append(button)
        ttk.Checkbutton(body, text="Поверх других окон", variable=self.on_top,
                        command=lambda: root.attributes("-topmost", self.on_top.get())).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(12, 8))
        self.status = tk.StringVar(value="Подключение к QEMU…")
        ttk.Label(body, textvariable=self.status, wraplength=300).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(body, text="Закрытие панели не выключает iOS.", wraplength=300).grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(10, 0))
        root.after(100, self.tick)

    def submit(self, kind, task):
        self.pending = True
        for button in self.buttons:
            button.state(["disabled"])
        def run():
            try:
                self.results.put((kind, task(), None))
            except Exception as error:
                self.results.put((kind, None, str(error)))
        self.worker.submit(run)

    def press(self, label, code, hold):
        if self.pending:
            return
        self.status.set(f"Нажатие: {label}…")
        def send():
            execute("send-key", {"keys": [{"type": "qcode", "data": code}], "hold-time": hold})
            time.sleep(hold / 1000 + .1)
            return label
        self.submit("button", send)

    def control_vm(self, operation):
        if self.pending:
            return
        self.status.set("Выполняю команду…")
        self.submit("lifecycle", lambda: operation(
            lambda text: self.results.put(("progress", text, None))))

    def tick(self):
        if self.closed:
            return
        try:
            kind, value, error = self.results.get_nowait()
            if kind == "progress":
                self.status.set(value)
                self.root.after(100, self.tick)
                return
            self.pending = False
            if error:
                self.status.set(error if kind == "lifecycle" else "Нет подключения. Нажми «Запустить iOS».")
            elif kind == "button":
                self.status.set(f"Команда отправлена: {value}")
            else:
                self.status.set({"running": "QEMU запущен. iOS может ещё загружаться.",
                                 "paused": "QEMU на паузе. «Запустить iOS» продолжит работу.",
                                 "stopped": "Эмулятор остановлен. Диски сохранены.",
                                 "offline": "Docker выключен. Нажми «Запустить iOS»."}.get(value, "Состояние неизвестно"))
            for button in self.buttons:
                button.state(["!disabled"])
            self.next_status = time.monotonic() + (4 if kind == "button" else 3)
        except queue.Empty:
            pass
        if not self.pending and time.monotonic() >= self.next_status:
            self.submit("status", lifecycle.state)
        self.root.after(100, self.tick)

    def close(self):
        self.closed = True
        self.worker.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    Controls(window)
    window.mainloop()
