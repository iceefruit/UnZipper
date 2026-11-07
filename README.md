# Unziper: Zero-Waste Archive Tool 🚀

> **Never run out of disk space while unzipping again.**

When you unzip a standard 50 GB archive on a drive with only 60 GB free, the extraction fails because it requires **2× the disk space** (50 GB archive + 50 GB extracted files = 100 GB).

**Unziper** solves this problem by ensuring extraction frees disk space as it runs, capping extra disk overhead to zero or a single chunk.

---

## 💡 How It Works

### 1. In-Place Shrink Extraction (`unzip`)
Standard ZIP files store their Central Directory metadata at the end of the archive.
1. Unziper reads the archive index and sorts files by their internal byte offset in **reverse order** (end to beginning).
2. It extracts each file safely to disk.
3. Immediately after writing each file, it **truncates the archive in-place** (`f.truncate(offset)`).
4. The archive shrinks cluster-by-cluster on your filesystem (NTFS, APFS, ext4, etc.).
5. When the first file is extracted, the archive is 0 bytes and is cleanly deleted.

### 2. Multi-Part Chunking (`pack-parts` & `unpack-parts`)
1. Compresses large folders into independent chunk parts (e.g. 500 MB per part: `backup.part0001.zip`, `backup.part0002.zip`).
2. On extraction, each part is unpacked and **automatically deleted immediately** before moving to the next part.
3. Your peak extra disk consumption never exceeds the size of **a single chunk**.

---

## 🖥️ Graphical Interface (GUI)

Simply run `main.py` without arguments:

```bash
python main.py
```

Features:
- **Real-time Metrics**: Live progress bar, space reclaimed counter, and remaining archive size.
- **Smart Detection**: Detects both regular `.zip` archives and multi-part `.part*.zip` files.
- **Background Worker**: Fully responsive UI that never freezes during large multi-gigabyte extractions.

---

## ⚡ Command Line (CLI)

### In-Place Shrink Unzip (Zero 2× Space)
```bash
python main.py unzip my_large_archive.zip
```
Custom destination:
```bash
python main.py unzip my_large_archive.zip -d /path/to/extracted
```

### Create Multi-Part Zero-Waste Archive
```bash
python main.py pack-parts /path/to/large_folder my_archive -s 500
```
*(Creates `my_archive.part0001.zip`, `my_archive.part0002.zip`, etc., capped at 500 MB each)*

### Extract & Auto-Delete Multi-Part Archive
```bash
python main.py unpack-parts my_archive.part0001.zip -d /path/to/extracted
```

---

## 🛡️ Safety & Integrity
- **Zip-Slip Protection**: Validates all paths to prevent malicious directory traversal.
- **Atomic File Writing**: Extracts to a temporary file first, verifies output, and only then renames and truncates the archive.
- **Timestamp Preservation**: Preserves original file modification timestamps.
- **Zero Third-Party Dependencies**: Built with 100% Python standard library (`zipfile`, `tkinter`, `shutil`).
