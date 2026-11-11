# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
import sys

block_cipher = None

backend_dir = Path(SPECPATH).resolve()
project_root = backend_dir.parent
out_dir = project_root / "out"

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules
import rapidocr_onnxruntime

datas = []
if out_dir.exists():
    datas.append((str(out_dir), "out"))

rapidocr_dir = Path(rapidocr_onnxruntime.__file__).resolve().parent
datas.append((str(rapidocr_dir), "rapidocr_onnxruntime"))
datas += collect_data_files('onnxruntime')
datas += collect_data_files('shapely')
datas += collect_data_files('cv2')

binaries = []
binaries += collect_dynamic_libs('onnxruntime')
binaries += collect_dynamic_libs('cv2')
binaries += collect_dynamic_libs('shapely')

hidden_imports = [
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "fastapi",
    "fastapi.staticfiles",
    "starlette",
    "starlette.staticfiles",
    "starlette.routing",
    "pydantic",
    "httpx",
    "sqlite3",
    "rank_bm25",
    "docx",
    "pypdf",
    "pymupdf",
    "fitz",
    "multipart",
    "python_multipart",
    "openpyxl",
    "openpyxl.utils",
    "csv",
    "app.config",
    "app.cross_document",
    "app.privacy_audit",
    "app.tabular_analytics",
    "app.agentic_research",
    "app.benchmark",
    "rapidocr_onnxruntime",
    "PIL",
    "PIL.Image",
    "numpy",
    "onnxruntime",
    "pyclipper",
    "shapely",
    "cv2",
]
hidden_imports += collect_submodules('pyclipper')
hidden_imports += collect_submodules('shapely')
hidden_imports += collect_submodules('cv2')
hidden_imports += collect_submodules('rapidocr_onnxruntime')

a = Analysis(
    [str(backend_dir / "desktop_server.py")],
    pathex=[str(backend_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "notebook", "scipy"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="privora-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="privora-engine",
)
