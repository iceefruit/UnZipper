#!/usr/bin/env python3
"""
Register or Unregister Unziper in Windows Explorer Right-Click Context Menu.
Mimics 7-Zip right-click integration without needing Administrator privileges
(registers in HKEY_CURRENT_USER).
"""

import os
import sys
import winreg
import argparse


def get_python_exe() -> str:
    """Return pythonw.exe if available to avoid flashing console window."""
    base_dir = os.path.dirname(sys.executable)
    pyw = os.path.join(base_dir, "pythonw.exe")
    if os.path.exists(pyw):
        return pyw
    return sys.executable


def register_shell():
    python_exe = get_python_exe()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(script_dir, "main.py")

    if not os.path.isfile(main_py):
        print(f"[ERROR] Could not find main.py at {main_py}")
        return False

    print("==============================================================")
    print("  Registering Unziper in Windows Right-Click Context Menu")
    print("==============================================================")
    print(f"Python Launcher: {python_exe}")
    print(f"Target Script:   {main_py}")
    print("--------------------------------------------------------------")

    # 1. Right click on .zip files -> "Extract with Unziper (Zero-Waste)"
    zip_shell_base = r"Software\Classes\SystemFileAssociations\.zip\shell"

    entries = [
        (
            rf"{zip_shell_base}\UnziperExtract",
            "Extract with Unziper (Zero-Waste)",
            f'"{python_exe}" "{main_py}" 7z-unzip "%1"',
        ),
        (
            rf"{zip_shell_base}\UnziperExtractHere",
            "Extract Here (Unziper Zero-Waste)",
            f'"{python_exe}" "{main_py}" 7z-unzip "%1" --here',
        ),
        (
            r"Software\Classes\Directory\shell\UnziperPack",
            "Unziper: Compress to Self-Deleting Parts",
            f'"{python_exe}" "{main_py}" pack-parts "%1" "%1_parts"',
        ),
    ]

    for key_path, menu_title, command_str in entries:
        try:
            # Create shell item key
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, menu_title)
                # Set icon if python.exe or shell icon
                winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, f'"{python_exe}",0')

            # Create command subkey
            cmd_path = rf"{key_path}\command"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_path) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, command_str)

            print(f"[OK] Registered: '{menu_title}'")
        except Exception as e:
            print(f"[FAIL] Error registering {key_path}: {e}")

    print("--------------------------------------------------------------")
    print("[SUCCESS] Context menu installed! Right-click any .zip file")
    print("or game archive in File Explorer to extract with Unziper!")
    print("==============================================================\n")
    return True


def unregister_shell():
    print("==============================================================")
    print("  Removing Unziper from Windows Right-Click Context Menu")
    print("==============================================================")

    keys_to_delete = [
        r"Software\Classes\SystemFileAssociations\.zip\shell\UnziperExtract\command",
        r"Software\Classes\SystemFileAssociations\.zip\shell\UnziperExtract",
        r"Software\Classes\SystemFileAssociations\.zip\shell\UnziperExtractHere\command",
        r"Software\Classes\SystemFileAssociations\.zip\shell\UnziperExtractHere",
        r"Software\Classes\Directory\shell\UnziperPack\command",
        r"Software\Classes\Directory\shell\UnziperPack",
    ]

    for kpath in keys_to_delete:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, kpath)
            print(f"[REMOVED] {kpath}")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[ERROR] Failed to delete {kpath}: {e}")

    print("--------------------------------------------------------------")
    print("[SUCCESS] Unziper context menu entries cleanly removed.")
    print("==============================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Configure Unziper Windows Explorer context menu")
    parser.add_argument("--remove", action="store_true", help="Remove Unziper from right-click context menu")
    args = parser.parse_args()

    if args.remove:
        unregister_shell()
    else:
        register_shell()


if __name__ == "__main__":
    main()
