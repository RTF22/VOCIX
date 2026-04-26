# LLM-Provider-Abstraktion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modi Business und Rage können neben Anthropic auch über OpenAI-kompatible APIs (OpenAI, Groq, OpenRouter, LM Studio, llama.cpp-Server, vLLM) und lokal über Ollama laufen — pro Modus konfigurierbar im Settings-Dialog.

**Architecture:** Neue Provider-Schicht (`vocix/processing/providers/`) mit einer `LLMProvider`-ABC und drei Implementierungen. Der bestehende `ClaudeProcessor` wird zu `LLMBackedProcessor` umgebaut und löst pro `process()`-Call den Provider via Config auf. Der Settings-Dialog bekommt einen neuen Tab „KI-Provider" mit drei festen Slots; alte Anthropic-Felder werden dorthin migriert. Bestehende `state.json`-Configs bleiben rückwärtskompatibel — die Resolution-Logik fällt automatisch auf die alten Top-Level-Keys zurück, solange das neue Schema leer ist.

**Tech Stack:** Python 3.12, `anthropic` (vorhanden), `openai>=1.0` (neu), Ollama via stdlib `urllib.request`, tkinter/ttk, pytest.

**Spec:** `docs/superpowers/specs/2026-04-26-llm-provider-abstraction-design.md`

---

## File Structure

**Neu:**
- `vocix/processing/providers/__init__.py` — Re-exports
- `vocix/processing/providers/base.py` — `LLMProvider`, `ProviderError`, `ProviderConfig`
- `vocix/processing/providers/anthropic_provider.py`
- `vocix/processing/providers/openai_provider.py`
- `vocix/processing/providers/ollama_provider.py`
- `vocix/processing/providers/factory.py` — `build_provider(slot_id, cfg)`
- `vocix/processing/llm_backed.py` — neuer `LLMBackedProcessor` (ersetzt `claude_base.py`)
- `tests/processing/__init__.py` (leer)
- `tests/processing/providers/__init__.py` (leer)
- `tests/processing/providers/test_anthropic.py`
- `tests/processing/providers/test_openai.py`
- `tests/processing/providers/test_ollama.py`
- `tests/processing/providers/test_factory.py`
- `tests/processing/test_llm_backed.py`
- `tests/test_config_llm.py`

**Geändert:**
- `vocix/config.py` — neue `llm`-Sektion, Helper, Migrations-Resolution
- `vocix/processing/business.py` — nutzt `LLMBackedProcessor`
- `vocix/processing/rage.py` — nutzt `LLMBackedProcessor`
- `vocix/processing/__init__.py` — Exports anpassen
- `vocix/ui/settings.py` — neuer Tab, Anthropic-Felder dorthin verschoben, Gating gegen neue Validated-Flags
- `vocix/locales/de.json` + `vocix/locales/en.json` — neue Keys
- `vocix/main.py` — Toast-Callback für Provider-Fallback verkabeln, Erstkontakt-Hinweis bei Migration
- `requirements.txt` — `+openai>=1.0`
- `tests/test_processors_fallback.py` — angepasst auf neuen Datenpfad

**Gelöscht:**
- `vocix/processing/claude_base.py` — ersetzt durch `llm_backed.py`

---

## Konventionen

- **Commits** als `Jens Fricke <aijourney22@gmail.com>`, ohne `Co-Authored-By: Claude`-Trailer:
  ```bash
  git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "..."
  ```
- **Tests** liegen unter `tests/`, Pattern wie in `tests/test_processors_fallback.py`. Aufruf: `python -m pytest tests/<datei> -v`.
- **i18n-Keys** in `vocix/locales/de.json` *und* `vocix/locales/en.json`, gleiche Keys in beiden Dateien.

---

## Phase 1: Provider-Schicht

### Task 1: Provider-Basisklassen und Datentypen

**Files:**
- Create: `vocix/processing/providers/__init__.py`
- Create: `vocix/processing/providers/base.py`
- Create: `tests/processing/__init__.py`
- Create: `tests/processing/providers/__init__.py`
- Test: (kommt in Task 2 ff.)

- [ ] **Step 1: Leere `__init__.py`-Dateien anlegen**

```bash
mkdir -p vocix/processing/providers tests/processing/providers
touch vocix/processing/providers/__init__.py tests/processing/__init__.py tests/processing/providers/__init__.py
```

- [ ] **Step 2: `vocix/processing/providers/base.py` schreiben**

```python
"""Provider-Basis: abstrakte LLM-Schnittstelle, Fehlerklasse, Config-DTO."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderError(Exception):
    """Einheitliche Fehlerklasse für alle LLM-Provider.

    Wird vom LLMBackedProcessor gefangen und löst Clean-Fallback + Toast aus.
    Die Provider mappen native Fehler (HTTP, SDK, Timeout, Auth, leere Antwort)
    auf diese Klasse, damit der Aufrufer nur einen Typ kennen muss.
    """


@dataclass
class ProviderConfig:
    """In-Memory-Repräsentation eines Provider-Slots aus state.json."""
    kind: str                # "anthropic" | "openai" | "ollama"
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    timeout: float = 15.0


class LLMProvider(ABC):
    """Abstrakte Provider-Schnittstelle.

    Jede konkrete Implementierung kapselt SDK/HTTP-Aufruf und mappt
    Provider-Fehler auf ProviderError.
    """

    @abstractmethod
    def complete(self, *, system: str, user: str, max_tokens: int = 1024) -> str:
        """Sendet system+user an das Modell, liefert die Text-Completion.

        Raises:
            ProviderError: bei jedem Fehler (Netz, Auth, Timeout, leerer Content).
        """
        ...
```

- [ ] **Step 3: Re-Exports in `vocix/processing/providers/__init__.py`**

```python
from vocix.processing.providers.base import LLMProvider, ProviderConfig, ProviderError

__all__ = ["LLMProvider", "ProviderConfig", "ProviderError"]
```

- [ ] **Step 4: Smoke-Test**

Run: `python -c "from vocix.processing.providers import LLMProvider, ProviderConfig, ProviderError; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add vocix/processing/providers/__init__.py vocix/processing/providers/base.py tests/processing/__init__.py tests/processing/providers/__init__.py
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "feat(providers): Basisklassen LLMProvider/ProviderError/ProviderConfig"
```

---

### Task 2: AnthropicProvider (TDD)

**Files:**
- Test: `tests/processing/providers/test_anthropic.py`
- Create: `vocix/processing/providers/anthropic_provider.py`

- [ ] **Step 1: Failing test schreiben**

```python
"""Tests für AnthropicProvider — mock anthropic SDK."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from vocix.processing.providers import ProviderConfig, ProviderError
from vocix.processing.providers.anthropic_provider import AnthropicProvider


def _cfg(api_key: str = "sk-ant-fake", model: str = "claude-test", timeout: float = 5.0) -> ProviderConfig:
    return ProviderConfig(kind="anthropic", api_key=api_key, model=model, timeout=timeout)


def _response(text: str | None) -> SimpleNamespace:
    if text is None:
        return SimpleNamespace(content=[])
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


def test_complete_success_returns_text():
    provider = AnthropicProvider(_cfg())
    provider._client = MagicMock()
    provider._client.messages.create.return_value = _response("Hallo Welt")

    result = provider.complete(system="be polite", user="hi")

    assert result == "Hallo Welt"
    kwargs = provider._client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-test"
    assert kwargs["system"] == "be polite"
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]


def test_complete_raises_provider_error_on_api_exception():
    provider = AnthropicProvider(_cfg())
    provider._client = MagicMock()
    provider._client.messages.create.side_effect = RuntimeError("network down")

    with pytest.raises(ProviderError):
        provider.complete(system="x", user="y")


def test_complete_raises_on_empty_content():
    provider = AnthropicProvider(_cfg())
    provider._client = MagicMock()
    provider._client.messages.create.return_value = _response(None)

    with pytest.raises(ProviderError):
        provider.complete(system="x", user="y")


def test_complete_raises_on_blank_text():
    provider = AnthropicProvider(_cfg())
    provider._client = MagicMock()
    provider._client.messages.create.return_value = _response("   ")

    with pytest.raises(ProviderError):
        provider.complete(system="x", user="y")


def test_complete_raises_on_non_text_block():
    provider = AnthropicProvider(_cfg())
    provider._client = MagicMock()
    block_without_text = SimpleNamespace()  # kein .text-Attribut
    provider._client.messages.create.return_value = SimpleNamespace(content=[block_without_text])

    with pytest.raises(ProviderError):
        provider.complete(system="x", user="y")


def test_construct_without_key_raises():
    with pytest.raises(ProviderError):
        AnthropicProvider(_cfg(api_key=""))


def test_construct_without_anthropic_package_raises():
    with patch.dict("sys.modules", {"anthropic": None}):
        with pytest.raises(ProviderError):
            AnthropicProvider(_cfg())
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `python -m pytest tests/processing/providers/test_anthropic.py -v`
Expected: ImportError (`anthropic_provider`-Modul existiert nicht).

- [ ] **Step 3: `vocix/processing/providers/anthropic_provider.py` schreiben**

```python
"""Anthropic-Provider — kapselt anthropic.Anthropic.messages.create."""
from __future__ import annotations

import logging

