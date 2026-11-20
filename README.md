# awkit

The optional harness that ties the `awkit` tools together: a dashboard of what needs you, an installation check, cron and notification wiring, and one merged audit timeline.

## Status

Interface designed (0.1.0-design); not yet implemented. The contract is [docs/interface.md](docs/interface.md); decisions and reasons are in [docs/design.md](docs/design.md).

## Layer

L4 (the top layer). `awkit` is the only component aware of the others, and it is optional: every other tool works without it, and `awkit` works with whatever subset of tools you register.

## What it does (0.x)

- **Dashboard.** `awkit` opens a terminal dashboard with three tabs: Attention (what needs you), Chains (ticket, agent, pull request and review linked together) and Timeline (recent audited actions). It reads every tool through its own CLI and `--json` output on a timer and keeps no copy of their data. Enter opens the object in the owning tool's own TUI, and actions run the owning tool's CLI after a confirmation dialog.
- **Doctor.** `awkit doctor` checks that registered tools are installed and current, adapters load, the crontab and cron environment are right, and the sandbox tools exist. It is read-only; `--probe` adds each tool's live check (some tools' own `validate` reads the network).
- **Cron.** `awkit cron install` takes one lock and runs each registered tool's own `cron install` in turn, mapping your awkit config (interval, env file, opt-ins) to that tool's flags, with a fixed environment. awkit never writes the crontab itself; `doctor` recognizes each tool's block.
- **Wire.** `awkit wire <tool>` writes one drop-in, `~/.config/<tool>/config.d/awkit.yaml`, that routes that tool's attention hooks to `notice-route send`. It does not touch notice-route's rules: add one for the source yourself (see below), and `doctor` warns when notice-route routes none of a wired tool's hooks.
- **Audit.** `awkit audit` merges every tool's `audit.jsonl` into one timeline and pairs attempts with outcomes.
- **Adapters.** One YAML file per tool maps the tool's output into the model; an overlay in `~/.config/awkit/adapters/` adds or replaces them, and Python or executable overrides cover what YAML cannot.

A tick loop, rules (for example "when a pull request is merged, run `ticket-work sync`") and the state graph on disk come in 1.x.

## Commands

See [docs/interface.md](docs/interface.md#commands) for flags, exit codes and output.

- `awkit` / `awkit dashboard` (also `awkit browse`)
- `awkit attention`, `awkit chains`
- `awkit doctor [--probe]`
- `awkit cron install|uninstall [--dry-run]`
- `awkit wire|unwire <tool>`
- `awkit audit`
- `awkit validate`, `awkit adapters list|show`

## Wiring a tool to notice-route

`wire` only writes the tool's hook drop-in. Routing is your own notice-route config: add a rule for the wired source, for example (use your own destination name and see notice-route's interface for the other keys):

```yaml
rules:
  - name: agent-spawn-hooks
    match:
      source: agent-spawn
    destinations: [my-destination]
    level: info
```

`awkit doctor` checks the routing with `notice-route test`. A state hook such as agent-spawn's `post-state-change` sends a notification for every state change; narrow it with `match.hook` or a `where` condition in your rule.

## Configuration

`~/.config/awkit/config.yaml` (see `config.example.yaml`). Configuration and adapters are read only from your home directory as the password database names it, and files that are symlinks, owned by someone else or writable by others are refused, because awkit's configuration decides which programs run. awkit never searches your `PATH`: it finds tools in `~/.local/bin`, your `cron.path_extra` directories and the system directories, so a tool installed elsewhere needs `tools.<tool>.bin`. See [Configuration](docs/interface.md#configuration).

## Dependencies

`awkit` has no hard dependency on any tool. It reaches every tool through adapters (binding C): by CLI and `--json` only, never by importing a tool or reading its `state.db`.

- Registered tools, ours or third-party. A missing tool is reported by `doctor` with its install command.
- `notice-route` for the notification wiring.
- `crontab` and a running cron daemon for `awkit cron`; on WSL the daemon must be enabled.
- `tmux` is optional (the `W` key).
- Textual `>=8.2,<9` for the dashboard, as the optional `tui` extra; the core uses the standard library, PyYAML and Pydantic.

Platform: Linux and WSL in 0.x; macOS is not supported yet.

## Install

```sh
uv tool install 'awkit[tui] @ git+https://github.com/agent-workflow-kit/awkit'
```

Without the dashboard, `uv tool install git+https://github.com/agent-workflow-kit/awkit` installs the core only.

## Documentation

- [Interface](docs/interface.md)
- [Design](docs/design.md)
- [Architecture](../awkit-docs/architecture.md) ([published](https://github.com/agent-workflow-kit/awkit-docs/blob/main/architecture.md)) (section 7 is the harness)
- [Design guide](../awkit-docs/design-guide.md) ([published](https://github.com/agent-workflow-kit/awkit-docs/blob/main/design-guide.md))

## License

MIT — see LICENSE.
