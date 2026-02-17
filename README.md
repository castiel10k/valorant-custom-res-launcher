
#  VALORANT Launcher - config.ini



[display]

# Target resolution width in pixels.
# Example: 1920
resolution_width = 1440

# Target resolution height in pixels.
# Example: 1080
resolution_height = 993

# Refresh rate in Hz.
# Must be a mode your monitor actually supports, otherwise the
# resolution change step will fail.
# Example: 60, 144, 240, 360, 600
refresh_rate = 600

# Which monitor to use (zero-based index).
# 0 = first/primary monitor, 1 = second monitor, etc.
# Value can be found in %LocalAppData%\VALORANT\Saved\Config\UID\GameUserSettings.ini 
monitor_index = 0

# Monitor device ID - used internally by the script but not
# written to the Valorant config. You can find this in:
#   Device Manager -> Monitors -> right-click your monitor
#   -> Properties -> Details tab
#   -> Property: "Device instance path"
# Example: DISPLAY\BNQ7FEC\XYZ890
# Value can be found in %LocalAppData%\VALORANT\Saved\Config\UID\GameUserSettings.ini
monitor_device_id = DISPLAY\BNQ7FEC\XYZ123

# Monitor config ID - this IS written to the Valorant config
# so the game knows which monitor to use.
# Find it in Device Manager the same way as monitor_device_id
# but look one level up at the parent device. It usually starts
# with MONITOR\ and contains a GUID in curly braces.
# Example: MONITOR\BNQ7FEC\{ABC123}\0008
# Value can be found in %LocalAppData%\VALORANT\Saved\Config\UID\GameUserSettings.ini

monitor_config_id = MONITOR\BNQ7FEC\{ABC123}\0008


[valorant]

# Comma-separated list of Valorant account folder names.
# Each account gets its own folder inside the Valorant config directory.
# To find your account IDs, open File Explorer and navigate to:
#   %LocalAppData%\VALORANT\Saved\Config\
# The folder names in there are your account IDs.
# Add one per line with a comma at the end (last one needs no comma).
# Example:
#   user_ids =
#       UID1,
#       UID2
user_ids =
    UID1,
    UID2


[paths]

# Full path to RiotClientServices.exe.
# Default location if you installed Riot Games to the default directory.
# The working directory for launching is derived automatically from this path,
# so you only need to set the exe.
# Example: C:\Program Files (x86)\Riot Games\Riot Client\RiotClientServices.exe
riot_client_exe = C:\Program Files (x86)\Riot Games\Riot Client\RiotClientServices.exe

# Path to the folder that contains all Valorant account config folders.
# %LocalAppData% is a Windows environment variable - leave it as-is,
# it expands automatically to C:\Users\<yourname>\AppData\Local
# Only change the part after Config\ if you have a non-standard install.
# Example: %LocalAppData%\VALORANT\Saved\Config
valorant_config_dir = %LocalAppData%\VALORANT\Saved\Config
