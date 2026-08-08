# Changelog

## 0.2.0 - Unreleased

- Discover current Codex CLI models from `codex debug models`.
- Discover current Claude models from the public `claude-models-list` snapshot.
- Cache successful model catalogs for 24 hours and refresh them without blocking Alfred.
- Fall back to each CLI's configured default when a model catalog cannot be refreshed.

## 0.1.0 - Unreleased

- Launch Codex CLI with Luna, Terra, or Sol.
- Launch Claude CLI with Fable, Opus, or Haiku.
- Open Codex Desktop or Claude Desktop Code with a prefilled prompt.
- Configure the Alfred keyword, defaulting to `ag`.
- Optionally apply one default CLI effort to supported models.
- Use Command-Enter for Fable and Option-Enter for Codex Desktop.
