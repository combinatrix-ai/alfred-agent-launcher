#!/usr/bin/python3

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen


CACHE_TTL_SECONDS = 24 * 60 * 60
ERROR_RETRY_SECONDS = 5 * 60
REFRESH_LOCK_TTL_SECONDS = 30
CACHE_VERSION = 1
CLAUDE_MODELS_URL = (
    "https://raw.githubusercontent.com/combinatrix-ai/"
    "claude-models-list/main/models.json"
)
MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
PROVIDERS = ("codex", "claude")
FAMILIES = {
    "codex": (("luna", "Luna"), ("terra", "Terra"), ("sol", "Sol")),
    "claude": (("fable", "Fable"), ("opus", "Opus"), ("haiku", "Haiku")),
}
CODEX_EFFORTS = {"minimal", "low", "medium", "high", "xhigh"}
CLAUDE_EFFORTS = {"low", "medium", "high", "xhigh", "max"}


def effective_effort(provider: str, surface: str, model: str, requested: str) -> str:
    if surface != "cli" or not requested:
        return ""
    if provider == "codex" and requested in CODEX_EFFORTS:
        return requested
    if provider == "claude" and "haiku" not in model.lower() and requested in CLAUDE_EFFORTS:
        return requested
    return ""


def payload(provider: str, surface: str, model: str, effort: str, prompt: str) -> str:
    raw = json.dumps(
        {
            "provider": provider,
            "surface": surface,
            "model": model,
            "effort": effort,
            "prompt": prompt,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def subtitle(provider: str, surface: str, model: str, effort: str, prompt: str) -> str:
    if surface == "desktop":
        text = "Model in app · review & send"
    else:
        product = "Codex CLI" if provider == "codex" else "Claude CLI"
        text = f"{product} · {model}"
        if effort:
            text += f" · {effort}"
    if not prompt:
        text = "Model in app · new session" if surface == "desktop" else f"{text} · new session"
    return text


def _valid_model(model: dict) -> bool:
    model_id = model.get("id")
    display_name = model.get("display_name")
    return (
        isinstance(model_id, str)
        and MODEL_ID_PATTERN.fullmatch(model_id) is not None
        and isinstance(display_name, str)
        and 0 < len(display_name) <= 100
    )


def normalize_codex_catalog(document: dict) -> list[dict]:
    raw_models = document.get("models")
    if not isinstance(raw_models, list):
        raise ValueError("Codex catalog has no models array")
    models = []
    for raw in raw_models:
        if not isinstance(raw, dict) or raw.get("visibility") != "list":
            continue
        model = {
            "id": raw.get("slug"),
            "display_name": raw.get("display_name"),
            "priority": raw.get("priority", 1_000_000),
        }
        if _valid_model(model):
            models.append(model)
    return models


def normalize_claude_catalog(document: dict) -> list[dict]:
    raw_models = document.get("data")
    if not isinstance(raw_models, list):
        raise ValueError("Claude catalog has no data array")
    models = []
    for raw in raw_models:
        if not isinstance(raw, dict):
            continue
        model = {
            "id": raw.get("id"),
            "display_name": raw.get("display_name"),
            "created_at": raw.get("created_at", ""),
        }
        if _valid_model(model):
            models.append(model)
    return models


def _matches_family(provider: str, model_id: str, family: str) -> bool:
    if provider == "codex":
        return model_id.lower().endswith(f"-{family}")
    return re.search(rf"(?:^|-){re.escape(family)}(?:-|$)", model_id.lower()) is not None


def select_family_models(provider: str, models: list[dict]) -> list[dict]:
    selected = []
    for family, title in FAMILIES[provider]:
        candidates = [model for model in models if _matches_family(provider, model["id"], family)]
        if not candidates:
            continue
        if provider == "codex":
            model = min(
                candidates,
                key=lambda item: (
                    item.get("priority") if isinstance(item.get("priority"), int) else 1_000_000,
                    item["id"],
                ),
            )
        else:
            model = max(candidates, key=lambda item: (str(item.get("created_at", "")), item["id"]))
        selected.append({"family": family, "title": title, **model})
    return selected


def _desktop_item(provider: str, prompt: str) -> dict:
    title = "Codex Desktop" if provider == "codex" else "Claude Desktop"
    uid = f"{provider}-desktop"
    return {
        "uid": uid,
        "title": title,
        "subtitle": subtitle(provider, "desktop", "", "", prompt),
        "arg": payload(provider, "desktop", "", "", prompt),
        "valid": True,
        "icon": {"path": f"icon-{provider}.png"},
        "text": {"copy": prompt, "largetype": prompt},
    }


def _status_item(provider: str, status: dict) -> dict:
    return {
        "uid": f"{provider}-models-status",
        "title": status["title"],
        "subtitle": status["subtitle"],
        "valid": False,
        "icon": {"path": f"icon-{provider}.png"},
    }


def build_items(
    prompt: str,
    requested_effort: str,
    models_by_provider: dict[str, list[dict]],
    statuses: dict[str, dict] | None = None,
) -> list[dict]:
    statuses = statuses or {}
    items = []
    args = {
        "codex-desktop": payload("codex", "desktop", "", "", prompt),
        "claude-desktop": payload("claude", "desktop", "", "", prompt),
    }
    selected_by_provider = {
        provider: select_family_models(provider, models_by_provider.get(provider, []))
        for provider in PROVIDERS
    }
    for provider, models in selected_by_provider.items():
        for model in models:
            effort = effective_effort(provider, "cli", model["id"], requested_effort)
            args[f"{provider}-{model['family']}-cli"] = payload(
                provider, "cli", model["id"], effort, prompt
            )

    for provider in PROVIDERS:
        for model in selected_by_provider[provider]:
            uid = f"{provider}-{model['family']}-cli"
            effort = effective_effort(provider, "cli", model["id"], requested_effort)
            items.append(
                {
                    "uid": uid,
                    "title": model["title"],
                    "subtitle": subtitle(provider, "cli", model["id"], effort, prompt),
                    "arg": args[uid],
                    "valid": True,
                    "icon": {"path": f"icon-{provider}.png"},
                    "text": {"copy": prompt, "largetype": prompt},
                }
            )
        items.append(_desktop_item(provider, prompt))
        if provider in statuses:
            items.append(_status_item(provider, statuses[provider]))

    fable_arg = args.get("claude-fable-cli")
    for item in items:
        if not item.get("valid"):
            continue
        if fable_arg:
            command_modifier = {
                "valid": True,
                "arg": fable_arg,
                "subtitle": "Claude CLI · "
                + next(
                    model["id"]
                    for model in selected_by_provider["claude"]
                    if model["family"] == "fable"
                )
                + (" · new session" if not prompt else ""),
            }
        else:
            command_modifier = {
                "valid": False,
                "subtitle": "Claude models unavailable",
            }
        item["mods"] = {
            "cmd": command_modifier,
            "alt": {
                "valid": True,
                "arg": args["codex-desktop"],
                "subtitle": "Codex Desktop · " + ("new session" if not prompt else "review & send"),
            },
        }
    return items


def workflow_cache_dir() -> Path:
    configured = os.environ.get("alfred_workflow_cache", "").strip()
    if configured:
        return Path(configured)
    return Path.home() / "Library/Caches/ai.combinatrix.alfred.agent-launcher"


def _cache_path(cache_dir: Path, provider: str) -> Path:
    return cache_dir / f"models-{provider}.json"


def _error_path(cache_dir: Path, provider: str) -> Path:
    return cache_dir / f"models-{provider}-error.json"


def _lock_path(cache_dir: Path) -> Path:
    return cache_dir / "models-refresh.lock"


def _read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def read_fresh_cache(cache_dir: Path, provider: str, now: float | None = None) -> list[dict] | None:
    now = time.time() if now is None else now
    cached = _read_json(_cache_path(cache_dir, provider))
    if not cached or cached.get("version") != CACHE_VERSION:
        return None
    fetched_at = cached.get("fetched_at")
    models = cached.get("models")
    if not isinstance(fetched_at, (int, float)) or now - fetched_at >= CACHE_TTL_SECONDS:
        return None
    if not isinstance(models, list) or not models or not all(isinstance(model, dict) and _valid_model(model) for model in models):
        return None
    return models


def _recent_error(cache_dir: Path, provider: str, now: float) -> dict | None:
    error = _read_json(_error_path(cache_dir, provider))
    if not error or not isinstance(error.get("attempted_at"), (int, float)):
        return None
    return error if now - error["attempted_at"] < ERROR_RETRY_SECONDS else None


def _status_for_error(provider: str, error: dict) -> dict:
    title = "Codex models unavailable" if provider == "codex" else "Claude models unavailable"
    if error.get("kind") == "cli_missing":
        subtitle_text = "Codex CLI not found — cannot list available models"
    elif provider == "claude":
        subtitle_text = "No internet access — cannot list latest models"
    else:
        subtitle_text = "Could not refresh the Codex model catalog"
    return {"title": title, "subtitle": subtitle_text}


def _loading_status(provider: str) -> dict:
    product = "Codex" if provider == "codex" else "Claude"
    return {
        "title": f"Refreshing {product} models…",
        "subtitle": "Model choices will appear automatically",
        "loading": True,
    }


def _lock_is_fresh(cache_dir: Path, now: float) -> bool:
    try:
        return now - _lock_path(cache_dir).stat().st_mtime < REFRESH_LOCK_TTL_SECONDS
    except OSError:
        return False


def _start_refresh(cache_dir: Path, providers: list[str]) -> bool:
    cache_dir.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(cache_dir)
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        if _lock_is_fresh(cache_dir, time.time()):
            return True
        try:
            lock_path.unlink()
        except OSError:
            return False
        return _start_refresh(cache_dir, providers)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(str(time.time()))
    try:
        subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--refresh-models",
                str(cache_dir),
                ",".join(providers),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except OSError:
        try:
            lock_path.unlink()
        except OSError:
            pass
        return False


def discover_models(cache_dir: Path, now: float | None = None) -> tuple[dict, dict, bool]:
    now = time.time() if now is None else now
    models_by_provider = {}
    statuses = {}
    pending = []
    for provider in PROVIDERS:
        models = read_fresh_cache(cache_dir, provider, now)
        if models is not None:
            models_by_provider[provider] = models
            continue
        error = _recent_error(cache_dir, provider, now)
        if error:
            statuses[provider] = _status_for_error(provider, error)
        else:
            pending.append(provider)

    if pending:
        refreshing = _lock_is_fresh(cache_dir, now) or _start_refresh(cache_dir, pending)
        if refreshing:
            for provider in pending:
                statuses[provider] = _loading_status(provider)
        else:
            for provider in pending:
                statuses[provider] = _status_for_error(provider, {"kind": "refresh_failed"})
    return models_by_provider, statuses, any(status.get("loading") for status in statuses.values())


def _resolve_codex() -> str:
    candidates = [
        Path.home() / ".local/bin/codex",
        Path("/opt/homebrew/bin/codex"),
        Path("/usr/local/bin/codex"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    resolved = shutil.which("codex")
    if resolved:
        return resolved
    raise FileNotFoundError("Codex CLI not found")


def fetch_codex_models() -> list[dict]:
    executable = _resolve_codex()
    result = subprocess.run(
        [executable, "debug", "models"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return normalize_codex_catalog(json.loads(result.stdout))


def fetch_claude_models() -> list[dict]:
    request = Request(
        CLAUDE_MODELS_URL,
        headers={"Accept": "application/json", "User-Agent": "alfred-agent-launcher/0.2"},
    )
    with urlopen(request, timeout=8) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("Claude model catalog is too large")
    return normalize_claude_catalog(json.loads(body.decode("utf-8")))


def refresh_models(cache_dir: Path, providers: list[str]) -> None:
    try:
        for provider in providers:
            try:
                models = fetch_codex_models() if provider == "codex" else fetch_claude_models()
                if not select_family_models(provider, models):
                    raise ValueError(f"No supported {provider} model families found")
                _write_json_atomic(
                    _cache_path(cache_dir, provider),
                    {
                        "version": CACHE_VERSION,
                        "provider": provider,
                        "fetched_at": time.time(),
                        "models": models,
                    },
                )
                try:
                    _error_path(cache_dir, provider).unlink()
                except OSError:
                    pass
            except Exception as error:
                kind = "cli_missing" if isinstance(error, FileNotFoundError) else "refresh_failed"
                _write_json_atomic(
                    _error_path(cache_dir, provider),
                    {
                        "version": CACHE_VERSION,
                        "provider": provider,
                        "attempted_at": time.time(),
                        "kind": kind,
                        "detail": str(error)[:200],
                    },
                )
    finally:
        try:
            _lock_path(cache_dir).unlink()
        except OSError:
            pass


def main() -> None:
    if len(sys.argv) == 4 and sys.argv[1] == "--refresh-models":
        cache_dir = Path(sys.argv[2])
        providers = [provider for provider in sys.argv[3].split(",") if provider in PROVIDERS]
        refresh_models(cache_dir, providers)
        return

    prompt = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    requested_effort = os.environ.get("default_effort", "").strip().lower()
    models_by_provider, statuses, rerun = discover_models(workflow_cache_dir())
    output = {"items": build_items(prompt, requested_effort, models_by_provider, statuses)}
    if rerun:
        output["rerun"] = 0.5
    json.dump(output, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
