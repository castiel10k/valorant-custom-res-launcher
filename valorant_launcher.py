import argparse
import configparser
import ctypes
import os
import re
import shutil
import stat
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.ini")

GAME_PROCESS = "VALORANT-Win64-Shipping.exe"
SECTION_HEADER = r'^\[/Script/ShooterGame\.ShooterGameUserSettings\]'
CREATE_NO_WINDOW = 0x08000000


# ---------------------------------------------------------------- helpers

def pause_and_exit(code=1):
    input("\nPress Enter to exit...")
    sys.exit(code)


def die(message, hint=None):
    print(f"X {message}")
    if hint:
        print(f"  {hint}")
    pause_and_exit(1)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate(extra_args):
    """Re-launch this script elevated (UAC). Uses the same Python interpreter."""
    script = os.path.abspath(sys.argv[0])
    params = subprocess.list2cmdline([script] + sys.argv[1:] + extra_args)
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, SCRIPT_DIR, 1
    )
    if ret <= 32:
        die("Could not get administrator privileges (UAC cancelled or failed).")
    sys.exit(0)


def countdown(seconds, label):
    if seconds <= 0:
        return
    print(f"{label}...")
    for i in range(seconds, 0, -1):
        print(f"  {i}...", end="\r")
        time.sleep(1)
    print()


def run_powershell(command):
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
    )


def is_game_running():
    result = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {GAME_PROCESS}", "/NH"],
        capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
    )
    return GAME_PROCESS.lower() in result.stdout.lower()


# ---------------------------------------------------------------- config

def load_config():
    """Load settings from config.ini"""
    if not os.path.exists(CONFIG_FILE):
        die(f"Config file not found: {CONFIG_FILE}",
            "Please create a config.ini file next to this script.")

    config = configparser.RawConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")

    try:
        settings = {
            "resolution_width":  config.getint("display", "resolution_width"),
            "resolution_height": config.getint("display", "resolution_height"),
            "refresh_rate":      config.getint("display", "refresh_rate"),
            "monitor_index":     config.getint("display", "monitor_index"),
            # Written to the Valorant config. Normalise doubled backslashes.
            "monitor_config_id": config.get("display", "monitor_config_id")
                                       .strip().replace("\\\\", "\\"),
            # Optional override, e.g. \\.\DISPLAY2. Normally found automatically.
            "display_device": config.get("display", "display_device", fallback="").strip(),

            "valorant_user_ids": [
                uid.strip()
                for uid in config.get("valorant", "user_ids").replace("\n", "").split(",")
                if uid.strip()
            ],

            "riot_client_exe":     config.get("paths", "riot_client_exe").strip(),
            "valorant_config_dir": config.get("paths", "valorant_config_dir").strip(),

            # Optional [timing] section
            "delay_after_disable": config.getint("timing", "delay_after_disable", fallback=3),
            "delay_before_launch": config.getint("timing", "delay_before_launch", fallback=7),
        }
        settings["riot_client_dir"] = os.path.dirname(settings["riot_client_exe"])
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        die(f"Config file error: {e}",
            "Please check that config.ini has all required sections and keys.")
    except ValueError as e:
        die(f"Config file error: invalid number ({e})",
            "resolution_*, refresh_rate and monitor_index must be plain integers.")

    if not settings["valorant_user_ids"]:
        die("No accounts listed under [valorant] user_ids in config.ini.")

    return settings


# ---------------------------------------------------------------- file patching

def set_file_readonly(path, readonly):
    """Set or clear the read-only attribute on a file."""
    current = os.stat(path).st_mode
    if readonly:
        os.chmod(path, current & ~stat.S_IWRITE)
    else:
        os.chmod(path, current | stat.S_IWRITE)


