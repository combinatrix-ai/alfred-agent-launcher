#!/usr/bin/python3

import base64
import json
import os
import sys


PRESETS = [
    ("codex-luna-cli", "Luna", "codex", "cli", "gpt-5.6-luna"),
    ("codex-terra-cli", "Terra", "codex", "cli", "gpt-5.6-terra"),
    ("codex-sol-cli", "Sol", "codex", "cli", "gpt-5.6-sol"),
    ("codex-desktop", "Codex Desktop", "codex", "desktop", ""),
    ("claude-fable-cli", "Fable", "claude", "cli", "fable"),
    ("claude-opus-cli", "Opus", "claude", "cli", "opus"),
    ("claude-haiku-cli", "Haiku", "claude", "cli", "haiku"),
    ("claude-desktop", "Claude Desktop", "claude", "desktop", ""),
]

CODEX_EFFORTS = {"minimal", "low", "medium", "high", "xhigh"}
CLAUDE_EFFORTS = {"low", "medium", "high", "xhigh", "max"}


def effective_effort(provider: str, surface: str, model: str, requested: str) -> str:
    if surface != "cli" or not requested:
        return ""
    if provider == "codex" and requested in CODEX_EFFORTS:
        return requested
    if provider == "claude" and model != "haiku" and requested in CLAUDE_EFFORTS:
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


def build_items(prompt: str, requested_effort: str) -> list[dict]:
    args = {}
    for uid, _title, provider, surface, model in PRESETS:
        effort = effective_effort(provider, surface, model, requested_effort)
        args[uid] = payload(provider, surface, model, effort, prompt)

    items = []
    for uid, title, provider, surface, model in PRESETS:
        effort = effective_effort(provider, surface, model, requested_effort)
        items.append(
            {
                "uid": uid,
                "title": title,
                "subtitle": subtitle(provider, surface, model, effort, prompt),
                "arg": args[uid],
                "valid": True,
                "icon": {"path": f"icon-{provider}.png"},
                "mods": {
                    "cmd": {
                        "valid": True,
                        "arg": args["claude-fable-cli"],
                        "subtitle": "Claude CLI · fable" + (" · new session" if not prompt else ""),
                    },
                    "alt": {
                        "valid": True,
                        "arg": args["codex-desktop"],
                        "subtitle": "Codex Desktop · " + ("new session" if not prompt else "review & send"),
                    },
                },
                "text": {"copy": prompt, "largetype": prompt},
            }
        )
    return items


def main() -> None:
    prompt = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    requested_effort = os.environ.get("default_effort", "").strip().lower()
    json.dump(
        {"items": build_items(prompt, requested_effort)},
        sys.stdout,
        ensure_ascii=False,
    )


if __name__ == "__main__":
    main()
