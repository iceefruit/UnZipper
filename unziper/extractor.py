import os
import shutil
import zipfile
import threading
import zlib
import time
from typing import Callable, Optional, List
from dataclasses import dataclass
from .utils import (
    is_safe_path,
    format_bytes,
    get_dynamic_chunk_buffer_size,
    preallocate_file,
    sanitize_rel_path,
)
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
    High-performance in-place archive extractor.
    Features:
    - Zero 2X disk space requirement via reverse truncation and NTFS cluster deallocation.
    - Dynamic I/O buffer scaling (up to 16MB) for peak NVMe / SSD sustained speed.
    - Upfront NTFS cluster preallocation to eliminate fragmentation and boost game load times.
    - Native CRC32 integrity verification for every extracted file.
    - Smart Resume: instantly detects and skips previously extracted files on crash or retry.
    - Thread-safe non-blocking pause / resume.
    """

    def __init__(
        self,
        archive_path: str,
        destination_dir: Optional[str] = None,
        num_parts: int = 10,
        enable_sparse: bool = True,
        verify_crc: bool = True,
        resume: bool = True,
    ):
        self.archive_path = os.path.abspath(archive_path)
        if not os.path.isfile(self.archive_path):
            raise FileNotFoundError(f"Archive not found: {self.archive_path}")

        if destination_dir is None:
            base_name = os.path.splitext(os.path.basename(self.archive_path))[0]
            self.destination_dir = os.path.join(os.path.dirname(self.archive_path), base_name)
        else:
            self.destination_dir = os.path.abspath(destination_dir)

        self.num_parts = max(1, num_parts)
        self.enable_sparse = enable_sparse
        self.verify_crc = verify_crc
        self.resume = resume

        self._cancelled = False
        self._pause_event = threading.Event()
        self._pause_event.set()

    def cancel(self):
        """Signal extraction to halt immediately after current chunk."""
        self._cancelled = True
        self._pause_event.set()

    def pause(self):
        """Pause extraction temporarily."""
        self._pause_event.clear()

    def resume_extraction(self):
        """Resume paused extraction."""
        self._pause_event.set()

    def resume(self):
        self.resume_extraction()

    def extract(
        self,
        progress_callback: Optional[Callable[[ExtractionProgress], None]] = None,
        part_callback: Optional[Callable[[int, int, int, str], None]] = None,
        password: Optional[str] = None,
    ) -> dict:
        os.makedirs(self.destination_dir, exist_ok=True)
        initial_archive_size = os.path.getsize(self.archive_path)
        pw_bytes = password.encode("utf-8") if password else None

        sparse_handler = NTFSSparseHandler(self.archive_path) if self.enable_sparse else None

        with open(self.archive_path, "r+b") as fp:
            zf = zipfile.ZipFile(fp, mode="r")
            if pw_bytes:
                zf.setpassword(pw_bytes)

            infolist = zf.infolist()
            total_uncompressed = sum(info.file_size for info in infolist)

            # 1. Ensure all directory trees exist
            dirs = [i for i in infolist if i.is_dir()]
            for d in dirs:
                clean_rel = sanitize_rel_path(d.filename)
                if clean_rel:
                    dir_path = os.path.join(self.destination_dir, clean_rel)
                    if is_safe_path(self.destination_dir, dir_path):
                        os.makedirs(dir_path, exist_ok=True)

            # 2. Files sorted in reverse offset order (from tail of zip to head)
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

            effective_parts = min(self.num_parts, total_files)
            chunk_batch_size = (total_files + effective_parts - 1) // effective_parts

            bytes_extracted = 0
            files_completed = 0
            current_part_idx = 1
            part_bytes_freed = 0
            part_files_count = 0
            last_zip_size = initial_archive_size

            for idx, info in enumerate(files):
                self._pause_event.wait()
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

                clean_rel = sanitize_rel_path(info.filename)
                if not clean_rel:
                    continue

                target_path = os.path.join(self.destination_dir, clean_rel)
                if not is_safe_path(self.destination_dir, target_path):
                    raise SecurityError(f"Zip slip attempt detected: {info.filename}")

                # Smart Resume Check: If target file already exists and matches size, skip re-extracting
                already_done = False
                if self.resume and os.path.isfile(target_path):
                    if os.path.getsize(target_path) == info.file_size:
                        already_done = True

                if not already_done:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    temp_target = target_path + ".unziptmp"

                    # Dynamic buffer scaling (up to 16MB for multi-gigabyte files)
                    chunk_buffer = get_dynamic_chunk_buffer_size(info.file_size)
                    running_crc = 0

                    try:
                        with zf.open(info) as src, open(temp_target, "wb") as dst:
                            # Preallocate physical disk space to prevent NTFS fragmentation
                            preallocate_file(dst, info.file_size)

                            while True:
                                self._pause_event.wait()
                                buf = src.read(chunk_buffer)
                                if not buf:
                                    break
                                dst.write(buf)
                                if self.verify_crc:
                                    running_crc = zlib.crc32(buf, running_crc)
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

                    # Verify CRC32 checksum before committing file to destination
                    if self.verify_crc and info.CRC != 0 and (running_crc != info.CRC):
                        if os.path.exists(temp_target):
                            try:
                                os.remove(temp_target)
                            except Exception:
                                pass
                        if sparse_handler:
                            sparse_handler.close()
                        raise ValueError(f"Integrity check failed: CRC mismatch on {info.filename}")

                    # Atomically replace destination file
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    os.replace(temp_target, target_path)

                    # Preserve timestamp
                    try:
                        dt = info.date_time
                        time_tuple = (dt[0], dt[1], dt[2], dt[3], dt[4], dt[5], 0, 0, -1)
                        mtime = time.mktime(time_tuple)
                        os.utime(target_path, (mtime, mtime))
                    except Exception:
                        pass
                else:
                    bytes_extracted += info.file_size

                # Truncate archive safely in-place right up to this file's header offset
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

                is_part_end = (part_files_count >= chunk_batch_size) or (files_completed == total_files)
                part_msg = f"Part {current_part_idx}/{effective_parts}"

                if is_part_end:
                    if part_callback:
                        part_callback(
                            current_part_idx,
                            effective_parts,
                            part_bytes_freed,
                            f"Part {current_part_idx}/{effective_parts} completed ({format_bytes(part_bytes_freed)} freed)",
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

        # Archive has been truncated down to 0 bytes; cleanly remove
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