def set_key(text, key, value, eol):
    """Replace `key=...` (whole key, start of line). If missing, insert it
    right under the ShooterGameUserSettings section, or append as a fallback."""
    line = f"{key}={value}"
    pattern = re.compile(rf'^{re.escape(key)}=[^\r\n]*', re.M)
    if pattern.search(text):
        return pattern.sub(lambda m: line, text, count=1)

    header = re.search(SECTION_HEADER + r'[^\r\n]*', text, re.M)
    if header:
        pos = header.end()
        return text[:pos] + eol + line + text[pos:]

    if text and not text.endswith("\n"):
        text += eol
    return text + line + eol


def set_monitor_id(text, key, monitor_id, eol):
    """Write a quoted monitor ID, matching the backslash style already in the file."""
    existing = re.search(rf'^{re.escape(key)}="([^"\r\n]*)"', text, re.M)
    doubled = bool(existing and "\\\\" in existing.group(1))
    value = monitor_id.replace("\\", "\\\\") if doubled else monitor_id
    return set_key(text, key, f'"{value}"', eol)


def patch_account(config_path, cfg):
    """Patch one GameUserSettings.ini. Returns True if the content changed."""
    width, height = cfg["resolution_width"], cfg["resolution_height"]
    monitor_id, monitor_index = cfg["monitor_config_id"], cfg["monitor_index"]

    set_file_readonly(config_path, False)
    try:
        with open(config_path, "r", encoding="utf-8", newline="") as f:
            original = f.read()

        eol = "\r\n" if "\r\n" in original else "\n"
        content = original

        # Fullscreen mode: 0=fullscreen, 1=borderless, 2=windowed
        for key in ("FullscreenMode", "LastConfirmedFullscreenMode", "PreferredFullscreenMode"):
            content = set_key(content, key, 0, eol)

        for key in ("bLastConfirmedShouldLetterbox", "bShouldLetterbox"):
            content = set_key(content, key, "False", eol)

        for key in ("ResolutionSizeX", "LastUserConfirmedResolutionSizeX",
                    "DesiredScreenWidth", "LastUserConfirmedDesiredScreenWidth"):
            content = set_key(content, key, width, eol)
        for key in ("ResolutionSizeY", "LastUserConfirmedResolutionSizeY",
                    "DesiredScreenHeight", "LastUserConfirmedDesiredScreenHeight"):
            content = set_key(content, key, height, eol)

        for key in ("DefaultMonitorDeviceID", "LastConfirmedDefaultMonitorDeviceID"):
            content = set_monitor_id(content, key, monitor_id, eol)
        for key in ("DefaultMonitorIndex", "LastConfirmedDefaultMonitorIndex"):
            content = set_key(content, key, monitor_index, eol)

        changed = content != original
        if changed:
            backup = config_path + ".bak"
            if not os.path.exists(backup):          # keep the very first original
                shutil.copy2(config_path, backup)
            tmp = config_path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            os.replace(tmp, config_path)
        return changed, content
    finally:
        if os.path.exists(config_path):
            set_file_readonly(config_path, True)   # lock so Valorant can't overwrite


def update_valorant_config(cfg):
    """Update GameUserSettings.ini for all accounts."""
    config_dir = os.path.expandvars(cfg["valorant_config_dir"])
    verify_keys = ("FullscreenMode", "ResolutionSizeX", "ResolutionSizeY", "bShouldLetterbox")
    ok = failed = 0

    for user_id in cfg["valorant_user_ids"]:
        path = os.path.join(config_dir, user_id, "WindowsClient", "GameUserSettings.ini")
        if not os.path.exists(path):
            print(f"  ! Config file not found: {path}")
            failed += 1
            continue
        try:
            changed, content = patch_account(path, cfg)
            print(f"  + {user_id[:8]}... {'(changes applied)' if changed else '(already correct)'}")
            for line in content.splitlines():
                if line.split("=")[0].strip() in verify_keys:
                    print(f"      {line.strip()}")
            ok += 1
        except Exception as e:
            print(f"  X Failed: {user_id[:8]}...: {e}")
            failed += 1

    print(f"\n+ Updated {ok} account(s)")
    if failed:
        print(f"X Failed  {failed} account(s)")
    print("  - Exclusive fullscreen, letterbox disabled")
    print(f"  - Resolution {cfg['resolution_width']}x{cfg['resolution_height']}")
    print("  - Config files locked read-only (run with --unlock to undo)")
    return ok > 0


