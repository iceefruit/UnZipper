import os
import shutil
import tempfile
import unittest
import zipfile

from unziper.extractor import InPlaceExtractor
from unziper.chunker import ChunkArchiver
from unziper.utils import format_bytes, is_safe_path


class TestUnziper(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_utils(self):
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(1024), "1.00 KB")
        self.assertEqual(format_bytes(1024 * 1024), "1.00 MB")
        self.assertEqual(format_bytes(1024 * 1024 * 1024), "1.00 GB")

        base = os.path.join(self.temp_dir, "base")
        os.makedirs(base, exist_ok=True)
        safe = os.path.join(base, "sub", "file.txt")
        unsafe = os.path.join(base, "..", "escape.txt")
        self.assertTrue(is_safe_path(base, safe))
        self.assertFalse(is_safe_path(base, unsafe))

    def test_inplace_extraction_and_shrinkage(self):
        zip_path = os.path.join(self.temp_dir, "test.zip")
        dest_dir = os.path.join(self.temp_dir, "output")

        # Create zip with multiple files
        test_files = {
            "alpha.txt": b"Alpha data " * 500,
            "subfolder/beta.txt": b"Beta data in nested folder " * 800,
            "subfolder/gamma.bin": b"\x00\x01\x02\x03" * 2000,
        }

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fname, data in test_files.items():
                zf.writestr(fname, data)

        initial_size = os.path.getsize(zip_path)
        self.assertGreater(initial_size, 0)

        shrink_sizes = []
        parts_seen = []

        def on_progress(p):
            shrink_sizes.append(p.archive_size_bytes)

        def on_part(part_idx, total_parts, freed, msg):
            parts_seen.append(part_idx)

        extractor = InPlaceExtractor(zip_path, dest_dir, num_parts=2)
        result = extractor.extract(progress_callback=on_progress, part_callback=on_part)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["files_completed"], 3)
        self.assertGreater(len(parts_seen), 0)
        self.assertFalse(os.path.exists(zip_path), "Archive should be deleted at end")

        # Verify all extracted content matches original
        for fname, expected_data in test_files.items():
            extracted_path = os.path.join(dest_dir, fname)
            self.assertTrue(os.path.isfile(extracted_path), f"Missing {fname}")
            with open(extracted_path, "rb") as f:
                self.assertEqual(f.read(), expected_data)

        # Verify sizes strictly decreased during extraction
        for i in range(len(shrink_sizes) - 1):
            self.assertGreaterEqual(shrink_sizes[i], shrink_sizes[i + 1])

    def test_chunk_archiver_create_and_extract_delete(self):
        src_dir = os.path.join(self.temp_dir, "src_data")
        os.makedirs(src_dir, exist_ok=True)

        for i in range(4):
            with open(os.path.join(src_dir, f"file_{i}.dat"), "wb") as f:
                f.write(f"Part payload {i} ".encode() * 20000)

        out_prefix = os.path.join(self.temp_dir, "split_arch")
        parts = ChunkArchiver.create_chunked_archive(src_dir, out_prefix, chunk_size_mb=1)
        self.assertGreater(len(parts), 1, "Should create multiple parts")

        for p in parts:
            self.assertTrue(os.path.isfile(p))

        # Extract and auto-delete
        dest_dir = os.path.join(self.temp_dir, "restored_data")
        res = ChunkArchiver.extract_and_delete_parts(parts, dest_dir, auto_delete=True)

        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["parts_deleted"], len(parts))

        # Confirm all parts are deleted
        for p in parts:
            self.assertFalse(os.path.exists(p), f"Part {p} was not deleted!")

        # Confirm restored files
        for i in range(4):
            restored_file = os.path.join(dest_dir, f"file_{i}.dat")
            self.assertTrue(os.path.isfile(restored_file))


if __name__ == "__main__":
    unittest.main()
