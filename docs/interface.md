# awkit: interface

Status: 0.1.0-design (2026-11-19). This document is the single normative source for awkit's rules. `design.md`, the README and the architecture link to its headings and never restate its tables. Section references (architecture §N, design guide §N) point to `../awkit-docs/architecture.md` and `../awkit-docs/design-guide.md`.

awkit is the harness (layer 4, architecture §7): the optional tool that knows the others only through configuration and adapters. Release 0.x is stateless apart from its own audit file and one small cache: it reads every tool through its documented CLI and `--json` output, shows what needs the user in a dashboard, checks the installation, runs each tool's own `cron install`, writes the notification wiring, and merges the tools' audit files into one timeline. The tick loop, the rules engine, the action ledger and the state graph on disk are 1.x (see Roadmap). Every other tool works without awkit, and awkit works with whatever subset of tools is registered.

## Overview

- **Tool.** A program with one adapter. Ours and third-party tools are treated the same.
- **Adapter.** One YAML file per tool that tells awkit how to run the tool, read its output into rows, find its attention items and links, run its actions, install its cron block, find its audit file and check it (see Adapters). Bundled adapters ship in the awkit repo; an overlay directory adds or replaces them.
- **Read.** A named command of an adapter that asks the tool to change nothing and prints `--json`; its output is turned into rows with a fixed field set by the path language (see Reads).
- **Attention item.** One entry of the Attention list: something that needs the user, derived by awkit from rows. Tools never create attention items.
- **Link and chain.** A link joins two objects of different tools; a chain is a connected set of linked objects that holds a ticket, agent, pull request or review. Every link carries a source tag of `record`, `branch` or `label` (see Links and chains).
- **Action.** A named operation on an object that runs the owning tool's own CLI after the confirmation recipe of its adapter (see Actions).
- **Block.** The tagged crontab block that a tool's own `cron install` writes. awkit recognizes blocks and never writes one itself (see Cron).
- **Check.** One result line of `doctor`.
- **Human present.** Exactly when stdin and stderr are terminals and `/dev/tty` opens for reading and writing. The dashboard additionally needs stdout to be a terminal (exit 13 otherwise). No other test is used.

**Registration.** A tool is registered when its adapter (bundled or overlay) loaded, `tools.<tool>.enabled` is not `false`, and its program resolves (see Program resolution). Each loaded adapter has one state: `registered`, `absent` (the adapter loaded and the program does not resolve), `disabled` (`enabled: false`), or `adapter_invalid` (the adapter failed to load; the tool is excluded and an overlay failure never falls back to the bundled adapter). The `roles` map is not the registry. Order everywhere (cron, doctor, `adapters list`, ties in Attention) is lexical by tool name in byte order. The rule as pseudocode:

```text
for adapter in sorted(loaded_adapters, key=tool):
    cfg = config.tools.get(tool, {})
    if cfg.enabled is False:            state = disabled
    elif resolve_program(adapter, cfg) is None:
        state = absent                  # explicit cfg.enabled == True -> doctor fail, else warn
    else:                               state = registered
failed adapters: state = adapter_invalid
```

awkit keeps no copy of any tool's data between runs. Everything on a screen is read again on the next refresh, so the dashboard can be stopped and started at any time.

## Commands

```text
awkit [dashboard] [--focus ID] [--result-file PATH]
awkit browse [--focus ID] [--result-file PATH]
awkit attention [--tool T]... [--reason R]... [--limit N]
awkit chains [--ticket KEY | --pr PR | --agent ID] [--limit N]
awkit doctor [--probe] [--tool T]...
awkit cron install [--tool T]... [--dry-run]
awkit cron uninstall [--tool T]... [--dry-run]
awkit wire TOOL [--yes] [--dry-run]
awkit unwire TOOL [--yes] [--dry-run]
awkit audit [--tool T]... [--action A]... [--pr PR] [--ticket KEY] [--label K=V]... [--by A] [--since DUR|TS] [--until TS] [--limit N] [--no-pair]
awkit validate [--config PATH]
awkit adapters list
awkit adapters show TOOL
```

`awkit` with no subcommand is `awkit dashboard`; `awkit --focus ...` and `awkit --result-file ...` without a subcommand also mean `dashboard`. `browse` is the same command under the guide's name for a TUI (a recorded deviation: the guide's `<tool> browse` is also accepted). `--version` and `--help` are accepted before a subcommand as well as after it.

A `TOOL` or `--tool` value is a tool name (grammar `^[a-z][a-z0-9-]{0,31}$`). A name that matches no loaded adapter exits 10. A tool that is `absent` or `disabled` exits 12 `tool_unavailable` for `wire`, `unwire` and `cron --tool`, and is skipped silently in runs that cover several tools. An `adapter_invalid` tool exits 20 `adapter_invalid` only when the command names it. `ID` for `--focus` is `<tool>:<object>` with a tool name and an object id as that tool prints it; the dashboard selects the first Attention item with that tool and object, else the first Chains node, else shows "not found" in the status line (the exit code does not change). `--pr` is a pull request URL or `host/<full project path>#N`. `--ticket` is `KEY` or `site:KEY`: a bare `KEY` matches every object whose ticket key part equals it, and more than one distinct `site:KEY` among the matches exits 21 with `details.candidates`; label links `ticket=KEY` with no site link to every ticket object of that key and carry the tag `label`. `--label` is `key=value` in the label grammar. `--since` is a duration or a timestamp. A value that does not match exits 2 `invalid_argument`. `--tool` repeats and ORs; different filters AND.

Durations are `^[1-9][0-9]*(ms|s|m|h|d)$` everywhere: no bare numbers and no fractions (a recorded deviation from the guide). Timestamps awkit writes are UTC `YYYY-MM-DDTHH:MM:SS.sssZ`; input accepts RFC 3339 with `Z` or an offset.

`attention` and `chains` print what the Attention and Chains tabs show (design guide §10: every TUI action is also a command). `audit` prints the Timeline. `adapters list` prints each loaded adapter with its source (`bundled` or `overlay`), tool, `min_version` and status; `adapters show` prints one adapter after loading, with the effective values (`enabled`, `bin` and the loaded adapter). `validate` loads the config, the drop-ins and every adapter and checks them against the schemas without running any tool or override; it is the one command that accepts `--config` (see Configuration).

Dashboard actions have no awkit command of their own, a recorded deviation: every action is a documented command of the owning tool, so its CLI equivalent is that command (`adapters show TOOL` prints the action argv). `d` in the dashboard is `awkit doctor`; `r` has no command.

### Global flags

`--json`, `--verbose`, `--quiet`, `--dry-run` where the command lists it, `--yes` where it lists it, and `--actor STRING` (grammar `^(human|auto):[A-Za-z0-9._@-]{1,64}$`; the default is `human:<user>` when a human is present, else `auto:unknown`, where `<user>` is `me.name` fitted to the grammar: other characters become `_` and the name is cut to 64 characters). Global flags go after the subcommand, except `--version` and `--help`. There is no `--config` except on `validate`.

## Exit codes

