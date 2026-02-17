@echo off
echo ===============================
echo Enable All Monitors
echo ===============================
echo.

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo Checking if VALORANT is running...
tasklist /FI "IMAGENAME eq VALORANT-Win64-Shipping.exe" 2>NUL | find /I /N "VALORANT-Win64-Shipping.exe">NUL
if %errorLevel% equ 0 (
    echo.
    echo VALORANT is currently running!
    echo Monitors will only be enabled when VALORANT is NOT running.
    goto end
)

echo VALORANT is NOT running.
echo.

echo Checking for disabled monitors...
REM Try to enable any disabled monitors and capture if any were found
powershell -Command "$disabled = Get-PnpDevice -Class Monitor | Where-Object {$_.Status -eq 'Error'}; if ($disabled) { Write-Host 'Found disabled monitors. Enabling...'; $disabled | Enable-PnpDevice -Confirm:$false; exit 1 } else { Write-Host 'All monitors are already enabled.'; exit 0 }"

if %errorLevel% equ 1 (
    echo.
    echo.
    echo Success! Monitors have been enabled.
)

echo.
echo Configuring monitor settings with ControlMyMonitor...
echo.

:end
