@echo off
echo Building Twitch Multi-Account Tool v3.1.0...

:: Make sure PyInstaller is installed
pip install pyinstaller

:: Create build directory if it doesn't exist
if not exist "dist" mkdir dist

:: Build the executable
pyinstaller --noconfirm --onefile --windowed --icon=assets/icon.ico --add-data="assets;assets" --name="TwitchMultiAccount" run.py

:: Copy additional files to the dist folder
copy README.md dist\README.md
copy CHANGELOG.md dist\CHANGELOG.md
copy LICENSE dist\LICENSE

echo Build complete! Executable is in the dist folder.
pause 