def unlock_all(cfg):
    """Remove the read-only flag from every configured account's file."""
    config_dir = os.path.expandvars(cfg["valorant_config_dir"])
    for user_id in cfg["valorant_user_ids"]:
        path = os.path.join(config_dir, user_id, "WindowsClient", "GameUserSettings.ini")
        if os.path.exists(path):
            set_file_readonly(path, False)
            print(f"  + Unlocked {user_id[:8]}...")
        else:
            print(f"  ! Not found: {path}")


# ---------------------------------------------------------------- display

class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName",         ctypes.c_wchar * 32),
        ("dmSpecVersion",        ctypes.c_ushort),
        ("dmDriverVersion",      ctypes.c_ushort),
        ("dmSize",               ctypes.c_ushort),
        ("dmDriverExtra",        ctypes.c_ushort),
        ("dmFields",             ctypes.c_ulong),
        ("dmPositionX",          ctypes.c_long),
        ("dmPositionY",          ctypes.c_long),
        ("dmDisplayOrientation", ctypes.c_ulong),
        ("dmDisplayFixedOutput", ctypes.c_ulong),
        ("dmColor",              ctypes.c_short),
        ("dmDuplex",             ctypes.c_short),
        ("dmYResolution",        ctypes.c_short),
        ("dmTTOption",           ctypes.c_short),
        ("dmCollate",            ctypes.c_short),
        ("dmFormName",           ctypes.c_wchar * 32),
        ("dmLogPixels",          ctypes.c_ushort),
        ("dmBitsPerPel",         ctypes.c_ulong),
        ("dmPelsWidth",          ctypes.c_ulong),
        ("dmPelsHeight",         ctypes.c_ulong),
        ("dmDisplayFlags",       ctypes.c_ulong),
        ("dmDisplayFrequency",   ctypes.c_ulong),
        ("dmICMMethod",          ctypes.c_ulong),
        ("dmICMIntent",          ctypes.c_ulong),
        ("dmMediaType",          ctypes.c_ulong),
        ("dmDitherType",         ctypes.c_ulong),
        ("dmReserved1",          ctypes.c_ulong),
        ("dmReserved2",          ctypes.c_ulong),
        ("dmPanningWidth",       ctypes.c_ulong),
        ("dmPanningHeight",      ctypes.c_ulong),
    ]


class DISPLAY_DEVICE(ctypes.Structure):
    _fields_ = [
        ("cb",           ctypes.c_ulong),
        ("DeviceName",   ctypes.c_wchar * 32),
        ("DeviceString", ctypes.c_wchar * 128),
        ("StateFlags",   ctypes.c_ulong),
        ("DeviceID",     ctypes.c_wchar * 128),
        ("DeviceKey",    ctypes.c_wchar * 128),
    ]


DM_PELSWIDTH, DM_PELSHEIGHT, DM_DISPLAYFREQUENCY = 0x80000, 0x100000, 0x400000
CDS_TEST = 0x2
ENUM_CURRENT_SETTINGS = -1
DISPLAY_DEVICE_ATTACHED = 0x1
DISPLAY_DEVICE_PRIMARY = 0x4

CDS_ERRORS = {
    1:  "restart required",
    -1: "failed",
    -2: "mode not supported (bad resolution/refresh rate combo)",
    -3: "could not write to registry",
    -4: "bad flags",
    -5: "bad parameter",
    -6: "bad dual-view",
}


