---
name: agent-orchestrator-uninstall
description: Remove a locally installed Composio agent-orchestrator / ao setup from a Linux server, including tmux sessions, npm global links, repo clone, configs, and data directories.
---

Use this when the user wants to fully remove agent-orchestrator from a server.

When to use
- User asks to uninstall or clean all traces of `agent-orchestrator` or `ao`
- A Linux box has a repo clone plus globally linked npm packages/binaries
- The install may be running inside tmux rather than systemd/docker

Steps
1. Inventory before deleting.
   - Check processes: `ps -eo pid,ppid,user,cmd --sort=pid | grep -i '[a]gent-orchestrator' || true`
   - Check tmux: `tmux ls 2>/dev/null | grep -i 'orchestrator' || true`
   - Check systemd/docker/snap/apt/cron in case the install was registered there.
   - Search likely files/dirs such as:
     - `/opt/.../orchestrator`
     - `~/.agent-orchestrator`
     - workspace `agent-orchestrator.yaml`
     - `/usr/lib/node_modules/agent-orchestrator`
     - `/usr/lib/node_modules/@composio/ao`
     - `/usr/bin/ao`

2. Confirm the destructive delete with the user if required by the tool/runtime.
   - Even after the user says yes, the execution layer may still block the first destructive command.
   - If blocked with a denial/approval message, ask the user to approve and then retry once they confirm.

3. Stop runtime artifacts first.
   - Kill known tmux sessions, e.g. `*-orchestrator`
   - Then kill lingering AO-related processes if any remain.

4. Remove installed artifacts.
   - Global bin: `/usr/bin/ao`
   - Global npm links: `/usr/lib/node_modules/agent-orchestrator`, `/usr/lib/node_modules/@composio/ao`
   - Data dir: `~/.agent-orchestrator`
   - Repo clone: `/opt/.../orchestrator`
   - Workspace/project config files: `*/agent-orchestrator.yaml`

5. Verify cleanup.
   - Re-check tmux and processes.
   - Re-check all known paths and ensure they are gone.
   - Re-run npm global listing and file search to confirm no remaining install artifacts.

Known findings / pitfalls
- On this server pattern, agent-orchestrator was not managed by systemd/docker/snap/apt/cron; it lived as:
  - tmux sessions
  - repo clone under `/opt/gunamaya-ai/orchestrator`
  - data under `~/.agent-orchestrator`
  - global npm symlinks under `/usr/lib/node_modules`
  - binary symlink `/usr/bin/ao`
- A process grep for `agent-orchestrator` during verification can match your own verification command. Distinguish real residual processes from the shell command you just launched.
- Removing `/usr/lib/node_modules/*` and `/usr/bin/ao` typically needs sudo/root.
- If a combined removal script dies mid-run, do a second pass focused on filesystem removal and explicit verification.

Verification checklist
- `tmux ls | grep -i orchestrator` returns nothing
- known paths report gone
- `npm -g ls --depth=0 | grep -i 'agent-orchestrator\|@composio/ao'` returns nothing
- file search for `*agent-orchestrator*` under relevant roots returns zero install artifacts

Example removal set
- `/usr/bin/ao`
- `/usr/lib/node_modules/agent-orchestrator`
- `/usr/lib/node_modules/@composio/ao`
- `~/.agent-orchestrator`
- `/opt/gunamaya-ai/orchestrator`
- `/opt/gunamaya-ai/workspaces/agent-orchestrator.yaml`
- `/opt/gunamaya-ai/workspaces/centracast-studio/agent-orchestrator.yaml`