from vocix.processing.providers.base import LLMProvider, ProviderConfig, ProviderError

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    def __init__(self, config: ProviderConfig):
        if not config.api_key:
            raise ProviderError("Anthropic: API-Key fehlt")
        try:
            import anthropic  # type: ignore
        except ImportError as e:
            raise ProviderError(f"anthropic package not installed: {e}") from e

        self._config = config
        self._client = anthropic.Anthropic(api_key=config.api_key, timeout=config.timeout)

    def complete(self, *, system: str, user: str, max_tokens: int = 1024) -> str:
        try:
            response = self._client.messages.create(
                model=self._config.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as e:
            raise ProviderError(f"Anthropic API error: {e}") from e

        content = getattr(response, "content", None)
        if not content or not hasattr(content[0], "text"):
            raise ProviderError("Anthropic: empty or non-text response")
        text = content[0].text.strip()
        if not text:
            raise ProviderError("Anthropic: blank text in response")
        return text
```

- [ ] **Step 4: Tests laufen lassen**

Run: `python -m pytest tests/processing/providers/test_anthropic.py -v`
Expected: alle 7 Tests grün.

- [ ] **Step 5: Commit**

```bash
git add vocix/processing/providers/anthropic_provider.py tests/processing/providers/test_anthropic.py
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "feat(providers): AnthropicProvider mit ProviderError-Mapping"
```

---

### Task 3: openai-Dependency hinzufügen

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Aktuelles requirements.txt lesen**

Run: `cat requirements.txt`
(zur Verifikation, dass `openai` noch nicht drin ist)

- [ ] **Step 2: `openai>=1.0` ergänzen**

Edit: `requirements.txt` — eine Zeile nach `anthropic>=0.40.0` einfügen:

```
openai>=1.0
```

- [ ] **Step 3: Installieren**

Run: `pip install "openai>=1.0"`
Expected: erfolgreiche Installation oder "already satisfied".

- [ ] **Step 4: Smoke-Test**

Run: `python -c "import openai; print(openai.__version__)"`
Expected: Version >= 1.0.0.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "deps: openai>=1.0 (für OpenAI-kompatible Provider)"
```

---

### Task 4: OpenAICompatibleProvider (TDD)

**Files:**
- Test: `tests/processing/providers/test_openai.py`
- Create: `vocix/processing/providers/openai_provider.py`

- [ ] **Step 1: Failing test schreiben**

```python
"""Tests für OpenAICompatibleProvider — mock openai SDK."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from vocix.processing.providers import ProviderConfig, ProviderError
from vocix.processing.providers.openai_provider import OpenAICompatibleProvider


def _cfg(api_key: str = "sk-fake", base_url: str = "", model: str = "gpt-4o-mini",
         timeout: float = 5.0) -> ProviderConfig:
    return ProviderConfig(kind="openai", api_key=api_key, base_url=base_url, model=model, timeout=timeout)


def _response(text: str | None) -> SimpleNamespace:
    if text is None:
        return SimpleNamespace(choices=[])
    msg = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


def test_complete_success_returns_text():
    provider = OpenAICompatibleProvider(_cfg())
    provider._client = MagicMock()
    provider._client.chat.completions.create.return_value = _response("Hallo Welt")

    result = provider.complete(system="be polite", user="hi", max_tokens=100)

    assert result == "Hallo Welt"
    kwargs = provider._client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["max_tokens"] == 100
    assert kwargs["messages"] == [
        {"role": "system", "content": "be polite"},
        {"role": "user", "content": "hi"},
    ]


def test_complete_raises_on_api_exception():
    provider = OpenAICompatibleProvider(_cfg())
    provider._client = MagicMock()
    provider._client.chat.completions.create.side_effect = RuntimeError("401")

    with pytest.raises(ProviderError):
        provider.complete(system="x", user="y")


def test_complete_raises_on_empty_choices():
    provider = OpenAICompatibleProvider(_cfg())
    provider._client = MagicMock()
    provider._client.chat.completions.create.return_value = _response(None)

    with pytest.raises(ProviderError):
        provider.complete(system="x", user="y")


def test_complete_raises_on_blank_content():
    provider = OpenAICompatibleProvider(_cfg())
    provider._client = MagicMock()
    provider._client.chat.completions.create.return_value = _response("   ")

    with pytest.raises(ProviderError):
        provider.complete(system="x", user="y")


def test_construct_passes_base_url_when_set():
    """base_url leer → openai-Default; base_url gesetzt → custom-endpoint."""
    fake_openai_class = MagicMock()
    with patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=fake_openai_class)}):
        OpenAICompatibleProvider(_cfg(base_url="https://api.groq.com/openai/v1"))
    kwargs = fake_openai_class.call_args.kwargs
    assert kwargs["base_url"] == "https://api.groq.com/openai/v1"
    assert kwargs["api_key"] == "sk-fake"


def test_construct_omits_base_url_when_empty():
    fake_openai_class = MagicMock()
    with patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=fake_openai_class)}):
        OpenAICompatibleProvider(_cfg(base_url=""))
    kwargs = fake_openai_class.call_args.kwargs
    assert "base_url" not in kwargs or kwargs.get("base_url") in (None, "")


def test_construct_without_key_raises():
    with pytest.raises(ProviderError):
        OpenAICompatibleProvider(_cfg(api_key=""))
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `python -m pytest tests/processing/providers/test_openai.py -v`
Expected: ImportError.

- [ ] **Step 3: `vocix/processing/providers/openai_provider.py` schreiben**

```python
"""OpenAI-kompatibler Provider — funktioniert mit OpenAI, Groq, OpenRouter,
LM Studio, llama.cpp-Server, vLLM. Steuerung via base_url-Override."""
from __future__ import annotations

import logging

from vocix.processing.providers.base import LLMProvider, ProviderConfig, ProviderError

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, config: ProviderConfig):
        if not config.api_key:
            raise ProviderError("OpenAI: API-Key fehlt")
        try:
            import openai  # type: ignore
        except ImportError as e:
            raise ProviderError(f"openai package not installed: {e}") from e

        self._config = config
        kwargs = {"api_key": config.api_key, "timeout": config.timeout}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = openai.OpenAI(**kwargs)

    def complete(self, *, system: str, user: str, max_tokens: int = 1024) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._config.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as e:
            raise ProviderError(f"OpenAI API error: {e}") from e

        choices = getattr(response, "choices", None)
        if not choices:
            raise ProviderError("OpenAI: empty choices in response")
        msg = getattr(choices[0], "message", None)
        content = getattr(msg, "content", None) if msg is not None else None
        if not content or not content.strip():
            raise ProviderError("OpenAI: blank content in response")
        return content.strip()
```

- [ ] **Step 4: Tests laufen lassen**

Run: `python -m pytest tests/processing/providers/test_openai.py -v`
Expected: alle 7 Tests grün.

- [ ] **Step 5: Commit**

```bash
git add vocix/processing/providers/openai_provider.py tests/processing/providers/test_openai.py
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "feat(providers): OpenAICompatibleProvider (OpenAI/Groq/OpenRouter/LM Studio)"
```

---

### Task 5: OllamaProvider (TDD, urllib-basiert)

**Files:**
- Test: `tests/processing/providers/test_ollama.py`
- Create: `vocix/processing/providers/ollama_provider.py`

- [ ] **Step 1: Failing test schreiben**

```python
"""Tests für OllamaProvider — HTTP-basiert, mock urllib.request."""
from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from vocix.processing.providers import ProviderConfig, ProviderError
from vocix.processing.providers.ollama_provider import OllamaProvider


def _cfg(base_url: str = "http://localhost:11434", model: str = "llama3.1:8b",
         timeout: float = 5.0) -> ProviderConfig:
    return ProviderConfig(kind="ollama", base_url=base_url, model=model, timeout=timeout)


def _http_ok(payload: dict) -> MagicMock:
    body = json.dumps(payload).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda *a: None
    return resp


def test_complete_success_returns_text():
    provider = OllamaProvider(_cfg())
    fake = _http_ok({"message": {"content": "Hallo Welt"}})
    with patch("urllib.request.urlopen", return_value=fake) as urlopen:
        result = provider.complete(system="be polite", user="hi", max_tokens=100)

    assert result == "Hallo Welt"
    req = urlopen.call_args.args[0]
    assert req.full_url == "http://localhost:11434/api/chat"
    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "llama3.1:8b"
    assert body["stream"] is False
    assert body["messages"] == [
        {"role": "system", "content": "be polite"},
        {"role": "user", "content": "hi"},
    ]


def test_complete_strips_trailing_slash_in_base_url():
    provider = OllamaProvider(_cfg(base_url="http://localhost:11434/"))
    fake = _http_ok({"message": {"content": "ok"}})
    with patch("urllib.request.urlopen", return_value=fake) as urlopen:
        provider.complete(system="x", user="y")
    assert urlopen.call_args.args[0].full_url == "http://localhost:11434/api/chat"


def test_complete_raises_on_http_error():
    provider = OllamaProvider(_cfg())
    err = HTTPError("http://x/api/chat", 500, "Server Error", {}, io.BytesIO(b"boom"))
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ProviderError):
            provider.complete(system="x", user="y")


def test_complete_raises_on_url_error():
    provider = OllamaProvider(_cfg())
    with patch("urllib.request.urlopen", side_effect=URLError("connection refused")):
        with pytest.raises(ProviderError):
            provider.complete(system="x", user="y")


def test_complete_raises_on_blank_content():
    provider = OllamaProvider(_cfg())
    fake = _http_ok({"message": {"content": "   "}})
    with patch("urllib.request.urlopen", return_value=fake):
        with pytest.raises(ProviderError):
            provider.complete(system="x", user="y")


def test_complete_raises_on_missing_message_field():
    provider = OllamaProvider(_cfg())
    fake = _http_ok({"foo": "bar"})
    with patch("urllib.request.urlopen", return_value=fake):
        with pytest.raises(ProviderError):
            provider.complete(system="x", user="y")


def test_construct_without_base_url_raises():
    with pytest.raises(ProviderError):
        OllamaProvider(_cfg(base_url=""))


def test_construct_without_model_raises():
    with pytest.raises(ProviderError):
        OllamaProvider(_cfg(model=""))
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `python -m pytest tests/processing/providers/test_ollama.py -v`
Expected: ImportError.

- [ ] **Step 3: `vocix/processing/providers/ollama_provider.py` schreiben**

```python
"""Ollama-Provider — HTTP-basiert, kein SDK, stdlib urllib.

API: POST {base_url}/api/chat mit JSON {model, messages, stream:false}.
Antwort: {"message": {"role": "assistant", "content": "..."}, ...}.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from vocix.processing.providers.base import LLMProvider, ProviderConfig, ProviderError

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    def __init__(self, config: ProviderConfig):
        if not config.base_url:
            raise ProviderError("Ollama: base_url fehlt")
        if not config.model:
            raise ProviderError("Ollama: model fehlt")
        self._config = config
        self._endpoint = config.base_url.rstrip("/") + "/api/chat"

    def complete(self, *, system: str, user: str, max_tokens: int = 1024) -> str:
        body = json.dumps({
            "model": self._config.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"num_predict": max_tokens},
        }).encode("utf-8")

        req = urllib.request.Request(
            self._endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._config.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ProviderError(f"Ollama HTTP {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise ProviderError(f"Ollama connection error: {e.reason}") from e
        except (TimeoutError, OSError) as e:
            raise ProviderError(f"Ollama I/O error: {e}") from e
        except json.JSONDecodeError as e:
            raise ProviderError(f"Ollama: invalid JSON response: {e}") from e

        msg = payload.get("message")
        if not isinstance(msg, dict):
            raise ProviderError("Ollama: missing 'message' in response")
        content = msg.get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Ollama: blank content")
        return content.strip()
```