def get_display_device_name(index):
    """Name (e.g. \\\\.\\DISPLAY1) of the Nth attached display, primary first."""
    user32 = ctypes.windll.user32
    devices, i = [], 0
    while True:
        dd = DISPLAY_DEVICE()
        dd.cb = ctypes.sizeof(DISPLAY_DEVICE)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        if dd.StateFlags & DISPLAY_DEVICE_ATTACHED:
            devices.append((not (dd.StateFlags & DISPLAY_DEVICE_PRIMARY), dd.DeviceName))
        i += 1
    devices.sort(key=lambda d: d[0])   # stable sort: primary display first
    if 0 <= index < len(devices):
        return devices[index][1]
    return None


def resolve_display(cfg):
    """Find the display (e.g. \\\\.\\DISPLAY2) to change.
    Matches the monitor code from monitor_config_id (e.g. BNQ7FEC), falling back
    to monitor_index. Must run BEFORE the monitors are disabled."""
    if cfg["display_device"]:
        return cfg["display_device"]

    parts = cfg["monitor_config_id"].split("\\")
    code = parts[1].upper() if len(parts) > 1 else ""
    user32 = ctypes.windll.user32
    i = 0
    while code:
        adapter = DISPLAY_DEVICE()
        adapter.cb = ctypes.sizeof(DISPLAY_DEVICE)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(adapter), 0):
            break
        i += 1
        if not adapter.StateFlags & DISPLAY_DEVICE_ATTACHED:
            continue
        j = 0
        while True:
            mon = DISPLAY_DEVICE()
            mon.cb = ctypes.sizeof(DISPLAY_DEVICE)
            if not user32.EnumDisplayDevicesW(adapter.DeviceName, j, ctypes.byref(mon), 0):
                break
            j += 1
            mp = mon.DeviceID.split("\\")
            if len(mp) > 1 and mp[1].upper() == code:
                print(f"  Found monitor {code} on {adapter.DeviceName}")
                return adapter.DeviceName

    print(f"  ! Monitor {code or '?'} not found by ID, falling back to monitor_index")
    return get_display_device_name(cfg["monitor_index"])


def list_modes(device):
    """All (width, height, hz) modes the driver offers for a display."""
    user32 = ctypes.windll.user32
    modes, n = set(), 0
    while True:
        dm = DEVMODE()
        dm.dmSize = ctypes.sizeof(DEVMODE)
        if not user32.EnumDisplaySettingsW(device, n, ctypes.byref(dm)):
            break
        modes.add((dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency))
        n += 1
    return modes


def change_resolution(cfg, device):
    """Change resolution and refresh rate of the given display."""
    width, height, hz = cfg["resolution_width"], cfg["resolution_height"], cfg["refresh_rate"]
    user32 = ctypes.windll.user32

    if device is None:
        print("  ! No display found, using primary display")
    else:
        print(f"  Target display: {device}")

    # Windows reports e.g. 599.94 Hz as 599 or 600, so match the nearest listed rate.
    modes = list_modes(device)
    rates = sorted(f for (w, h, f) in modes if w == width and h == height)
    if not rates:
        print(f"X The driver does not offer {width}x{height} on this display.")
        print("  Create it as a custom resolution (NVIDIA Control Panel > Change resolution")
        print("  > Customize > Create custom resolution), then run the launcher again.")
        return False
    best = min(rates, key=lambda f: abs(f - hz))
    if abs(best - hz) > 2:
        print(f"X {width}x{height} exists but not at {hz}Hz. Available rates: {rates}")
        return False
    if best != hz:
        print(f"  Using listed rate {best}Hz for requested {hz}Hz")

    devmode = DEVMODE()
    devmode.dmSize = ctypes.sizeof(DEVMODE)
    # Start from the current mode so position / colour depth are preserved
    user32.EnumDisplaySettingsW(device, ENUM_CURRENT_SETTINGS, ctypes.byref(devmode))
    devmode.dmPelsWidth = width
    devmode.dmPelsHeight = height
    devmode.dmDisplayFrequency = best
    devmode.dmFields |= DM_PELSWIDTH | DM_PELSHEIGHT | DM_DISPLAYFREQUENCY

    # Validate first, then apply
    result = user32.ChangeDisplaySettingsExW(device, ctypes.byref(devmode), None, CDS_TEST, None)
    if result == 0:
        result = user32.ChangeDisplaySettingsExW(device, ctypes.byref(devmode), None, 0, None)

    if result == 0:
        print(f"+ Resolution changed to {width}x{height} @ {best}Hz")
        return True

    print(f"X Failed to change resolution: {CDS_ERRORS.get(result, f'error {result}')}")
    return False


