**🌐 [English](README.md) · [Deutsch](README.de.md)**

<p align="center">
  <a href="https://vocix.de/">
    <img src="https://img.shields.io/badge/%F0%9F%8C%90_Landing_Page-vocix.de-1a3d8f?style=for-the-badge" alt="VOCIX Landing Page">
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
  - **B — Business:** Rewrites speech into professional business language (LLM-powered)
  - **C — Rage:** De-escalates aggressive language into polite phrasing (LLM-powered)
- **Multi-provider LLM for modes B and C** — pick your backend in the settings dialog: Anthropic Claude, any OpenAI-compatible API (OpenAI, Groq, OpenRouter, LM Studio, llama.cpp-server, vLLM via `base_url`) or local Ollama models. Per-mode override (e.g. Business on cloud Claude, Rage on local Llama). Provider failures fall back to Clean mode and surface an orange toast — no more silent degradation.
- **Settings dialog** in the tray menu — four tabs (Basics / Advanced / Expert / AI Provider) with Test buttons, hotkey capture and per-mode validation. Changes follow a strict draft model: nothing takes effect until you press **Save**, **Cancel** discards everything. Almost every setting applies live; only log level / log file require a restart (you're prompted, and VOCIX restarts itself on confirmation)
- **System tray** with a colour-coded microphone icon and mode switching
- **Status overlay** with a live VU meter while recording — instant visual feedback that the mic is picking up signal
- **History of the last 20 dictations** in the tray — click an entry to re-insert it (saves your text when the target window has changed)
- **Usage statistics** — words per day/week/total, estimated typing time saved (200 keystrokes/min), distribution across modes
- **Snippet expansion** — your own shortcuts (`/sig`, `/adr`, …) inside the dictation are replaced with full text before insertion; Whisper transcripts like "slash sig" are normalised automatically
- **Auto-update from the tray** — new releases are detected in the background; one click downloads the Win-x64 ZIP, verifies the SHA256 and swaps the files automatically
- **Local processing** — speech-to-text runs fully offline (faster-whisper)
- **Configurable Whisper model** — switch between `tiny` / `base` / `small` (default) / `medium` / `large-v3` / `large-v3-turbo` at runtime via the tray menu (larger = more accurate, slower)
- **Optional NVIDIA GPU acceleration** — auto-detects CUDA when available, falls back to CPU; switchable in the tray menu (`Auto` / `GPU` / `CPU`). Source install only (the packaged ZIP stays CPU-only)
- **Multilingual UI** (German / English) — switchable at runtime via the tray menu, also drives Claude prompts and the Whisper STT language
- **Optional offline translation to English** — toggle in the tray menu: speak in any of ~50 Whisper-supported languages and VOCIX inserts native English text at the cursor, fully offline (no API key needed)
- **Configurable hotkeys** via `.env`
- **RDP mode** for Remote Desktop sessions
- **Log file** with configurable log level
- **Portable .exe** — no Python installation required

## Requirements

- Windows 10/11
- Microphone
- Optional for modes B and C: any one of
  - [Anthropic API key](https://console.anthropic.com/), or
  - an OpenAI-compatible endpoint (OpenAI, Groq, OpenRouter, LM Studio, llama.cpp-server, vLLM …), or
  - a local [Ollama](https://ollama.com/) install — no API key needed

## Installation

### Option A: winget

```powershell
winget install RTF22.VOCIX
```

### Option B: Scoop

```powershell
scoop bucket add vocix https://github.com/RTF22/scoop-vocix
scoop install vocix
```

### Option C: Portable .exe

1. [Download a release](https://github.com/RTF22/VOCIX/releases)
2. Extract the folder anywhere
3. Optional: rename `.env.example` to `.env` and fill in your API key
4. Launch `VOCIX.exe`

The Whisper model (~500 MB) is downloaded automatically into the `models/` subfolder on first start.

### Option D: From source

```bash
git clone https://github.com/RTF22/VOCIX.git
cd VOCIX
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m vocix.main
```

### GPU acceleration (optional, NVIDIA only)

```bash
pip install -r requirements-gpu.txt
```

Pulls cuBLAS + cuDNN (~600 MB) and lets `ctranslate2` use the GPU. After the
install, pick **Beschleunigung → GPU (CUDA)** in the tray menu (or set
`VOCIX_WHISPER_ACCELERATION=gpu`). The packaged Win-x64 ZIP does **not** include
these libraries — GPU is opt-in for source installs only.

### Build the .exe yourself

```bash
pip install pyinstaller
build_exe.bat
```

The result lives in `dist\VOCIX\` — the whole folder is portable.

## Configuration

The recommended way to configure VOCIX is the **Settings dialog** (tray icon → Settings). The `AI Provider` tab carries three slots — Anthropic, OpenAI-compatible and Ollama — each with its own Test button. Pick a default and optionally override per mode (Business / Rage). Nothing is written until you press **Save** — **Cancel** discards every change, including provider Test results.

For headless setups everything is also available via `.env`:

```ini
# --- LLM providers (modes B and C) -----------------------------------------
# Pick a default provider and optionally override per mode.
VOCIX_LLM_DEFAULT=anthropic            # anthropic | openai | ollama
VOCIX_LLM_BUSINESS=                    # leave empty to use the default
VOCIX_LLM_RAGE=

# Anthropic Claude
VOCIX_LLM_ANTHROPIC_API_KEY=sk-ant-your-key-here
VOCIX_LLM_ANTHROPIC_MODEL=claude-sonnet-4-6
VOCIX_LLM_ANTHROPIC_TIMEOUT=15

# OpenAI-compatible (OpenAI, Groq, OpenRouter, LM Studio, llama.cpp, vLLM …)
VOCIX_LLM_OPENAI_API_KEY=
VOCIX_LLM_OPENAI_BASE_URL=https://api.openai.com/v1
VOCIX_LLM_OPENAI_MODEL=gpt-4o-mini
VOCIX_LLM_OPENAI_TIMEOUT=15

# Ollama (local, no API key)
VOCIX_LLM_OLLAMA_BASE_URL=http://localhost:11434
VOCIX_LLM_OLLAMA_MODEL=llama3.1
VOCIX_LLM_OLLAMA_TIMEOUT=30

# --- App ------------------------------------------------------------------
# Language — controls UI, LLM prompts and Whisper STT (de, en)
# The tray selection (stored in state.json) overrides this value.
VOCIX_LANGUAGE=en

# Whisper model — tiny | base | small (default) | medium | large-v3 | large-v3-turbo
# Tray selection (state.json) overrides this value.
VOCIX_WHISPER_MODEL=small

# Acceleration — auto (GPU if available) | gpu (force CUDA) | cpu (force CPU)
# GPU mode needs `pip install -r requirements-gpu.txt` and is source-install only.
VOCIX_WHISPER_ACCELERATION=auto

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

Without any configured provider, modes B and C automatically fall back to mode A (Clean). Configurations from VOCIX 1.3.x (`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_TIMEOUT`) keep working unchanged — saving once in the new settings tab migrates them.

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

**Tray menu:** right-click the tray icon → mode switch, **Language / Sprache** (English / Deutsch — switches UI, Claude prompts and Whisper STT), **Whisper-Modell** (`tiny` … `large-v3-turbo` at runtime), **Beschleunigung** (Auto / GPU / CPU — GPU greyed out when no CUDA detected), **About** (version + repo link), **Quit**

> Note: tray-menu choices (mode, language, Whisper model, acceleration) are persisted in `state.json` and override the corresponding `.env` values on next launch.

## Troubleshooting

| Problem | Solution |
|---|---|
| SmartScreen: "Windows protected your PC" on first launch | Click **More info → Run anyway**. VOCIX is open source and the release ZIP is reproducible from `main` via `build_exe.bat`. Code signing is tracked in [#12](https://github.com/RTF22/VOCIX/issues/12). |
| Tray icon not visible | Check hidden icons in the taskbar (arrow pointing up) |
| "VOCIX requires a CPU with AVX support" on startup | Your CPU is older than ~2012 and cannot run CTranslate2. VOCIX will not work on this machine. |
| Hotkey doesn't respond | Run the app as administrator |
| Laptop without a `Pause` key | Set `VOCIX_HOTKEY_RECORD=scroll lock` (or `f7`) in `.env` |
| "Microphone unavailable" | Check microphone permissions in Windows settings |
| Modes B/C only return Clean results | Open Settings → AI Provider, configure at least one slot and hit Test |
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
│   ├── llm_backed.py    # Shared LLM-backed processor (used by B/C)
│   ├── business.py      # Mode B: business language
│   ├── rage.py          # Mode C: de-escalation
│   └── providers/       # Anthropic / OpenAI-compatible / Ollama backends
├── output/injector.py   # Clipboard-based text insertion
└── ui/
    ├── tray.py          # System tray with microphone icon
    ├── overlay.py       # Status overlay (tkinter)
    └── settings.py      # Settings dialog (Basics / Advanced / Expert / AI Provider)
```

## License

[MIT License](LICENSE) — free to use, including commercially. No warranty.

VOCIX bundles third-party Python libraries in the portable distribution. See
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for the required copyright
and permission notices (MIT / BSD / HPND / LGPL-3.0).
