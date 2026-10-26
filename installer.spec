# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder specification for the Windows release."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules


ROOT = Path(SPECPATH)
datas = []
for folder in ("assets", "models", "bin"):
    source = ROOT / folder
    if source.exists():
        datas.append((str(source), folder))

web_ui = ROOT / "app" / "ui"
if web_ui.exists():
    datas.append((str(web_ui), "app/ui"))

hiddenimports = collect_submodules("fastapi") + collect_submodules("starlette")
hiddenimports += collect_submodules("uvicorn") + collect_submodules("multipart")
hiddenimports += collect_submodules("vieneu")
hiddenimports += collect_submodules("pypdf") + collect_submodules("pypdfium2")
hiddenimports += ["pytesseract", "PIL", "PIL.Image", "PIL.ImageOps", "PIL.ImageEnhance"]
binaries = collect_dynamic_libs("pypdfium2")

# The OCR adapter imports these modules lazily.  Bundle their native DLLs and
# package data so the one-folder release remains fully offline.
for package in ("paddle", "paddleocr", "paddlex", "torch", "torchvision", "vietocr", "cv2"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torchaudio"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PhatThanhAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PhatThanhAI",
)
