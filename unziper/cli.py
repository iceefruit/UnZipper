import os
import sys
import argparse
from typing import Optional
from .extractor import InPlaceExtractor, ExtractionProgress
from .chunker import ChunkArchiver, ChunkProgress
from .utils import format_bytes, get_free_disk_space


def render_progress_bar(percent: float, length: int = 25) -> str:
    filled = int(length * percent / 100.0)
    bar = "=" * filled + "-" * (length - filled)
    return f"[{bar}] {percent:5.1f}%"


def cli_extract_inplace(
    archive_path: str,
    dest_dir: Optional[str],
    password: Optional[str] = None,
    num_parts: int = 10,
):
    print(f"\n==================================================================")
    print(f"  Unziper: Zero 2X Space Game & Big Archive Extractor")
    print(f"==================================================================")
    print(f"Archive:          {archive_path}")
    orig_size = os.path.getsize(archive_path)
    print(f"Original Size:    {format_bytes(orig_size)}")

    extractor = InPlaceExtractor(archive_path, dest_dir, num_parts=num_parts)
    print(f"Destination:      {extractor.destination_dir}")
    print(f"Available Space:  {format_bytes(get_free_disk_space(extractor.destination_dir))}")
    print(f"Partition Plan:   Dividing extraction into ~{num_parts} parts")
    print(f"------------------------------------------------------------------")
    print(f"Extraction underway: Unzips part-by-part & deletes extracted data!")
    print(f"Your disk space will be continuously reclaimed in real-time.\n")

    def on_part_done(part_idx: int, total_parts: int, freed_bytes: int, msg: str):
        # Print a clear milestone when a part finishes
        sys.stdout.write(f"\n[PART COMPLETED] {msg}\n")
        sys.stdout.flush()

    def on_progress(p: ExtractionProgress):
        pbar = render_progress_bar(p.percent_done)
        truncated_name = p.current_file if len(p.current_file) <= 25 else "..." + p.current_file[-22:]
        msg = (
            f"\r{pbar} | Part {p.current_part}/{p.total_parts} "
            f"| Freed: {format_bytes(p.space_reclaimed_bytes)} "
            f"| Zip: {format_bytes(p.archive_size_bytes)} "
            f"| {truncated_name:<25}"
        )
        sys.stdout.write(msg)
        sys.stdout.flush()

    try:
        result = extractor.extract(
            progress_callback=on_progress,
            part_callback=on_part_done,
            password=password,
        )
        print("\n" + "=" * 66)
        if result.get("status") == "completed":
            print(f"[SUCCESS] Game / Archive successfully extracted and cleaned up!")
            print(f"Parts Processed:   {result.get('parts_completed', num_parts)} parts")
            print(f"Files Extracted:   {result['files_completed']} files")
            print(f"Total Uncompressed:{format_bytes(result['bytes_extracted'])}")
            print(f"Total Space Freed: {format_bytes(result['space_reclaimed'])} (Archive 100% deleted)")
            print(f"Output Directory:  {result['destination']}")
        else:
            print(f"[CANCELLED] Extraction stopped early.")
        print("=" * 66 + "\n")
    except KeyboardInterrupt:
        print("\n\n[WARNING] Process interrupted by user.")
        extractor.cancel()
    except Exception as e:
        print(f"\n\n[ERROR] Extraction failed: {e}")
        sys.exit(1)


def cli_create_chunks(source_dir: str, output_prefix: str, chunk_size_mb: int = 0):
    print(f"\n==================================================================")
    print(f"  Unziper: Create Multi-Part Zero-Waste Archive")
    print(f"==================================================================")
    print(f"Source Folder:  {source_dir}")
    print(f"Output Prefix:  {output_prefix}")
    target_str = f"{chunk_size_mb} MB per part" if chunk_size_mb > 0 else "Auto-Optimized (smart WiFi/disk balance)"
    print(f"Chunk Target:   {target_str}")
    print(f"------------------------------------------------------------------")

    def on_progress(rel_path, current_idx, total_files):
        pbar = render_progress_bar((current_idx / total_files) * 100.0)
        disp_name = rel_path if len(rel_path) <= 30 else "..." + rel_path[-27:]
        sys.stdout.write(f"\r{pbar} | Packing {current_idx}/{total_files} | {disp_name:<30}")
        sys.stdout.flush()

    try:
        parts = ChunkArchiver.create_chunked_archive(
            source_dir=source_dir,
            output_prefix=output_prefix,
            chunk_size_mb=chunk_size_mb,
            progress_callback=on_progress,
        )
        print("\n\n" + "=" * 66)
        print(f"[SUCCESS] Successfully created {len(parts)} part archives:")
        total_size = 0
        for p in parts:
            sz = os.path.getsize(p)
            total_size += sz
            print(f"  - {os.path.basename(p)} ({format_bytes(sz)})")
        print(f"Total Size: {format_bytes(total_size)}")
        print("=" * 66 + "\n")
    except Exception as e:
        print(f"\n\n[ERROR] Archiving failed: {e}")
        sys.exit(1)


