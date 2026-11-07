import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

from .extractor import InPlaceExtractor, ExtractionProgress
from .chunker import ChunkArchiver, ChunkProgress
from .utils import format_bytes, get_free_disk_space


class MinimalUnziperApp:
    """
    Clean, minimal, native Windows extraction utility.
    Styled like standard Windows utilities (7-Zip / WinRAR / installer wizard),
    free of AI banners and clutter.
    """

    def __init__(self, root: tk.Tk, initial_archive: Optional[str] = None, destination: Optional[str] = None):
        self.root = root
        self.root.title("Unziper")
        self.root.geometry("520x260")
        self.root.minsize(480, 240)

        # Use native Windows Vista/10/11 visual styles
        self.style = ttk.Style()
        for theme in ["vista", "xpnative", "winnative"]:
            if theme in self.style.theme_names():
                try:
                    self.style.theme_use(theme)
                    break
                except Exception:
                    pass

        self._center_window(520, 260)

        self.archive_var = tk.StringVar(value=initial_archive or "")
        self.dest_var = tk.StringVar(value=destination or "")
        self.auto_delete_var = tk.BooleanVar(value=True)
        self.context_menu_var = tk.BooleanVar(value=True)

        self.extractor: Optional[InPlaceExtractor] = None
        self.is_paused = False
        self.start_time = 0.0
        self.last_time = 0.0
        self.last_bytes = 0

        # Main container
        self.container = ttk.Frame(self.root, padding="18 16 18 16")
        self.container.pack(fill=tk.BOTH, expand=True)

        if initial_archive:
            self._update_default_dest(initial_archive)

        self._show_select_view()

    def _center_window(self, w: int, h: int):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def _update_default_dest(self, archive_path: str):
        if not self.dest_var.get() and archive_path:
            base_dir = os.path.dirname(os.path.abspath(archive_path))
            stem = os.path.splitext(os.path.basename(archive_path))[0]
            if ".part" in stem.lower():
                stem = stem.split(".part")[0]
            self.dest_var.set(os.path.join(base_dir, stem))

    # =========================================================================
    # VIEW 1: Ready / Selection View
    # =========================================================================
    def _show_select_view(self):
        self._clear_container()
        self.root.title("Unziper - Extract Archive")

        # Archive row
        lbl_archive = ttk.Label(self.container, text="Archive:")
        lbl_archive.pack(anchor="w")

        row_arch = ttk.Frame(self.container)
        row_arch.pack(fill=tk.X, pady=(2, 10))

        ent_arch = ttk.Entry(row_arch, textvariable=self.archive_var)
        ent_arch.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_browse_arch = ttk.Button(row_arch, text="Browse...", command=self._browse_archive)
        btn_browse_arch.pack(side=tk.RIGHT)

        # Destination row
        lbl_dest = ttk.Label(self.container, text="Extract to:")
        lbl_dest.pack(anchor="w")

        row_dest = ttk.Frame(self.container)
        row_dest.pack(fill=tk.X, pady=(2, 10))

        ent_dest = ttk.Entry(row_dest, textvariable=self.dest_var)
        ent_dest.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_browse_dest = ttk.Button(row_dest, text="Browse...", command=self._browse_dest)
        btn_browse_dest.pack(side=tk.RIGHT)

        # Options
        chk_del = ttk.Checkbutton(
            self.container,
            text="Delete archive as files are extracted (zero extra space)",
            variable=self.auto_delete_var,
        )
        chk_del.pack(anchor="w", pady=(2, 2))

        # Bottom Button Bar
        btn_bar = ttk.Frame(self.container)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        btn_cancel = ttk.Button(btn_bar, text="Cancel", width=10, command=self.root.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=(6, 0))

        btn_extract = ttk.Button(btn_bar, text="Extract", width=12, command=self._start_extraction)
        btn_extract.pack(side=tk.RIGHT)

    def _browse_archive(self):
        f = filedialog.askopenfilename(
            title="Select Archive",
            filetypes=[("Archives", "*.zip *.part*.zip"), ("All Files", "*.*")],
        )
        if f:
            self.archive_var.set(f)
            self._update_default_dest(f)

    def _browse_dest(self):
        d = filedialog.askdirectory(title="Select Destination Folder")
        if d:
            self.dest_var.set(d)

    # =========================================================================
    # VIEW 2: Extracting Progress View
    # =========================================================================
    def _show_progress_view(self):
        self._clear_container()
        archive_name = os.path.basename(self.archive_var.get())
        self.root.title(f"Extracting: {archive_name}")

        self.lbl_extracting = ttk.Label(self.container, text=f"Extracting {archive_name}...", font=("Segoe UI", 9))
        self.lbl_extracting.pack(anchor="w", pady=(0, 6))

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progressbar = ttk.Progressbar(self.container, variable=self.progress_var, maximum=100)
        self.progressbar.pack(fill=tk.X, pady=(0, 6))

        self.lbl_stats = ttk.Label(self.container, text="Preparing extraction...", foreground="#475569")
        self.lbl_stats.pack(anchor="w", pady=(0, 2))

        self.lbl_file = ttk.Label(self.container, text="", foreground="#64748b", font=("Segoe UI", 8))
        self.lbl_file.pack(anchor="w", pady=(0, 10))

        # Bottom Button Bar
        btn_bar = ttk.Frame(self.container)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        self.btn_cancel = ttk.Button(btn_bar, text="Cancel", width=10, command=self._cancel)
        self.btn_cancel.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_pause = ttk.Button(btn_bar, text="Pause", width=10, command=self._toggle_pause)
        self.btn_pause.pack(side=tk.RIGHT)

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
        if messagebox.askyesno("Cancel Extraction", "Are you sure you want to stop extraction?"):
            if self.extractor:
                self.extractor.cancel()
            self.root.destroy()

    def _start_extraction(self):
        archive = self.archive_var.get().strip()
        dest = self.dest_var.get().strip()

        if not archive or not os.path.isfile(archive):
            messagebox.showerror("Error", "Please select a valid archive file.")
            return

        if not dest:
            messagebox.showerror("Error", "Please specify an extraction folder.")
            return

        self._show_progress_view()
        self.start_time = time.time()
        self.last_time = self.start_time
        self.last_bytes = 0

        threading.Thread(target=self._worker, args=(archive, dest), daemon=True).start()

    def _worker(self, archive: str, dest: str):
        try:
            parts = ChunkArchiver.find_all_parts(archive)
            total_freed = os.path.getsize(archive)

            if len(parts) > 1:
                def on_chunk(p: ChunkProgress):
                    def update():
                        self.progress_var.set(p.percent_done)
                        self.root.title(f"Extracting: {os.path.basename(archive)} - {int(p.percent_done)}%")
                        self.lbl_stats.config(text=f"Part {p.part_index}/{p.total_parts}  •  {p.message}")
                    self.root.after(0, update)

                res = ChunkArchiver.extract_and_delete_parts(
                    parts=parts,
                    destination_dir=dest,
                    auto_delete=self.auto_delete_var.get(),
                    progress_callback=on_chunk,
                )
            else:
                self.extractor = InPlaceExtractor(archive, dest)

                def on_prog(p: ExtractionProgress):
                    now = time.time()
                    dt = now - self.last_time
                    if dt >= 0.25 or p.files_completed == p.total_files:
                        db = p.bytes_extracted - self.last_bytes
                        speed = (db / dt) if dt > 0 else 0
                        self.last_time = now
                        self.last_bytes = p.bytes_extracted

                        remaining_bytes = max(0, p.total_uncompressed_bytes - p.bytes_extracted)
                        eta_secs = int(remaining_bytes / speed) if speed > 1024 else 0
                        eta_str = f"{eta_secs // 60:02d}:{eta_secs % 60:02d}"

                        def update():
                            self.progress_var.set(p.percent_done)
                            self.root.title(f"Extracting: {os.path.basename(archive)} - {int(p.percent_done)}%")
                            stats_txt = (
                                f"{p.percent_done:.0f}%  •  "
                                f"Remaining: {eta_str}  •  "
                                f"{format_bytes(int(speed))}/s  •  "
                                f"Freed: {format_bytes(p.space_reclaimed_bytes)}"
                            )
                            self.lbl_stats.config(text=stats_txt)

                            fname = os.path.basename(p.current_file)
                            if len(fname) > 55:
                                fname = fname[:52] + "..."
                            self.lbl_file.config(text=fname)

                        self.root.after(0, update)

                res = self.extractor.extract(progress_callback=on_prog)

            # Show finished state
            self.root.after(0, lambda: self._show_finished_view(dest, total_freed))

        except Exception as e:
            def on_err():
                messagebox.showerror("Extraction Error", str(e))
                self._show_select_view()
            self.root.after(0, on_err)

    # =========================================================================
    # VIEW 3: Finished View
    # =========================================================================
    def _show_finished_view(self, dest_folder: str, freed_bytes: int):
        self._clear_container()
        self.root.title("Unziper - Extraction Finished")

        lbl_done = ttk.Label(
            self.container,
            text="Extraction Finished",
            font=("Segoe UI", 12, "bold"),
            foreground="#166534",
        )
        lbl_done.pack(anchor="w", pady=(4, 6))

        lbl_desc = ttk.Label(
            self.container,
            text=(
                f"All files have been extracted successfully.\n"
                f"Archive was deleted, freeing {format_bytes(freed_bytes)} of disk space.\n\n"
                f"Location:\n{dest_folder}"
            ),
            font=("Segoe UI", 9),
            justify="left",
            wraplength=480,
        )
        lbl_desc.pack(anchor="w", pady=(0, 16))

        # Bottom Button Bar with Finish button
        btn_bar = ttk.Frame(self.container)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        btn_finish = ttk.Button(
            btn_bar,
            text="Finish",
            width=12,
            command=self.root.destroy,
        )
        btn_finish.pack(side=tk.RIGHT, padx=(6, 0))

        btn_open = ttk.Button(
            btn_bar,
            text="Open Folder",
            width=14,
            command=lambda: os.startfile(dest_folder) if os.path.isdir(dest_folder) else None,
        )
        btn_open.pack(side=tk.RIGHT)

        btn_finish.focus_set()


def launch_gui(initial_archive: Optional[str] = None, destination: Optional[str] = None):
    root = tk.Tk()
    app = MinimalUnziperApp(root, initial_archive, destination)
    root.mainloop()


if __name__ == "__main__":
    archive_arg = sys.argv[1] if len(sys.argv) > 1 else None
    dest_arg = sys.argv[2] if len(sys.argv) > 2 else None
    launch_gui(archive_arg, dest_arg)
