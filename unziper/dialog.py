import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from .extractor import InPlaceExtractor, ExtractionProgress
from .chunker import ChunkArchiver, ChunkProgress
from .utils import format_bytes, get_free_disk_space


class SevenZipExtractionDialog:
    """
    Compact, sleek extraction progress dialog styled after 7-Zip.
    Displays real-time elapsed time, ETA, transfer speed, files completed,
    and live reclaimed disk space.
    """

    def __init__(self, archive_path: str, destination_dir: Optional[str] = None):
        self.archive_path = os.path.abspath(archive_path)
        self.destination_dir = destination_dir

        self.root = tk.Tk()
        archive_name = os.path.basename(self.archive_path)
        self.root.title(f"Extracting: {archive_name}")
        self.root.geometry("500x320")
        self.root.resizable(False, False)

        # Center on screen
        self._center_window()

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.extractor: Optional[InPlaceExtractor] = None
        self.start_time = 0.0
        self.last_bytes = 0
        self.last_time = 0.0
        self.current_speed = 0.0
        self.is_paused = False
        self.is_completed = False
        self.auto_close_var = tk.BooleanVar(value=True)

        self._build_ui(archive_name)

    def _center_window(self):
        self.root.update_idletasks()
        w = 500
        h = 320
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self, archive_name: str):
        # Top banner with archive name and percentage
        top_frame = ttk.Frame(self.root, padding="12 10 12 5")
        top_frame.pack(fill=tk.X)

        self.lbl_headline = ttk.Label(
            top_frame,
            text=f"Extracting: {archive_name}",
            font=("Segoe UI", 10, "bold"),
        )
        self.lbl_headline.pack(anchor="w")

        # Progress Bar
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progressbar = ttk.Progressbar(top_frame, variable=self.progress_var, maximum=100)
        self.progressbar.pack(fill=tk.X, pady=(6, 2))

        self.lbl_percent = ttk.Label(top_frame, text="0%", font=("Segoe UI", 9))
        self.lbl_percent.pack(anchor="e")

        # 7-Zip Grid Stats
        stats_frame = ttk.LabelFrame(self.root, text="Progress Information", padding=10)
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))

        # Row 0: Elapsed & Remaining (ETA)
        ttk.Label(stats_frame, text="Elapsed time:").grid(row=0, column=0, sticky="w", pady=2)
        self.val_elapsed = ttk.Label(stats_frame, text="00:00:00", font=("Consolas", 9))
        self.val_elapsed.grid(row=0, column=1, sticky="w", padx=(6, 20), pady=2)

        ttk.Label(stats_frame, text="Remaining:").grid(row=0, column=2, sticky="w", pady=2)
        self.val_remaining = ttk.Label(stats_frame, text="--:--:--", font=("Consolas", 9))
        self.val_remaining.grid(row=0, column=3, sticky="w", padx=6, pady=2)

        # Row 1: Files & Speed
        ttk.Label(stats_frame, text="Files:").grid(row=1, column=0, sticky="w", pady=2)
        self.val_files = ttk.Label(stats_frame, text="0 / 0", font=("Consolas", 9))
        self.val_files.grid(row=1, column=1, sticky="w", padx=(6, 20), pady=2)

        ttk.Label(stats_frame, text="Speed:").grid(row=1, column=2, sticky="w", pady=2)
        self.val_speed = ttk.Label(stats_frame, text="0.0 MB/s", font=("Consolas", 9))
        self.val_speed.grid(row=1, column=3, sticky="w", padx=6, pady=2)

        # Row 2: Processed size & Space Reclaimed
        ttk.Label(stats_frame, text="Processed:").grid(row=2, column=0, sticky="w", pady=2)
        self.val_processed = ttk.Label(stats_frame, text="0 B", font=("Consolas", 9))
        self.val_processed.grid(row=2, column=1, sticky="w", padx=(6, 20), pady=2)

        ttk.Label(stats_frame, text="Reclaimed:").grid(row=2, column=2, sticky="w", pady=2)
        self.val_reclaimed = ttk.Label(stats_frame, text="0 B", font=("Consolas", 9, "bold"), foreground="#059669")
        self.val_reclaimed.grid(row=2, column=3, sticky="w", padx=6, pady=2)

        # Row 3: Current file being unzipped
        ttk.Label(stats_frame, text="Current file:").grid(row=3, column=0, sticky="nw", pady=(4, 0))
        self.val_current_file = ttk.Label(stats_frame, text="Initializing...", font=("Segoe UI", 8), wraplength=340)
        self.val_current_file.grid(row=3, column=1, columnspan=3, sticky="w", padx=6, pady=(4, 0))

        # Bottom Bar: Auto close checkbox & Buttons
        bottom_frame = ttk.Frame(self.root, padding="12 4 12 10")
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        chk_autoclose = ttk.Checkbutton(bottom_frame, text="Close on finish", variable=self.auto_close_var)
        chk_autoclose.pack(side=tk.LEFT)

        btn_box = ttk.Frame(bottom_frame)
        btn_box.pack(side=tk.RIGHT)

        self.btn_bg = ttk.Button(btn_box, text="Background", width=11, command=self._send_to_background)
        self.btn_bg.pack(side=tk.LEFT, padx=3)

        self.btn_pause = ttk.Button(btn_box, text="Pause", width=9, command=self._toggle_pause)
        self.btn_pause.pack(side=tk.LEFT, padx=3)

        self.btn_cancel = ttk.Button(btn_box, text="Cancel", width=9, command=self._cancel)
        self.btn_cancel.pack(side=tk.LEFT, padx=3)

    def _format_time(self, seconds: float) -> str:
        if seconds < 0 or seconds > 360000:
            return "--:--:--"
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"

    def _send_to_background(self):
        self.root.iconify()

    def _toggle_pause(self):
        if not self.extractor:
            return
        if self.is_paused:
            self.extractor.resume()
            self.is_paused = False
            self.btn_pause.config(text="Pause")
        else:
            self.extractor.pause()
            self.is_paused = True
            self.btn_pause.config(text="Resume")

    def _cancel(self):
        if self.is_completed:
            self.root.destroy()
            return
        if messagebox.askyesno("Cancel Extraction", "Are you sure you want to stop extraction?"):
            if self.extractor:
                self.extractor.cancel()
            self.root.destroy()

    def start(self):
        self.start_time = time.time()
        self.last_time = self.start_time
        self.last_bytes = 0

        # Start extraction in background thread
        threading.Thread(target=self._run_worker, daemon=True).start()
        self.root.mainloop()

    def _run_worker(self):
        try:
            parts = ChunkArchiver.find_all_parts(self.archive_path)
            if len(parts) > 1:
                # Multi-part mode
                def on_chunk(p: ChunkProgress):
                    def update():
                        self.progress_var.set(p.percent_done)
                        self.lbl_percent.config(text=f"{p.percent_done:.1f}%")
                        self.val_files.config(text=f"Part {p.part_index} / {p.total_parts}")
                        self.val_current_file.config(text=p.message)
                    self.root.after(0, update)

                res = ChunkArchiver.extract_and_delete_parts(
                    parts=parts,
                    destination_dir=self.destination_dir or os.path.dirname(self.archive_path),
                    auto_delete=True,
                    progress_callback=on_chunk,
                )
            else:
                # In-place reverse shrink mode
                self.extractor = InPlaceExtractor(self.archive_path, self.destination_dir)

                def on_prog(p: ExtractionProgress):
                    now = time.time()
                    dt = now - self.last_time
                    if dt >= 0.3 or p.files_completed == p.total_files:
                        db = p.bytes_extracted - self.last_bytes
                        speed = (db / dt) if dt > 0 else 0
                        self.last_time = now
                        self.last_bytes = p.bytes_extracted

                        elapsed = now - self.start_time
                        remaining_bytes = max(0, p.total_uncompressed_bytes - p.bytes_extracted)
                        eta = (remaining_bytes / speed) if speed > 1024 else 0

                        def update():
                            self.progress_var.set(p.percent_done)
                            self.lbl_percent.config(text=f"{p.percent_done:.1f}%")
                            self.root.title(f"Extracting: {os.path.basename(self.archive_path)} - {int(p.percent_done)}%")

                            self.val_elapsed.config(text=self._format_time(elapsed))
                            self.val_remaining.config(text=self._format_time(eta))
                            self.val_files.config(text=f"{p.files_completed} / {p.total_files}")
                            self.val_speed.config(text=f"{format_bytes(int(speed))}/s")
                            self.val_processed.config(text=f"{format_bytes(p.bytes_extracted)} / {format_bytes(p.total_uncompressed_bytes)}")
                            self.val_reclaimed.config(text=format_bytes(p.space_reclaimed_bytes))

                            disp_f = os.path.basename(p.current_file)
                            if len(disp_f) > 50:
                                disp_f = disp_f[:47] + "..."
                            self.val_current_file.config(text=disp_f)

                        self.root.after(0, update)

                res = self.extractor.extract(progress_callback=on_prog)

            self.is_completed = True

            def on_finish():
                self.progress_var.set(100.0)
                self.lbl_percent.config(text="100%")
                self.val_current_file.config(text="Extraction completed! Archive deleted to free space.")
                self.btn_cancel.config(text="Close")
                self.btn_pause.config(state=tk.DISABLED)

                if self.auto_close_var.get():
                    self.root.after(400, self.root.destroy)

            self.root.after(0, on_finish)

        except Exception as e:
            def on_err():
                self.val_current_file.config(text=f"Error: {e}")
                messagebox.showerror("Extraction Error", str(e))
                self.btn_cancel.config(text="Close")
            self.root.after(0, on_err)


def show_7zip_dialog(archive_path: str, destination_dir: Optional[str] = None):
    """Entry point to launch the 7-Zip style extraction dialog."""
    dialog = SevenZipExtractionDialog(archive_path, destination_dir)
    dialog.start()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        show_7zip_dialog(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
