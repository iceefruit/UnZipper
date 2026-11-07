import os
import re
import glob
import shutil
import zipfile
from typing import Callable, List, Optional
from dataclasses import dataclass
from .utils import is_safe_path, format_bytes


@dataclass
class ChunkProgress:
    part_index: int
    total_parts: int
    current_part_file: str
    files_in_part: int
    bytes_processed: int
    total_bytes: int
    percent_done: float
    message: str


class ChunkArchiver:
    """
    Creates and extracts multi-part archives designed specifically for zero-waste extraction.
    Each part is a standalone zip chunk. During extraction, each part is automatically
    deleted as soon as its files are written, capping peak extra disk usage to the size
    of a single chunk.
    """

    @staticmethod
    def create_chunked_archive(
        source_dir: str,
        output_prefix: str,
        chunk_size_mb: int = 500,
        compression: int = zipfile.ZIP_DEFLATED,
        compresslevel: int = 6,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[str]:
        """
        Compresses source_dir into multiple independent zip parts (output_prefix.part001.zip, etc.)
        so each can be extracted and deleted sequentially.
        """
        source_dir = os.path.abspath(source_dir)
        if not os.path.isdir(source_dir):
            raise NotADirectoryError(f"Source is not a directory: {source_dir}")

        chunk_size_bytes = chunk_size_mb * 1024 * 1024
        part_files: List[str] = []

        # Gather all files in source_dir
        all_entries = []
        for root, _, files in os.walk(source_dir):
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, source_dir)
                size = os.path.getsize(full_path)
                all_entries.append((full_path, rel_path, size))

        part_num = 1
        current_chunk_size = 0
        current_zf = None
        current_part_path = ""

        try:
            for idx, (full_path, rel_path, size) in enumerate(all_entries):
                # If no open zip or current chunk exceeds chunk_size_bytes, start new part
                if current_zf is None or (current_chunk_size > 0 and current_chunk_size + size > chunk_size_bytes):
                    if current_zf is not None:
                        current_zf.close()
                        part_files.append(current_part_path)

                    current_part_path = f"{output_prefix}.part{part_num:04d}.zip"
                    current_zf = zipfile.ZipFile(
                        current_part_path,
                        mode="w",
                        compression=compression,
                        compresslevel=compresslevel,
                    )
                    part_num += 1
                    current_chunk_size = 0

                current_zf.write(full_path, arcname=rel_path)
                # Estimate compressed addition
                current_chunk_size += size

                if progress_callback:
                    progress_callback(rel_path, idx + 1, len(all_entries))

            if current_zf is not None:
                current_zf.close()
                part_files.append(current_part_path)

        except Exception:
            if current_zf is not None:
                current_zf.close()
            # Clean up on failure
            for p in part_files:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
            raise

        return part_files

    @staticmethod
    def find_all_parts(first_part_or_any_part: str) -> List[str]:
        """
        Given one part file (e.g. archive.part0001.zip), find all matching parts in sequence.
        """
        path = os.path.abspath(first_part_or_any_part)
        dirname = os.path.dirname(path)
        filename = os.path.basename(path)

        # Match pattern: <prefix>.part<number>.zip
        match = re.match(r"^(.*?)\.part\d+\.zip$", filename, re.IGNORECASE)
        if not match:
            return [path]

        prefix = match.group(1)
        pattern = os.path.join(dirname, f"{prefix}.part*.zip")
        found = glob.glob(pattern)

        def sort_key(p):
            m = re.search(r"\.part(\d+)\.zip$", p, re.IGNORECASE)
            return int(m.group(1)) if m else 0

        found.sort(key=sort_key)
        return found

    @staticmethod
    def extract_and_delete_parts(
        parts: List[str],
        destination_dir: str,
        auto_delete: bool = True,
        progress_callback: Optional[Callable[[ChunkProgress], None]] = None,
    ) -> dict:
        """
        Extracts parts one by one. Deletes each part as soon as extraction of that part succeeds.
        """
        os.makedirs(destination_dir, exist_ok=True)
        total_parts = len(parts)
        total_bytes_extracted = 0
        total_parts_deleted = 0

        for idx, part_path in enumerate(parts):
            if not os.path.exists(part_path):
                continue

            part_name = os.path.basename(part_path)
            part_size = os.path.getsize(part_path)

            if progress_callback:
                progress_callback(
                    ChunkProgress(
                        part_index=idx + 1,
                        total_parts=total_parts,
                        current_part_file=part_name,
                        files_in_part=0,
                        bytes_processed=total_bytes_extracted,
                        total_bytes=0,
                        percent_done=((idx) / total_parts * 100.0),
                        message=f"Extracting {part_name}...",
                    )
                )

            # Extract this part
            with zipfile.ZipFile(part_path, "r") as zf:
                infolist = zf.infolist()
                for info in infolist:
                    target_path = os.path.join(destination_dir, info.filename)
                    if not is_safe_path(destination_dir, target_path):
                        raise SecurityError(f"Unsafe path in archive: {info.filename}")

                    if info.is_dir():
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with zf.open(info) as src, open(target_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        total_bytes_extracted += info.file_size

            # Part extracted successfully -> Delete it immediately to reclaim space!
            if auto_delete:
                try:
                    os.remove(part_path)
                    total_parts_deleted += 1
                except Exception as e:
                    pass

            if progress_callback:
                progress_callback(
                    ChunkProgress(
                        part_index=idx + 1,
                        total_parts=total_parts,
                        current_part_file=part_name,
                        files_in_part=len(infolist),
                        bytes_processed=total_bytes_extracted,
                        total_bytes=0,
                        percent_done=((idx + 1) / total_parts * 100.0),
                        message=f"Extracted and deleted {part_name} (freed {format_bytes(part_size)})",
                    )
                )

        return {
            "status": "completed",
            "total_parts": total_parts,
            "parts_deleted": total_parts_deleted,
            "total_bytes_extracted": total_bytes_extracted,
            "destination": destination_dir,
        }
