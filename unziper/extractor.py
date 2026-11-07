import os
import shutil
import zipfile
from typing import Callable, Optional, List
from dataclasses import dataclass
from .utils import is_safe_path, format_bytes
from .sparse import NTFSSparseHandler


@dataclass
class ExtractionProgress:
    current_file: str
    files_completed: int
    total_files: int
    bytes_extracted: int
    total_uncompressed_bytes: int
    archive_size_bytes: int
    initial_archive_size: int
    space_reclaimed_bytes: int
    percent_done: float
    current_part: int = 1
    total_parts: int = 1
    part_message: str = ""


class InPlaceExtractor:
    """
    Extracts a ZIP archive in reverse offset order, truncating the archive
    as each part/file is written to disk. This frees disk space continuously during
    extraction and eliminates the need for 2x disk space for large game files.
    """

    def __init__(
        self,
        archive_path: str,
        destination_dir: Optional[str] = None,
        num_parts: int = 10,
        enable_sparse: bool = True,
    ):
        self.archive_path = os.path.abspath(archive_path)
        if not os.path.isfile(self.archive_path):
            raise FileNotFoundError(f"Archive not found: {self.archive_path}")

        if destination_dir is None:
            # Default to folder named after the archive without .zip extension
            base_name = os.path.splitext(os.path.basename(self.archive_path))[0]
            self.destination_dir = os.path.join(os.path.dirname(self.archive_path), base_name)
        else:
            self.destination_dir = os.path.abspath(destination_dir)

        self.num_parts = max(1, num_parts)
        self.enable_sparse = enable_sparse
        self._cancelled = False

    def cancel(self):
        """Signal extraction to halt after the current file."""
        self._cancelled = True

    def extract(
        self,
        progress_callback: Optional[Callable[[ExtractionProgress], None]] = None,
        part_callback: Optional[Callable[[int, int, int, str], None]] = None,
        password: Optional[str] = None,
        chunk_size: int = 512 * 1024,
    ) -> dict:
        """
        Execute in-place reverse extraction.
        Divides the archive into parts, extracts each file/part, and truncates
        the archive to free space dynamically.
        """
        os.makedirs(self.destination_dir, exist_ok=True)
        initial_archive_size = os.path.getsize(self.archive_path)
        pw_bytes = password.encode("utf-8") if password else None

        sparse_handler = NTFSSparseHandler(self.archive_path) if self.enable_sparse else None

        # Open the archive in read+binary update mode
        with open(self.archive_path, "r+b") as fp:
            zf = zipfile.ZipFile(fp, mode="r")
            if pw_bytes:
                zf.setpassword(pw_bytes)

            infolist = zf.infolist()
            total_uncompressed = sum(info.file_size for info in infolist)

            # 1. Create directory structure first
            dirs = [i for i in infolist if i.is_dir()]
            for d in dirs:
                dir_path = os.path.join(self.destination_dir, d.filename)
                if is_safe_path(self.destination_dir, dir_path):
                    os.makedirs(dir_path, exist_ok=True)

            # 2. Files to extract, sorted by header_offset DESCENDING (reverse order)
            files = [i for i in infolist if not i.is_dir()]
            files.sort(key=lambda x: x.header_offset, reverse=True)
            total_files = len(files)

            if total_files == 0:
                zf.close()
                fp.truncate(0)
                if sparse_handler:
                    sparse_handler.close()
                try:
                    os.remove(self.archive_path)
                except Exception:
                    pass
                return {
                    "status": "completed",
                    "files_completed": 0,
                    "total_files": 0,
                    "bytes_extracted": 0,
                    "space_reclaimed": initial_archive_size,
                    "destination": self.destination_dir,
                }

            # Divide files into parts/phases for structured game extraction
            effective_parts = min(self.num_parts, total_files)
            chunk_batch_size = (total_files + effective_parts - 1) // effective_parts

            bytes_extracted = 0
            files_completed = 0
            current_part_idx = 1
            part_bytes_freed = 0
            part_files_count = 0
            last_zip_size = initial_archive_size

            for idx, info in enumerate(files):
                if self._cancelled:
                    zf.close()
                    if sparse_handler:
                        sparse_handler.close()
                    return {
                        "status": "cancelled",
                        "files_completed": files_completed,
                        "total_files": total_files,
                        "bytes_extracted": bytes_extracted,
                        "destination": self.destination_dir,
                    }

                target_path = os.path.join(self.destination_dir, info.filename)
                if not is_safe_path(self.destination_dir, target_path):
                    raise SecurityError(f"Zip slip attempt detected: {info.filename}")

                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                temp_target = target_path + ".unziptmp"

                # Stream copy from compressed archive to temporary destination
                try:
                    with zf.open(info) as src, open(temp_target, "wb") as dst:
                        while True:
                            buf = src.read(chunk_size)
                            if not buf:
                                break
                            dst.write(buf)
                            bytes_extracted += len(buf)
                except Exception as e:
                    if os.path.exists(temp_target):
                        try:
                            os.remove(temp_target)
                        except Exception:
                            pass
                    if sparse_handler:
                        sparse_handler.close()
                    raise RuntimeError(f"Error extracting {info.filename}: {e}") from e

                # Replace temporary with final destination file
                if os.path.exists(target_path):
                    os.remove(target_path)
                os.replace(temp_target, target_path)

                # Preserve original timestamps
                try:
                    import time
                    dt = info.date_time
                    time_tuple = (dt[0], dt[1], dt[2], dt[3], dt[4], dt[5], 0, 0, -1)
                    mtime = time.mktime(time_tuple)
                    os.utime(target_path, (mtime, mtime))
                except Exception:
                    pass

                # Truncate archive to delete extracted file data in-place
                fp.truncate(info.header_offset)
                fp.flush()

                files_completed += 1
                part_files_count += 1
                current_archive_size = os.path.getsize(self.archive_path)
                freed_this_file = max(0, last_zip_size - current_archive_size)
                part_bytes_freed += freed_this_file
                last_zip_size = current_archive_size

                space_reclaimed = max(0, initial_archive_size - current_archive_size)
                percent = (files_completed / total_files * 100.0) if total_files else 100.0

                # Check if this part batch is completed
                is_part_end = (part_files_count >= chunk_batch_size) or (files_completed == total_files)
                part_msg = f"Part {current_part_idx}/{effective_parts}"

                if is_part_end:
                    if part_callback:
                        part_callback(
                            current_part_idx,
                            effective_parts,
                            part_bytes_freed,
                            f"Part {current_part_idx}/{effective_parts} extracted & deleted ({format_bytes(part_bytes_freed)} freed)",
                        )
                    current_part_idx = min(current_part_idx + 1, effective_parts)
                    part_bytes_freed = 0
                    part_files_count = 0

                if progress_callback:
                    progress = ExtractionProgress(
                        current_file=info.filename,
                        files_completed=files_completed,
                        total_files=total_files,
                        bytes_extracted=bytes_extracted,
                        total_uncompressed_bytes=total_uncompressed,
                        archive_size_bytes=current_archive_size,
                        initial_archive_size=initial_archive_size,
                        space_reclaimed_bytes=space_reclaimed,
                        percent_done=percent,
                        current_part=current_part_idx,
                        total_parts=effective_parts,
                        part_message=part_msg,
                    )
                    progress_callback(progress)

            zf.close()

        if sparse_handler:
            sparse_handler.close()

        # Archive has been truncated down to 0 bytes; delete the empty file
        try:
            os.remove(self.archive_path)
        except Exception:
            pass

        return {
            "status": "completed",
            "files_completed": files_completed,
            "total_files": total_files,
            "bytes_extracted": bytes_extracted,
            "space_reclaimed": initial_archive_size,
            "destination": self.destination_dir,
            "parts_completed": effective_parts,
        }
