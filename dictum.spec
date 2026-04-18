# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec für DICTUM — portable Standalone-App."""

import os
import importlib

block_cipher = None

# faster-whisper Assets (VAD-Modell) und CTranslate2 DLLs müssen mitgebundelt werden
faster_whisper_path = os.path.dirname(importlib.import_module("faster_whisper").__file__)
ctranslate2_path = os.path.dirname(importlib.import_module("ctranslate2").__file__)

a = Analysis(
    ["dictum/main.py"],
    pathex=[],
    binaries=[],
    datas=[
        (".env.example", "."),
        (os.path.join(faster_whisper_path, "assets"), "faster_whisper/assets"),
    ],
    hiddenimports=[
        "faster_whisper",
        "ctranslate2",
        "sounddevice",
        "numpy",
        "keyboard",
        "pyperclip",
        "pystray",
        "PIL",
        "anthropic",
        "dotenv",
        "tkinter",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="DICTUM",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Kein Konsolenfenster
    icon=None,      # Optional: .ico Datei hier angeben
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DICTUM",
)
