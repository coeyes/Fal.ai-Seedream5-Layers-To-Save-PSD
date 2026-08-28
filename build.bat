@echo off
setlocal
@REM Build Fal.ai-Seedream5-Layers-To-Save-PSD.exe with PyInstaller.
@REM Converts icon.png to a multi-size icon.ico, then packages gui.py.
cd /d "%~dp0"
call .venv\Scripts\activate.bat

python -c "from PIL import Image; Image.open('icon.png').save('icon.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
if errorlevel 1 exit /b 1

pyinstaller --noconfirm --onefile --windowed ^
  --name Fal.ai-Seedream5-Layers-To-Save-PSD ^
  --icon icon.ico ^
  --add-data "icon.png;." ^
  gui.py
if errorlevel 1 exit /b 1

echo Done: dist\Fal.ai-Seedream5-Layers-To-Save-PSD.exe
