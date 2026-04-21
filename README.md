**🌐 [English](README.md) · [Deutsch](README.de.md)**

<p align="center">
  <a href="https://rtf22.github.io/VOCIX/">
    <img src="https://img.shields.io/badge/%F0%9F%8C%90_Landing_Page-rtf22.github.io%2FVOCIX-1a3d8f?style=for-the-badge" alt="VOCIX Landing Page">
  </a>
</p>

# VOCIX — Voice Capture & Intelligent eXpression

![Release](https://img.shields.io/github/v/release/RTF22/VOCIX)
![Downloads](https://img.shields.io/github/downloads/RTF22/VOCIX/total)
![License](https://img.shields.io/github/license/RTF22/VOCIX)
![Platform](https://img.shields.io/badge/platform-Windows-blue)

Local voice dictation app for Windows 11 with a global hotkey. Capture speech, transcribe it, transform it intelligently, and insert it system-wide at the cursor position — in any application (browser, Word, Outlook, IDEs, etc.).

## Features

- **Push-to-Talk** via global hotkey (default: `Pause`)
- **Three modes:**
  - **A — Clean:** Clean transcription; strips filler words (um, uh, like, ...) with light corrections
  - **B — Business:** Rewrites speech into professional business language (Claude API)
  - **C — Rage:** De-escalates aggressive language into polite phrasing (Claude API)
- **System tray** with a colour-coded microphone icon and mode switching
- **Status overlay** with a live VU meter while recording — instant visual feedback that the mic is picking up signal
- **History of the last 20 dictations** in the tray — click an entry to re-insert it (saves your text when the target window has changed)
- **Usage statistics** — words per day/week/total, estimated typing time saved (200 keystrokes/min), distribution across modes
- **Snippet expansion** — your own shortcuts (`/sig`, `/adr`, …) inside the dictation are replaced with full text before insertion; Whisper transcripts like "slash sig" are normalised automatically
- **Auto-update from the tray** — new releases are detected in the background; one click downloads the Win-x64 ZIP, verifies the SHA256 and swaps the files automatically
- **Local processing** — speech-to-text runs fully offline (faster-whisper)
- **Multilingual UI** (German / English) — switchable at runtime via the tray menu, also drives Claude prompts and the Whisper STT language
- **Optional offline translation to English** — toggle in the tray menu: speak in any of ~50 Whisper-supported languages and VOCIX inserts native English text at the cursor, fully offline (no API key needed)
- **Configurable hotkeys** via `.env`
- **RDP mode** for Remote Desktop sessions
- **Log file** with configurable log level
- **Portable .exe** — no Python installation required

## Requirements

- Windows 10/11
- Microphone
- Optional: [Anthropic API key](https://console.anthropic.com/) for modes B and C

## Installation

### Option A: Portable .exe (recommended)

1. [Download a release](https://github.com/RTF22/VOCIX/releases) or build it yourself (see below)
2. Extract the folder anywhere
3. Optional: rename `.env.example` to `.env` and fill in your API key
4. Launch `VOCIX.exe`

The Whisper model (~500 MB) is downloaded automatically into the `models/` subfolder on first start.

### Option B: From source

```bash
git clone https://github.com/RTF22/VOCIX.git
cd VOCIX
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m vocix.main
```

### Build the .exe yourself

```bash
pip install pyinstaller
build_exe.bat
```

The result lives in `dist\VOCIX\` — the whole folder is portable.

## Configuration

All settings are controlled via the `.env` file in the application directory:

```ini
# Anthropic API key (optional, for modes B and C)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Language — controls UI, Claude prompts and Whisper STT (de, en)
# The tray selection (stored in state.json) overrides this value.
VOCIX_LANGUAGE=en

# Hotkeys — push-to-talk requires a single key, mode switchers may be combos
VOCIX_HOTKEY_RECORD=pause
VOCIX_HOTKEY_MODE_A=ctrl+shift+1
VOCIX_HOTKEY_MODE_B=ctrl+shift+2
VOCIX_HOTKEY_MODE_C=ctrl+shift+3

# Logging (DEBUG, INFO, WARNING, ERROR)
VOCIX_LOG_LEVEL=INFO
VOCIX_LOG_FILE=vocix.log

# RDP mode (longer clipboard delays)
VOCIX_RDP_MODE=true
```

Without an API key, modes B and C automatically fall back to mode A (Clean).

**Env precedence:** variables already present in the process environment are not overridden by the `.env` file (default behaviour of `python-dotenv`). To temporarily override a value, export it before launching the app.

## Usage

| Shortcut | Action |
|---|---|
| `Pause` (hold) | Push-to-talk — speak, release to process |
| `Ctrl+Shift+1` | Mode A: Clean transcription |
| `Ctrl+Shift+2` | Mode B: Business mode |
| `Ctrl+Shift+3` | Mode C: Rage mode |

**Workflow:**
1. Place the cursor in the target field (e-mail, chat, text editor, …)
2. Hold `Pause` and speak
3. Release — the text is transcribed, transformed and automatically inserted

**Tray menu:** right-click the tray icon → mode switch, **Language / Sprache** (English / Deutsch — switches UI, Claude prompts and Whisper STT), **About** (version + repo link), **Quit**

## Troubleshooting

| Problem | Solution |
|---|---|
| SmartScreen: "Windows protected your PC" on first launch | Click **More info → Run anyway**. VOCIX is open source and the release ZIP is reproducible from `main` via `build_exe.bat`. Code signing is tracked in [#12](https://github.com/RTF22/VOCIX/issues/12). |
| Tray icon not visible | Check hidden icons in the taskbar (arrow pointing up) |
| "VOCIX requires a CPU with AVX support" on startup | Your CPU is older than ~2012 and cannot run CTranslate2. VOCIX will not work on this machine. |
| Hotkey doesn't respond | Run the app as administrator |
| Laptop without a `Pause` key | Set `VOCIX_HOTKEY_RECORD=scroll lock` (or `f7`) in `.env` |
| "Microphone unavailable" | Check microphone permissions in Windows settings |
| Modes B/C only return Clean results | Verify `ANTHROPIC_API_KEY` in `.env` |
| Whisper download fails | Check your internet connection; configure proxy/firewall if needed |
| Text contains wrong characters | Make sure the target app supports Ctrl+V / paste |
| RDP: text is not inserted | Set `VOCIX_RDP_MODE=true` in `.env` |

## Project structure

```
vocix/
├── main.py              # Entry point, orchestration
├── config.py            # Settings (.env, paths, hotkeys)
├── i18n.py              # Translation lookup
├── locales/             # JSON translation files (de.json, en.json)
├── audio/recorder.py    # Microphone capture (sounddevice)
├── stt/
│   ├── base.py          # Abstract STT interface
│   └── whisper_stt.py   # faster-whisper implementation
├── processing/
│   ├── base.py          # Abstract processor interface
│   ├── clean.py         # Mode A: filler-word cleanup (local)
│   ├── business.py      # Mode B: business language (Claude API)
│   └── rage.py          # Mode C: de-escalation (Claude API)
├── output/injector.py   # Clipboard-based text insertion
└── ui/
    ├── tray.py          # System tray with microphone icon
    └── overlay.py       # Status overlay (tkinter)
```

## License

[MIT License](LICENSE) — free to use, including commercially. No warranty.

VOCIX bundles third-party Python libraries in the portable distribution. See
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for the required copyright
and permission notices (MIT / BSD / HPND / LGPL-3.0).
