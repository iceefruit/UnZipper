# Unziper: Zero-Waste Game & Large Archive Extractor 🎮📦

> **Never run out of disk space while extracting giant game files again.**

### The Problem
Imagine you download a **big 80 GB game** in a `.zip` archive on a drive with only 90 GB of free space.
Standard extraction fails immediately with a **"Disk Full" error** because standard extractors need **2× the space** (80 GB archive + 80 GB unzipped game = 160 GB).

### The Solution: Unziper
Unziper divides the extraction into parts and **automatically deletes / truncates whatever is unzipped as it extracts**.
The archive shrinks in real-time right on your disk, so the extracted game files seamlessly replace the archive with **zero extra space wasted**.

---

## ⚡ Key Capabilities

### 1. Big Game In-Place Shrink Extraction
- Automatically partitions large game archives into logical parts/milestones.
- Extracts files in reverse order and immediately calls file system truncation (`ftruncate`/`SetEndOfFile`) and NTFS cluster deallocation (`FSCTL_SET_ZERO_DATA`).
- As textures, shaders, audio, and game binaries are unzipped to your game folder, the `.zip` file shrinks cluster-by-cluster on your disk.
- When the first file is extracted, the archive is 0 bytes and deleted.

```bash
# Unzip a big game file without needing 2x space
python main.py unzip "BigGame.zip"

# Divide into 15 progress parts
python main.py unzip "BigGame.zip" --parts 15
```

### 2. Multi-Part Game Archiving (Auto-Deleting Chunks)
Want to share a 100 GB game or folder with someone low on disk space?
- Compress it into self-contained parts (e.g. 1 GB each: `game.part0001.zip`, `game.part0002.zip`).
- When extracting, Unziper unzips `part0001.zip`, **deletes it immediately**, then unzips `part0002.zip` and deletes it.
- Disk usage never exceeds the size of a single part!

```bash
# Create 1GB part archives from game directory
python main.py pack-parts "C:\Games\MyGame" "MyGameBackup" -s 1000

# Extract and auto-delete parts one by one
python main.py unpack-parts "MyGameBackup.part0001.zip" -d "C:\Games\RestoredGame"
```

---

## 🗂️ Windows Explorer Integration (7-Zip & WinRAR Style)

Unziper integrates seamlessly into Windows Explorer as a clean cascading submenu:

```text
Unziper  >
    ├── Extract files...       (Opens clean minimal dialog)
    ├── Extract Here           (Extracts directly to current folder)
    └── Extract to folder      (Extracts to <ArchiveName>\)
```

Run this once to register (no administrator rights needed):
```powershell
python register_context_menu.py
```
*(To show directly on Windows 11 top-level menu without clicking "Show more options", pass `--classic-menu`)*

---

## 🚀 High-Performance Engine Under The Hood

Without cluttering the clean, minimal UI, Unziper includes enterprise-grade optimizations:

- **Dynamic I/O Scaling (up to 16MB buffers)**: Adapts read/write buffer sizes dynamically from 64KB for small scripts up to 16MB for multi-gigabyte game binaries, maximizing NVMe/SSD sustained bus throughput.
- **Physical NTFS Pre-allocation**: Pre-allocates contiguous disk clusters upfront before writing, eliminating file fragmentation and significantly speeding up subsequent game loading times.
- **Hardware-Accelerated CRC32 Verification**: Computes running CRC32 checksums in native C speed during decompression to guarantee 100% bit-for-bit file integrity before any archive truncation occurs.
- **Smart Crash Resume**: If an extraction of a massive 100GB game is interrupted (due to power loss, sleep, or cancellation), Unziper verifies already extracted files in seconds and resumes right where it left off.
- **Windows Reserved Path Protection**: Sanitizes DOS-inherited reserved names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`, trailing dots/spaces) to prevent Windows filesystem locks and path traversal vulnerabilities.
- **Zero 2X Space**: Truncates archive in-place as files are written and leverages Windows NTFS cluster deallocation (`FSCTL_SET_ZERO_DATA`).

---

## 🖥️ Minimal Native Windows UI

- Pure native Windows controls (`vista` style theme) with zero AI banners or clutter.
- Clean 3-step wizard: **Select $\rightarrow$ Extracting $\rightarrow$ Finished**.
- Shows a prominent **"Finish"** button (and **"Open Folder"**) when done, just like standard Windows installers.


---

## 🛡️ Safety & Integrity
- **Zip-Slip Protection**: Hardened against path traversal vulnerabilities.
- **Atomic Safe Writes**: Each file is extracted to a temporary state and verified before the archive is truncated.
- **Timestamp Preservation**: Preserves original game file creation and modification timestamps.
- **Pure Standard Library**: No external dependencies or complicated setup required.