- [ ] **Step 4: Tests laufen lassen**

Run: `python -m pytest tests/processing/providers/test_ollama.py -v`
Expected: alle 8 Tests grün.

- [ ] **Step 5: Commit**

```bash
git add vocix/processing/providers/ollama_provider.py tests/processing/providers/test_ollama.py
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "feat(providers): OllamaProvider (lokale Modelle via HTTP)"
```

---

### Task 6: Provider-Factory (TDD)

**Files:**
- Test: `tests/processing/providers/test_factory.py`
- Create: `vocix/processing/providers/factory.py`
- Modify: `vocix/processing/providers/__init__.py`

- [ ] **Step 1: Failing test schreiben**

```python
"""Tests für build_provider — Slot-ID → konkrete LLMProvider-Instanz."""
from __future__ import annotations

import pytest

from vocix.processing.providers import ProviderConfig, ProviderError, build_provider
from vocix.processing.providers.anthropic_provider import AnthropicProvider
from vocix.processing.providers.openai_provider import OpenAICompatibleProvider
from vocix.processing.providers.ollama_provider import OllamaProvider


def test_build_anthropic():
    cfg = ProviderConfig(kind="anthropic", api_key="sk-ant-x", model="claude-test")
    p = build_provider(cfg)
    assert isinstance(p, AnthropicProvider)


def test_build_openai():
    cfg = ProviderConfig(kind="openai", api_key="sk-x", model="gpt-4o-mini")
    p = build_provider(cfg)
    assert isinstance(p, OpenAICompatibleProvider)


def test_build_ollama():
    cfg = ProviderConfig(kind="ollama", base_url="http://localhost:11434", model="llama3.1:8b")
    p = build_provider(cfg)
    assert isinstance(p, OllamaProvider)


def test_build_unknown_kind_raises():
    cfg = ProviderConfig(kind="gemini", api_key="x", model="y")
    with pytest.raises(ProviderError):
        build_provider(cfg)
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `python -m pytest tests/processing/providers/test_factory.py -v`
Expected: ImportError (`build_provider` nicht exportiert).

- [ ] **Step 3: `vocix/processing/providers/factory.py` schreiben**

```python
"""Factory: ProviderConfig → konkrete LLMProvider-Instanz."""
from __future__ import annotations

from vocix.processing.providers.base import LLMProvider, ProviderConfig, ProviderError


def build_provider(config: ProviderConfig) -> LLMProvider:
    if config.kind == "anthropic":
        from vocix.processing.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(config)
    if config.kind == "openai":
        from vocix.processing.providers.openai_provider import OpenAICompatibleProvider
        return OpenAICompatibleProvider(config)
    if config.kind == "ollama":
        from vocix.processing.providers.ollama_provider import OllamaProvider
        return OllamaProvider(config)
    raise ProviderError(f"Unknown provider kind: {config.kind!r}")
```

- [ ] **Step 4: Re-Export in `__init__.py` ergänzen**

Edit `vocix/processing/providers/__init__.py`:

```python
from vocix.processing.providers.base import LLMProvider, ProviderConfig, ProviderError
from vocix.processing.providers.factory import build_provider

__all__ = ["LLMProvider", "ProviderConfig", "ProviderError", "build_provider"]
```

- [ ] **Step 5: Tests laufen lassen**

Run: `python -m pytest tests/processing/providers/ -v`
Expected: alle Tests aus Tasks 2/4/5/6 grün (insgesamt ~26).

- [ ] **Step 6: Commit**

```bash
git add vocix/processing/providers/factory.py vocix/processing/providers/__init__.py tests/processing/providers/test_factory.py
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "feat(providers): build_provider-Factory + Re-Exports"
```

---

## Phase 2: Config-Schicht

### Task 7: LLMConfig & Resolution-Logik in `Config` (TDD)

**Files:**
- Test: `tests/test_config_llm.py`
- Modify: `vocix/config.py`

**Schema in state.json:**
```json
{
  "llm": {
    "default": "anthropic",
    "business": null,
    "rage": null,
    "providers": {
      "anthropic": {"api_key": "...", "model": "...", "timeout": 15.0, "validated": true},
      "openai":    {"api_key": "...", "base_url": "...", "model": "...", "timeout": 15.0, "validated": false},
      "ollama":    {"base_url": "...", "model": "...", "timeout": 30.0, "validated": false}
    }
  }
}
```

**Resolution-Regeln:**
1. `Config.llm_resolve(slot_id)` → liefert `ProviderConfig`. Wenn Slot leer und `slot_id == "anthropic"`, fällt auf alte Top-Level-Felder (`anthropic_api_key`, `anthropic_model`, `anthropic_timeout`) zurück. Env-Overrides (`VOCIX_LLM_<SLOT>_*`) haben höchste Priorität.
2. `Config.llm_provider_for(mode)` → liefert `ProviderConfig` für `"business"` / `"rage"`. Override gesetzt → Override-Slot, sonst `default`-Slot. Fehlt `default` und ist Anthropic-Alt-Key gesetzt → impliziter Default `"anthropic"`.
3. `Config.llm_validated(slot_id)` → bool. Anthropic/OpenAI: `validated`-Flag. Ollama: `bool(base_url and model)`.

- [ ] **Step 1: Failing tests schreiben**

```python
"""Tests für LLM-Provider-Config-Resolution in vocix.config."""
from __future__ import annotations

from pathlib import Path

import pytest

from vocix.config import Config


def _cfg() -> Config:
    return Config()


def test_llm_resolve_reads_new_schema(monkeypatch, tmp_path):
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {
        "llm": {
            "default": "openai",
            "providers": {
                "openai": {"api_key": "sk-x", "base_url": "https://api.groq.com/openai/v1",
                           "model": "llama-3.1-70b-versatile", "timeout": 12.0, "validated": True},
            },
        },
    }
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    pc = c.llm_resolve("openai")
    assert pc.kind == "openai"
    assert pc.api_key == "sk-x"
    assert pc.base_url == "https://api.groq.com/openai/v1"
    assert pc.model == "llama-3.1-70b-versatile"
    assert pc.timeout == 12.0


def test_llm_resolve_falls_back_to_legacy_anthropic(monkeypatch, tmp_path):
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    # Alte Felder, kein neues llm-Schema
    state = {
        "anthropic_api_key": "sk-ant-old",
        "anthropic_model": "claude-old",
        "anthropic_timeout": 17.0,
    }
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    pc = c.llm_resolve("anthropic")
    assert pc.kind == "anthropic"
    assert pc.api_key == "sk-ant-old"
    assert pc.model == "claude-old"
    assert pc.timeout == 17.0


def test_llm_provider_for_uses_default_when_override_null(monkeypatch, tmp_path):
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {
        "llm": {
            "default": "anthropic",
            "business": None,
            "providers": {
                "anthropic": {"api_key": "sk-ant", "model": "claude-test", "timeout": 15.0},
            },
        },
    }
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    pc = c.llm_provider_for("business")
    assert pc.kind == "anthropic"


def test_llm_provider_for_uses_override_when_set(monkeypatch, tmp_path):
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {
        "llm": {
            "default": "anthropic",
            "business": "ollama",
            "providers": {
                "anthropic": {"api_key": "sk-ant", "model": "claude-test"},
                "ollama": {"base_url": "http://localhost:11434", "model": "llama3.1"},
            },
        },
    }
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    pc = c.llm_provider_for("business")
    assert pc.kind == "ollama"
    assert pc.model == "llama3.1"


def test_llm_provider_for_legacy_implicit_anthropic_default(monkeypatch, tmp_path):
    """Kein neues Schema, nur Alt-Key → Default ist implizit anthropic."""
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {"anthropic_api_key": "sk-ant-old"}
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    pc = c.llm_provider_for("business")
    assert pc.kind == "anthropic"
    assert pc.api_key == "sk-ant-old"


def test_llm_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    monkeypatch.setenv("VOCIX_LLM_DEFAULT", "ollama")
    monkeypatch.setenv("VOCIX_LLM_OLLAMA_BASE_URL", "http://envhost:11434")
    monkeypatch.setenv("VOCIX_LLM_OLLAMA_MODEL", "envmodel")
    monkeypatch.setenv("VOCIX_LLM_OLLAMA_TIMEOUT", "42")

    c = Config.load()
    pc = c.llm_provider_for("business")
    assert pc.kind == "ollama"
    assert pc.base_url == "http://envhost:11434"
    assert pc.model == "envmodel"
    assert pc.timeout == 42.0


def test_llm_validated_anthropic_requires_flag(monkeypatch, tmp_path):
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {"llm": {"providers": {"anthropic": {"api_key": "sk-ant", "validated": False}}}}
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    assert c.llm_validated("anthropic") is False

    state["llm"]["providers"]["anthropic"]["validated"] = True
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")
    c = Config.load()
    assert c.llm_validated("anthropic") is True


def test_llm_validated_ollama_no_flag_required(monkeypatch, tmp_path):
    """Ollama braucht keine Validierung — base_url+model reicht."""
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {"llm": {"providers": {"ollama": {"base_url": "http://localhost:11434",
                                              "model": "llama3.1"}}}}
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    assert c.llm_validated("ollama") is True


def test_llm_validated_legacy_anthropic_key_counts_as_validated(monkeypatch, tmp_path):
    """Der bestehende state-Flag anthropic_key_validated zählt als Migration."""
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {"anthropic_api_key": "sk-ant-old", "anthropic_key_validated": True}
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    assert c.llm_validated("anthropic") is True
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `python -m pytest tests/test_config_llm.py -v`
Expected: AttributeError — `llm_resolve` etc. existieren noch nicht.

- [ ] **Step 3: Resolution-Helper in `vocix/config.py` ergänzen**

