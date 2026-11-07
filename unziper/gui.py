import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

from .extractor import InPlaceExtractor, ExtractionProgress
from .chunker import ChunkArchiver, ChunkProgress
from .utils import format_bytes, get_free_disk_space


class UnziperApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Unziper - Big Game Zero-Waste Extractor")
        self.root.geometry("680x550")
        self.root.minsize(620, 500)

        # Apply modern ttk theme styling
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.current_extractor: Optional[InPlaceExtractor] = None
        self.is_running = False

        self._build_ui()

    def _build_ui(self):
        # Header frame
        header_frame = tk.Frame(self.root, bg="#0f172a", height=65)
        header_frame.pack(fill=tk.X, side=tk.TOP)

        title_label = tk.Label(
            header_frame,
            text="Unziper: Zero-Waste Extractor",
            font=("Segoe UI", 15, "bold"),
            fg="#38bdf8",
            bg="#0f172a",
        )
        title_label.pack(side=tk.LEFT, padx=18, pady=12)

        subtitle_label = tk.Label(
            header_frame,
            text="Divides into parts & deletes unzipped data automatically",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#0f172a",
        )
        subtitle_label.pack(side=tk.RIGHT, padx=18, pady=18)

        # Notebook tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        self.tab_extract = ttk.Frame(self.notebook, padding=12)
        self.tab_create = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(self.tab_extract, text=" Extract Game / Archive ")
        self.notebook.add(self.tab_create, text=" Compress Folder to Parts ")

        self._setup_extract_tab()
        self._setup_create_tab()

    def _setup_extract_tab(self):
        # File selector
        file_frame = ttk.LabelFrame(self.tab_extract, text="Select Game or Archive File", padding=10)
        file_frame.pack(fill=tk.X, pady=(0, 10))

        self.archive_path_var = tk.StringVar()
        entry_archive = ttk.Entry(file_frame, textvariable=self.archive_path_var)
        entry_archive.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_browse_archive = ttk.Button(file_frame, text="Browse...", command=self._browse_archive)
        btn_browse_archive.pack(side=tk.RIGHT)

        # Destination selector
        dest_frame = ttk.LabelFrame(self.tab_extract, text="Extraction Destination", padding=10)
        dest_frame.pack(fill=tk.X, pady=(0, 10))

        self.dest_path_var = tk.StringVar()
        entry_dest = ttk.Entry(dest_frame, textvariable=self.dest_path_var)
        entry_dest.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_browse_dest = ttk.Button(dest_frame, text="Browse...", command=self._browse_dest)
        btn_browse_dest.pack(side=tk.RIGHT)

        # Partition & Space Card
        info_frame = ttk.LabelFrame(self.tab_extract, text="Partition & Space Tracking", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        self.lbl_orig_size = ttk.Label(info_frame, text="Archive Size: -", font=("Segoe UI", 9))
        self.lbl_orig_size.grid(row=0, column=0, sticky="w", padx=6, pady=2)

        self.lbl_disk_free = ttk.Label(info_frame, text="Free Disk Space: -", font=("Segoe UI", 9))
        self.lbl_disk_free.grid(row=0, column=1, sticky="w", padx=6, pady=2)

        self.lbl_space_freed = ttk.Label(info_frame, text="Space Reclaimed: 0 B", font=("Segoe UI", 9, "bold"), foreground="#059669")
        self.lbl_space_freed.grid(row=1, column=0, sticky="w", padx=6, pady=2)

        self.lbl_part_info = ttk.Label(info_frame, text="Part Progress: Waiting...", font=("Segoe UI", 9, "bold"), foreground="#2563eb")
        self.lbl_part_info.grid(row=1, column=1, sticky="w", padx=6, pady=2)

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(self.tab_extract, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(5, 5))

        self.lbl_status = ttk.Label(self.tab_extract, text="Ready. Select an archive to begin.", font=("Segoe UI", 9))
        self.lbl_status.pack(anchor="w", pady=(0, 10))

        # Action Buttons
        btn_box = ttk.Frame(self.tab_extract)
        btn_box.pack(fill=tk.X, side=tk.BOTTOM, pady=5)

        self.btn_extract = ttk.Button(
            btn_box,
            text="Extract & Auto-Delete Unzipped Data",
            command=self._start_extraction,
        )
        self.btn_extract.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)

        self.btn_open_folder = ttk.Button(
            btn_box,
            text="Open Folder",
            state=tk.DISABLED,
            command=self._open_destination,
        )
        self.btn_open_folder.pack(side=tk.RIGHT)

    def _setup_create_tab(self):
        src_frame = ttk.LabelFrame(self.tab_create, text="Source Folder (e.g. Game Directory)", padding=10)
        src_frame.pack(fill=tk.X, pady=(0, 10))

        self.create_src_var = tk.StringVar()
        entry_src = ttk.Entry(src_frame, textvariable=self.create_src_var)
        entry_src.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_browse_src = ttk.Button(src_frame, text="Browse...", command=self._browse_create_src)
        btn_browse_src.pack(side=tk.RIGHT)

        out_frame = ttk.LabelFrame(self.tab_create, text="Output Archive Base Name", padding=10)
        out_frame.pack(fill=tk.X, pady=(0, 10))

        self.create_out_var = tk.StringVar()
        entry_out = ttk.Entry(out_frame, textvariable=self.create_out_var)
        entry_out.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_browse_out = ttk.Button(out_frame, text="Save As...", command=self._browse_create_out)
        btn_browse_out.pack(side=tk.RIGHT)

        opts_frame = ttk.LabelFrame(self.tab_create, text="Part Options", padding=10)
        opts_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(opts_frame, text="Maximum Part Size (MB):").pack(side=tk.LEFT, padx=(0, 8))
        self.chunk_size_var = tk.StringVar(value="1000")
        entry_chunk = ttk.Entry(opts_frame, textvariable=self.chunk_size_var, width=10)
        entry_chunk.pack(side=tk.LEFT)

        self.lbl_create_status = ttk.Label(self.tab_create, text="Divides into parts that auto-delete when unzipped so 2X space is never needed.", font=("Segoe UI", 9))
        self.lbl_create_status.pack(anchor="w", pady=(0, 10))

        self.btn_create_parts = ttk.Button(
            self.tab_create,
            text="Compress to Self-Deleting Parts",
            command=self._start_create_parts,
        )
        self.btn_create_parts.pack(fill=tk.X, side=tk.BOTTOM, pady=5)

    def _browse_archive(self):
        path = filedialog.askopenfilename(
            title="Select Game or ZIP Archive",
            filetypes=[("Zip & Game Archives", "*.zip *.part*.zip"), ("All Files", "*.*")],
        )
        if path:
            self.archive_path_var.set(path)
            base_dir = os.path.dirname(path)
            file_base = os.path.splitext(os.path.basename(path))[0]
            if ".part" in file_base.lower():
                file_base = file_base.split(".part")[0]
            default_dest = os.path.join(base_dir, file_base)
            self.dest_path_var.set(default_dest)

            sz = os.path.getsize(path)
            self.lbl_orig_size.config(text=f"Archive Size: {format_bytes(sz)}")
            free_sp = get_free_disk_space(default_dest)
            self.lbl_disk_free.config(text=f"Free Disk Space: {format_bytes(free_sp)}")
            self.lbl_status.config(text="Ready. Click button to extract and delete unzipped data automatically.")

    def _browse_dest(self):
        d = filedialog.askdirectory(title="Select Destination Folder")
        if d:
            self.dest_path_var.set(d)
            free_sp = get_free_disk_space(d)
            self.lbl_disk_free.config(text=f"Free Disk Space: {format_bytes(free_sp)}")

    def _browse_create_src(self):
        d = filedialog.askdirectory(title="Select Folder to Compress")
        if d:
            self.create_src_var.set(d)
            if not self.create_out_var.get():
                self.create_out_var.set(d)

    def _browse_create_out(self):
        f = filedialog.asksaveasfilename(title="Save Part Prefix As", confirmoverwrite=False)
        if f:
            if f.endswith(".zip"):
                f = f[:-4]
            self.create_out_var.set(f)

    def _open_destination(self):
        dest = self.dest_path_var.get()
        if os.path.isdir(dest):
            os.startfile(dest)

    def _start_extraction(self):
        archive = self.archive_path_var.get().strip()
        dest = self.dest_path_var.get().strip()

        if not archive or not os.path.isfile(archive):
            messagebox.showerror("Error", "Please select a valid archive file.")
            return

        if not dest:
            messagebox.showerror("Error", "Please specify a destination folder.")
            return

        self.btn_extract.config(state=tk.DISABLED)
        self.btn_open_folder.config(state=tk.DISABLED)
        self.is_running = True

        threading.Thread(target=self._run_extraction_worker, args=(archive, dest), daemon=True).start()

    def _run_extraction_worker(self, archive: str, dest: str):
        try:
            parts = ChunkArchiver.find_all_parts(archive)
            if len(parts) > 1:
                # Multi-part chunk mode
                def on_chunk_prog(p: ChunkProgress):
                    def update():
                        self.progress_var.set(p.percent_done)
                        self.lbl_part_info.config(text=f"Part {p.part_index}/{p.total_parts}")
                        self.lbl_status.config(text=p.message)
                    self.root.after(0, update)

                res = ChunkArchiver.extract_and_delete_parts(
                    parts=parts,
                    destination_dir=dest,
                    auto_delete=True,
                    progress_callback=on_chunk_prog,
                )
            else:
                # In-place partition & shrink mode
                extractor = InPlaceExtractor(archive, dest, num_parts=10)
                self.current_extractor = extractor

                def on_inplace_prog(p: ExtractionProgress):
                    def update():
                        self.progress_var.set(p.percent_done)
                        self.lbl_space_freed.config(text=f"Space Reclaimed: {format_bytes(p.space_reclaimed_bytes)}")
                        self.lbl_part_info.config(text=f"Part {p.current_part}/{p.total_parts}")
                        short_f = os.path.basename(p.current_file)
                        self.lbl_status.config(text=f"Unzipping & Deleting ({p.files_completed}/{p.total_files}): {short_f}")
                    self.root.after(0, update)

                def on_part_done(part_idx, total_parts, freed_bytes, msg):
                    def update():
                        self.lbl_part_info.config(text=f"Part {part_idx}/{total_parts} Done (-{format_bytes(freed_bytes)})")
                    self.root.after(0, update)

                res = extractor.extract(progress_callback=on_inplace_prog, part_callback=on_part_done)

            def on_done():
                self.progress_var.set(100.0)
                self.btn_extract.config(state=tk.NORMAL)
                self.btn_open_folder.config(state=tk.NORMAL)
                self.lbl_status.config(text="Extraction finished! Archive completely deleted.")
                messagebox.showinfo("Success", f"Extraction completed!\nExtracted to:\n{dest}\n\nArchive deleted automatically without needing 2X space!")

            self.root.after(0, on_done)

        except Exception as e:
            def on_err():
                self.btn_extract.config(state=tk.NORMAL)
                self.lbl_status.config(text=f"Error: {e}")
                messagebox.showerror("Extraction Error", str(e))
            self.root.after(0, on_err)

    def _start_create_parts(self):
        src = self.create_src_var.get().strip()
        out_base = self.create_out_var.get().strip()

        if not src or not os.path.isdir(src):
            messagebox.showerror("Error", "Please select a valid source directory.")
            return

        if not out_base:
            messagebox.showerror("Error", "Please choose an output prefix.")
            return

        try:
            chunk_mb = int(self.chunk_size_var.get().strip())
            if chunk_mb <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Chunk size must be a positive integer in MB.")
            return

        self.btn_create_parts.config(state=tk.DISABLED)

        def worker():
            try:
                def prog(rel, cur, tot):
                    self.root.after(0, lambda: self.lbl_create_status.config(text=f"Compressing file {cur}/{tot}: {os.path.basename(rel)}"))

                parts = ChunkArchiver.create_chunked_archive(src, out_base, chunk_mb, progress_callback=prog)
                def done():
                    self.btn_create_parts.config(state=tk.NORMAL)
                    self.lbl_create_status.config(text=f"Created {len(parts)} parts successfully.")
                    messagebox.showinfo("Success", f"Successfully created {len(parts)} parts!")
                self.root.after(0, done)
            except Exception as e:
                def err():
                    self.btn_create_parts.config(state=tk.NORMAL)
                    self.lbl_create_status.config(text=f"Error: {e}")
                    messagebox.showerror("Error", str(e))
                self.root.after(0, err)

        threading.Thread(target=worker, daemon=True).start()


def launch_gui():
    root = tk.Tk()
    app = UnziperApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
