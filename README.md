# VALORANT Launcher

Automates pre-launch setup for VALORANT: patches config files for all accounts, disables monitors, sets resolution and refresh rate, then launches the game.

---

## Requirements

- Windows 10/11
- Python 3.x
- Administrator privileges (the script will prompt for elevation automatically)
- VALORANT installed via the Riot Client

---

## Usage

```
python valorant_launcher.py
```

The script will request UAC elevation if not already running as admin. Place `config.ini` in the same folder as the script.

---

## What it does

1. Patches `GameUserSettings.ini` for every account listed in the config — forces exclusive fullscreen, sets resolution, disables letterbox, and locks the file read-only so Valorant can't overwrite it on launch
2. Disables all monitors via Device Manager
3. Waits 3 seconds
4. Changes the Windows display resolution and refresh rate
5. Waits 7 seconds
6. Launches Valorant via RiotClientServices

---

## config.ini

All settings live in `config.ini` next to the script. A full annotated sample is below.

### `[display]`
The ratio `width / height` must be **≥ 1.45** (e.g. 1440/993 = 1.450, 1568/1080 = 1.452, 2088/1440 = 1.450)
| Key | Description |
|-----|-------------|
| `resolution_width` | Target width in pixels, e.g. `2088`, `1568`, `1440` |
| `resolution_height` | Target height in pixels, e.g. `1440`, `1080`, `993`. |
| `refresh_rate` | Hz — must be a mode your monitor actually supports, e.g. `60`, `144`, `360`, `600` |
| `monitor_index` | Zero-based monitor index. `0` = primary, `1` = second monitor, etc. |
| `monitor_device_id` | Windows device instance path for your monitor (see below) |
| `monitor_config_id` | Monitor ID written into the Valorant config (see below) |

#### Finding monitor_device_id and monitor_config_id

Both values can be found in two ways:

**Option A — from an existing Valorant config:**
Open `%LocalAppData%\VALORANT\Saved\Config\<any-account-id>\WindowsClient\GameUserSettings.ini` and search for `DefaultMonitorDeviceID` and `DefaultMonitorIndex`. The values already there are the ones to use.

**Option B — from Device Manager:**
1. Open Device Manager (`Win + X` → Device Manager)
2. Expand **Monitors**
3. Right-click your monitor → **Properties**
4. Go to the **Details** tab
5. In the **Property** dropdown, select **Device instance path**
6. The value shown is your `monitor_device_id` (starts with `DISPLAY\...`)
7. For `monitor_config_id`, look at the parent entry — it starts with `MONITOR\` and contains a GUID in curly braces

---

### `[valorant]`

| Key | Description |
|-----|-------------|
| `user_ids` | Comma-separated list of Valorant account folder names (one per line) |

#### Finding your account IDs

Open File Explorer and navigate to:
```
%LocalAppData%\VALORANT\Saved\Config\
```
Each folder name in there is an account ID. Add all the accounts you want the script to patch.

---

### `[paths]`

| Key | Description |
|-----|-------------|
| `riot_client_exe` | Full path to `RiotClientServices.exe`. The launch working directory is derived from this automatically. |
| `valorant_config_dir` | Path to the folder containing all account config folders. Leave `%LocalAppData%` as-is — Windows expands it automatically. |

---

## Sample config.ini

```ini
[display]
resolution_width = 1440
resolution_height = 993
refresh_rate = 600
monitor_index = 0
monitor_device_id = DISPLAY\BNQ7FEC\XYZ123
monitor_config_id = MONITOR\BNQ7FEC\{ABC123}\0008

[valorant]
user_ids =
    UID1,
    UID2

[paths]
riot_client_exe = C:\Program Files (x86)\Riot Games\Riot Client\RiotClientServices.exe
valorant_config_dir = %LocalAppData%\VALORANT\Saved\Config
```

---

## Notes

- Config files are locked **read-only** after being patched. The script automatically unlocks them before each run, so re-running always works.
- If a key like `FullscreenMode` is missing from an account's config (e.g. the account has never launched the game), the script appends it to the file rather than skipping it.
- If the Riot Client is not found at the configured path, the script will print an error and skip the launch step.
