"""Tkinter window: enter settings, start/stop syncs, watch what is downloading."""

from __future__ import annotations

import queue
import threading
import webbrowser
from datetime import datetime
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from . import __version__
from .config import DEFAULT_ARCHIVE, USER_ENV_FILE, Settings, read_env_file, write_env_file
from .daemon import next_run, parse_hhmm
from .donate import DONATE_URL
from .progress import Progress
from .sync import sync

MAX_LOG_LINES = 2000
HELP = (
    "Cookies: log in to x.com in your browser, export the cookies as a Netscape "
    "'cookies.txt' (browser extension \"Get cookies.txt\") and select the file here."
)


class App:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title(f"tiny-x-downloader {__version__}")
        root.minsize(720, 560)
        ttk.Style().theme_use("clam")

        saved = read_env_file(USER_ENV_FILE)
        self.v_cookies = StringVar(value=saved.get("X_COOKIES", ""))
        self.v_output = StringVar(value=saved.get("TINY_X_DOWNLOADER_OUTPUT_DIR", "~/Downloads/tiny-x-downloader"))
        self.v_archive = StringVar(value=saved.get("TINY_X_DOWNLOADER_ARCHIVE", DEFAULT_ARCHIVE))
        self.v_time = StringVar(value=saved.get("X_SYNC_TIME", "04:00"))
        self.v_daily = BooleanVar(value=saved.get("X_GUI_DAILY", "0") == "1")
        self.v_full = BooleanVar(value=False)
        self.v_status = StringVar(value="Idle")
        self.v_file = StringVar(value="")
        self.v_last = StringVar(value="Last run: never")
        self.v_next = StringVar(value="")

        self.progress = Progress()
        self.lines: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel = threading.Event()
        self.worker: threading.Thread | None = None
        self.next_target: datetime | None = None

        self._build()
        self._reschedule()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(150, self._tick)

    # ---- layout -------------------------------------------------------
    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        box = ttk.LabelFrame(outer, text="Settings", padding=8)
        box.pack(fill="x")
        box.columnconfigure(1, weight=1)
        rows = [
            ("Cookies file", self.v_cookies, self._pick_cookies),
            ("Download folder", self.v_output, self._pick_output),
            ("Archive file", self.v_archive, self._pick_archive),
        ]
        for i, (label, var, browse) in enumerate(rows):
            ttk.Label(box, text=label).grid(row=i, column=0, sticky="w", **pad)
            ttk.Entry(box, textvariable=var).grid(row=i, column=1, sticky="ew", **pad)
            if browse:
                ttk.Button(box, text="Browse...", command=browse).grid(row=i, column=2, **pad)
        ttk.Label(box, text="The archive remembers downloaded posts. Keep it, even if you "
                  "move the downloaded files.", foreground="#555").grid(
            row=4, column=1, columnspan=2, sticky="w", padx=8)

        daily = ttk.Frame(box)
        daily.grid(row=5, column=0, columnspan=3, sticky="w", **pad)
        ttk.Checkbutton(daily, text="Sync automatically every day at", variable=self.v_daily,
                        command=self._reschedule).pack(side="left")
        ttk.Entry(daily, textvariable=self.v_time, width=6).pack(side="left", padx=4)
        ttk.Label(daily, text="(only while this window is open)").pack(side="left")
        ttk.Button(box, text="Save settings", command=self._save).grid(row=5, column=2, **pad)
        ttk.Label(box, text=HELP, wraplength=680, foreground="#555").grid(
            row=6, column=0, columnspan=3, sticky="w", padx=8, pady=(4, 0))

        ctl = ttk.LabelFrame(outer, text="Sync", padding=8)
        ctl.pack(fill="x", pady=(10, 0))
        bar = ttk.Frame(ctl)
        bar.pack(fill="x")
        self.btn_sync = ttk.Button(bar, text="Sync now", command=lambda: self._start(False))
        self.btn_sync.pack(side="left")
        self.btn_dry = ttk.Button(bar, text="Dry run", command=lambda: self._start(True))
        self.btn_dry.pack(side="left", padx=6)
        self.btn_stop = ttk.Button(bar, text="Stop", command=self._stop, state="disabled")
        self.btn_stop.pack(side="left")
        ttk.Checkbutton(bar, text="Full rescan", variable=self.v_full).pack(side="left", padx=12)
        ttk.Button(bar, text="Support on Ko-fi",
                   command=lambda: webbrowser.open(DONATE_URL)).pack(side="right")

        ttk.Label(ctl, textvariable=self.v_status, font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w", pady=(8, 0))
        ttk.Label(ctl, textvariable=self.v_file).pack(anchor="w")
        self.bar = ttk.Progressbar(ctl, mode="indeterminate")
        self.bar.pack(fill="x", pady=4)
        ttk.Label(ctl, textvariable=self.v_last).pack(anchor="w")
        ttk.Label(ctl, textvariable=self.v_next).pack(anchor="w")

        logf = ttk.LabelFrame(outer, text="Log", padding=4)
        logf.pack(fill="both", expand=True, pady=(10, 0))
        self.log = ScrolledText(logf, height=10, state="disabled", wrap="none",
                                font=("TkFixedFont", 9))
        self.log.pack(fill="both", expand=True)

    # ---- settings -----------------------------------------------------
    def _pick_cookies(self) -> None:
        f = filedialog.askopenfilename(title="Select cookies.txt",
                                       filetypes=[("Text", "*.txt"), ("All", "*")])
        if f:
            self.v_cookies.set(f)

    def _pick_output(self) -> None:
        f = filedialog.askdirectory(title="Select download folder")
        if f:
            self.v_output.set(f)

    def _pick_archive(self) -> None:
        f = filedialog.asksaveasfilename(title="Archive file", defaultextension=".sqlite3",
                                         initialfile="archive.sqlite3")
        if f:
            self.v_archive.set(f)

    def _settings(self) -> Settings:
        s = Settings.from_values(self.v_cookies.get(),
                                 self.v_output.get(), self.v_archive.get())
        parse_hhmm(self.v_time.get())
        return s

    def _save(self) -> bool:
        try:
            self._settings()
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return False
        write_env_file(USER_ENV_FILE, {
            "X_COOKIES": self.v_cookies.get().strip(),
            "TINY_X_DOWNLOADER_OUTPUT_DIR": self.v_output.get().strip(),
            "TINY_X_DOWNLOADER_ARCHIVE": self.v_archive.get().strip(),
            "X_SYNC_TIME": self.v_time.get().strip(),
            "X_GUI_DAILY": "1" if self.v_daily.get() else "0",
        })
        self._reschedule()
        self._log(f"settings saved to {USER_ENV_FILE}")
        return True

    # ---- running ------------------------------------------------------
    def _start(self, dry_run: bool) -> None:
        if self.worker and self.worker.is_alive():
            return
        try:
            settings = self._settings()
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return
        self.cancel.clear()
        self.progress.start()
        full = self.v_full.get()
        self._log(f"=== {'dry run' if dry_run else 'sync'} started {datetime.now():%F %T} ===")
        self.btn_sync.state(["disabled"]); self.btn_dry.state(["disabled"])
        self.btn_stop.state(["!disabled"])
        self.bar.start(12)

        def work() -> None:
            try:
                code = sync(settings, full=full, dry_run=dry_run,
                            on_line=lambda l: self.lines.put(("line", l)), cancel=self.cancel)
            except Exception as exc:  # show instead of dying silently
                self.lines.put(("line", f"error: {exc}"))
                code = 2
            self.lines.put(("done", code))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _stop(self) -> None:
        if self.worker and self.worker.is_alive():
            self.cancel.set()
            self.progress.state = "stopping"
            self.btn_stop.state(["disabled"])

    def _tick(self) -> None:
        try:
            while True:
                kind, payload = self.lines.get_nowait()
                if kind == "line":
                    self.progress.feed(str(payload))
                    self._log(str(payload))
                else:
                    self._finished(int(payload))
        except queue.Empty:
            pass
        self.v_status.set(self.progress.summary())
        self.v_file.set(f"Current: {self.progress.current_file}" if self.progress.current_file else "")
        if self.progress.errors and self.progress.state != "idle":
            self.v_status.set(self.v_status.get() + f", {self.progress.errors} error(s)")
        self._maybe_daily()
        self.root.after(150, self._tick)

    def _finished(self, code: int) -> None:
        self.progress.finish(code)
        self.bar.stop()
        self.btn_sync.state(["!disabled"]); self.btn_dry.state(["!disabled"])
        self.btn_stop.state(["disabled"])
        self.v_last.set(f"Last run: {self.progress.last_finished:%F %T}, {self.progress.last_result}")
        self._log(f"=== finished (exit {code}) ===")
        self._reschedule()

    # ---- daily timer while the window is open ---------------------------
    def _reschedule(self) -> None:
        if self.v_daily.get():
            try:
                self.next_target = next_run(datetime.now(), self.v_time.get())
                self.v_next.set(f"Next automatic sync: {self.next_target:%F %H:%M}")
                return
            except ValueError:
                pass
        self.next_target = None
        self.v_next.set("Automatic daily sync: off")

    def _maybe_daily(self) -> None:
        if (self.next_target and datetime.now() >= self.next_target
                and not (self.worker and self.worker.is_alive())):
            self._reschedule()
            self._start(False)

    # ---- misc ---------------------------------------------------------
    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        extra = int(self.log.index("end-1c").split(".")[0]) - MAX_LOG_LINES
        if extra > 0:
            self.log.delete("1.0", f"{extra + 1}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Quit", "A sync is running. Stop it and quit?"):
                return
            self.cancel.set()
        self.root.destroy()


def run_gui() -> int:
    root = Tk()
    App(root)
    root.mainloop()
    return 0
