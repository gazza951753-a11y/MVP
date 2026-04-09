#!/usr/bin/env bash
# build_exe.sh — Build StudyAssist for the current platform (Linux/macOS)
# On Windows use build_exe.bat instead.
#
# Output: dist/StudyAssist/StudyAssist (or .exe on Windows via Wine)
set -euo pipefail

echo "===================================================="
echo " StudyAssist Intel System — desktop build"
echo "===================================================="

# Install build tools
echo "[1/4] Installing build dependencies..."
pip install --upgrade pyinstaller pywebview \
    fastapi "uvicorn[standard]" sqlalchemy pydantic-settings \
    httpx sentry-sdk prometheus-client python-multipart \
    beautifulsoup4 PyJWT -q

# Optional icon generation
echo "[2/4] Generating icon..."
mkdir -p assets
python - << 'PYEOF'
try:
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (256, 256), (30, 34, 54, 255))
    d = ImageDraw.Draw(img)
    d.ellipse([40, 40, 180, 180], outline=(59, 130, 246, 255), width=20)
    d.line([155, 155, 210, 210], fill=(59, 130, 246, 255), width=22)
    img.save("assets/icon.ico", format="ICO", sizes=[(256, 256), (64, 64), (32, 32)])
    print("  Icon created")
except ImportError:
    print("  Pillow not found — skipping icon")
PYEOF

echo "[3/4] Running PyInstaller..."
rm -rf build dist/StudyAssist
pyinstaller studyassist.spec --noconfirm --clean

echo "[4/4] Done!"
echo ""
echo "  Output : dist/StudyAssist/"
echo "  Binary : dist/StudyAssist/StudyAssist"
echo ""
echo "  Distribute by zipping the entire dist/StudyAssist/ folder."