def cli_extract_chunks(part_path: str, dest_dir: str, auto_delete: bool = True):
    print(f"\n==================================================================")
    print(f"  Unziper: Multi-Part Sequential Auto-Delete Extractor")
    print(f"==================================================================")
    parts = ChunkArchiver.find_all_parts(part_path)
    if not parts:
        print(f"[ERROR] No matching parts found for: {part_path}")
        sys.exit(1)

    print(f"Found {len(parts)} parts.")
    print(f"Destination:  {dest_dir}")
    print(f"Auto-Delete:  {'ENABLED (Parts deleted as unzipped)' if auto_delete else 'DISABLED'}")
    print(f"------------------------------------------------------------------")

    def on_progress(p: ChunkProgress):
        pbar = render_progress_bar(p.percent_done)
        print(f"{pbar} Part {p.part_index}/{p.total_parts}: {p.message}")

    try:
        result = ChunkArchiver.extract_and_delete_parts(
            parts=parts,
            destination_dir=dest_dir,
            auto_delete=auto_delete,
            progress_callback=on_progress,
        )
        print("\n" + "=" * 66)
        print(f"[SUCCESS] Multi-part extraction completed!")
        print(f"Parts Processed:   {result['total_parts']}")
        print(f"Parts Deleted:     {result['parts_deleted']}")
        print(f"Total Extracted:   {format_bytes(result['total_bytes_extracted'])}")
        print(f"Destination:       {result['destination']}")
        print("=" * 66 + "\n")
    except Exception as e:
        print(f"\n[ERROR] Multi-part extraction failed: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="unziper",
        description="Unziper: Zero-Waste Game & Archive Extractor (Never waste 2x disk space unzipping)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # In-place unzipper
    p_unzip = subparsers.add_parser("unzip", help="Unzip a large game or archive in-place, deleting parts as it extracts")
    p_unzip.add_argument("archive", help="Path to the .zip archive")
    p_unzip.add_argument("-d", "--dest", help="Destination folder (defaults to folder named after archive)")
    p_unzip.add_argument("--parts", type=int, default=10, help="Divide archive into N logical parts/milestones (default: 10)")
    p_unzip.add_argument("-p", "--password", help="Archive password if encrypted")
    p_unzip.add_argument("--dialog", action="store_true", help="Display 7-Zip style extraction progress window")

    # 7-Zip style dialog shortcut (used by context menu)
    p_7z = subparsers.add_parser("7z-unzip", help="Launch 7-Zip style extraction progress window directly")
    p_7z.add_argument("archive", help="Path to archive")
    p_7z.add_argument("-d", "--dest", help="Destination directory")
    p_7z.add_argument("--here", action="store_true", help="Extract to current directory")

    # Split-zip creator
    p_pack = subparsers.add_parser("pack-parts", help="Compress a game folder into self-deleting multi-parts")
    p_pack.add_argument("source", help="Source folder to compress")
    p_pack.add_argument("output", help="Output archive prefix (e.g. game_backup)")
    p_pack.add_argument("-s", "--chunk-size", type=int, default=0, help="Part size in MB (0 for smart auto-sizing e.g. 500MB-1GB, default: 0)")

    # Split-unzip extractor
    p_unpack = subparsers.add_parser("unpack-parts", help="Extract and auto-delete multi-part archive chunks")
    p_unpack.add_argument("first_part", help="Path to the first part or any part (.part0001.zip)")
    p_unpack.add_argument("-d", "--dest", required=True, help="Destination directory")
    p_unpack.add_argument("--keep", action="store_true", help="Keep part files instead of auto-deleting them")

    if len(sys.argv) == 1:
        # Launch GUI if no arguments passed
        from .gui import launch_gui
        launch_gui()
        return

    # If first argument is an existing file or path (e.g. dragged onto exe or from right-click)
    if len(sys.argv) == 2 and os.path.isfile(sys.argv[1]):
        from .gui import launch_gui
        launch_gui(sys.argv[1])
        return

    args = parser.parse_args()

    if args.command == "unzip":
        if args.dialog:
            from .dialog import show_7zip_dialog
            show_7zip_dialog(args.archive, args.dest)
        else:
            cli_extract_inplace(args.archive, args.dest, args.password, num_parts=args.parts)
    elif args.command == "7z-unzip":
        from .dialog import show_7zip_dialog
        dest = args.dest
        if args.here:
            dest = os.path.dirname(os.path.abspath(args.archive))
        show_7zip_dialog(args.archive, dest)
    elif args.command == "pack-parts":
        cli_create_chunks(args.source, args.output, args.chunk_size)
    elif args.command == "unpack-parts":
        cli_extract_chunks(args.first_part, args.dest, auto_delete=not args.keep)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
