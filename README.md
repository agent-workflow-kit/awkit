# awkit

The optional harness that ties the `awkit` tools together: tool registry, adapters, label-derived state graph, rules, tick/run loop, hook wiring, dashboard TUI and merged audit timeline.

## Status

Pre-design: interface not yet specified; see [docs/design.md](docs/design.md).

## Layer

L4 (the top layer). `awkit` is the only component aware of the others, and it is optional: every other tool works without it.

## What it does

- **Tool registry and adapters.** Reads a registry (`roles: {githost: forgectl, ...}`) from its config naming which tool fills each role. Each registered tool has an adapter describing how `awkit` talks to it: declarative YAML first (command templates, jq/JSONPath mappings, triggers, `periodic:` declarations), with Python or external-executable escape hatches. Adapters for our tools and common third-party CLIs ship in this repo; a user overlay at `~/.config/awkit/adapters/` adds or overrides them.
- **Tick and run.** `awkit tick` polls due adapters, diffs snapshots, derives harness events, updates the state graph and evaluates rules. Cron runs `awkit tick`; `awkit run` (and the open dashboard) loops ticks with early-tick triggers (poll intervals, file watchers on tools' public logs, pushes via `awkit notify-tick`). One tick runs at a time; ticks are idempotent.
- **Hook wiring.** `awkit wire <tool>` shows and applies the hook registrations that let a tool call `awkit`, writing only the drop-in `~/.config/<tool>/config.d/awkit.yaml`; `awkit unwire <tool>` reverses it.
- **State graph.** Tickets, worktrees, agents, windows, jobs, PRs, review drafts, gate decisions and notifications, linked mostly through labels on lower-tool objects; largely disposable and rebuildable from tool outputs.
- **Rules.** "When X then Y" on derived events; actions run detached or via jobsctl and never block the tick.
- **Dashboard TUI.** Attention list, ticket → agent → PR → review chains, recent events; launches tools' own TUIs in the foreground; actions go through the owning tool's CLI.
- **Other commands.** Merged audit timeline, cron installation from adapters' `periodic:` declarations, `doctor`.

## Indicative commands

Indicative, finalized in [docs/interface.md](docs/interface.md).

- `awkit dashboard` (or `awkit` with no arguments)
- `awkit tick`, `awkit run`
- `awkit notify-tick [--source <tool>]`
- `awkit wire <tool> [--yes]`, `awkit unwire <tool>`
- `awkit audit`
- `awkit cron install|uninstall`
- `awkit doctor`

## Dependencies

`awkit` has no hard dependency on any tool. It reaches every tool through the tool registry and adapters (architecture section 7.1); which tools are used is configuration.

- Registered tools (ours or third-party), via adapters: binding C (adapter) by architecture; adapter format details are decided in this tool's design session.
- `crontab` (for `awkit cron install|uninstall`): binding TBD (A/B/C), decided in this tool's design session.
- Textual (dashboard TUI) and the YAML/Pydantic stack from the design guide: to be justified in the design session.

## Install

```sh
uv tool install git+https://github.com/agent-workflow-kit/awkit
```

## Documentation

- [Architecture](../awkit-docs/architecture.md) ([published](https://github.com/agent-workflow-kit/awkit-docs/blob/main/architecture.md)) (section 7 is the harness)
- [Design guide](../awkit-docs/design-guide.md) ([published](https://github.com/agent-workflow-kit/awkit-docs/blob/main/design-guide.md))

## License

MIT — see LICENSE.
