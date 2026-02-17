import ctypes
import time
import os
import stat
import subprocess
import re
import sys
import configparser

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")

def load_config():
    """Load settings from config.ini"""
    if not os.path.exists(CONFIG_FILE):
        print(f"X Config file not found: {CONFIG_FILE}")
        print("  Please create a config.ini file next to this script.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    config = configparser.RawConfigParser()
    config.read(CONFIG_FILE)

    try:
        settings = {
            "resolution_width":   config.getint("display", "resolution_width"),
            "resolution_height":  config.getint("display", "resolution_height"),
            "refresh_rate":       config.getint("display", "refresh_rate"),
            "monitor_index":      config.getint("display", "monitor_index"),
            "monitor_device_id":  config.get("display", "monitor_device_id").strip(),
            "monitor_config_id":  config.get("display", "monitor_config_id").strip(),

            "valorant_user_ids": [
                uid.strip()
                for uid in config.get("valorant", "user_ids").replace("\n", "").split(",")
                if uid.strip()
            ],

            "riot_client_exe":     config.get("paths", "riot_client_exe").strip(),
            "valorant_config_dir": config.get("paths", "valorant_config_dir").strip(),
        }
        settings["riot_client_dir"] = os.path.dirname(settings["riot_client_exe"])
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        print(f"X Config file error: {e}")
        print("  Please check that config.ini has all required sections and keys.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    return settings


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin():
    """Re-launch the script elevated. Window closes automatically when done."""
    try:
        if sys.argv[-1] != 'asadmin':
            script = os.path.abspath(sys.argv[0])
            params = f'/c python "{script}" asadmin'
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", params, None, 1)
            sys.exit(0)
    except Exception as e:
        print(f"Failed to elevate privileges: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)


def set_file_readonly(path, readonly):
    """Set or clear the read-only attribute on a file."""
    current = os.stat(path).st_mode
    if readonly:
        os.chmod(path, current & ~stat.S_IWRITE)
    else:
        os.chmod(path, current | stat.S_IWRITE)


def update_valorant_config(cfg):
    """Update VALORANT GameUserSettings.ini for all accounts, then lock the file read-only."""
    width         = cfg["resolution_width"]
    height        = cfg["resolution_height"]
    user_ids      = cfg["valorant_user_ids"]
    config_dir    = os.path.expandvars(cfg["valorant_config_dir"])
    monitor_id    = cfg["monitor_config_id"]
    monitor_index = cfg["monitor_index"]

    updated_count = 0
    failed_count  = 0

    for user_id in user_ids:
        config_path = os.path.join(config_dir, user_id, "WindowsClient", "GameUserSettings.ini")

        if not os.path.exists(config_path):
            print(f"  ! Config file not found: {config_path}")
            failed_count += 1
            continue

        try:
            # Ensure the file is writable before editing
            set_file_readonly(config_path, False)

            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original = content

            def set_key(text, pattern, replacement, fallback):
                """Replace key if present, otherwise append it to end of file."""
                result, n = re.subn(pattern, replacement, text)
                if n == 0:
                    result = text.rstrip('\n') + f'\n{fallback}\n'
                return result

            # Fullscreen mode: 0=fullscreen, 1=borderless, 2=windowed
            content = set_key(content, r'FullscreenMode=\d+',             'FullscreenMode=0',             'FullscreenMode=0')
            content = set_key(content, r'LastConfirmedFullscreenMode=\d+', 'LastConfirmedFullscreenMode=0', 'LastConfirmedFullscreenMode=0')
            content = set_key(content, r'PreferredFullscreenMode=\d+',     'PreferredFullscreenMode=0',     'PreferredFullscreenMode=0')

            # Letterbox
            content = set_key(content, r'bLastConfirmedShouldLetterbox=\w+', 'bLastConfirmedShouldLetterbox=False', 'bLastConfirmedShouldLetterbox=False')
            content = set_key(content, r'bShouldLetterbox=\w+',              'bShouldLetterbox=False',              'bShouldLetterbox=False')

            # Resolution
            content = re.sub(r'ResolutionSizeX=\d+',                      f'ResolutionSizeX={width}',                      content)
            content = re.sub(r'ResolutionSizeY=\d+',                      f'ResolutionSizeY={height}',                     content)
            content = re.sub(r'LastUserConfirmedResolutionSizeX=\d+',     f'LastUserConfirmedResolutionSizeX={width}',      content)
            content = re.sub(r'LastUserConfirmedResolutionSizeY=\d+',     f'LastUserConfirmedResolutionSizeY={height}',     content)
            content = re.sub(r'DesiredScreenWidth=\d+',                   f'DesiredScreenWidth={width}',                   content)
            content = re.sub(r'DesiredScreenHeight=\d+',                  f'DesiredScreenHeight={height}',                 content)
            content = re.sub(r'LastUserConfirmedDesiredScreenWidth=\d+',  f'LastUserConfirmedDesiredScreenWidth={width}',   content)
            content = re.sub(r'LastUserConfirmedDesiredScreenHeight=\d+', f'LastUserConfirmedDesiredScreenHeight={height}', content)

            # Monitor
            mid_esc = monitor_id.replace('\\', '\\\\')
            content = re.sub(r'DefaultMonitorDeviceID="[^"]*"',              f'DefaultMonitorDeviceID="{mid_esc}"',              content)
            content = re.sub(r'DefaultMonitorIndex=\d+',                     f'DefaultMonitorIndex={monitor_index}',              content)
            content = re.sub(r'LastConfirmedDefaultMonitorDeviceID="[^"]*"', f'LastConfirmedDefaultMonitorDeviceID="{mid_esc}"',  content)
            content = re.sub(r'LastConfirmedDefaultMonitorIndex=\d+',        f'LastConfirmedDefaultMonitorIndex={monitor_index}', content)

            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Lock file so Valorant can't overwrite settings on launch
            set_file_readonly(config_path, True)

            changed = content != original
            print(f"  + Updated: {user_id[:8]}... {'(changes applied)' if changed else '(already correct)'}")

            # Print the key values that were set so you can verify
            verify_keys = {
                'FullscreenMode', 'ResolutionSizeX', 'ResolutionSizeY', 'bShouldLetterbox'
            }
            for line in content.splitlines():
                key = line.split('=')[0].strip() if '=' in line else ''
                if key in verify_keys:
                    print(f"      {line.strip()}")

            updated_count += 1

        except Exception as e:
            print(f"  X Failed: {user_id[:8]}...: {e}")
            failed_count += 1

    print(f"\n+ Updated {updated_count} account(s)")
    if failed_count > 0:
        print(f"X Failed  {failed_count} account(s)")
    print(f"  - FullscreenMode=0 (exclusive fullscreen)")
    print(f"  - Letterbox disabled")
    print(f"  - Resolution set to {width}x{height}")
    print(f"  - Config files locked read-only")
    return updated_count > 0


def change_resolution(cfg):
    """Change display resolution and refresh rate."""
    width        = cfg["resolution_width"]
    height       = cfg["resolution_height"]
    refresh_rate = cfg["refresh_rate"]

    user32 = ctypes.windll.user32

    class DEVMODE(ctypes.Structure):
        _fields_ = [
            ('dmDeviceName',         ctypes.c_wchar * 32),
            ('dmSpecVersion',        ctypes.c_ushort),
            ('dmDriverVersion',      ctypes.c_ushort),
            ('dmSize',               ctypes.c_ushort),
            ('dmDriverExtra',        ctypes.c_ushort),
            ('dmFields',             ctypes.c_ulong),
            ('dmPositionX',          ctypes.c_long),
            ('dmPositionY',          ctypes.c_long),
            ('dmDisplayOrientation', ctypes.c_ulong),
            ('dmDisplayFixedOutput', ctypes.c_ulong),
            ('dmColor',              ctypes.c_short),
            ('dmDuplex',             ctypes.c_short),
            ('dmYResolution',        ctypes.c_short),
            ('dmTTOption',           ctypes.c_short),
            ('dmCollate',            ctypes.c_short),
            ('dmFormName',           ctypes.c_wchar * 32),
            ('dmLogPixels',          ctypes.c_ushort),
            ('dmBitsPerPel',         ctypes.c_ulong),
            ('dmPelsWidth',          ctypes.c_ulong),
            ('dmPelsHeight',         ctypes.c_ulong),
            ('dmDisplayFlags',       ctypes.c_ulong),
            ('dmDisplayFrequency',   ctypes.c_ulong),
            ('dmICMMethod',          ctypes.c_ulong),
            ('dmICMIntent',          ctypes.c_ulong),
            ('dmMediaType',          ctypes.c_ulong),
            ('dmDitherType',         ctypes.c_ulong),
            ('dmReserved1',          ctypes.c_ulong),
            ('dmReserved2',          ctypes.c_ulong),
            ('dmPanningWidth',       ctypes.c_ulong),
            ('dmPanningHeight',      ctypes.c_ulong),
        ]

    devmode = DEVMODE()
    devmode.dmSize             = ctypes.sizeof(DEVMODE)
    devmode.dmPelsWidth        = width
    devmode.dmPelsHeight       = height
    devmode.dmDisplayFrequency = refresh_rate
    devmode.dmFields           = 0x80000 | 0x100000 | 0x180000

    result = user32.ChangeDisplaySettingsW(ctypes.byref(devmode), 0)

    if result == 0:
        print(f"+ Resolution changed to {width}x{height} @ {refresh_rate}Hz")
        return True
    else:
        print(f"X Failed to change resolution (Error code: {result})")
        print("  Note: The requested refresh rate may not be supported by your display.")
        return False


def launch_valorant(cfg):
    """Launch VALORANT using RiotClientServices."""
    executable  = cfg["riot_client_exe"]
    working_dir = cfg["riot_client_dir"]
    args        = "--launch-product=valorant --launch-patchline=live"

    if not os.path.exists(executable):
        print(f"X Riot Client not found at: {executable}")
        print("  Please update 'riot_client_exe' in config.ini")
        return False

    try:
        subprocess.Popen(f'"{executable}" {args}', cwd=working_dir, shell=True)
        print("+ Launched VALORANT")
        return True
    except Exception as e:
        print(f"X Failed to launch VALORANT: {e}")
        return False


def disable_all_monitors():
    """Disable all monitors via Device Manager."""
    try:
        cmd = (
            'powershell -Command "'
            "Get-PnpDevice -Class Monitor | "
            "Where-Object {$_.Status -eq 'OK'} | "
            'Disable-PnpDevice -Confirm:$false"'
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            print(f"  Output: {result.stdout.strip()}")
        if result.stderr:
            print(f"  Stderr: {result.stderr.strip()}")

        if result.returncode == 0:
            print("+ All monitors disabled")
            return True
        else:
            print(f"X Failed to disable monitors (return code: {result.returncode})")
            return False
    except Exception as e:
        print(f"X Failed to disable monitors: {e}")
        return False


def countdown(seconds, label):
    print(f"{label}...")
    for i in range(seconds, 0, -1):
        print(f"  {i}...", end='\r')
        time.sleep(1)
    print()


if __name__ == "__main__":
    if not is_admin():
        print("Requesting administrator privileges...")
        run_as_admin()

    cfg = load_config()

    print("=== VALORANT Launcher ===")
    print(f"Config     : {CONFIG_FILE}")
    print(f"Resolution : {cfg['resolution_width']}x{cfg['resolution_height']} @ {cfg['refresh_rate']}Hz")
    print(f"Accounts   : {len(cfg['valorant_user_ids'])}")
    print()

    print("Updating VALORANT config files...")
    update_valorant_config(cfg)
    print()

    print("Disabling all monitors...")
    disable_all_monitors()
    print()

    countdown(3, "Waiting 3 seconds")

    print("Changing resolution...")
    change_resolution(cfg)
    print()

    countdown(7, "Waiting 7 seconds")

    print("Launching VALORANT...")
    launch_valorant(cfg)
    print()

    print("Done!")