Am Ende von `vocix/config.py` (vor evtl. vorhandenen Modul-Suffixen) zwei neue Felder + Methoden in der `Config`-Dataclass anfügen sowie ein paar Top-Level-Helper:

```python
# Am Anfang der Datei, neben dem bestehenden ProviderConfig-Import (gibt’s noch nicht):
from vocix.processing.providers import ProviderConfig
```

In der `Config`-Dataclass nach den bestehenden Anthropic-Feldern ergänzen:

```python
    # Roher llm-Block aus state.json — wird in load() gefüllt.
    # Format siehe docs/superpowers/specs/2026-04-26-llm-provider-abstraction-design.md
    llm: dict = field(default_factory=dict)
```

Im `Config.load()`-Pfad (nach den anderen state-Lookups, vor `__post_init__`) ergänzen:

```python
        # LLM-Provider-Block (rohes Dict; Resolution erfolgt lazy in llm_resolve)
        if isinstance(state.get("llm"), dict):
            config.llm = state["llm"]
```

Dann am Ende der `Config`-Klasse drei neue Methoden:

```python
    # ---- LLM-Provider-Resolution -------------------------------------------

    _LLM_SLOTS = ("anthropic", "openai", "ollama")

    def _llm_slot_dict(self, slot_id: str) -> dict:
        return (self.llm.get("providers") or {}).get(slot_id) or {}

    def _legacy_anthropic_present(self) -> bool:
        return bool(self.anthropic_api_key)

    def llm_resolve(self, slot_id: str) -> ProviderConfig:
        """Liefert ProviderConfig für einen Slot. Berücksichtigt:
        env-Overrides > state.json llm-Block > Legacy-Anthropic-Felder.
        """
        if slot_id not in self._LLM_SLOTS:
            raise ValueError(f"Unknown LLM slot: {slot_id!r}")

        slot = self._llm_slot_dict(slot_id)
        api_key = slot.get("api_key", "")
        base_url = slot.get("base_url", "")
        model = slot.get("model", "")
        timeout = slot.get("timeout", 15.0 if slot_id != "ollama" else 30.0)

        # Legacy-Fallback nur für anthropic, nur wenn neues Schema leer
        if slot_id == "anthropic" and not api_key and self._legacy_anthropic_present():
            api_key = self.anthropic_api_key
            model = model or self.anthropic_model
            timeout = self.anthropic_timeout

        # Env-Overrides (höchste Priorität)
        prefix = f"VOCIX_LLM_{slot_id.upper()}_"
        env_key = os.getenv(prefix + "API_KEY")
        if env_key is not None:
            api_key = env_key
        env_url = os.getenv(prefix + "BASE_URL")
        if env_url is not None:
            base_url = env_url
        env_model = os.getenv(prefix + "MODEL")
        if env_model is not None:
            model = env_model
        env_timeout = os.getenv(prefix + "TIMEOUT")
        if env_timeout is not None:
            try:
                timeout = float(env_timeout)
            except ValueError:
                pass

        return ProviderConfig(
            kind=slot_id, api_key=api_key, base_url=base_url, model=model, timeout=float(timeout),
        )

    def llm_default_slot(self) -> str:
        """Default-Provider-Slot. Env > state.json > impliziter Legacy-Default."""
        env = os.getenv("VOCIX_LLM_DEFAULT")
        if env in self._LLM_SLOTS:
            return env
        configured = self.llm.get("default")
        if configured in self._LLM_SLOTS:
            return configured
        if self._legacy_anthropic_present():
            return "anthropic"
        # Fallback: anthropic — der Resolve liefert dann eine leere Config,
        # build_provider wirft ProviderError, LLMBackedProcessor fällt auf Clean.
        return "anthropic"

    def llm_mode_slot(self, mode: str) -> str:
        """Slot für business/rage. Env > state.json > Default."""
        if mode not in ("business", "rage"):
            raise ValueError(f"Unknown LLM mode: {mode!r}")
        env = os.getenv(f"VOCIX_LLM_{mode.upper()}")
        if env in self._LLM_SLOTS:
            return env
        override = self.llm.get(mode)
        if override in self._LLM_SLOTS:
            return override
        return self.llm_default_slot()

    def llm_provider_for(self, mode: str) -> ProviderConfig:
        return self.llm_resolve(self.llm_mode_slot(mode))

    def llm_validated(self, slot_id: str) -> bool:
        """Ob ein Slot benutzbar konfiguriert ist (für UI-Gating).
        - anthropic/openai: explizites validated-Flag oder Legacy-Flag.
        - ollama: base_url + model gesetzt reicht.
        """
        cfg = self.llm_resolve(slot_id)
        if slot_id == "ollama":
            return bool(cfg.base_url and cfg.model)
        if not cfg.api_key:
            return False
        slot = self._llm_slot_dict(slot_id)
        if slot.get("validated") is True:
            return True
        # Legacy: alter anthropic_key_validated-Flag in state.json
        if slot_id == "anthropic":
            return bool(load_state().get("anthropic_key_validated"))
        return False
```

- [ ] **Step 4: Tests laufen lassen**

Run: `python -m pytest tests/test_config_llm.py -v`
Expected: alle 9 Tests grün.

- [ ] **Step 5: Sicherstellen, dass bestehende Config-Tests grün bleiben**

Run: `python -m pytest tests/test_config.py tests/test_settings_state.py -v`
Expected: keine Regressionen.

- [ ] **Step 6: Commit**

```bash
git add vocix/config.py tests/test_config_llm.py
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "feat(config): LLM-Provider-Resolution mit Legacy-Fallback und Env-Overrides"
```

---

## Phase 3: Processor-Schicht

### Task 8: LLMBackedProcessor (TDD, ersetzt ClaudeProcessor)

**Files:**
- Test: `tests/processing/test_llm_backed.py`
- Create: `vocix/processing/llm_backed.py`

- [ ] **Step 1: Failing test schreiben**

```python
"""Tests für LLMBackedProcessor — Provider-Aufruf, Fallback, Callback."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vocix.config import Config
from vocix.processing.llm_backed import LLMBackedProcessor
from vocix.processing.providers import ProviderError


def _config() -> Config:
    c = Config()
    c.anthropic_api_key = ""
    c.llm = {
        "default": "anthropic",
        "providers": {"anthropic": {"api_key": "sk-x", "model": "claude-test", "validated": True}},
    }
    return c


def test_blank_input_short_circuits():
    proc = LLMBackedProcessor(_config(), name="Business", prompt_key="prompt.business", mode="business")
    assert proc.process("") == ""
    assert proc.process("   ") == "   "


def test_successful_completion_returned():
    cfg = _config()
    fake_provider = MagicMock()
    fake_provider.complete.return_value = "Sehr geehrte Damen und Herren."
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake_provider):
        proc = LLMBackedProcessor(cfg, name="Business", prompt_key="prompt.business", mode="business")
        out = proc.process("das ist fertig")
    assert out == "Sehr geehrte Damen und Herren."
    fake_provider.complete.assert_called_once()
    kwargs = fake_provider.complete.call_args.kwargs
    assert kwargs["user"] == "das ist fertig"
    assert kwargs["system"]  # nicht-leer aus i18n


def test_provider_error_falls_back_to_clean():
    cfg = _config()
    fake_provider = MagicMock()
    fake_provider.complete.side_effect = ProviderError("network down")
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake_provider):
        proc = LLMBackedProcessor(cfg, name="Business", prompt_key="prompt.business", mode="business")
        out = proc.process("äh das ist gut.")
    # Clean entfernt "äh" und setzt Satzanfang groß
    assert out == "Das ist gut."


def test_build_failure_falls_back_to_clean():
    cfg = _config()
    with patch("vocix.processing.llm_backed.build_provider",
               side_effect=ProviderError("config invalid")):
        proc = LLMBackedProcessor(cfg, name="Business", prompt_key="prompt.business", mode="business")
        out = proc.process("äh das ist gut.")
    assert out == "Das ist gut."


def test_fallback_callback_fired_with_mode_name():
    cfg = _config()
    fake_provider = MagicMock()
    fake_provider.complete.side_effect = ProviderError("boom")
    seen = []
    proc = LLMBackedProcessor(
        cfg, name="Business", prompt_key="prompt.business", mode="business",
        on_fallback=lambda mode_name, reason: seen.append((mode_name, reason)),
    )
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake_provider):
        proc.process("hallo")
    assert len(seen) == 1
    assert seen[0][0] == "Business"
    assert "boom" in seen[0][1]


def test_name_property():
    proc = LLMBackedProcessor(_config(), name="Rage", prompt_key="prompt.rage", mode="rage")
    assert proc.name == "Rage"
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `python -m pytest tests/processing/test_llm_backed.py -v`
Expected: ImportError.

- [ ] **Step 3: `vocix/processing/llm_backed.py` schreiben**

```python
"""LLM-gestützter Text-Processor — generalisiert ClaudeProcessor.

Löst pro process()-Call den Provider via Config auf. Bei jedem Fehler
(ProviderError aus dem Provider, oder Config-Issue beim Bau) fällt auf
CleanProcessor zurück und ruft optional den on_fallback-Callback für
das Toast-Overlay.
"""
from __future__ import annotations

import logging
from typing import Callable

from vocix.config import Config
from vocix.i18n import t
from vocix.processing.base import TextProcessor
from vocix.processing.clean import CleanProcessor
from vocix.processing.providers import ProviderError, build_provider

logger = logging.getLogger(__name__)

FallbackCallback = Callable[[str, str], None]
"""(mode_name, reason) → wird gefeuert, wenn auf Clean-Fallback zurückgefallen wird."""


class LLMBackedProcessor(TextProcessor):
    """Modus-Processor, der ein LLM via konfigurierbarem Provider aufruft."""

    def __init__(
        self,
        config: Config,
        *,
        name: str,
        prompt_key: str,
        mode: str,  # "business" | "rage"
        on_fallback: FallbackCallback | None = None,
    ):
        self._config = config
        self._name = name
        self._prompt_key = prompt_key
        self._mode = mode
        self._fallback = CleanProcessor()
        self._on_fallback = on_fallback

    def set_fallback_callback(self, cb: FallbackCallback | None) -> None:
        self._on_fallback = cb

    @property
    def name(self) -> str:
        return self._name

    def process(self, text: str) -> str:
        if not text.strip():
            return text

        provider_cfg = self._config.llm_provider_for(self._mode)
        try:
            provider = build_provider(provider_cfg)
            result = provider.complete(system=t(self._prompt_key), user=text)
        except ProviderError as e:
            logger.info("%s: provider failed (%s) — falling back to Clean", self._name, e)
            if self._on_fallback is not None:
                try:
                    self._on_fallback(self._name, str(e))
                except Exception:  # nie an Callback-Fehler scheitern
                    logger.exception("on_fallback callback raised")
            return self._fallback.process(text)

        return result