| Code | `error.code` values | Meaning |
|---|---|---|
| 0 | none | Success. `doctor` exits 0 when no check failed, even with warnings. `cron` and `wire` exit 0 for `unchanged`. `validate` exits 0 when everything is valid. |
| 1 | `internal` | Unexpected internal error. |
| 2 | `invalid_argument`, `missing_option`, `config_invalid` | Usage error, or an invalid or unsafe value found in the config, the environment or an adapter (`validate` always prints its result document and exits 2 when anything is invalid). |
| 10 | `not_found` | An unknown tool, object or adapter. |
| 12 | `unavailable`, `checks_failed`, `tool_unavailable`, `cron_partial` | Expected failure. `unavailable` carries a `reason`: `locked`, `crontab_failed`, `crontab_unusable` or `wire_rejected`. `checks_failed`: `doctor` found a failed check. `tool_unavailable`: a tool the command needs is absent, disabled or answered badly. `cron_partial`: a tool's own installer failed. |
| 13 | `human_required` | A human is needed: `dashboard` or an action that needs a terminal has none, or `wire` or `unwire` without `--yes` has no human present. |
| 20 | `refused` | Refused with a `reason` (see below). |
| 21 | `ambiguous` | Ambiguous selector; `details.candidates` is an array of `<tool>:<object>` or `site:KEY` strings. |