def disable_all_monitors():
    """Disable all monitors via Device Manager."""
    result = run_powershell(
        "Get-PnpDevice -Class Monitor | Where-Object {$_.Status -eq 'OK'} | "
        "Disable-PnpDevice -Confirm:$false -ErrorAction Stop"
    )
    if result.stderr.strip():
        print(f"  Stderr: {result.stderr.strip()}")
    if result.returncode == 0:
        print("+ All monitors disabled")
        return True
    print(f"X Failed to disable monitors (return code: {result.returncode})")
    return False


def enable_all_monitors():
    """Re-enable disabled monitors (only used if this script itself fails midway)."""
    result = run_powershell(
        "Get-PnpDevice -Class Monitor | Where-Object {$_.Status -eq 'Error'} | "
        "Enable-PnpDevice -Confirm:$false"
    )
    print("+ Monitors re-enabled" if result.returncode == 0 else "X Failed to re-enable monitors")


# ---------------------------------------------------------------- launch

def launch_valorant(cfg):
    """Launch VALORANT via RiotClientServices, then return (nothing keeps running)."""
    try:
        subprocess.Popen(
            [cfg["riot_client_exe"], "--launch-product=valorant", "--launch-patchline=live"],
            cwd=cfg["riot_client_dir"],
        )
        print("+ Launched VALORANT")
        return True
    except Exception as e:
        print(f"X Failed to launch VALORANT: {e}")
        return False


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="VALORANT launcher")
    parser.add_argument("--unlock", action="store_true",
                        help="remove the read-only flag from all configured GameUserSettings.ini files and exit")
    parser.add_argument("--elevated", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.unlock:
        unlock_all(load_config())
        input("\nPress Enter to exit...")
        return

    if not is_admin():
        if args.elevated:
            die("Still not running as administrator after elevation.")
        print("Requesting administrator privileges...")
        elevate(["--elevated"])

    cfg = load_config()

    print("=== VALORANT Launcher ===")
    print(f"Config     : {CONFIG_FILE}")
    print(f"Resolution : {cfg['resolution_width']}x{cfg['resolution_height']} @ {cfg['refresh_rate']}Hz")
    print(f"Accounts   : {len(cfg['valorant_user_ids'])}")
    print()

    # Pre-flight checks, before anything is changed
    if is_game_running():
        die("VALORANT is already running.",
            "Close it first - it would overwrite the patched settings when it exits.")
    if not os.path.exists(cfg["riot_client_exe"]):
        die(f"Riot Client not found at: {cfg['riot_client_exe']}",
            "Please update 'riot_client_exe' in config.ini")

    print("Locating display...")
    display = resolve_display(cfg)
    print()

    print("Updating VALORANT config files...")
    update_valorant_config(cfg)
    print()

    print("Disabling all monitors...")
    if not disable_all_monitors():
        print("  Continuing anyway.")
    print()

    try:
        countdown(cfg["delay_after_disable"], f"Waiting {cfg['delay_after_disable']} seconds")

        print("Changing resolution...")
        change_resolution(cfg, display)
        print()

        countdown(cfg["delay_before_launch"], f"Waiting {cfg['delay_before_launch']} seconds")

        print("Launching VALORANT...")
        launched = launch_valorant(cfg)
        print()
    except Exception as e:
        # Unexpected crash: don't leave the user with disabled monitors
        print(f"X Unexpected error: {e}")
        enable_all_monitors()
        pause_and_exit(1)

    if not launched:
        enable_all_monitors()
        pause_and_exit(1)

    print("Done!")   # script ends here; nothing stays running while you play


if __name__ == "__main__":
    main()
