---
name: hermes-gateway-command-surface-audit
description: Audit the safest command surface for exposing repo/runtime actions in Hermes chat platforms, especially Telegram.
---

# Hermes Gateway Command Surface Audit

Use this when a user wants to trigger local scripts, runtime wrappers, or repo-specific actions from Hermes chat (Telegram/Discord/etc.) and you need to decide whether to use a built-in slash command, quick_commands, or plugins.

## Goal

Pick the lowest-risk integration surface that already works in Hermes, and avoid half-implemented plugin paths.

## Procedure

1. Verify target repo and current dirty state first.
   - Run:
     - `pwd`
     - `git branch --show-current`
     - `git remote -v | head`
     - `git status --short`
   - If dirty files already exist, explicitly note them before proposing implementation.

2. Inspect gateway dispatch order.
   - Read `gateway/run.py` around the main command dispatch section.
   - Confirm whether the desired surface is:
     - built-in canonical command
     - quick command from config
     - plugin command
     - skill slash command
   - Important: quick_commands run before the agent loop and bypass LLM calls.

3. Inspect config ingestion for quick commands.
   - Read `gateway/config.py` to confirm `quick_commands` from `~/.hermes/config.yaml` are loaded into gateway config.
   - Read docs/tests for quick_commands to confirm intended behavior.

4. Inspect CLI parity.
   - Read `cli.py` and `hermes_cli/commands.py` so the recommendation accounts for both CLI and gateway behavior.
   - This matters because a surface that works only in CLI may still be wrong for Telegram.

5. Audit plugin command viability before recommending plugins.
   - Search for:
     - `get_plugin_command_handler`
     - `_plugin_commands`
     - `register_plugin_command`
   - If dispatch references exist in `cli.py` / `gateway/run.py` but implementation is missing in `hermes_cli/plugins.py`, treat plugin slash commands as non-authoritative / unusable.
   - Check tests for notes about removed or unimplemented plugin command support.

6. Check runtime/tool side constraints.
   - For CentraCast-style runtime wrappers, inspect package scripts and helper docs.
   - Confirm whether the command surface needs:
     - static command only
     - dynamic user args
     - status/inspect latest
     - run by explicit ID/ref

7. Recommend the simplest surface that satisfies the need.
   - Prefer `quick_commands` when all of these are true:
     - the action can be expressed as a fixed shell command
     - instant/no-LLM invocation is desirable
     - Telegram chat should invoke it directly
   - Prefer built-in slash commands only when behavior is product-level, stateful, or needs custom parsing/output handling.
   - Do **not** recommend plugin slash commands unless you have verified the full implementation path exists.

## Known findings from April 2026

### Quick commands are the current safest Telegram surface

- `gateway/run.py` dispatches `quick_commands` before normal agent execution.
- `gateway/config.py` loads `quick_commands` from `config.yaml`.
- Tests in `tests/test_quick_commands.py` verify gateway behavior.

### Plugin slash commands are currently a trap

Audit found a mismatch:
- `cli.py` and `gateway/run.py` attempt to call `get_plugin_command_handler(...)`
- `cli.py` also references `get_plugin_manager()._plugin_commands`
- but `hermes_cli/plugins.py` does not implement that command-handler surface
- `tests/test_plugins.py` contains a note that plugin command support was removed / never implemented

Conclusion: do not route Telegram runtime actions through plugin slash commands unless that subsystem is repaired first.

### Important quick_commands limitation

- `type: exec` is static shell execution.
- `type: alias` forwards arguments to another slash command, not to an arbitrary shell template.
- Therefore, quick_commands are great for fixed flows like:
  - start latest runtime wrapper
  - inspect latest
  - inspect blocker latest
- But not enough by themselves for rich dynamic commands like `/inspect_run <ref>` unless you add argument-aware command templating or a built-in handler.

## Recommended decision rule

For first-slice Telegram runtime integration:
1. use quick_commands for fixed run/inspect flows
2. add tiny wrapper scripts if output needs shaping
3. only add a built-in command if dynamic args or richer stateful UX is required
4. avoid plugin commands until the implementation gap is fixed

## Good verification checklist

- Confirm gateway dispatch order in `gateway/run.py`
- Confirm config ingestion in `gateway/config.py`
- Confirm tests exist in `tests/test_quick_commands.py`
- Confirm plugin command implementation is real, not just referenced
- Confirm runtime scripts/docs support the proposed fixed commands
- Re-check `git status --short` so you do not touch unrelated dirty files

## Pitfalls

- Assuming plugin command dispatch is working because the call sites exist
- Recommending a built-in slash command when `quick_commands` already solves the first slice
- Forgetting that `exec` quick_commands are static and do not interpolate arbitrary user args
- Ignoring unrelated dirty files in the repo before implementation