```

- [ ] **Step 4: Tests laufen lassen**

Run: `python -m pytest tests/processing/test_llm_backed.py -v`
Expected: alle 6 Tests grün.

- [ ] **Step 5: Commit**

```bash
git add vocix/processing/llm_backed.py tests/processing/test_llm_backed.py
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "feat(processing): LLMBackedProcessor mit Fallback-Callback"
```

---

### Task 9: Business/Rage auf LLMBackedProcessor umstellen, claude_base entfernen

**Files:**
- Modify: `vocix/processing/business.py`
- Modify: `vocix/processing/rage.py`
- Delete: `vocix/processing/claude_base.py`
- Modify: `tests/test_processors_fallback.py`

- [ ] **Step 1: `business.py` umschreiben**

Vollständiger neuer Inhalt von `vocix/processing/business.py`:

```python
from vocix.config import Config
from vocix.processing.llm_backed import LLMBackedProcessor


class BusinessProcessor(LLMBackedProcessor):
    """Modus B: Professionelle Geschäftssprache."""

    def __init__(self, config: Config):
        super().__init__(config, name="Business", prompt_key="prompt.business", mode="business")
```

- [ ] **Step 2: `rage.py` umschreiben**

Vollständiger neuer Inhalt von `vocix/processing/rage.py`:

```python
from vocix.config import Config
from vocix.processing.llm_backed import LLMBackedProcessor


class RageProcessor(LLMBackedProcessor):
    """Modus C: Deeskalation — aggressiv → höflich."""

    def __init__(self, config: Config):
        super().__init__(config, name="Rage", prompt_key="prompt.rage", mode="rage")
