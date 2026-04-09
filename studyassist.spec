# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for StudyAssist Intel System (Windows .exe)
#
# Usage:
#   pyinstaller studyassist.spec
#
# Output: dist/StudyAssist/StudyAssist.exe  (one-dir, ~120–200 MB)

import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

# --------------------------------------------------------------------------- #
# Collect packages that PyInstaller commonly misses                            #
# --------------------------------------------------------------------------- #

datas = []
binaries = []
hiddenimports = []

# uvicorn needs these at runtime
for pkg in ("uvicorn", "starlette", "fastapi", "anyio", "httpx",
            "pydantic", "pydantic_settings", "sqlalchemy",
            "prometheus_client", "sentry_sdk", "bs4"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# uvicorn loop / protocol backends
hiddenimports += [
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "uvicorn.logging",
    "anyio._backends._asyncio",
    "anyio._backends._trio",
    "email.mime.text",
    "email.mime.multipart",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.postgresql",
    # psycopg is optional (PostgreSQL mode); include if present
    "psycopg",
    "psycopg.adapt",
    # pywebview backends
    "webview",
    "webview.platforms.winforms",
    "webview.platforms.cef",
    "webview.platforms.gtk",
    "webview.platforms.qt",
    # JWT for Google Sheets
    "jwt",
    "cryptography",
    "cryptography.hazmat.primitives.asymmetric.rsa",
    # App modules
    "app",
    "app.main",
    "app.api",
    "app.gui",
    "app.config",
    "app.pipeline",
    "app.launcher",
    "app.db.base",
    "app.db.models",
    "app.collectors.base",
    "app.collectors.sources.mock_seed",
    "app.collectors.sources.tg_catalog",
    "app.collectors.sources.vk_public",
    "app.collectors.sources.forums",
    "app.processing.classify_rules",
    "app.processing.dedupe",
    "app.processing.normalize",
    "app.processing.scoring",
    "app.tasks.creator",
    "app.tasks.templates",
    "app.integrations.base_client",
    "app.integrations.airtable",
    "app.integrations.notion",
    "app.integrations.google_sheets",
    "app.integrations.telegram_notify",
    "app.observability.sentry",
    "app.observability.metrics",
    "multipart",          # python-multipart for FastAPI forms
    "python_multipart",
]

# --------------------------------------------------------------------------- #
# Analysis                                                                     #
# --------------------------------------------------------------------------- #

a = Analysis(
    ["app/launcher.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib", "numpy", "pandas", "scipy", "PIL", "tkinter",
        "IPython", "jupyter", "notebook",
        "test", "tests",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# --------------------------------------------------------------------------- #
# EXE — one-directory build for fast startup and WebView2 DLL compatibility   #
# --------------------------------------------------------------------------- #

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StudyAssist",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no console window on Windows
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico" if __import__("os").path.exists("assets/icon.ico") else None,
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="StudyAssist",
)
