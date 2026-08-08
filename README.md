# Agent Launcher for Alfred

Send one prompt to Codex or Claude, in CLI or Desktop.

![Agent Launcher showing Codex and Claude launch targets in Alfred](assets/agent-launcher.jpg)

Type `ag`, enter a prompt, and choose an agent. CLI targets start in Terminal;
Desktop targets open the prompt for review before sending.

## Latest models

When online, Agent Launcher refreshes available model names every 24 hours.
Codex models come from the installed Codex CLI, and Claude models come from
[claude-models-list](https://github.com/combinatrix-ai/claude-models-list).

If a model list cannot be refreshed and no fresh cache is available, its CLI
choices are hidden. Desktop choices remain available.

## Install

Requires macOS and Alfred 5 with the Powerpack. Install at least one supported
[Codex](https://developers.openai.com/codex/) or
[Claude](https://claude.ai/download) app or CLI.

Download `Agent-Launcher.alfredworkflow` from the latest GitHub release and
open it. The default Alfred keyword is `ag`.

## Development

```bash
./scripts/test.sh
./scripts/build.sh
```

## License

[MIT](LICENSE)
