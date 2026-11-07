#!/usr/bin/env python3
"""
Register or Unregister Unziper in Windows Explorer Right-Click Context Menu.
Clean, professional cascading menu styled exactly like 7-Zip and WinRAR.
Registers in HKEY_CURRENT_USER (no admin privileges needed).
"""

import os
import sys
import winreg
import argparse


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_binary_target() -> str:
    """Return path to Unziper.exe or pythonw.exe + main.py."""
    if is_frozen():
        return sys.executable

    script_dir = os.path.dirname(os.path.abspath(__file__))
    dist_exe = os.path.join(script_dir, "dist", "Unziper.exe")
    if os.path.isfile(dist_exe):
        return dist_exe

    # Running from python script
    base_dir = os.path.dirname(sys.executable)
    pyw = os.path.join(base_dir, "pythonw.exe")
    python_exe = pyw if os.path.exists(pyw) else sys.executable
    main_py = os.path.join(script_dir, "main.py")
    return f'"{python_exe}" "{main_py}"'


def get_icon_path() -> str:
    if is_frozen():
        return sys.executable
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dist_exe = os.path.join(script_dir, "dist", "Unziper.exe")
    if os.path.isfile(dist_exe):
        return dist_exe
    base_dir = os.path.dirname(sys.executable)
    pyw = os.path.join(base_dir, "pythonw.exe")
    return pyw if os.path.exists(pyw) else sys.executable


def delete_key_tree(root, path):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)
                    delete_key_tree(root, rf"{path}\{sub}")
                except OSError:
                    break
        winreg.DeleteKey(root, path)
    except FileNotFoundError:
        pass


def register_shell() -> bool:
    bin_target = get_binary_target()
    icon_path = get_icon_path()

    print("==============================================================")
    print("  Registering Unziper Context Menu (7-Zip / WinRAR Style)")
    print("==============================================================")

    # 1. Clean cascading submenu for archives (*.zip, *.7z, *.rar, *.part*.zip)
    archive_base = r"Software\Classes\*\shell\Unziper"
    
    # Remove any old version first
    delete_key_tree(winreg.HKEY_CURRENT_USER, archive_base)
    delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\SystemFileAssociations\.zip\shell\Unziper")
    delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\shell\Unziper")

    try:
        # Parent cascading menu "Unziper"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, archive_base) as k:
            winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, "Unziper")
            winreg.SetValueEx(k, "SubCommands", 0, winreg.REG_SZ, "")
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, f'"{icon_path}",0')
            winreg.SetValueEx(k, "AppliesTo", 0, winreg.REG_SZ, 'System.FileExtension:=.zip OR System.FileExtension:=.7z OR System.FileExtension:=.rar OR System.FileName:~=".part"')

        # Subcommand 1: "Extract files..." (opens extraction dialog)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{archive_base}\shell\open") as k:
            winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, "Extract files...")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{archive_base}\shell\open\command") as k:
            if is_frozen():
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{bin_target}" "%1"')
            else:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'{bin_target} "%1"')

        # Subcommand 2: "Extract Here"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{archive_base}\shell\extracthere") as k:
            winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, "Extract Here")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{archive_base}\shell\extracthere\command") as k:
            if is_frozen():
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{bin_target}" 7z-unzip "%1" --here')
            else:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'{bin_target} 7z-unzip "%1" --here')

        # Subcommand 3: "Extract to folder"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{archive_base}\shell\extractto") as k:
            winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, "Extract to folder")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{archive_base}\shell\extractto\command") as k:
            if is_frozen():
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{bin_target}" 7z-unzip "%1"')
            else:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'{bin_target} 7z-unzip "%1"')

        # 2. Directory cascading menu for folders
        dir_base = r"Software\Classes\Directory\shell\Unziper"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, dir_base) as k:
            winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, "Unziper")
            winreg.SetValueEx(k, "SubCommands", 0, winreg.REG_SZ, "")
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, f'"{icon_path}",0')

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{dir_base}\shell\pack") as k:
            winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, "Compress to self-deleting parts...")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{dir_base}\shell\pack\command") as k:
            if is_frozen():
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{bin_target}" pack-parts "%1" "%1_parts"')
            else:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'{bin_target} pack-parts "%1" "%1_parts"')

        print("[OK] Registered clean cascading 'Unziper >' context menu.")
        print("     - Extract files...")
        print("     - Extract Here")
        print("     - Extract to folder")
        print("--------------------------------------------------------------")
        print("[SUCCESS] Context menu installed!")
        print("Note: On Windows 11, select 'Show more options' (or Shift + Right Click)")
        print("to see the full classic context menu.")
        print("==============================================================\n")
        return True
    except Exception as e:
        print(f"[FAIL] Error registering context menu: {e}")
        return False


def unregister_shell():
    print("==============================================================")
    print("  Removing Unziper from Windows Context Menu")
    print("==============================================================")
    delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\*\shell\Unziper")
    delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\SystemFileAssociations\.zip\shell\Unziper")
    delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\shell\Unziper")
    print("[SUCCESS] Unziper context menu entries cleanly removed.")
    print("==============================================================\n")


def enable_windows11_full_menu(enable: bool = True):
    """
    Enables or disables classic full context menu in Windows 11,
    making all tools (Unziper, 7-Zip, Notepad++) appear directly at top-level
    without needing to click 'Show more options'.
    """
    key_path = r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"
    if enable:
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "")
            print("[OK] Classic top-level context menu enabled. Restart Explorer or sign out to apply.")
            # Restart explorer.exe
            os.system("taskkill /f /im explorer.exe & start explorer.exe")
        except Exception as e:
            print(f"[ERROR] Failed to enable classic menu: {e}")
    else:
        delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}")
        os.system("taskkill /f /im explorer.exe & start explorer.exe")


def main():
    parser = argparse.ArgumentParser(description="Configure Unziper Windows Explorer context menu")
    parser.add_argument("--remove", action="store_true", help="Remove Unziper from right-click context menu")
    parser.add_argument("--classic-menu", action="store_true", help="Show full context menu on Windows 11 directly without 'Show more options'")
    args = parser.parse_args()

    if args.remove:
        unregister_shell()
    elif args.classic_menu:
        enable_windows11_full_menu(True)
    else:
        register_shell()


if __name__ == "__main__":
    main()
