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

## 🖥️ Graphical User Interface (GUI)

Simply double-click or run:
```bash
python main.py
```

- **Live Partition Tracking**: Displays the current part number and size freed.
- **Space Reclaimed Meter**: Real-time counter showing megabytes/gigabytes freed back to Windows.
- **Responsive Threading**: Extraction runs on background threads, ensuring the UI remains smooth even during multi-hour 100 GB game unpacks.

---

## 🛡️ Safety & Integrity
- **Zip-Slip Protection**: Hardened against path traversal vulnerabilities.
- **Atomic Safe Writes**: Each file is extracted to a temporary state and verified before the archive is truncated.
- **Timestamp Preservation**: Preserves original game file creation and modification timestamps.
- **Pure Standard Library**: No external dependencies or complicated setup required.
