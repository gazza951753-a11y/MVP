@echo off
:: ============================================================
:: build_exe.bat — Build StudyAssist Intel System for Windows
:: ============================================================
:: Prerequisites (install once):
::   pip install pyinstaller pywebview
::   winget install Microsoft.EdgeWebView2Runtime   (for Windows < 10 1809)
::
:: Output: dist\StudyAssist\StudyAssist.exe
:: ============================================================

setlocal EnableDelayedExpansion

echo ==========================================================
echo  StudyAssist Intel System — Windows EXE build
echo ==========================================================
echo.

:: ---- Check Python -------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ from python.org
    pause & exit /b 1
)

:: ---- Install / upgrade build tools --------------------------------
echo [1/5] Installing build dependencies...
pip install --upgrade pyinstaller pywebview ^
    fastapi uvicorn[standard] sqlalchemy pydantic-settings ^
    httpx sentry-sdk prometheus-client python-multipart ^
    beautifulsoup4 PyJWT -q
if errorlevel 1 ( echo [ERROR] pip install failed & pause & exit /b 1 )

:: ---- Create assets directory and icon -----------------------------
echo [2/5] Generating app icon...
if not exist assets mkdir assets
python -c "
import struct, zlib, base64
# Minimal 32x32 ICO with a simple blue square + magnifier symbol
# We create it programmatically to avoid needing Pillow
try:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGBA', (256, 256), (30, 34, 54, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([40,40,180,180], outline=(59,130,246,255), width=20)
    draw.line([155,155,210,210], fill=(59,130,246,255), width=22)
    img.save('assets/icon.ico', format='ICO', sizes=[(256,256),(64,64),(32,32),(16,16)])
    print('  Icon created with Pillow')
except ImportError:
    print('  Pillow not available — building without custom icon')
"

:: ---- Clean previous build -----------------------------------------
echo [3/5] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist\StudyAssist rmdir /s /q dist\StudyAssist

:: ---- Run PyInstaller -----------------------------------------------
echo [4/5] Running PyInstaller...
pyinstaller studyassist.spec --noconfirm --clean
if errorlevel 1 ( echo [ERROR] PyInstaller failed & pause & exit /b 1 )

:: ---- Post-build info -----------------------------------------------
echo [5/5] Build complete!
echo.
echo  Output folder : dist\StudyAssist\
echo  Executable    : dist\StudyAssist\StudyAssist.exe
echo  Size          :
dir /s /-c "dist\StudyAssist" 2>nul | find "File(s)"
echo.
echo  To distribute: zip the entire dist\StudyAssist\ folder.
echo  Requires      : Windows 10 1809+ (Edge WebView2 built-in)
echo                  Older Windows: install Edge WebView2 Runtime first.
echo.
pause
