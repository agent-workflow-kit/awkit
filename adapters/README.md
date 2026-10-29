# Bundled adapters

An adapter describes how `awkit` talks to one registered tool (architecture section 7.1). The tool registry in `~/.config/awkit/config.yaml` maps roles to tools (e.g. `roles: {githost: forgectl, tickets: ticketctl, notify: notice-route}`); each registered tool needs an adapter.

This directory holds the adapters that ship with `awkit`: one per awkit tool, plus adapters for common third-party CLIs.

## Forms

- **Declarative YAML first.** Command templates (e.g. `list: "jobsctl list --json --queue {queue}"`), jq/JSONPath mappings from the tool's `--json` output into the harness model, trigger definitions (poll intervals, files to watch as early-poll triggers), and `periodic:` declarations used by `awkit cron install`.
- **Escape hatches.** Any single operation, or a whole adapter, can instead be:
  - a Python function, or
  - an external executable speaking the harness-defined stdin/stdout JSON protocol.

  The protocol belongs to the harness; tools never see it and never change for it.

## User overlay

`~/.config/awkit/adapters/` adds adapters or overrides bundled ones, for example a private adapter pointing a role at an organization-internal tool. Organization-specific adapters never belong in this repo.

## Status

The adapter file format is an open topic of the `awkit` design session (`docs/design.md`); it will be specified in `docs/interface.md`. No adapters ship yet.
