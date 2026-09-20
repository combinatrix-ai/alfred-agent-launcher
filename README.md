# Agent Launcher for Alfred

Send one prompt to Codex or Claude, in CLI or Desktop.

Type `ag`, enter a prompt, and choose an agent. CLI targets start in Terminal;
Desktop targets open the prompt for review before sending.

## Latest models

When online, Agent Launcher refreshes available model names every 24 hours.
Codex models come from the installed Codex CLI, and Claude models come from
[claude-models-list](https://github.com/combinatrix-ai/claude-models-list).

If latest models are unavailable, Agent Launcher uses each CLI's default model.

## Install

Requires macOS and Alfred 5 with the Powerpack. Install at least one supported
[Codex](https://developers.openai.com/codex/) or
[Claude](https://claude.ai/download) app or CLI.

Download [Agent-Launcher.alfredworkflow](https://github.com/combinatrix-ai/alfred-agent-launcher/releases/latest/download/Agent-Launcher.alfredworkflow)
and open it in Alfred. The default keyword is `ag`. Sign in to the app or CLI
you want to use before launching it through Alfred.

To update, download the latest workflow and replace the existing workflow in
Alfred. Updates are manual. The release includes a SHA-256 checksum file; place
it alongside the download and run:

```bash
shasum -a 256 -c Agent-Launcher.alfredworkflow.sha256
```

## Local data and support

Model catalogs and refresh errors are cached in Alfred’s workflow cache directory
(or `~/Library/Caches/ai.combinatrix.alfred.agent-launcher` when run outside Alfred).
The launcher does not write prompts to this cache. Prompts are passed to the
selected app or CLI; that application manages its own history and authentication.
Removing the workflow does not delete history held by those applications.

Report issues on [GitHub](https://github.com/combinatrix-ai/alfred-agent-launcher/issues).

## Development

```bash
./scripts/test.sh
./scripts/build.sh
```

## License

[MIT](LICENSE)
