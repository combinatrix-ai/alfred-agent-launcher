#!/usr/bin/python3

import base64
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from urllib.parse import urlencode


ALLOWED_MODELS = {
    "codex": {"gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"},
    "claude": {"fable", "opus", "haiku"},
}
ALLOWED_EFFORTS = {
    "codex": {"", "minimal", "low", "medium", "high", "xhigh"},
    "claude": {"", "low", "medium", "high", "xhigh", "max"},
}


def decode_payload(encoded: str) -> dict[str, str]:
    padding = "=" * (-len(encoded) % 4)
    request = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
    required = {"provider", "surface", "model", "effort", "prompt"}
    if set(request) != required or not all(isinstance(value, str) for value in request.values()):
        raise SystemExit("Invalid workflow payload")
    return request


def resolve_executable(name: str) -> str:
    candidates = [
        Path.home() / ".local/bin" / name,
        Path("/opt/homebrew/bin") / name,
        Path("/usr/local/bin") / name,
        Path.home() / ".npm-global/bin" / name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    resolved = shutil.which(name)
    if resolved:
        return resolved
    raise SystemExit(f"{name} CLI was not found")


def validate_cli_request(request: dict[str, str]) -> None:
    provider = request["provider"]
    if provider not in ALLOWED_MODELS:
        raise SystemExit("Unsupported provider")
    if request["model"] not in ALLOWED_MODELS[provider]:
        raise SystemExit("Unsupported model")
    if request["effort"] not in ALLOWED_EFFORTS[provider]:
        raise SystemExit("Unsupported effort")


def build_cli_command(request: dict[str, str], executable: str) -> str:
    validate_cli_request(request)
    argv = ["exec", executable, "--model", request["model"]]
    if request["effort"]:
        if request["provider"] == "codex":
            argv.extend(["-c", f'model_reasoning_effort="{request["effort"]}"'])
        else:
            argv.extend(["--effort", request["effort"]])
    if request["prompt"]:
        argv.append(request["prompt"])
    return shlex.join(argv)


def launch_terminal(command: str) -> None:
    script = r'''
on run argv
    set commandText to item 1 of argv
    set terminalWasRunning to application "Terminal" is running
    tell application "Terminal"
        if terminalWasRunning and (count of windows) > 0 then
            activate
            tell application "System Events" to keystroke "t" using command down
            delay 0.15
            do script commandText in selected tab of front window
        else
            do script commandText
            activate
        end if
    end tell
end run
'''
    subprocess.run(["/usr/bin/osascript", "-e", script, command], check=True)


def launch_cli(request: dict[str, str]) -> None:
    executable = resolve_executable(request["provider"])
    launch_terminal(build_cli_command(request, executable))


def desktop_url(request: dict[str, str]) -> str:
    if request["provider"] == "codex":
        url = "codex://threads/new"
        query = {"prompt": request["prompt"]}
    elif request["provider"] == "claude":
        url = "claude://code/new"
        query = {"q": request["prompt"]}
    else:
        raise SystemExit("Unsupported provider")
    return url + ("?" + urlencode(query) if request["prompt"] else "")


def launch_desktop(request: dict[str, str]) -> None:
    if request["model"] or request["effort"]:
        raise SystemExit("Desktop payload cannot override model or effort")
    subprocess.run(["/usr/bin/open", desktop_url(request)], check=True)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Expected one encoded Alfred argument")
    request = decode_payload(sys.argv[1])
    if request["surface"] == "cli":
        launch_cli(request)
    elif request["surface"] == "desktop":
        launch_desktop(request)
    else:
        raise SystemExit("Unsupported surface")


if __name__ == "__main__":
    main()
