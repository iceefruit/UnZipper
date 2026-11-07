import os
import sys
import ctypes
from typing import Optional

FSCTL_SET_SPARSE = 0x000900C4
FSCTL_SET_ZERO_DATA = 0x000980C8


class FILE_ZERO_DATA_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("FileOffset", ctypes.c_int64),
        ("BeyondFinalZero", ctypes.c_int64),
    ]


class NTFSSparseHandler:
    """
    Windows NTFS Sparse File Manager.
    Marks a file as sparse and deallocates byte ranges directly from the file system,
    immediately releasing physical disk clusters back to the free storage pool.
    """

    def __init__(self, file_path: str):
        self.file_path = os.path.abspath(file_path)
        self.is_windows = sys.platform == "win32"
        self._handle = None
        self._is_sparse = False

        if self.is_windows:
            self._init_handle()

    def _init_handle(self):
        try:
            kernel32 = ctypes.windll.kernel32
            GENERIC_READ = 0x80000000
            GENERIC_WRITE = 0x40000000
            FILE_SHARE_READ = 1
            FILE_SHARE_WRITE = 2
            OPEN_EXISTING = 3

            self._handle = kernel32.CreateFileW(
                self.file_path,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                0,
                None,
            )

            if self._handle == -1 or self._handle == 0:
                self._handle = None
                return

            # Mark file as sparse
            bytes_returned = ctypes.c_ulong()
            ok = kernel32.DeviceIoControl(
                self._handle,
                FSCTL_SET_SPARSE,
                None,
                0,
                None,
                0,
                ctypes.byref(bytes_returned),
                None,
            )
            self._is_sparse = bool(ok)
        except Exception:
            self._is_sparse = False

    def punch_hole(self, offset: int, length: int) -> bool:
        """
        Deallocate 'length' bytes starting at 'offset'.
        Releases physical disk blocks immediately on NTFS.
        """
        if not self.is_windows or not self._handle or not self._is_sparse or length <= 0:
            return False

        try:
            kernel32 = ctypes.windll.kernel32
            zero_info = FILE_ZERO_DATA_INFORMATION()
            zero_info.FileOffset = offset
            zero_info.BeyondFinalZero = offset + length

            bytes_returned = ctypes.c_ulong()
            ok = kernel32.DeviceIoControl(
                self._handle,
                FSCTL_SET_ZERO_DATA,
                ctypes.byref(zero_info),
                ctypes.sizeof(zero_info),
                None,
                0,
                ctypes.byref(bytes_returned),
                None,
            )
            return bool(ok)
        except Exception:
            return False

    def get_allocated_size(self) -> int:
        """Get actual disk space used by file (after holes are punched)."""
        if not self.is_windows or not os.path.exists(self.file_path):
            return os.path.getsize(self.file_path) if os.path.exists(self.file_path) else 0

        try:
            kernel32 = ctypes.windll.kernel32
            high_order = ctypes.c_ulong()
            low_order = kernel32.GetCompressedFileSizeW(self.file_path, ctypes.byref(high_order))
            return (high_order.value << 32) + low_order
        except Exception:
            return os.path.getsize(self.file_path)

    def close(self):
        if self.is_windows and self._handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None