```

- [ ] **Step 3: `claude_base.py` löschen**

Run: `rm vocix/processing/claude_base.py`

- [ ] **Step 4: `tests/test_processors_fallback.py` an neuen Datenpfad anpassen**

Vollständiger neuer Inhalt:

```python
"""Tests für Business/Rage-Processor — Fallback-Verhalten.

Geprüft werden die drei Wege, auf denen der LLM-Pfad den Clean-Fallback
aktiviert: (1) Provider-Bau scheitert (kein Key), (2) Provider raised,
(3) Provider liefert leere/ungültige Antwort (im Provider gemappt).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from vocix.config import Config
from vocix.processing.business import BusinessProcessor
from vocix.processing.providers import ProviderError
from vocix.processing.rage import RageProcessor


def _config(api_key: str = "") -> Config:
    c = Config()
    c.anthropic_api_key = api_key
    if api_key:
        c.llm = {
            "default": "anthropic",
            "providers": {"anthropic": {"api_key": api_key, "model": "claude-test",
                                        "timeout": 15.0, "validated": True}},
        }
    return c


# --- BusinessProcessor ---------------------------------------------------

def test_business_no_api_key_falls_back_to_clean():
    proc = BusinessProcessor(_config(api_key=""))
    assert proc.process("äh das ist gut.") == "Das ist gut."


def test_business_provider_exception_falls_back_to_clean():
    proc = BusinessProcessor(_config(api_key="sk-fake"))
    fake = MagicMock()
    fake.complete.side_effect = ProviderError("network down")
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake):
        assert proc.process("äh das ist gut.") == "Das ist gut."


def test_business_successful_response_is_returned():
    proc = BusinessProcessor(_config(api_key="sk-fake"))
    fake = MagicMock()
    fake.complete.return_value = "Sehr geehrte Damen und Herren, der Vorgang ist abgeschlossen."
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake):
        assert proc.process("das ist fertig").startswith("Sehr geehrte")


def test_business_empty_input_short_circuits():
    proc = BusinessProcessor(_config(api_key="sk-fake"))
    assert proc.process("") == ""
    assert proc.process("   ") == "   "


# --- RageProcessor (Parität) ---------------------------------------------

def test_rage_no_api_key_falls_back():
    proc = RageProcessor(_config(api_key=""))
    assert proc.process("äh das ist gut.") == "Das ist gut."


def test_rage_provider_exception_falls_back():
    proc = RageProcessor(_config(api_key="sk-fake"))
    fake = MagicMock()
    fake.complete.side_effect = ProviderError("500")
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake):
        assert proc.process("äh das ist gut.") == "Das ist gut."


def test_rage_uses_rage_prompt_key():
    proc = RageProcessor(_config(api_key="sk-fake"))
    fake = MagicMock()
    fake.complete.return_value = "höflicher Text"
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake):
        proc.process("das ist scheisse")
    kwargs = fake.complete.call_args.kwargs
    assert "system" in kwargs and kwargs["system"]


def test_business_uses_business_prompt_key():
    proc = BusinessProcessor(_config(api_key="sk-fake"))
    fake = MagicMock()
    fake.complete.return_value = "professionell"
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake):
        proc.process("das ist fertig")
    kwargs = fake.complete.call_args.kwargs
    assert "system" in kwargs and kwargs["system"]


def test_names_are_stable():
    """Public names ändern sich durch das Refactor nicht."""
    assert BusinessProcessor(_config()).name == "Business"
    assert RageProcessor(_config()).name == "Rage"
```

- [ ] **Step 5: Tests laufen lassen**

Run: `python -m pytest tests/test_processors_fallback.py tests/processing/ -v`
Expected: alle Tests grün.

- [ ] **Step 6: Gesamten Test-Lauf für Regressionen**

Run: `python -m pytest tests/ -q`
Expected: keine neuen roten Tests. Existierende rote Tests (falls vorher schon rot) ignorieren — nichts an unserem Diff darf verschlimmern.

- [ ] **Step 7: Commit**

```bash
git add vocix/processing/business.py vocix/processing/rage.py tests/test_processors_fallback.py
git rm vocix/processing/claude_base.py
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "refactor(processing): Business/Rage nutzen LLMBackedProcessor, claude_base entfernt"
```

---

## Phase 4: Wiring + UI

### Task 10: Toast-Callback und Migrations-Hinweis in `main.py`

**Files:**
- Modify: `vocix/main.py`

**Ziel:** Bei Provider-Fallback erscheint ein orangenes Overlay-Toast. Beim ersten Start nach Update mit erkanntem Alt-Anthropic-Key erscheint ein einmaliges blaues/oranges Hinweis-Overlay.

- [ ] **Step 1: Konstruktion der Processoren erweitern**

Aktuelle Stelle in `vocix/main.py` (~Zeile 145–150):

```python
self._processors: dict[str, TextProcessor] = {
    "clean": CleanProcessor(),
    "business": BusinessProcessor(self._config),
    "rage": RageProcessor(self._config),
}
```

Ersetzen durch:

```python
self._processors: dict[str, TextProcessor] = {
    "clean": CleanProcessor(),
    "business": BusinessProcessor(self._config),
    "rage": RageProcessor(self._config),
}
# Toast-Callback verkabeln: bei Provider-Fallback orange Meldung im Overlay
def _on_llm_fallback(mode_name: str, reason: str) -> None:
    msg = t("provider.fallback.toast", mode=mode_name)
    logger.info("LLM fallback for %s: %s", mode_name, reason)
    self._overlay.show_temporary(msg, "error")
self._processors["business"].set_fallback_callback(_on_llm_fallback)
self._processors["rage"].set_fallback_callback(_on_llm_fallback)
```

- [ ] **Step 2: Migrations-Hinweis nach `self._overlay.show_temporary(t("overlay.ready"), "done")`**

Nach der `overlay.ready`-Zeile (ca. Z. 180), aber vor dem Logging:

```python
        self._maybe_show_llm_migration_hint()
```

Und eine neue Methode am Ende der Klasse `VocixApp`:

```python
    def _maybe_show_llm_migration_hint(self) -> None:
        """Einmaliger Hinweis bei Update von einer Vorversion mit Alt-Key."""
        from vocix.config import load_state, update_state
        state = load_state()
        if state.get("llm_migration_seen"):
            return
        if not self._config.anthropic_api_key:
            return
        # Wenn der User schon ein neues llm-Schema hat, ist nichts zu sagen.
        if (state.get("llm") or {}).get("providers"):
            return
        self._overlay.show_temporary(t("migration.llm.headline"), "warn", duration=8.0)
        with update_state() as s:
            s["llm_migration_seen"] = True
```

> **Hinweis zum `"warn"`-Style:** Falls `StatusOverlay.show_temporary` keinen `"warn"`-Style kennt, stattdessen `"error"` (orange/rot) verwenden — das ist der existierende Stil für Aufmerksamkeitsmeldungen. Vorher mit `grep -n "show_temporary" vocix/ui/overlay.py` prüfen, welche Stile unterstützt sind, und ggf. anpassen.
> **Hinweis zum `duration`-Argument:** Falls `show_temporary` keinen `duration`-Parameter akzeptiert, das Argument weglassen und in Kauf nehmen, dass der Standard-Timeout greift.

- [ ] **Step 3: Smoke-Test**

Run: `python -m pytest tests/test_main_reload_stt.py -v`
Expected: Tests grün (keine Regression durch unsere Änderungen).

- [ ] **Step 4: Commit**

```bash
git add vocix/main.py
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "feat(main): Provider-Fallback-Toast + Migrations-Hinweis"
```

---

### Task 11: i18n-Strings ergänzen (DE + EN)

**Files:**
- Modify: `vocix/locales/de.json`
- Modify: `vocix/locales/en.json`

- [ ] **Step 1: Neue Keys in `vocix/locales/de.json` einfügen**

Vor der schließenden `}` einfügen (passend einsortiert, JSON-Komma vor neuen Block beachten):

```json
  "provider.anthropic.name": "Anthropic (Claude)",
  "provider.openai.name": "OpenAI-kompatibel",
  "provider.ollama.name": "Ollama (lokal)",

  "provider.test.success": "Verbindung OK",
  "provider.test.error": "Fehler: {detail}",
  "provider.test.in_progress": "Teste…",

  "provider.fallback.toast": "{mode} nicht verfügbar — Cleanmodus aktiv",

  "settings.tab.llm": "KI-Provider",
  "settings.llm.section.routing": "Modus-Zuordnung",
  "settings.llm.default": "Standard-Provider",
  "settings.llm.business_override": "Business",
  "settings.llm.rage_override": "Rage",
  "settings.llm.use_default": "Standard verwenden",
  "settings.llm.section.anthropic": "Anthropic (Claude)",
  "settings.llm.section.openai": "OpenAI-kompatibel",
  "settings.llm.section.ollama": "Ollama (lokal)",
  "settings.llm.field.api_key": "API-Key",
  "settings.llm.field.base_url": "Basis-URL",
  "settings.llm.field.model": "Modell",
  "settings.llm.field.timeout": "Timeout (s)",
  "settings.llm.help.openai_base_url": "Leer = OpenAI. Beispiele: https://api.groq.com/openai/v1, https://openrouter.ai/api/v1, http://localhost:1234/v1 (LM Studio).",
  "settings.llm.help.ollama_base_url": "Standard: http://localhost:11434. Modelle vorher mit \"ollama pull <name>\" laden.",

  "migration.llm.headline": "Neu: VOCIX unterstützt jetzt mehrere KI-Provider. Deine Claude-Konfiguration läuft unverändert. Settings → KI-Provider zum Erweitern.",
```

- [ ] **Step 2: Identische Keys in `vocix/locales/en.json` einfügen (englische Texte)**

```json
  "provider.anthropic.name": "Anthropic (Claude)",
  "provider.openai.name": "OpenAI-compatible",
  "provider.ollama.name": "Ollama (local)",

  "provider.test.success": "Connection OK",
  "provider.test.error": "Error: {detail}",
  "provider.test.in_progress": "Testing…",

  "provider.fallback.toast": "{mode} unavailable — using Clean mode",

  "settings.tab.llm": "AI Provider",
  "settings.llm.section.routing": "Mode Routing",
  "settings.llm.default": "Default provider",
  "settings.llm.business_override": "Business",
  "settings.llm.rage_override": "Rage",
  "settings.llm.use_default": "Use default",
  "settings.llm.section.anthropic": "Anthropic (Claude)",
  "settings.llm.section.openai": "OpenAI-compatible",
  "settings.llm.section.ollama": "Ollama (local)",
  "settings.llm.field.api_key": "API key",
  "settings.llm.field.base_url": "Base URL",
  "settings.llm.field.model": "Model",
  "settings.llm.field.timeout": "Timeout (s)",
  "settings.llm.help.openai_base_url": "Empty = OpenAI. Examples: https://api.groq.com/openai/v1, https://openrouter.ai/api/v1, http://localhost:1234/v1 (LM Studio).",
  "settings.llm.help.ollama_base_url": "Default: http://localhost:11434. Pull models first with \"ollama pull <name>\".",

  "migration.llm.headline": "New: VOCIX now supports multiple AI providers. Your Claude config keeps working. Settings → AI Provider to add more.",
```

- [ ] **Step 3: JSON validieren**

Run:
```bash
python -c "import json; [json.loads(open(p, encoding='utf-8').read()) for p in ('vocix/locales/de.json','vocix/locales/en.json')]; print('OK')"
```
Expected: `OK`. Bei Fehler die Komma-Position prüfen.

- [ ] **Step 4: i18n-Tests**

Run: `python -m pytest tests/test_i18n.py -v`
Expected: grün — Auto-Discovery erkennt die zusätzlichen Keys.

- [ ] **Step 5: Commit**

```bash
git add vocix/locales/de.json vocix/locales/en.json
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "i18n: Strings für KI-Provider-Tab + Fallback-Toast (DE/EN)"
```

---

### Task 12: Settings-Dialog — neuer Tab „KI-Provider", alte Felder verschieben

**Files:**
- Modify: `vocix/ui/settings.py`

**Ziel:** Vier Tabs: Basics / KI-Provider / Erweitert / Expert. Anthropic-API-Key wandert aus Basics in KI-Provider; Anthropic-Modell+Timeout aus Expert in KI-Provider. Drei Karten (Anthropic, OpenAI-kompatibel, Ollama) mit Test-Button. Mode-Routing oben.

> **Hinweis:** Dieser Schritt ist umfangreicher als die übrigen — er verändert eine 638-Zeilen-Datei. Alle Änderungen ausschließlich an den unten markierten Stellen, restliche Methoden unverändert lassen. Nach dem Edit ist ein vollständiger Smoke-Test des Dialogs Pflicht.

- [ ] **Step 1: Neue Helper am Modul-Anfang ergänzen (nach `_ping_anthropic`)**

```python
def _ping_openai(api_key: str, base_url: str, model: str, timeout: float) -> tuple[bool, str]:
    try:
        from vocix.processing.providers import ProviderConfig
        from vocix.processing.providers.openai_provider import OpenAICompatibleProvider
        cfg = ProviderConfig(kind="openai", api_key=api_key, base_url=base_url,
                             model=model or "gpt-4o-mini", timeout=timeout)
        p = OpenAICompatibleProvider(cfg)
        p.complete(system="ping", user="ok", max_tokens=1)
        return True, ""
    except Exception as e:
        return False, str(e)


def _ping_ollama(base_url: str, model: str, timeout: float) -> tuple[bool, str]:
    try:
        from vocix.processing.providers import ProviderConfig
        from vocix.processing.providers.ollama_provider import OllamaProvider
        cfg = ProviderConfig(kind="ollama", base_url=base_url, model=model, timeout=timeout)
        p = OllamaProvider(cfg)
        p.complete(system="ping", user="ok", max_tokens=1)
        return True, ""
    except Exception as e:
        return False, str(e)
```

Den bestehenden `_ping_anthropic` analog auf `tuple[bool, str]` umstellen:

```python
def _ping_anthropic(api_key: str, model: str, timeout: float) -> tuple[bool, str]:
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key, timeout=timeout)
        client.messages.create(
            model=model, max_tokens=1,
            messages=[{"role": "user", "content": "ok"}],
        )
        return True, ""
    except Exception as e:
        logger.info("Anthropic ping failed: %s", e)
        return False, str(e)
```

Anschließend die einzige bestehende Aufrufstelle (`_on_test_api`) anpassen:

```python
        ok, _err = _ping_anthropic(key, self._draft.anthropic_model, self._draft.anthropic_timeout)
```

- [ ] **Step 2: Notebook um neuen Tab erweitern**

In `__init__`, vor `self._tab_advanced = ttk.Frame(...)` (~Zeile 67):

```python
        self._tab_llm = ttk.Frame(self.notebook, padding=12)
```

Direkt nach den existierenden `self.notebook.add(...)` für basics:

```python
        self.notebook.add(self._tab_llm, text=t("settings.tab.llm"))
```

(Die Reihenfolge im UI: Basics, KI-Provider, Erweitert, Expert.)

Anschließend nach `self._build_basics(...)` ergänzen:

```python
        self._build_llm(self._tab_llm)
```

- [ ] **Step 3: API-Key-Block aus `_build_basics` entfernen**

Den gesamten Abschnitt von Zeile ~192 (`# API-Key`) bis vor `# Default Mode` (~Z. 219) löschen. Die zugehörigen Variablen (`self._var_api_key`, `self._api_entry`, `self._var_api_status`) werden in `_build_llm` neu angelegt.

Außerdem in `_refresh_api_gated_widgets` und `_update_mode_combo_values` die Bedingung `bool(self._draft.anthropic_api_key) and self._key_validated()` durch ein neues Helper-Property ersetzen:

```python
    def _any_llm_validated(self) -> bool:
        """B/C nur freischalten, wenn der für sie gewählte Provider validiert ist."""
        for m in ("business", "rage"):
            slot = self._draft.llm_mode_slot(m)
            if not self._draft.llm_validated(slot):
                return False
        return True
```

Und in den beiden Methoden:

```python
    def _refresh_api_gated_widgets(self) -> None:
        valid = self._any_llm_validated()
        ...

    def _update_mode_combo_values(self) -> None:
        valid = self._any_llm_validated()
        ...
```

- [ ] **Step 4: Anthropic-LabelFrame aus `_build_expert` entfernen**

Die Zeilen ab `# Anthropic` (~Z. 513) bis inklusive `self._show_anthropic_section(self._key_validated())` (~Z. 540) entfernen. Auch der `_show_anthropic_section`-Aufruf in `_on_test_api` (Z. 332) verschwindet — Anthropic-Section lebt nun komplett im neuen Tab.

- [ ] **Step 5: Neue Methode `_build_llm` ans Ende der Klasse anfügen (vor `_on_external_language_change`)**

```python
    def _build_llm(self, frame: ttk.Frame) -> None:
        from vocix.ui.tooltip import Tooltip
        import threading

        for col in (0, 1, 2):
            frame.columnconfigure(col, weight=1 if col == 1 else 0)

        # ---- Routing-Sektion (oben) -----------------------------------
        routing = ttk.LabelFrame(frame, text=t("settings.llm.section.routing"), padding=8)
        routing.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        for col in (0, 1):
            routing.columnconfigure(col, weight=0)
        routing.columnconfigure(2, weight=1)

        slot_labels = (
            ("anthropic", t("provider.anthropic.name")),
            ("openai", t("provider.openai.name")),
            ("ollama", t("provider.ollama.name")),
        )
        slot_values = [k for k, _ in slot_labels]
        slot_display = {k: v for k, v in slot_labels}

        # Default
        ttk.Label(routing, text=t("settings.llm.default")).grid(row=0, column=0, sticky="w", pady=2)
        self._var_llm_default = tk.StringVar(value=self._draft.llm_default_slot())
        cb_default = ttk.Combobox(routing, state="readonly", width=22, textvariable=self._var_llm_default,
                                  values=tuple(slot_values))
        cb_default.grid(row=0, column=1, sticky="w")
        cb_default.bind("<<ComboboxSelected>>", lambda _e: self._on_routing_changed())

        # Business override
        ttk.Label(routing, text=t("settings.llm.business_override")).grid(row=1, column=0, sticky="w", pady=2)
        self._var_llm_business = tk.StringVar(value=(self._draft.llm.get("business") or "__default__"))
        cb_b = ttk.Combobox(routing, state="readonly", width=22, textvariable=self._var_llm_business,
                            values=("__default__", *slot_values))
        cb_b.grid(row=1, column=1, sticky="w")
        cb_b.bind("<<ComboboxSelected>>", lambda _e: self._on_routing_changed())

        # Rage override
        ttk.Label(routing, text=t("settings.llm.rage_override")).grid(row=2, column=0, sticky="w", pady=2)
        self._var_llm_rage = tk.StringVar(value=(self._draft.llm.get("rage") or "__default__"))
        cb_r = ttk.Combobox(routing, state="readonly", width=22, textvariable=self._var_llm_rage,
                            values=("__default__", *slot_values))
        cb_r.grid(row=2, column=1, sticky="w")
        cb_r.bind("<<ComboboxSelected>>", lambda _e: self._on_routing_changed())

        # ---- Provider-Karten -----------------------------------------
        self._llm_status_vars: dict[str, tk.StringVar] = {}

        # Anthropic
        anth = ttk.LabelFrame(frame, text=t("settings.llm.section.anthropic"), padding=8)
        anth.grid(row=1, column=0, columnspan=3, sticky="ew", pady=4)
        anth.columnconfigure(1, weight=1)
        self._var_llm_anth_key = tk.StringVar(value=self._draft.anthropic_api_key or "")
        self._var_llm_anth_model = tk.StringVar(value=self._draft.anthropic_model)
        self._var_llm_anth_timeout = tk.DoubleVar(value=self._draft.anthropic_timeout)
        self._llm_status_vars["anthropic"] = tk.StringVar(value="")
        self._build_provider_card(
            anth, slot_id="anthropic",
            fields=[
                ("api_key", self._var_llm_anth_key, "password"),
                ("model", self._var_llm_anth_model, "text"),
                ("timeout", self._var_llm_anth_timeout, "spin"),
            ],
        )

        # OpenAI-kompatibel
        oai = ttk.LabelFrame(frame, text=t("settings.llm.section.openai"), padding=8)
        oai.grid(row=2, column=0, columnspan=3, sticky="ew", pady=4)
        oai.columnconfigure(1, weight=1)
        slot_oai = (self._draft.llm.get("providers") or {}).get("openai") or {}
        self._var_llm_oai_key = tk.StringVar(value=slot_oai.get("api_key", ""))
        self._var_llm_oai_url = tk.StringVar(value=slot_oai.get("base_url", ""))
        self._var_llm_oai_model = tk.StringVar(value=slot_oai.get("model", "gpt-4o-mini"))
        self._var_llm_oai_timeout = tk.DoubleVar(value=slot_oai.get("timeout", 15.0))
        self._llm_status_vars["openai"] = tk.StringVar(value="")
        self._build_provider_card(
            oai, slot_id="openai",
            fields=[
                ("base_url", self._var_llm_oai_url, "text"),
                ("api_key", self._var_llm_oai_key, "password"),
                ("model", self._var_llm_oai_model, "text"),
                ("timeout", self._var_llm_oai_timeout, "spin"),
            ],
            help_key="settings.llm.help.openai_base_url",
        )

        # Ollama
        oll = ttk.LabelFrame(frame, text=t("settings.llm.section.ollama"), padding=8)
        oll.grid(row=3, column=0, columnspan=3, sticky="ew", pady=4)
        oll.columnconfigure(1, weight=1)
        slot_oll = (self._draft.llm.get("providers") or {}).get("ollama") or {}
        self._var_llm_oll_url = tk.StringVar(value=slot_oll.get("base_url", "http://localhost:11434"))
        self._var_llm_oll_model = tk.StringVar(value=slot_oll.get("model", "llama3.1:8b"))
        self._var_llm_oll_timeout = tk.DoubleVar(value=slot_oll.get("timeout", 30.0))
        self._llm_status_vars["ollama"] = tk.StringVar(value="")
        self._build_provider_card(
            oll, slot_id="ollama",
            fields=[
                ("base_url", self._var_llm_oll_url, "text"),
                ("model", self._var_llm_oll_model, "text"),
                ("timeout", self._var_llm_oll_timeout, "spin"),
            ],
            help_key="settings.llm.help.ollama_base_url",
        )

    def _build_provider_card(
        self,
        parent: ttk.LabelFrame,
        *,
        slot_id: str,
        fields: list[tuple[str, tk.Variable, str]],
        help_key: str | None = None,
    ) -> None:
        from vocix.ui.tooltip import Tooltip
        row = 0
        for fname, var, kind in fields:
            ttk.Label(parent, text=t(f"settings.llm.field.{fname}")).grid(row=row, column=0, sticky="w", pady=2)
            if kind == "password":
                e = ttk.Entry(parent, textvariable=var, show="*", width=36)
            elif kind == "spin":
                e = ttk.Spinbox(parent, from_=1, to=120, increment=1, width=8, textvariable=var)
            else:
                e = ttk.Entry(parent, textvariable=var, width=36)
            e.grid(row=row, column=1, sticky="ew")
            row += 1

        # Help-Text optional
        if help_key:
            ttk.Label(parent, text=t(help_key), foreground="#666", wraplength=560).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(2, 4)
            )
            row += 1

        # Test-Button + Status
        btn = ttk.Button(parent, text=t("settings.button.test"),
                         command=lambda s=slot_id: self._on_llm_test(s))
        btn.grid(row=row, column=0, sticky="w", pady=(4, 0))
        ttk.Label(parent, textvariable=self._llm_status_vars[slot_id]).grid(
            row=row, column=1, sticky="w", padx=(8, 0), pady=(4, 0)
        )

    def _on_routing_changed(self) -> None:
        # Werte ins llm-Dict spiegeln
        self._draft.llm.setdefault("providers", {})
        self._draft.llm["default"] = self._var_llm_default.get()
        b = self._var_llm_business.get()
        r = self._var_llm_rage.get()
        self._draft.llm["business"] = None if b == "__default__" else b
        self._draft.llm["rage"] = None if r == "__default__" else r
        self._refresh_api_gated_widgets()

    def _on_llm_test(self, slot_id: str) -> None:
        from vocix.config import update_state
        status_var = self._llm_status_vars[slot_id]
        status_var.set(t("provider.test.in_progress"))
        self._win.update_idletasks()

        if slot_id == "anthropic":
            ok, err = _ping_anthropic(
                self._var_llm_anth_key.get().strip(),
                self._var_llm_anth_model.get().strip(),
                float(self._var_llm_anth_timeout.get()),
            )
        elif slot_id == "openai":
            ok, err = _ping_openai(
                self._var_llm_oai_key.get().strip(),
                self._var_llm_oai_url.get().strip(),
                self._var_llm_oai_model.get().strip(),
                float(self._var_llm_oai_timeout.get()),
            )
        elif slot_id == "ollama":
            ok, err = _ping_ollama(
                self._var_llm_oll_url.get().strip(),
                self._var_llm_oll_model.get().strip(),
                float(self._var_llm_oll_timeout.get()),
            )
        else:
            ok, err = False, f"unknown slot {slot_id}"

        # Status-Flag in state.json sofort persistieren (für sofortiges Gating)
        with update_state() as s:
            s.setdefault("llm", {}).setdefault("providers", {}).setdefault(slot_id, {})
            s["llm"]["providers"][slot_id]["validated"] = ok

        if ok:
            status_var.set(t("provider.test.success"))
        else:
            short = (err or "")[:80]
            status_var.set(t("provider.test.error", detail=short))

        self._refresh_api_gated_widgets()
```

- [ ] **Step 6: `_on_apply` / `_on_ok` müssen alle neuen Felder ins `llm`-Schema schreiben und Legacy-Felder bereinigen**

In `_on_apply` und `_on_ok` *vor* dem `self._on_apply_cb(replace(self._draft))`-Call:

```python
        self._persist_llm_draft()
```

Neue Methode:

```python
    def _persist_llm_draft(self) -> None:
        """Schreibt die UI-Variablen ins draft.llm-Schema und entfernt Legacy-Felder."""
        providers = self._draft.llm.setdefault("providers", {})
        providers["anthropic"] = {
            "api_key": self._var_llm_anth_key.get().strip(),
            "model": self._var_llm_anth_model.get().strip(),
            "timeout": float(self._var_llm_anth_timeout.get()),
            "validated": providers.get("anthropic", {}).get("validated", False),
        }
        providers["openai"] = {
            "api_key": self._var_llm_oai_key.get().strip(),
            "base_url": self._var_llm_oai_url.get().strip(),
            "model": self._var_llm_oai_model.get().strip(),
            "timeout": float(self._var_llm_oai_timeout.get()),
            "validated": providers.get("openai", {}).get("validated", False),
        }
        providers["ollama"] = {
            "base_url": self._var_llm_oll_url.get().strip(),
            "model": self._var_llm_oll_model.get().strip(),
            "timeout": float(self._var_llm_oll_timeout.get()),
        }
        # Legacy-Felder im draft leerziehen — VocixApp.apply_settings schreibt das
        # neue Schema; eine leere Anthropic-Top-Level-Konfig signalisiert dem
        # apply-Pfad, die Alt-Keys aus state.json zu löschen.
        self._draft.anthropic_api_key = providers["anthropic"]["api_key"]
        self._draft.anthropic_model = providers["anthropic"]["model"]
        self._draft.anthropic_timeout = providers["anthropic"]["timeout"]
```

> **Hinweis:** Das Bereinigen der Top-Level-Legacy-Keys aus `state.json` passiert in `VocixApp.apply_settings`. Falls der dortige Schreibpfad nur einzelne Felder schreibt: dort zusätzlich `s.pop("anthropic_api_key", None)`, `s.pop("anthropic_model", None)`, `s.pop("anthropic_timeout", None)` ergänzen, sobald `s["llm"]["providers"]["anthropic"]` gesetzt ist. Mit `grep -n "anthropic_api_key" vocix/main.py` die Stelle finden.

- [ ] **Step 7: Existierende Settings-Tests anpassen oder ergänzen**

Run: `python -m pytest tests/test_apply_settings.py tests/test_settings_state.py tests/test_i18n_settings.py -v`

Falls Tests rot werden, weil sie auf das alte API-Key-Feld in Basics zugreifen:
- Die Tests passend auf den neuen Tab umziehen (Test-IDs in Tab `settings.tab.llm`).
- Wenn ein Test reine state.json-Migration prüft (alte Felder → bleiben sichtbar), ist das nach unserem Design erwünscht — der Test darf grün bleiben.

Ziel: alle drei Dateien bleiben grün oder bekommen klar lokalisierte, neue Assertions.

- [ ] **Step 8: Manueller UI-Smoke-Test**

Run: `python -m vocix.main`
Anschließend Tray → Einstellungen → Tab „KI-Provider" öffnen.
Erwartet:
- Vier Tabs sichtbar.
- Drei Karten (Anthropic / OpenAI / Ollama), jede mit Test-Button.
- Default-Provider-Dropdown zeigt drei Optionen.
- Business/Rage-Dropdowns zeigen "Standard verwenden" + drei Slots.
- Test-Button bei leeren Feldern → roter Status mit Fehlermeldung.
- Test mit echten Anthropic-Credentials → grüner ✓-Status, B/C-Modus-Dropdowns werden aktiviert.

Wenn der Smoke-Test scheitert (Crash, falsches Layout, fehlende Übersetzungen): vor dem Commit fixen.

- [ ] **Step 9: Commit**

```bash
git add vocix/ui/settings.py
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "feat(ui/settings): Tab \"KI-Provider\" mit drei Slots + Test-Button"
```

---

### Task 13: VocixApp.apply_settings — neues llm-Schema persistieren, Legacy bereinigen

**Files:**
- Modify: `vocix/main.py`
- Test: bestehender `tests/test_apply_settings.py` als Regressionsschutz

- [ ] **Step 1: apply_settings-Pfad lokalisieren**

Run: `grep -n "def apply_settings\|def _save_state_from_config\|anthropic_api_key" vocix/main.py`
Notiere die Zeile(n), die heute `s["anthropic_api_key"] = ...` schreiben.

- [ ] **Step 2: Schreibpfad anpassen**

Im `apply_settings`-Pfad (oder dem Helper, der `state.json` aus dem Config-Draft schreibt) den bisherigen Block, der die drei Anthropic-Felder einzeln schreibt, ersetzen durch:

```python
        # Neues llm-Schema (führt) — komplett aus draft.llm übernehmen
        if isinstance(new_config.llm, dict) and new_config.llm:
            s["llm"] = new_config.llm
            # Legacy-Felder ausräumen, sobald neues Schema vorhanden ist
            for legacy in ("anthropic_api_key", "anthropic_model",
                           "anthropic_timeout", "anthropic_key_validated"):
                s.pop(legacy, None)
        else:
            # Pre-Migration-Pfad — alte Felder weiter pflegen
            s["anthropic_api_key"] = new_config.anthropic_api_key
            s["anthropic_model"] = new_config.anthropic_model
            s["anthropic_timeout"] = new_config.anthropic_timeout
```

> **Hinweis:** Wenn der Schreibpfad eine andere Variable als `s` und `new_config` verwendet, Bezeichner entsprechend anpassen. Wenn der Block in einer anderen Datei lebt (z. B. einem Settings-Service), dort analog anwenden.

- [ ] **Step 3: Tests laufen**

Run: `python -m pytest tests/test_apply_settings.py tests/test_settings_state.py -v`
Expected: grün. Falls rot: Test-Erwartungen an das neue Schema anpassen (state-Inhalt nach Apply enthält nun `llm` statt `anthropic_*`).

- [ ] **Step 4: Vollständiger Test-Lauf**

Run: `python -m pytest tests/ -q`
Expected: keine neuen Roten gegenüber Baseline.

- [ ] **Step 5: Commit**

```bash
git add vocix/main.py tests/test_apply_settings.py tests/test_settings_state.py
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "feat(main): apply_settings schreibt llm-Schema, Legacy-Keys aufräumen"
```

---

## Phase 5: Abschluss

### Task 14: README/Beispielkonfig + Manueller End-to-End-Test

**Files:**
- (optional) Modify: `README.md` falls Provider-Doku ergänzt werden soll — nur wenn in der Spec verlangt
- Modify: `.env.example` — neue Env-Variablen erwähnen

- [ ] **Step 1: `.env.example` erweitern**

Am Ende der Datei anhängen:

```bash

# --- LLM-Provider (optional) ----------------------------------------------
# Wahl pro Modus. Werte: anthropic | openai | ollama
# VOCIX_LLM_DEFAULT=anthropic
# VOCIX_LLM_BUSINESS=ollama
# VOCIX_LLM_RAGE=anthropic

# OpenAI-kompatible Provider (OpenAI, Groq, OpenRouter, LM Studio, …)
# VOCIX_LLM_OPENAI_API_KEY=sk-…
# VOCIX_LLM_OPENAI_BASE_URL=https://api.groq.com/openai/v1
# VOCIX_LLM_OPENAI_MODEL=llama-3.1-70b-versatile
# VOCIX_LLM_OPENAI_TIMEOUT=15

# Ollama (lokal)
# VOCIX_LLM_OLLAMA_BASE_URL=http://localhost:11434
# VOCIX_LLM_OLLAMA_MODEL=llama3.1:8b
# VOCIX_LLM_OLLAMA_TIMEOUT=30
```

- [ ] **Step 2: Manueller End-to-End-Test (mit echtem Ollama, falls verfügbar)**

Vorbereitung (einmalig):
```bash
# Ollama installieren — siehe https://ollama.com
# ollama pull llama3.1:8b
```

Anschließend in VOCIX:
1. App starten: `python -m vocix.main`
2. Tray → Einstellungen → KI-Provider
3. Ollama-Karte: base_url `http://localhost:11434`, model `llama3.1:8b`, Test-Button drücken → ✓
4. Default-Provider auf `ollama` umstellen, OK
5. Mode B (Business) per Hotkey wechseln, ein Diktat aufnehmen → Antwort vom lokalen Modell
6. Ollama stoppen (`taskkill /IM ollama.exe /F` oder Service stoppen)
7. Erneutes Diktat → Toast „Business nicht verfügbar — Cleanmodus aktiv", Text wird sauber transkribiert (Clean-Fallback)

Falls kein Ollama verfügbar: alternativ OpenAI-kompatibel mit z. B. einem kostenlosen Groq-Key testen.

- [ ] **Step 3: Smoke-Test der gesamten Suite**

Run: `python -m pytest tests/ -v`
Expected: alle Tests grün.

- [ ] **Step 4: Commit**

```bash
git add .env.example
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -m "docs: .env.example um LLM-Provider-Variablen erweitert"
```

---

### Task 15: Migration-Toast und Memory-Eintrag

**Files:**
- Modify: `C:\Users\RTF\.claude\projects\E--Claude-RTF-TextME\memory\project_textme.md` (oder neuer Memory-Eintrag)

- [ ] **Step 1: Memory-Eintrag aktualisieren**

`MEMORY.md` und/oder ein passender Memory-Eintrag (`project_*.md`) sollten festhalten:
- LLM-Provider-Abstraktion gelandet (Anthropic + OpenAI-kompatibel + Ollama).
- State-Schema-Erweiterung (`llm`-Sektion).
- Spec-Referenz: `docs/superpowers/specs/2026-04-26-llm-provider-abstraction-design.md`.

Datei direkt editieren, kurzer Eintrag, ein Satz in `MEMORY.md` als Hook.

- [ ] **Step 2: Final Commit**

```bash
git -c user.name="Jens Fricke" -c user.email="aijourney22@gmail.com" commit -am "docs(memory): LLM-Provider-Abstraktion verzeichnet"
```

(Memory-Dateien liegen außerhalb des Repos — der Commit-Schritt entfällt, falls keine Repo-Datei betroffen ist. In dem Fall Memory-Update außerhalb von git.)

---

## Self-Review

**Spec-Coverage:**

| Spec-Anforderung | Task |
|---|---|
| `LLMProvider`-ABC + drei Implementierungen | 1, 2, 4, 5 |
| `ProviderError` einheitlich | 1, in jedem Provider |
| `build_provider`-Factory | 6 |
| `openai>=1.0` Dependency | 3 |
| `state.json llm`-Schema (default/business/rage/providers) | 7 |
| `Config.llm_provider_for(mode)` Resolution | 7 |
| Env-Overrides | 7, 14 |
| Nicht-destruktive Migration der Legacy-Felder | 7 (Resolution), 13 (Save-Pfad) |
| `LLMBackedProcessor` ersetzt `ClaudeProcessor` | 8, 9 |
| Toast bei Fallback | 10 |
| Erstkontakt-Hinweis (`llm_migration_seen`) | 10 |
| Settings-Tab mit drei Karten + Test-Button | 12 |
| Mode-Routing (Default + Per-Mode-Override) | 12 |
| i18n DE+EN | 11 |
| Tests pro Provider + Integration + Migration | 2, 4, 5, 6, 7, 8, 9 |

**Placeholder-Scan:** Keine "TBD"/"TODO"/"implement later" gefunden. Alle Code-Blöcke vollständig.

**Type-Konsistenz:**
- `ProviderConfig` Felder: `kind`, `api_key`, `base_url`, `model`, `timeout` — durchgängig.
- `ProviderError`: einheitlich bei allen Providern und im LLMBackedProcessor gefangen.
- `LLMBackedProcessor.__init__`: Kwargs `name`, `prompt_key`, `mode`, `on_fallback` — Tasks 8, 9, 10 stimmen überein.
- `Config.llm_resolve` / `llm_provider_for` / `llm_validated` / `llm_default_slot` / `llm_mode_slot` — Naming durchgängig in Tasks 7, 12.

**Scope:** Eine Implementierungseinheit. Kein Subsystem, das man hätte abspalten müssen.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-26-llm-provider-abstraction.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — ich dispatche pro Task einen frischen Subagent, prüfe zwischen Tasks, schnelle Iteration.

**2. Inline Execution** — Tasks in dieser Session, batched mit Checkpoints.

**Welcher Weg?**