Reasons of exit 20: `config_unsafe` (a config, drop-in, adapter, state file or parent directory that is a symlink, not owned by the user, or group- or world-writable), `adapter_invalid`, `drop_in_foreign` (the drop-in exists and lacks awkit's first-line marker), `duplicate_state_hooks` (wiring both agent-spawn's and claude-session's state hooks to notifications), `stale_object` (an action's confirmation facts no longer match the object, reported by the owning tool), `unsafe_value` (a value awkit would write into a drop-in or pass to a tool's installer does not match the safe-value grammar), `xdg_mismatch` (`wire` with `XDG_CONFIG_HOME` set to a non-default value), `unsupported_platform` (on a platform other than Linux, every command except `validate` and `adapters`). Codes 22 and above are not used in 0.x. Codes 14 to 19 never occur (awkit waits on no session); a child's exit code is reported in the result and never passed through as awkit's own.

## Output by exit code and error envelope

With `--json`, exit 0 prints the result object of the command (member names are those of `schemas/cli/`). Exit 12 from `doctor` prints the same document as exit 0. Every other non-zero exit prints the envelope `{"error": {"code": "<exit-name>", "message": "...", "reason": "...", "details": {...}}}` on stdout and the message on stderr. `reason` appears only on exits 12 and 20. Strings that came from a tool are sanitized (see Output sanitizing) in every output. `dashboard` and `browse` print nothing with `--json`; their machine output is the result file.

Top-level members per command:

| Command | Members |
|---|---|
| `attention` | `items`, `stale`, `partial` |
| `chains` | `chains`, `stale`, `partial` |
| `doctor` | `ts`, `probe`, `checks`, `counts` (the same document as `doctor-last.json`) |
| `cron install`, `cron uninstall` | `dry_run`, `unchanged`, `tools` |
| `wire`, `unwire` | `tool`, `dry_run`, `outcome`, `files` |
| `audit` | `entries`, `skipped` |
| `validate` | `valid`, `checked` |
| `adapters list` | `adapters` |
| `adapters show` | `tool`, `source`, `path`, `status`, `enabled`, `bin`, `adapter` |

`attention` and `chains` exit 0 with `stale` and `partial` lists when a tool's read failed or was cut short; `chains --ticket` with no match exits 0 with an empty list. `adapters show` of a failed adapter exits 0 with `status: failed` and `adapter: null`.

## Adapters

An adapter is one YAML file `<tool>.yaml` validated by `schemas/adapter.json`. Bundled adapters live in the repo's `adapters/` directory and are read-only data. The overlay directory is `~/.config/awkit/adapters/` under the home directory of the password database (see Configuration). An overlay file with the same `tool` replaces the bundled adapter wholesale; there is no merging. A file that fails to load excludes only its tool: `doctor` reports `adapter.loaded` failed (naming the overlay path) and the other tools keep working.

### Adapter file

The required keys are `tool`, `binding` and `bin`; every other key is optional.

| Key | Meaning |
|---|---|
| `tool` | Tool name. |
| `binding` | `C` for every adapter (architecture §3.3). |
| `bin` | The program name, never a path; found through Program resolution. `tools.<tool>.bin` overrides it with an absolute path. The first element of every argv the adapter runs for the tool is this name. |
| `install` | The install command `doctor` prints for a missing tool. |
| `min_version` | The lowest tool version the adapter was written against. |
| `version` | How to read the installed version: `package: <distribution name>` (package metadata of the tool's own environment) or `argv` of a command that prints it. |
| `reads` | Named reads (see Reads). |
| `attention` | Rules that turn rows into Attention items (see Attention). |
| `links` | Label keys, branch patterns and record fields that join objects (see Links and chains). |
| `actions` | Actions (see Actions). |
| `tui` | How to open the tool's own TUI on an object (see Terminal handoff and Child result). |
| `cron` | How to run the tool's own `cron install` and `uninstall` and recognize its block (see Cron). |
| `audit` | The tool's audit file and how to pair its records (see Audit). |
| `doctor` | The tool's own `validate` argv, probe and extra checks (see Doctor). |
| `wire` | Hooks to route to notifications (see Wire). |
| `overrides` | Escape hatches (see Escape hatches). |

### Reads

A read declares `argv`, an optional `timeout` (default `dashboard.read_timeout`), `kind` (the node kind of its rows), `items` (a path selecting the row elements; filters go inside it), `fields` (a map from row field name to a path relative to one element) and an optional `truncated` (a path; see below). Reserved row fields are `id` (required), `title`, `since`, `labels`, `branch` and `state`; any other field name is free and usable in `when` and `show`. A read has no placeholders.

A read asks the tool to change nothing. Some tools run their own liveness checks on list commands and may record state changes; awkit accepts and documents that (the bundled table names agent-spawn `list` and claude-session `list`), and the bundled adapters use non-mutating forms where they exist (for example `--no-refresh`) and pass an explicit `--limit` at the tool's maximum. A read runs with the inherited environment, no standard input, in a new session, and never with a terminal.

Limits: stdout is read up to 8 MiB and 64 KiB of stderr is kept. Reaching a cap or the timeout sends SIGTERM to the read's own process group, then SIGKILL after 2 s, and reaps it. A read that exits non-zero, exceeds a limit, prints invalid JSON, or fails every element's `id` marks the tool stale for that refresh; the previous rows stay on screen with their age. Every exception from parsing (including recursion depth and huge integers), path evaluation and sanitizing is a read failure for that tool. A read whose `truncated` path yields `true` marks the tool partial (like stale, but the rows are shown). Rows whose `id` fails the `object_id` grammar are dropped and counted; the count is shown in the marker details and the tool is partial.

```text
def run_read(read) -> rows | stale:
    doc = gateway.run_json(read.argv, timeout)
    elems = path_eval(read.items, doc)                   # list; scalar -> [scalar]; null -> []
    rows, dropped = [], 0
    for e in elems:
        row = {name: path_eval_scalar(p, e) for name, p in read.fields.items()}
        if not valid_object_id(row.get("id")):  dropped += 1; continue   # grammar before sanitizing
        if row.get("since") is not None and not rfc3339(row["since"]): row["since"] = None
        if row.get("title") is not None and not isinstance(row["title"], (str, int, float)): row["title"] = None
        rows.append(sanitize_row(row))
    return rows, dropped
```

`path_eval_scalar` returns `null` when the path yields a list (it never zips elements by position). A required `id` path that fails for every element, with `elems` non-empty, marks the tool stale.

### Path language

Paths are small and total. They are evaluated by awkit itself with no external program. Errors happen only when an adapter loads (invalid path text, or more than one filter in a step); evaluation never raises.

```text
path    = first *step
first   = name / bracket
step    = "." name / bracket
name    = ALPHA_ / "_" *( ALNUM / "_" / "-" )
bracket = "[*]" / "[" 1*DIGIT "]" / "[?" name op literal "]"
op      = "=" / "!="
literal = "null" / "true" / "false" / int / string     ; int = ["-"] 1*DIGIT
string  = 1*128( any char except "]" )                  ; taken verbatim, no quoting
```

Evaluation is over a list of current values starting with `[doc]`:

- `.name` on an object yields the member or `null`; on a non-object it yields `null`.
- `[*]` on an array yields its elements (flattening one level), on anything else nothing.
- `[N]` on an array yields the element or `null` when out of range.
- `[?f op lit]` keeps array elements that are objects whose member `f` equals (or does not equal) the literal. Equality is typed: `null`, `true`, `false` and int literals compare to JSON null, booleans and integers only, and a string literal compares to JSON strings only (`[?n=1]` does not match `"1"`).
- After `[*]` or a filter, `null` results of later member steps are dropped.

There are no parent references, functions, arithmetic, concatenation or regular expressions. Whatever this language cannot express is done by an override (see Escape hatches).

### Templates and argv rules

Commands are argv lists, never shell strings, and awkit never runs a shell for an adapter command. Action argv placeholders are a closed set filled by awkit: `{object}` (the row's `id`, grammar `object_id`), `{actor}` (the actor fitted to the tool's character set; a dry run gets `auto:awkit`) and `{pass.<name>}` (a typed pass value, see Actions). A placeholder is a whole argv element: `--flag={x}` and unknown names are load errors, and a literal `{` in argv is written `{{`. There is no `params` key in 0.x. Every value is checked against a closed grammar of `schemas/defs.json` before it is substituted, each with a first character that is not `-`: `object_id` (`^[A-Za-z0-9/*][A-Za-z0-9._:@/#=+~*-]{0,255}$` with no `..` path segment), `hash` (`^[0-9a-f]{12,128}$`), `int` (`^(0|[1-9][0-9]{0,17})$`) and `enum` (listed values). A value that does not match refuses the call. Only grammar-checked identifiers taken from the selected row or the dry run (`{object}`, `{pass.*}`) ever enter an argv; free text never does and no link-derived value ever does. Argv items after the first may be empty strings. All patterns are anchored with `(?![\s\S])` in the schemas, so a trailing line feed never matches.

### Escape hatches

Any single operation, or a whole adapter, can be replaced. Both override kinds speak the same protocol in a child process: `exec: <absolute path>` runs that file, and `python: <spec>:<function>` runs `[sys.executable, "-I", "-m", "awkit.override_host", <spec>, <function>]`, where `<spec>` is either `awkit.<module>` (bundled, inside awkit's own package) or a file name `<name>.py` relative to the overlay directory (loaded by `importlib.util.spec_from_file_location`, never by module search). The file, an `exec` target and every parent directory up to the home (or `/` for paths outside it) must pass the ownership rule (owned by the user or root, not group- or world-writable, the file itself not a symlink). The request goes on stdin (a pipe; nothing else is on stdin) and the reply on stdout; the read rules apply otherwise (timeout, new session, 8 MiB cap, no terminal). `validate` only checks names and file ownership; it never imports or runs an override. The protocol belongs to awkit; tools never see it.

Protocol `awkit-adapter/1`. The request is `{protocol, operation, adapter, params}`; the reply is `{"ok": true, "result": ...}` or `{"ok": false, "error": {"code": "...", "message": "..."}}`. A failed or invalid reply marks the operation stale (a read) or failed (anything else).

| Operation | `params` | `result` |
|---|---|---|
| `read` | `{read: <name>}` | `{rows: [<row>...], truncated: bool}` (rows as in Reads, before sanitizing) |
| `attention` | `{rows_by_read: {...}}` | `{items: [{reason, severity, object, title?, since?}]}` |
| `links` | `{rows_by_read: {...}}` | `{links: [{from: {tool, object}, to: {tool, object}, tag}]}` with `tag` one of `record`, `branch`, `label` |
| `action_plan` | `{action: <id>, object}` | `{plan_lines: [str], pass: {<name>: <value>}, refused: null or {code, reason}}` (replaces the derived dry run for that action) |
| `doctor` | `{}` | `{checks: [{id, status, reason, details}]}` (ids must start with `tool.<tool>.`) |

The `overrides` key is `{adapter?, read{<name>}, attention, links, action_plan{<action id>}, doctor}`; `adapter` replaces every operation not overridden individually.

### Worked example

An adapter with one read, one attention rule, one label link and one recipe action (the tool's flags here are an illustration, not a statement about the real tool):

```yaml
tool: agent-spawn
binding: C
bin: agent-spawn
install: uv tool install agent-spawn
min_version: 0.3.0
version:
  package: agent-spawn
reads:
  needs_attention:
    argv: [agent-spawn, list, --needs-attention, --json, --limit, "500"]
    timeout: 10s
    kind: agent
    items: agents[*]
    fields:
      id: id
      title: title
      since: since
      state: state
      labels: labels
attention:
  - read: needs_attention
    reason: escalated
    severity: action
    when: {state: escalated}
links:
  labels:
    - {read: needs_attention, key: ticket, to_kind: ticket}
actions:
  - id: teardown
    label: Tear down
    applies_to: [escalated]
    argv: [agent-spawn, teardown, "{object}"]
    destructive: true
    recipe:
      dry_run: true
      show: [plan.summary]
      pass:
        - {name: plan_hash, flag: --plan-hash, from: dry_run.plan.hash, type: hash}
      "yes": true
```

## Attention and chains

### Attention

An attention rule is `{read, reason, severity, when?}`. It takes the rows of its read; `when` is one equality on a row field (`{field: value}`) and skips the rows that do not match. Reasons are adapter-defined (grammar `^[a-z][a-z0-9_]{0,63}$`) and the severity (`info`, `action` or `error`) is declared per rule. Each row yields one item:

```text
def attention(rule, rows):
    for row in rows:
        if rule.when and not equal(row.get(field), value): continue
        yield Item(id=f"{tool}:{rule.reason}:{row.id}", tool, reason=rule.reason,
                   severity=rule.severity, title=row.title or row.id, object=row.id,
                   since=row.since, links=links_of(row), actions=actions_for(row, rule.reason))
order: severity (error, action, info), since ascending with null last, then id (byte order)
```

An Attention item has the members `id`, `tool`, `reason`, `severity`, `title` (sanitized), `object`, `since`, `links` and `actions`. Items exist while the tool lists them: awkit keeps no dismissal state. Idle sessions are never items.

The bundled adapters derive items from these sources (the first release builds them from each tool's interface at the time; `design.md` lists the verification issue):

| Tool | Source | Reasons |
|---|---|---|
| agent-spawn | `list --needs-attention` | `unreported`, `escalated`, `blocked`, `failed`, `timeout`, `lost`, `launch_failed`, `session_missing` |
| claude-session | sessions in `needs-input` | `needs_input` |
| jobsctl | held and failed jobs (jobsctl's own default window: terminal jobs older than 24 h are omitted) | `held`, `job_failed` |
| review-watch | drafts awaiting accept, escalated and stale items | `draft_awaiting_accept`, `escalated`, `stale`, `failed` |
| ticket-work, review-respond | `pending`, attention list | `pending_confirmation`, `attention` |
| ticket-queue | `boards`, `claims`, `list --skipped --query "failures > 0"` | `board_status`, `claim_state`, `skipped_failures` |
| ticket-create | drafts in `ready`, orphaned `drafting` rows | `ready_to_create`, `orphan` |
| gatectl | policies that dropped to shadow (to be confirmed by the verification issue) | `policy_shadowed` |
| notice-route | `validate` warnings (`flush_stale`) | `flush_stale` |

Only reasons that a read can produce are listed. The hook-only reasons of review-watch (`poll_failed`, `submit_failed`, `post_failed`, `daily_limit`, `round_limit`, unless a stored state shows them) and the comparable review-respond and ticket-work ones are hook only; they arrive with `notify-tick` in 1.x.

### Links and chains

Nodes carry an open node kind (grammar `^[a-z][a-z0-9_.-]{0,31}$`). The bundled vocabulary is `ticket`, `worktree`, `agent`, `session`, `tmux_window`, `job`, `pull_request`, `review_item`, `review_draft`, `pending`, `gate_decision`, `notification`. Label keys are an open grammar of the same shape; the bundled vocabulary is `ticket`, `pr`, `repo`, `kind`, `owner`, `job`, `rw-item`, `draft`, `consumer`, `agent`, `decision`, `run`, `round`. A row's `labels` field may be a list of `"k=v"` strings or an object of string or string-list values; awkit normalizes both to a multiset of `(key, value)`. An adapter's `links` declares three forms, each bound to a read:

```text
labels:   [{read, key, to_kind, to_tool?}]           # row.labels[key] values -> node (to_tool, value), tag label
branches: [{read, pattern, to_kind, to_tool?}]       # re.fullmatch(pattern, row.branch); group "ref" -> node, tag branch
records:  [{read, field, to_kind, to_tool?}]         # row[field] -> node, tag record
```

For each declared form, each row of `read` and each extracted value that passes `object_id`, awkit adds the edge `(tool, row.id, kind) -> (to_tool or the owner of to_kind, value, to_kind)` with the tag, one edge per pair keeping the strongest tag (`record`, then `branch`, then `label`). Attributes such as `repo`, `kind`, `owner` and `consumer` are not edges unless an adapter declares them in `labels`. Each link has a source tag:

| Tag | Meaning |
|---|---|
| `record` | A tool's own stored id for the other object (for example a pull request id a workflow stored). |
| `branch` | Derived from a branch name that matches an adapter pattern. |
| `label` | Derived from a label only. |

Chains are the connected components that contain a `ticket`, `agent`, `pull_request` or `review_item` node, each printed as nodes sorted by kind order then id, plus its edges (`{nodes[{tool, object, kind, title?}], links[{from, to, source}]}`).

Labels are not authenticated against processes of the same user. The views show `branch` and `label` links dimmed, and `chains --json` prints the tag of every link. In 0.x no link-derived value ever enters an action's argv: every action acts on the selected row's own object, confirmed by the owning tool's own dry run and refusals, and the dialog shows the object the tool itself confirmed. Re-verification of links against an authoritative source, and a `forge` tag, return in 1.x with the rules engine.

## Dashboard

`awkit dashboard` needs a terminal on stdin, stdout and stderr (a human present plus stdout) and the optional `tui` extra (Textual `>=8.2,<9`); without a terminal it exits 13, without the extra it exits 12 `tool_unavailable` with the install command. The core never imports Textual.

### Views and keys

Three tabs: Attention (the default), Chains and Timeline (the newest 500 records of the merged audit). The header shows the tool name, the badge (the result of the last `doctor` from its cache file, with its age) and one marker per tool whose last read failed (stale, with the age of its data) or was cut short (partial). The footer shows key hints and the status line shows the last action's result. A detail pane shows the selected row's fields only. A selection stays on the same item across refreshes. Every view respects the terminal's colors and never hard-codes backgrounds.

| Key | Action |
|---|---|
| `1`, `2`, `3` | Switch tab. |
| `enter` | Open the selected object in its owning tool's own TUI as a child (see Terminal handoff), when the adapter has a `tui` key; otherwise the status line says it is not available. On Timeline it does nothing. |
| `a` | Actions menu for the selected item (see Actions). |
| `W` | Run the same child in a new tmux window when `$TMUX` is set (see Child result). |
| `d` | Run `doctor` and update the badge. |
| `r` | Refresh now. |
| `/` | Filter the current tab by text; it matches title, object and tool. |
| `?` | Help. |
| `q` | Quit. |

States:

| State | Shown |
|---|---|
| Before the first refresh | "Loading". |
| No registered tool | "No tools registered; run `awkit doctor`". |
| Empty Attention | "Nothing needs you". |
| `doctor-last.json` missing, invalid or over 1 MiB | The badge reads "no doctor result". |
| A tool's last read failed | A stale marker with the age. |
| A tool's rows were cut short or dropped | A partial marker with the details. |
| `W` with no tmux | A status line message that it is disabled. |
| Chains | A selection is a node; actions and `enter` act on the node's row. |

### Refresh

One worker refreshes all tools: reads run concurrently under a semaphore of `dashboard.concurrency` (default 8). A cycle ends when every read has ended; the next cycle starts `dashboard.refresh` (default 15 s, at least 5 s) after the previous start, or at once when the previous cycle ran longer. A manual refresh joins the running cycle. A slow tool therefore delays the cycle by at most its timeout plus 2 s. The Timeline reads audit files by byte offset (see Audit).

### Terminal handoff

A child that needs the terminal (a tool's TUI, `ticket-create create`, an interactive agent session) runs with the dashboard suspended in the same terminal. The dashboard ignores SIGINT for the child's lifetime, discards pending typeahead on the terminal before the child starts and again after it exits, restores the terminal state it saved, and then redraws. The child starts in its own process group (`setpgid`) and is made the foreground group with `tcsetpgrp` while SIGTTOU is ignored; SIGTERM and SIGHUP are forwarded with `killpg` of that recorded group only, and the dashboard takes the foreground back after the child exits. A child whose output awkit captures runs in a new session with standard input from `/dev/null`, so it can never read the dashboard's terminal. The dashboard installs a handler for SIGTERM and SIGHUP that restores the terminal before exiting.

### Child result

An adapter's `tui: {argv, result_file, intents}` has an argv such as `[tool, tui, --focus, "{object}"]` (whole-element `{object}` only), a `result_file` boolean and `intents`, a map from the child's intent to an action id. `enter` runs `tui.argv` for the selected row's tool under Terminal handoff. With `result_file: true` awkit creates a 0700 directory with `mkdtemp` in its state directory, passes `--result-file <dir>/result.json`, and after the child exits reads the file (a regular file owned by the user, at most 64 KiB, a strict JSON object, strings sanitized). An `intent` listed in `intents` opens that action's dialog for `selected[0].object` (it never runs the action directly); any other intent or a missing file returns to the dashboard; the directory is removed.

`W` runs `tmux new-window -d` followed by the argv as separate arguments, with no `-c`, `-n` or `-t` and no tool string; `tmux` is resolved by Program resolution. `W` is disabled when `$TMUX` is unset or names a socket not owned by the user; the child gets the tmux server's environment (documented), never touches the dashboard's terminal, and awkit does not wait.

### Result file

With `--result-file PATH`, `awkit dashboard` and `awkit browse` write on exit 0, under `enter`, `{"intent": "open", "selected": [{"tool": "...", "object": "..."}]}` and, under `q`, `{"intent": "back", "selected": []}`; `selected` has at most one item. The temporary file is created in the target directory with `O_CREAT|O_EXCL|O_NOFOLLOW`, an unpredictable name and mode 0600, synced, renamed, and unlinked on failure. Nothing is written otherwise, and a pre-existing file is never read. The caller removes a stale file before launching.

## Actions

An action is an entry of an adapter's `actions` with `id`, `label`, `applies_to` (a list of reasons of the same adapter), an optional `when` (one equality on a row field; the action is hidden when false), `argv` (a template), `destructive` (true when it ends work or leaves the machine) and exactly one form:

- **`recipe`**: `{dry_run: bool, show: [path...], pass: [{name, flag, from, type}], yes: bool, actor_charset?}`. With `dry_run: true` awkit runs the action's own argv plus `--dry-run --json`, never with `--yes` or a human actor (the loader refuses a separate dry-run argv). `from` is `dry_run.<path>` or `row.<field>`, and `type` is `hash`, `object_id`, `int` or `enum`; each passed value is checked against its grammar. The `yes` key is written quoted (`"yes": true`) because YAML 1.1 loaders read a bare `yes` as a boolean. `dry_run: false` is allowed only when `destructive` is false. An `action_plan` override replaces the derived dry run and applies only to actions with `dry_run: true`. `show` paths are read from the dry-run result (from the row when `dry_run` is false).
- **`terminal: true`**: handed the terminal (see Terminal handoff); the tool asks the human itself. This is the only form for a command without `--yes`, including `ticket-create create`.

A destructive action must be a recipe with `dry_run: true` or a terminal action. The dry-run exit rule: exit 0 with a JSON object is the plan; any other exit is a refusal shown as `refused: <code> <reason>` (sanitized) with no `y`.

These action kinds are not in 0.x (a recorded deviation): actions that need human-written text (`--prompt-file`, `--reason-file`, `--note-file`), a second chosen object (move before X, pin with expiry), multi-select, continuation of a refused call (escalation scope), and every reserved human flag except one. The reserved flags (`--force`, `--override-escalation`, an enforced-state change, `wtctl baseline accept`) are never passed. The single exception is claude-session's resume with `--allow-tainted`, a human-only override that the bundled adapter declares as its own action with `human_flag: --allow-tainted`; the flag appears in the dialog chrome. Reorder in 0.x is done in the owning tool's TUI. The user reaches the rest through the tool's own TUI (`enter`) or CLI. `--yes` never overrides a refusal (exit 20). An action never runs from a read, and nothing is run by a rule in 0.x.

For a recipe, awkit runs the dry run, shows the dialog (below) and, after an explicit `y`, runs the real command with `--yes` (when `yes`), `--actor human:<user>` (the user fitted to the tool's own character set where the adapter says so) and the passed flags. If the real command refuses because the facts moved (a tool's own exit 20), awkit shows its `reason` and does nothing else.

The status line shows `done` for exit 0. For any other exit it shows the exit code, the envelope's `code` and `reason` (sanitized) and, for exit 12, "the outcome may be partial; check <tool>". The dialog never reopens by itself; the next refresh shows the new state. A child's exit code is never awkit's own.

### Confirmation dialog

```text
on key "a" with row R (snapshot by value):
    action = choose from actions_for(R)
    if action.dry_run: plan = run(fill(action.argv, object=R.id, actor="auto:awkit") + ["--dry-run", "--json"])   # read rules, no terminal
        if plan.exit != 0 or not object: show refusal; return
        pass = {p.name: grammar_check(p.type, path(plan or R, p.from)) for p in action.pass}
        if any check fails: show "refused: invalid <name>"; return
    real = fill(action.argv, object=R.id, actor=fit(human:<user>), pass) + (["--yes"] if yes) + ["--actor", actor] + flags(pass)
    show dialog:
        chrome (awkit text, own widget, never scrolls): tool, action label, object R.id, actor,
              the full real argv (one element per line), "destructive" marker, question "Run? [y/N]"
        body (scroll area): each show field in full, each line prefixed "| ", plain text
        if total body > 64 KiB: show "too large to confirm here; use <tool> directly" and no y
    flush typeahead (tcflush TCIFLUSH) when the dialog is shown; ignore keys for 0.5 s
    y accepted only after the body has been scrolled to its end once; Enter, paste, any other key = no
    refresh while open never changes R, plan, pass or real
    on y: run real
```

An argv that contains `{actor}` gets the actor there and no appended `--actor`. The sanitizer's per-field cut does not apply to dialog body fields; the other sanitizer rules do.

## Cron

`awkit cron install` takes awkit's own lock and runs each registered tool's own `cron install` in lexical order (all registered tools with a `cron` key unless `--tool` narrows it); `uninstall` runs each tool's own `cron uninstall`. awkit never writes the crontab itself. The adapter's `cron` key is `{install: argv, uninstall: argv, dry_run: bool, start, end, interval_flag?, interval_pattern?, env_file_flag?, options?: {<name>: [flags]}}`: it maps awkit's config to the tool's flags. `config cron.intervals.<tool>` is the tool's own interval value, passed with `interval_flag` after it matches `interval_pattern` (a value for a tool with no `interval_flag` is a `config_invalid` error). `cron.options.<tool>` lists opt-in names (for example `--with-start` of ticket-work) whose flags the adapter maps in `options`. `cron.env_file` is passed with `env_file_flag` only where the tool has that flag (agent-spawn, claude-session, wtctl) and is otherwise the tool's own config. Every tool's own refusals and its own `PATH`, env file and XDG handling apply. A registered tool without a `cron` key is skipped with outcome `skipped`.

### Recognizers

Each adapter has one recognizer per tool: `start` (`{exact: text}`, `{prefix: text}` or `{regex: pattern}`, a full match on a line) and `end` (an exact line, or `null` for a tool whose block has no end line). The end line is tested before the start line, because a loose start rule can also match an end line. A line that merely contains a tag in a comment is not a block. A block is present (a start line found), absent, or malformed (an end line without a start, a start without an end where `end` is not null, a duplicate, or interleaved blocks). `doctor cron.block` and the `cron` report use it. Where `dry_run` is true, the tool's `cron install --dry-run --json` (a read-only call, and its `changed` member) tells whether the block is current.

### Install order

```text
lock cron.lock (exit 12 unavailable, reason locked, if held)
before = read_crontab()
audit attempted (inputs.before_sha256)
for tool in registered tools with adapter.cron, lexical:
    if --dry-run: run install argv + ["--dry-run", "--json"] where dry_run, else print the argv; continue
    r = run(install argv + mapped flags, read rules, timeout 60s)
    outcome[tool] = "done" if r.exit == 0 else "failed" (exit code kept)     # tool message sanitized
after = read_crontab(); audit outcome (after_sha256, per-tool outcomes, unchanged when after == before)
exit 12 cron_partial when any tool failed, else 0

def read_crontab():
    r = gateway.run([crontab, "-l"], env={LC_ALL: C, PATH: SYSTEM_PATH}, stdin=DEVNULL, timeout=30s)
    if r.exit == 0:
        if b"\0" in r.stdout or len(r.stdout) > 1 MiB: fail(12, unavailable, crontab_unusable)
        return r.stdout
    if r.exit == 1 and r.stderr.startswith(b"no crontab for"): return b""
    fail(12, unavailable, crontab_failed)
```

With `--dry-run` awkit prints per-tool outcomes (`planned`, with the tool's `changed` where it reports one) and writes no audit record and reads no crontab. The crontab is read for the audit hashes and by `doctor`; the lock serializes awkit runs only, and each tool's own installer keeps its own small write window against a hand edit (see Residual risks). Every non-dry-run `cron` command writes one pair of audit records (see Audit); its outcome carries `unchanged` when the crontab did not change. `uninstall` runs the same steps with each tool's `uninstall` argv. A lock held after retries exits 12 `unavailable` with `reason: locked`.

## Wire

`awkit wire TOOL` writes the notification wiring for one tool: the drop-in `~/.config/<TOOL>/config.d/awkit.yaml` under the home directory of the password database, and nothing else. Its first line is `# awkit managed`, and it holds only `hooks:` entries (design guide §5, §8) for the hooks the adapter's `wire` lists, each `{name, timeout?, state?}` with `name` matching `^(?:post|on)-[a-z][a-z0-9_-]{0,63}$` (never `pre-`: a failing notice hook must not veto a step). awkit writes `cmd: ["<absolute notice-route>", "send", "--source", "<TOOL>", "--stdin-json"]`, `async: true`, and `timeout` when given. Hook selectors (`states`, `kinds`, `labels`) are out of 0.x. A tool whose adapter lists no hooks, and `wire notice-route`, exit 0 with `nothing_to_wire`. The bundled hook lists come from the verification issue. awkit never edits a `config.yaml`, any other file of a tool, or notice-route's rules: routing `source: <TOOL>` is the user's notice-route config (the README shows the rule), `wire` prints one line saying notice-route needs a rule for that source, and `doctor` warns when a wired tool has none (`wire.rule`).

`wire` shows the exact drop-in text and applies it after confirmation: a human present answers `y` on `/dev/tty` (prompts and reads go there), or `--yes` skips the question (exit 13 when neither a human is present nor `--yes` is given; `unwire` follows the same rule). Outcomes are `wired`, `replaced`, `unchanged`, `removed` (for `unwire`) and `nothing_to_wire`. A drop-in that exists without the first-line marker is `drop_in_foreign` (exit 20): awkit never overwrites a file it did not write. `wire` with `XDG_CONFIG_HOME` set to a non-default value refuses with exit 20 `xdg_mismatch`, because the tool would not read the drop-in. Values written into `cmd` must match the safe-value grammar (see Configuration; else exit 20 `unsafe_value`).

```text
wire TOOL:
    target_dir = <home>/.config/<TOOL>/config.d
    if not exists <home>/.config/<TOOL>: exit 12 tool_unavailable ("tool has no config directory")
    open <home>/.config/<TOOL> by fd (O_DIRECTORY|O_NOFOLLOW), check ownership; create config.d 0700 if missing
    existing = openat(dirfd, "awkit.yaml", O_NOFOLLOW); if exists and first line != "# awkit managed": exit 20 drop_in_foreign
    plan text; if equal: outcome unchanged
    show text, confirm (human on /dev/tty or --yes), audit attempted
    write temp (O_CREAT|O_EXCL|O_NOFOLLOW, 0600) in dirfd, fsync, re-check marker of existing via dirfd, renameat
    if adapter.doctor.validate: run it; exit 2 from it -> restore previous bytes (or unlink) and exit 12 wire_rejected
    audit outcome
unwire TOOL: absent file -> unchanged; foreign file -> exit 20 drop_in_foreign; else same steps with removal
duplicate_state_hooks: refused when the other tool's awkit drop-in exists with the marker and lists a hook marked state: true;
                       hooks the user wrote by hand are not seen (documented)
```

Wiring both agent-spawn's and claude-session's state hooks to notifications is `duplicate_state_hooks` (exit 20). The early-tick hooks (`awkit notify-tick`) arrive with the loop (see Roadmap).

## Doctor

`awkit doctor` runs the checks below and prints each as `ok`, `warn` or `fail` with an id, a `reason` and `details`. It is offline and read-only: it runs only each tool's offline `validate --json` and the local checks, never a probe, and it is safe to run from cron or from the dashboard. A tool that is not registered gets only `tool.installed` and `adapter.loaded`; every other per-tool check is skipped for it. `--probe` also runs each tool's `validate --probe` (named by the adapter), one tool at a time, each with `doctor.probe_timeout`, after printing what it will call; it never sends a test message. The result is written to `doctor-last.json` in the state directory (temporary file, `fsync`, rename) for the dashboard badge; on read it is capped at 1 MiB, validated and sanitized, and any defect means no badge. Check ids are open with grammar `^[a-z][a-z0-9_.-]{0,63}$`.

| Id | Fails when | Warns when | Mechanism |
|---|---|---|---|
| `config.safe` | A config file, drop-in, overlay file or parent fails the ownership rule. | None. | `lstat` walk |
| `adapter.loaded` | An adapter fails to load (the reason names the overlay path). | None. | Loader |
| `tool.installed` | `tools.<tool>.enabled: true` is set explicitly and the program does not resolve. | The program does not resolve (the adapter's `install` command is printed). | Program resolution |
| `tool.version` | Never. | The version is below `min_version` or cannot be read (`version_unreadable`). | Version reading (below) |
| `tool.validate` | Per the mapping below. | Per the mapping below. | Adapter `doctor.validate` |
| `cron.daemon` | No `cron` or `crond` process runs. | On WSL, pid 1 is not systemd. | `ps -eo comm`, `/proc/1/comm` |
| `cron.block` | The block is malformed (see Recognizers). | The block is absent for a registered tool that has a `cron` key, or not current where the tool's dry run says so. | Recognizer |
| `cron.env_file` | `cron.env_file` exists but is not a regular user-owned file, is group or world accessible, a parent fails the ownership rule, or `sh -n` fails. | A variable an adapter lists is not assigned with `export` or under `set -a`. | `lstat` walk, `/bin/sh -n`, name scan (values never read into output) |
| `env.xdg` | None. | `XDG_CONFIG_HOME`, `XDG_STATE_HOME` or `XDG_DATA_HOME` is set to anything other than `<home>/.config`, `<home>/.local/state`, `<home>/.local/share`, because tools then use other directories than awkit reads (audit paths) and writes (drop-ins). | Environment |
| `env.variables` | None. | A name an adapter lists is set neither in awkit's environment nor in the env file. | Name scan |
| `sandbox.tools` | None. | `bwrap` or `socat` needed by a registered tool does not resolve. | Program resolution; `claude-session kinds --json` is shown in `details` without a judgment |
| `pair.<id>` | None. | A sibling is below the declared minimum. | `{id, tool, min_version}` only |
| `wire.rule` | None. | A wired tool (its drop-in exists with the marker) has no matching notice-route rule. | The `wire.rules_read` read of the notice-route adapter |
| `audit.coverage` | None. | A registered tool declares no audit file. | Adapter |
| `probe.<tool>` | The probe failed. | None. | `--probe` only |
| `tool.<tool>.*` | Per override. | Per override. | `doctor` override |

The `tool.validate` mapping: `doctor.validate` is `{argv, ok_exits: [0], info_exits: [], warnings: <path>?}`. An exit in `ok_exits` is `ok`, or `warn` when the `warnings` path yields a non-empty list; an exit in `info_exits` is `ok` with `reason: info`; any other exit is `fail` with the envelope's `code` (sanitized). A tool with no `validate` has no such check. Normalization beyond this is the `doctor` override operation.

Version reading: with `version.package`, awkit reads the first line of the program (at most 512 bytes); when it starts with `#!` and names an absolute interpreter that passes the ownership rule, it runs `[interp, "-E", "-P", "-c", "import sys,importlib.metadata as m;print(m.version(sys.argv[1]))", package]` (5 s, read rules). Otherwise, or when that fails, it runs `version.argv` (5 s) and takes the first version-shaped token of stdout, unless it is `0.0.0`. Nothing readable is a `version_unreadable` warning. Versions compare as leading `N.N.N` (missing parts are 0; pre-release and local suffixes are ignored; unparsable is a warning); an installed version below `min_version` is a warning and the tool stays usable. Tags are never read.

Exit 12 `checks_failed` when any check is `fail`.

## Audit

### Reading

`awkit audit` reads each registered tool's public `audit.jsonl` directly (design guide §2, §6). The path comes from the adapter's `audit.path` (default `<home>/.local/state/<tool>/audit.jsonl` under the home directory of the password database; `XDG_STATE_HOME` is ignored, and `doctor` warns when it differs). A line is accepted when it parses as a JSON object with a string `ts` that is RFC 3339; every other member is kept as read (sanitized), so tool upgrades never hide records. A file is opened with `O_RDONLY|O_NOFOLLOW|O_NONBLOCK` and checked with `fstat`: a regular file owned by the user, else the tool contributes nothing and is counted in `skipped.files`. A missing file contributes nothing. Lines longer than 1 MiB are skipped and counted in `skipped.lines`, a malformed line is skipped and counted without echoing it, and only LF-terminated lines are consumed (a partial tail stays for the next pass). `awkit audit` streams whole files. The dashboard records `(st_dev, st_ino, offset)` per file and restarts from the start when the inode changes or the size falls below the offset; its first read starts at `max(0, size - 8 MiB)` and skips to the first LF.

Pairing is declared per adapter: `audit: {path, pair?: {key: [path...], attempted: {path, value}}}`. Without `pair` every record stands alone. Foreign `attempt_id` values are not grammar-checked beyond being strings of at most 128 characters; awkit's own records keep `^[A-Za-z0-9_-]{22}$`. Cross-tool correlation is out of 0.x.

```text
groups = {}
for rec in records_of(tool):                      # in file order
    k = tuple(path_eval_scalar(p, rec) for p in pair.key)
    if any(v is None for v in k): emit single(rec); continue
    groups.setdefault((tool,) + k, []).append(rec)
for key, recs in groups:
    att = [r for r in recs if path_eval_scalar(pair.attempted.path, r) == pair.attempted.value]
    if att and len(recs) > len(att): status = paired
    elif att: status = "in_flight" if now - ts(att[0]) < 60s else "unknown"
    else: status = unpaired
    emit entry(tool, key, status, ts=min ts of recs, records=recs)   # any number of records
merge all entries and singles by (ts as UTC instant, tool, file offset of first record)
```

The bundled descriptors, to be confirmed by the verification issue: `phase=attempted` with key `[attempt_id]` (review-watch, review-respond, ticket-create); `result=attempted` with `[attempt_id]` (forgectl, pr-comment, ticket-work) and with `[attempt_id, step]` (ticketctl); `result.status=attempted` (review-run); none for the rest. `--no-pair` prints every record as `single`. Entries have `tool`, `key`, `pairing` (`paired`, `in_flight`, `unknown`, `unpaired` or `single`), `ts` and `records` (one or more).

Filters: `--by A` filters by actor and `--action A` (repeatable) by action. `--pr` and `--ticket` match after normalizing both sides (a PR URL to `host/path#N`; `site:KEY` or `KEY` as in Commands) against the record's `target` string or its `target` object members and the `inputs` string values. `--label` matches records whose target equals the `id` of a row carrying that label in this run's reads (records carry no labels). `--limit` defaults to 200: the newest N entries are printed oldest first. Tools that declare no audit file contribute nothing.

### Own records

awkit appends to `~/.local/state/awkit/audit.jsonl` (schema `schemas/audit.json`) for the actions only it performs: `cron.install`, `cron.uninstall`, `wire` and `unwire`. Fields are `ts`, `phase` (`attempted` or `outcome`), `attempt_id`, `actor`, `actor_source` (`flag`, `tty` or `default`), `stdin_tty`, `action`, `target` (`crontab` or the absolute drop-in path), `inputs` (`tools`, and `before_sha256` and `after_sha256` of the text, never the text) and `result` (`outcome` of `done`, `failed` or `unknown`; `code`; `unchanged`; per-tool outcomes). There is no `decision_id`. There is one pair per changed file. No record is written for `--dry-run` or for a command whose plan changes nothing (`unchanged`, `nothing_to_wire`); a `cron` command cannot know beforehand, so every non-dry-run cron command writes a pair and the outcome carries `unchanged`. The attempted record is appended (with `fsync`) after planning and before the first change; a failed append stops the command. Readers show an attempted record without an outcome as `unknown`. awkit records no dashboard action: the owning tool's audit, where it has one, is the record (`audit.coverage` lists tools without one).

## Output sanitizing

Every string and every object key that comes from outside awkit (any tool's output, any audit file, cache file, config or adapter string, any tool's version or error text) is sanitized once, where it enters the model and before anything is displayed or printed. The sanitizer allows by Unicode general category; everything else is replaced by a visible marker `<U+XXXX>`:

```text
def sanitize(s, limit):                 # s already decoded; invalid UTF-8 bytes decoded with errors="replace"
    out = []
    marks = 0
    for ch in s:
        cat = unicodedata.category(ch)
        if ch == "<" and next three chars are "U+" : out.append("<U+003C>"); continue   # marker cannot be forged
        if cat[0] in "LNPS" and ch not in FILLERS:      marks = 0; out.append(ch)
        elif cat[0] == "M" and marks < 3 and out:       marks += 1; out.append(ch)
        elif cat == "Zs":                               marks = 0; out.append(" ")
        else:                                            marks = 0; out.append(f"<U+{ord(ch):04X}>")
    text = "".join(out)
    return text if len(text) <= limit else text[:limit-1] + "…"      # limit counts the ellipsis
FILLERS = {U+115F, U+1160, U+3164, U+FFA0, U+2800, U+17B4, U+17B5, U+034F}
limits: title 200, other strings 1000; dialog body fields: no cut
```

Cc, Cf, Cs (lone surrogates), Co, Cn, Zl, Zp and everything not listed are replaced; LF and TAB are replaced like other controls, because there is no multi-line field in 0.x outputs (the wire `text` is awkit's own generated text, not tool text). The output encoding never raises, because no surrogate survives. Ids are grammar-checked before sanitizing and pass unchanged; strings from `doctor-last.json` are sanitized again on read. This applies to every string, not only the fields a schema marks `x-untrusted`.

The dashboard never interprets markup in displayed text. No string from a tool, adapter, config, cache file or audit file is parsed as markup: widgets receive plain `Content` or `Text` objects built from plain strings (or `markup=False`), covering table cells, list items, the detail pane, the dialog, notifications and the status line. Each row render is wrapped so an exception renders a marker row (`<render error>`) instead of ending the app. A test runs a corpus of hostile strings (including markup, every control character and every code point) through every view and every `--json` output.

## Configuration

`~/.config/awkit/config.yaml`, `~/.config/awkit/config.d/*.yaml` (lexical order, maps merged, lists replaced; at most 64 drop-ins) and the overlay `~/.config/awkit/adapters/` (at most 128 adapters) are read only under the home directory of the password database. `XDG_CONFIG_HOME` and every environment variable that would name a path or a command are ignored. A config file, drop-in, adapter file or any of their parent directories that is a symlink, is not owned by the user, or is group- or world-writable is refused (`config_unsafe`, exit 20, naming the path). One strict loader reads config, drop-ins and adapters: a PyYAML `SafeLoader` subclass that refuses anchors, aliases, tags other than the core schema, duplicate keys, NUL and lone surrogates; at most 1 MiB per file; files are opened with `O_NOFOLLOW` and checked with `fstat` on the descriptor, and parents are walked by descriptor. `--config PATH` exists only on `validate`, which runs nothing: it loads that file plus its sibling `config.d/` and the default overlay, applies the same ownership checks and reports (does not exempt) a failure. Unknown keys and invalid values fail fast naming the key. Every key whose default is "none" accepts `null`. A `tools.<tool>` entry for a tool with no adapter is a `validate` warning and ignored at runtime. Schema: `schemas/config.json`; every key is documented in `config.example.yaml`.

| Key | Default | Meaning |
|---|---|---|
| `me.name` | OS user | The `<user>` of `human:<user>`. |
| `me.github`, `me.gitlab`, `me.jira` | none | Account names (grammar `^[A-Za-z0-9_.][A-Za-z0-9_.@:-]{0,254}$`). 0.x: validated only; reserved for 1.x rules and passed nowhere. |
| `roles.<role>` | none | Role (grammar `^[a-z][a-z0-9_-]{0,31}$`) to tool, for example `githost: forgectl`, `tickets: ticketctl`, `notify: notice-route`. 0.x: validated only; a value must name a loaded adapter (`validate` warns otherwise). |
| `tools.<tool>.enabled` | true | A disabled tool is skipped everywhere. An explicit `true` turns "not installed" into a doctor failure. |
| `tools.<tool>.bin` | none | An absolute path (safe-value grammar) that overrides the adapter's program name. |
| `dashboard.refresh` | `15s` | The refresh interval (at least `5s`). |
| `dashboard.concurrency` | `8` | The most concurrent reads (1 to 16). |
| `dashboard.read_timeout` | `10s` | The default read timeout. |
| `cron.env_file` | none | A user-owned file (safe-value grammar) passed to the tools whose installer takes an env file. |
| `cron.path_extra` | `[]` | Absolute directories (safe-value grammar) searched for tool programs after `~/.local/bin`. |
| `cron.intervals.<tool>` | the tool's own | The tool's own interval value (pattern `^[1-9][0-9]{0,3}[mh]$` or a five-field expression, and the adapter's `interval_pattern`). |
| `cron.options.<tool>` | `[]` | Opt-in names the adapter's `cron.options` maps to flags. |
| `doctor.probe_timeout` | `60s` | The timeout of one probe. |

There are no `repos:` and no `hooks:` keys in 0.x.

**Safe values.** Every path awkit writes into a drop-in `cmd` or passes to a tool's installer must match `^/[A-Za-z0-9._+@/-]{0,4095}$`, with no `//` and no `..` segment (schema def `safe_path`). Values failing it are refused at load (`validate` and every command; exit 2 `config_invalid` naming the key) for `tools.<tool>.bin`, `cron.env_file` and `cron.path_extra`, and at write time (exit 20 `unsafe_value`) for resolved programs and the home directory.

### Program resolution

awkit never searches the process `PATH`. A tool program is `tools.<tool>.bin` (absolute) or the first match of the adapter's `bin` in `<home>/.local/bin`, each `cron.path_extra` entry, `/usr/local/bin`, `/usr/bin` and `/bin`. Helper programs (`crontab`, `tmux`, `sh`, `bwrap`, `socat`, `ps`) come from `/usr/local/bin`, `/usr/bin`, `/bin`, `/usr/sbin` and `/sbin`. A candidate is accepted only when it is a regular file (after following symlinks) with `X_OK`, and the file and every directory from it up to `/` (for both the link and its target) are owned by the user or root and not group- or world-writable. The path awkit passes or writes is the unresolved candidate path (symlinks kept). When no candidate is accepted the program is unresolved (see Registration); a tool installed elsewhere needs `tools.<tool>.bin`.

## Environment variables

Only `AWKIT_DASHBOARD__REFRESH`, `AWKIT_DASHBOARD__CONCURRENCY` and `AWKIT_DASHBOARD__READ_TIMEOUT` override config keys; an environment variable wins over the config file and is validated by the same schema (failure exits 2 `config_invalid` naming the variable). awkit reads `TMUX` (for `W`) and `HOME`-derived paths from the password database, not from `HOME`. Reads and actions run with the inherited environment, so the credentials the tools name in their own configs are available to them; awkit adds no variable and never prints one.

## Hooks

awkit exposes no hooks in 0.x (a recorded deviation from the design guide's `pre-` and `post-` rule). awkit consumes other tools' hooks through `wire`.

## Labels

awkit creates no long-lived objects and has no `label` command. It reads labels as described in Links and chains.

## Files

| Path | Content |
|---|---|
| `~/.config/awkit/config.yaml`, `config.d/`, `adapters/` | Configuration and overlay (user-owned, never group- or world-writable). |
| `~/.local/state/awkit/` | The state directory, created 0700; the home's `.local/state` chain must pass the ownership rule. Every file in it is opened relative to a verified directory descriptor with `O_NOFOLLOW`, created 0600, and must be a regular file owned by the user, else exit 20 `config_unsafe` naming it. |
| `~/.local/state/awkit/audit.jsonl` | awkit's own audit records. |
| `~/.local/state/awkit/doctor-last.json` | The last `doctor --json` document, for the dashboard badge. |
| `~/.local/state/awkit/cron.lock` | The `flock` file of `cron` commands. |
| `~/.config/<tool>/config.d/awkit.yaml` | A drop-in written by `wire`. |
| `schemas/defs.json` | Shared schema definitions of the awkit repo (`schemas/config.json` repeats the ones it needs, so it is self-contained). |

There is no `log.jsonl` and no `schemas/log.json` in 0.x (a recorded deviation from the design guide).

## Concurrency

Reads, `attention`, `chains`, `audit`, `validate` and `adapters` keep no locks and can run any number of times at once. `cron install|uninstall` takes the exclusive lock above. `wire` and `unwire` replace one file by rename. Two dashboards may run at once.

## Dependencies

| Tool | Binding | Use |
|---|---|---|
| every registered tool | C | The adapter's reads and actions, by CLI and `--json` only. |
| notice-route | C | The destination of `wire`d hooks. |
| `crontab`, a cron daemon | third-party | `cron` (through each tool's own installer), `doctor`. |
| tmux | third-party, optional | `W`. |

awkit imports no tool and reads no tool's `state.db`. The `tui` extra is Textual `>=8.2,<9`. The core uses the standard library, PyYAML (strict loader) and Pydantic (design guide §3).

## Roadmap

Reserved for 1.x and not implemented in 0.x: `awkit tick`, `awkit run`, `awkit notify-tick [--source TOOL]`, `awkit reconcile`, the rules engine with its write-ahead action ledger, the state graph on disk, `repos:` and `hooks:` config keys, link re-verification and the `forge` tag, the early-tick hooks of `wire`, hook-only attention reasons, notification selectors for state hooks, cross-tool audit correlation, and dashboard actions with human-written text, a second object, multi-select or escalation-scope continuation. The constraints the architecture already fixes (architecture §7.2 to §7.5) apply to them. `design.md` lists the open items.

## Upgrades

An adapter's `min_version` is a floor, not a pin. A tool below it is reported by `doctor` (`tool.version`) and stays usable at the user's risk. A tool newer than the adapter's design is read as usual; a row field that vanished marks the tool stale or partial, never the whole dashboard. The first implementation issue is a verification pass over every tool's current interface that updates the adapters.

## Residual risks

- A process of the same user can write the config, the overlay and the audit files; awkit refuses files other users could write but cannot defend against its own user.
- Labels are not authenticated; the views dim label and branch links, and in 0.x no link-derived value ever enters an argv, but a record that lies in the owning tool is out of scope.
- Each tool's own `cron install` rewrites the crontab with its own small window against a hand edit or another installer; awkit's lock serializes only awkit runs.
- `--actor human:<user>` is a claim: a same-user process can make it. The audit record shows how the claim was made.
- A trusted agent that can reach the user's tmux server can send keys to the dashboard and confirm a dialog. Run the dashboard in its own tmux server or a plain terminal; the dialog is not a boundary against it.
- `PYTHONPATH` and similar variables still affect awkit's own imports (overrides are isolated in child processes). Tools installed outside the program search list need `tools.<tool>.bin`.
- The sanitizer cannot make a terminal safe against a bug in the terminal itself.
- `doctor` is advice and not a security boundary.

## Platform notes

Linux and WSL (Ubuntu) are supported in 0.x. On any other platform every command except `validate` and `adapters` exits 20 `unsupported_platform`; macOS is not supported because awkit is not in the architecture's macOS list. On WSL the cron daemon must be running (`doctor` checks), a long-lived tmux or cron environment can hold a stale interop socket, and the Windows filesystem under `/mnt/c` is not used for state. Outside tmux everything works except `W`.
