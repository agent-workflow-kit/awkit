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

### Registration

A tool is registered when its adapter (bundled or overlay) loaded, `tools.<tool>.enabled` is not `false`, and its program resolves (see Program resolution). Each loaded adapter has one state: `registered`, `absent` (the adapter loaded and the program does not resolve), `disabled` (`enabled: false`), or `adapter_invalid` (the adapter failed to load; the tool is excluded and an overlay failure never falls back to the bundled adapter). An adapter file is `<tool>.yaml` and its `tool` key equals that name, else `adapter_invalid` (the tool name is taken from the file name). The `roles` map is not the registry. Order everywhere (cron, doctor, `adapters list`, ties in Attention) is lexical by tool name in byte order. The rule as pseudocode:

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

Without `--json` the output is for humans and may change (design guide §2). `attention --limit` defaults to 200 and `chains --limit` to 50; chains are ordered by their first node.

`awkit` with no subcommand is `awkit dashboard`; `awkit --focus ...` and `awkit --result-file ...` without a subcommand also mean `dashboard`. `browse` is the same command under the guide's name for a TUI (a recorded deviation: the guide's `<tool> browse` is also accepted). `--version` and `--help` are accepted before a subcommand as well as after it.

A `TOOL` or `--tool` value is a tool name (grammar `^[a-z][a-z0-9-]{0,31}$`). A name that matches no loaded adapter exits 10. A tool that is `absent` or `disabled` exits 12 `tool_unavailable` for `wire`, `unwire` and `cron --tool`, and is skipped silently in runs that cover several tools. An `adapter_invalid` tool exits 20 `adapter_invalid` only when the command names it. `ID` for `--focus` is `<tool>:<object>` with a tool name and an object id as that tool prints it; the dashboard selects the first Attention item with that tool and object, else the first Chains node, else shows "not found" in the status line (the exit code does not change). `--pr` is a pull request URL or `host/<full project path>#N`, `--ticket` is `KEY` or `site:KEY` and `--agent` is an agent object id; `--pr`, `--ticket` and `--agent` select chains as in Links and chains (`pr_norm`, `key_part`), and more than one distinct `site:KEY` among the matches exits 21 with `details.candidates`. `audit --tool` also accepts `awkit` (awkit's own records). `--label` is `key=value` in the label grammar. `--since` is a duration or a timestamp. A value that does not match exits 2 `invalid_argument`. `--tool` repeats and ORs; different filters AND.

Durations are `^[1-9][0-9]*(ms|s|m|h|d)$` everywhere: no bare numbers and no fractions (a recorded deviation from the guide). Timestamps awkit writes are UTC `YYYY-MM-DDTHH:MM:SS.sssZ`; input timestamps (row `since`, audit `ts`, `--since`, `--until`) are normalized by `norm_ts` (below); a value it rejects is null (a row field), malformed (an audit line) or `invalid_argument` (a flag). Records in `audit` output keep their own `ts` text.

```text
TS_IN = ^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d{1,9})?(Z|[+-]\d{2}:\d{2})$
def norm_ts(v) -> str | None:
    if not isinstance(v, str) or len(v) > 40 or not re.fullmatch(TS_IN, v): return None
    try: dt = datetime(Y, M, D, h, m, s, micro=first 6 fraction digits, tzinfo=offset); u = dt.astimezone(UTC)
    except (ValueError, OverflowError): return None
    if not 1970 <= u.year <= 9999: return None
    return u.strftime("%Y-%m-%dT%H:%M:%S.") + f"{u.microsecond // 1000:03d}Z"
order by the normalized string (fixed width UTC, so lexical order is chronological)
```

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
| 12 | `unavailable`, `checks_failed`, `tool_unavailable`, `cron_partial` | Expected failure. `unavailable` carries a `reason`: `locked`, `crontab_failed`, `crontab_unusable` or `wire_rejected`. `checks_failed`: `doctor` found a failed check. `tool_unavailable`: a tool the command needs is absent, disabled or answered badly. `cron_partial`: a tool's own installer failed or the run was interrupted; the cron document is printed. |
| 13 | `human_required` | A human is needed: `dashboard` or an action that needs a terminal has none, or `wire` or `unwire` without `--yes` has no human present. |
| 20 | `refused` | Refused with a `reason` (see below). |
| 21 | `ambiguous` | Ambiguous selector; `details.candidates` is an array of `<tool>:<object>` or `site:KEY` strings. |

Reasons of exit 20: `config_unsafe` (a config, drop-in, adapter, state file or parent directory that is a symlink, not owned by the user, or group- or world-writable), `adapter_invalid`, `drop_in_foreign` (the drop-in exists and is not awkit's unedited file), `duplicate_state_hooks` (wiring a `state: true` hook while another tool's state hooks are wired by awkit), `stale_object` (an action's confirmation facts no longer match the object, reported by the owning tool), `unsafe_value` (a value awkit would write into a drop-in or pass to a tool's installer does not match the safe-value grammar), `xdg_mismatch` (`wire` with `XDG_CONFIG_HOME` set to a non-default value), `unsupported_platform` (on a platform other than Linux, every command except `validate` and `adapters`). Codes 22 and above are not used in 0.x. Codes 14 to 19 never occur (awkit waits on no session); a child's exit code is reported in the result and never passed through as awkit's own.

## Output by exit code and error envelope

With `--json`, exit 0 prints the result object of the command (member names are those of `schemas/cli/`). Three exits print the command's document instead of the envelope: exit 12 `checks_failed` from `doctor`, exit 12 `cron_partial` from `cron`, and exit 2 from `validate`. Every other non-zero exit prints the envelope `{"error": {"code": "<exit-name>", "message": "...", "reason": "...", "details": {...}}}` on stdout and the message on stderr. `reason` appears only on exits 12 and 20. Strings that came from a tool are sanitized (see Output sanitizing) in every output. `dashboard` and `browse` print nothing with `--json`; their machine output is the result file.

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

`attention` and `chains` exit 0 with `stale` and `partial` lists when a tool's read failed or was cut short; `chains --ticket` with no match exits 0 with an empty list. `adapters show` of a failed adapter exits 0 with `status: adapter_invalid` and `adapter: null`.

## Adapters

An adapter is one YAML file `<tool>.yaml` validated by `schemas/adapter.json`. Bundled adapters live in the repo's `adapters/` directory and are read-only data. The overlay directory is `~/.config/awkit/adapters/` under the home directory of the password database (see Configuration). An overlay file with the same `tool` replaces the bundled adapter wholesale; there is no merging. A file that fails to load excludes only its tool: `doctor` reports `adapter.loaded` failed (naming the overlay path) and the other tools keep working.

### Adapter file

The required keys are `tool`, `binding` and `bin`; every other key is optional.

| Key | Meaning |
|---|---|
| `tool` | Tool name. |
| `binding` | `C` for every adapter (architecture §3.3). |
| `bin` | The program name, never a path; found through Program resolution. `tools.<tool>.bin` overrides it with an absolute path. The first element of every argv the adapter runs for the tool is this name; awkit replaces it with the resolved program path. |
| `install` | The install command `doctor` prints for a missing tool. |
| `min_version` | The lowest tool version the adapter was written against. |
| `version` | How to read the installed version: `package: <distribution name>` (package metadata of the tool's own environment) or `argv` of a command that prints it. |
| `reads` | Named reads (see Reads). |
| `attention` | Rules that turn rows into Attention items (see Attention). |
| `links` | Label keys, branch patterns and record fields that join objects (see Links and chains). |
| `actions` | Actions (see Actions). |
| `tui` | How to open the tool's own TUI on an object (see Child TUI). |
| `cron` | How to run the tool's own `cron install` and `uninstall` and recognize its block (see Cron). |
| `audit` | The tool's audit file and how to pair its records (see Audit). |
| `doctor` | `{validate: {argv, ok_exits, info_exits, warnings}, probe: argv, env: [names], needs: [programs], pair: [{id, tool, min_version}]}` (see Doctor). |
| `wire` | Hooks to route to notifications and the `check` command (see Wire). |
| `overrides` | Escape hatches (see Escape hatches). |

### Reads

A read declares `argv`, an optional `timeout` (default `dashboard.read_timeout`), `kind` (the node kind of its rows), `items` (a path selecting the row elements; filters go inside it), `fields` (a map from row field name to a path relative to one element) and an optional `truncated` (a path; see below). Reserved row fields are `id` (required), `title`, `since`, `labels`, `branch` and `state`; any other field name is free and usable in `when` and `show`. A read has no placeholders.

A read asks the tool to change nothing. Some tools run their own liveness checks on list commands and may record state changes; awkit accepts and documents that (the bundled table names agent-spawn `list` and claude-session `list`), and the bundled adapters use non-mutating forms where they exist and pass `--limit` at the tool's maximum where the tool has one. A read runs with the inherited environment, no standard input, in a new session, and never with a terminal.

Limits: stdout is read up to 8 MiB and 64 KiB of stderr is kept. Reaching a cap or the timeout sends SIGTERM to the read's own process group, then SIGKILL after 2 s, and reaps it. A read that exits non-zero, exceeds a limit or prints invalid JSON marks the tool stale for that refresh; the previous rows stay on screen with their age. Every exception from parsing (including recursion depth and huge integers), path evaluation and sanitizing is a read failure for that tool. JSON parsing refuses `NaN` and `Infinity`. Parsing, path evaluation and sanitizing run in one worker thread, one document at a time, never on the event loop. A read whose `truncated` path yields `true` marks the tool partial (like stale, but the rows are shown). Rows whose `id` is null, fails the `object_id` grammar or repeats an earlier row's `id` are dropped and counted; the count is shown in the marker details and the tool is partial. Free fields keep only strings, integers, booleans and null; any other value is null, and `title` must be a string (else null).

```text
def run_read(read) -> (rows, dropped) | stale:
    doc = gateway.run_json(read.argv, timeout)           # json.loads(..., parse_constant=refuse); in the worker thread
    elems = path_eval(read.items, doc)                   # list; scalar -> [scalar]; null -> []
    rows, seen, dropped = [], set(), 0
    for e in elems:
        row = {name: path_eval_scalar(p, e) for name, p in read.fields.items()}
        if not valid_object_id(row.get("id")) or row["id"] in seen: dropped += 1; continue
        seen.add(row["id"])
        row["since"] = norm_ts(row.get("since"))
        if not isinstance(row.get("title"), str): row["title"] = None
        for k in free fields: if type(row[k]) not in (str, int, bool, NoneType): row[k] = None
        rows.append(sanitize_row(row))
    return rows, dropped                                 # dropped > 0 -> partial
```

`path_eval_scalar` returns `null` when the path yields a list (it never zips elements by position). A tool whose every row is dropped is partial with zero rows.

### Path language

Paths are small and total. They are evaluated by awkit itself with no external program. Errors happen only when an adapter loads (invalid path text, or more than one filter in a step); evaluation never raises.

```text
path    = first *step
first   = name / bracket
step    = "." name / bracket
name    = ( ALPHA / "_" ) *( ALPHA / DIGIT / "_" / "-" )
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

### Argv rules

Commands are argv lists, never shell strings, and awkit never runs a shell for an adapter command. Action argv placeholders are a closed set filled by awkit: `{object}` (the row's `id`, grammar `object_id`), `{actor}` (the fitted actor; the dry run gets the same one) and `{pass.<name>}` (a flagless `row.` pass value, see Actions). A placeholder is a whole argv element: `--flag={x}` and unknown names are load errors, and a literal `{` in argv is written `{{`. There is no `params` key in 0.x. Every value is checked against a closed grammar of `schemas/defs.json` before it is substituted, each with a first character that is not `-`: `object_id` (`^[A-Za-z0-9/*][A-Za-z0-9._:@/#=+~*-]{0,255}$` with no `..` path segment), `hash` (`^[0-9a-f]{12,128}$`), `int` (`^(0|[1-9][0-9]{0,17})$`) and `enum` (listed values). A value that does not match refuses the call. Only grammar-checked identifiers taken from the selected row or the dry run (`{object}`, `{pass.*}`) ever enter an argv; free text never does and no link-derived value ever does. Argv items after the first may be empty strings. The first element of every argv awkit runs is replaced by the resolved program path (Program resolution). awkit's grammars are injection boundaries, not the tool's own validation; the tool refuses a value of the wrong form itself. All patterns are anchored with `(?![\s\S])` in the schemas, so a trailing line feed never matches.

### Escape hatches

Any single operation, or a whole adapter, can be replaced. Both override kinds speak the same protocol in a child process: `exec: <absolute path>` runs that file, and `python: <spec>:<function>` runs `[sys.executable, "-I", "-m", "awkit.override_host", <spec>, <function>]`, where `<spec>` is either `awkit.<module>` (bundled, inside awkit's own package) or a file name `<name>.py` relative to the overlay directory (loaded by `importlib.util.spec_from_file_location`, never by module search). The file, an `exec` target and every parent directory up to the home (or `/` for paths outside it) must pass the ownership rule (owned by the user or root, not group- or world-writable, the file itself not a symlink). The request goes on stdin (a pipe; nothing else is on stdin) and the reply on stdout; the read rules apply otherwise (timeout, new session, 8 MiB cap, no terminal). `validate` only checks names and file ownership; it never imports or runs an override. An overlay file is loaded as module `awkit_override_<tool>` (dashes as underscores). awkit writes the request under the operation's timeout; a broken pipe is a failure. The protocol belongs to awkit; tools never see it.

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
    argv: [agent-spawn, list, --needs-attention, --json]
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
    - {read: needs_attention, key: ticket, to_kind: ticket, to_tool: ticketctl}
actions:
  - id: teardown
    label: Tear down
    applies_to: [escalated]
    argv: [agent-spawn, teardown, "{object}", --json]
    destructive: true
    recipe:
      dry_run: true
      show: [plan.summary]
      pass:
        # illustrative: a pass entry takes a value from the dry run and appends it as a flag
        - {name: plan_hash, flag: --plan-hash, from: dry_run.plan.hash, type: hash}
      "yes": true
```

## Attention and chains

### Attention

An attention rule is `{read, reason, severity, when?}`. It takes the rows of its read; `when` is one typed equality on a row field (`{field: value}`, typed as in the path language) and skips the rows that do not match. Reasons are adapter-defined (grammar `^[a-z][a-z0-9_]{0,63}$`) and the severity (`info`, `action` or `error`) is declared per rule. Each row yields one item:

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
labels:   [{read, key, to_kind, to_tool}]           # row.labels[key] values -> node (to_tool, value), tag label
branches: [{read, pattern, to_kind, to_tool}]       # re.fullmatch(pattern, row.branch); group "ref" -> node, tag branch
records:  [{read, field, to_kind, to_tool}]         # row[field] -> node, tag record
```

For each declared form, each row of `read` and each extracted value that passes `object_id`, awkit adds the edge `(tool, row.id, kind) -> targets(to_tool, to_kind, value)` with the tag, one edge per pair keeping the strongest tag (`record`, then `branch`, then `label`). A node is identified by `(tool, kind, object)`, so equal ids of different kinds never collide. `branches` patterns are Python `re`, compiled at load and applied with `re.fullmatch` to a `branch` of at most 1000 characters. Attributes such as `repo`, `kind`, `owner` and `consumer` are not edges unless an adapter declares them in `labels`. Each link has a source tag:

| Tag | Meaning |
|---|---|
| `record` | A tool's own stored id for the other object (for example a pull request id a workflow stored). |
| `branch` | Derived from a branch name that matches an adapter pattern. |
| `label` | Derived from a label only. |

```text
key_part(obj) = obj.rsplit(":", 1)[-1]
def pr_norm(s):                                     # --pr input; label and node values compare as printed
    https://<host>/<path>/pull/<N>             -> "<host>/<path>#<N>"
    https://<host>/<path>/-/merge_requests/<N> -> "<host>/<path>#<N>"
    "<host>/<path>#<N>"                         -> as is;   anything else -> exit 2 invalid_argument
def targets(to_tool, to_kind, v):                  # edge targets for an extracted value v
    nodes = [n for n in nodes_of(to_tool) if n.kind == to_kind]
    if to_kind == "ticket" and ":" not in v: hit = [n for n in nodes if key_part(n.object) == v]
    else: hit = [n for n in nodes if n.object == v]
    return hit or [Node(to_tool, to_kind, v)]       # a link-only node when the tool lists none
chains --pr P:     chains with a pull_request node whose object == pr_norm(P)
chains --ticket K: chains with a ticket node whose object == K, or key_part(object) == K when K has no ":";
                   more than one distinct site:KEY among the matched nodes -> exit 21 (candidates)
chains --agent A:  chains with an agent node whose object == A
```

Chains are the connected components that contain a `ticket`, `agent`, `pull_request` or `review_item` node, each printed as nodes sorted by kind (in the vocabulary order) then object, plus its edges (`{nodes[{tool, object, kind, title?}], links[{from, to, source}]}`). Chains are ordered by their first node.

Labels are not authenticated against processes of the same user. The views show `branch` and `label` links dimmed, and `chains --json` prints the tag of every link. In 0.x no link-derived value ever enters an action's argv: every action acts on the selected row's own object, confirmed by the owning tool's own dry run and refusals, and the dialog shows the object the tool itself confirmed. Re-verification of links against an authoritative source, and a `forge` tag, return in 1.x with the rules engine.

## Dashboard

`awkit dashboard` needs a terminal on stdin, stdout and stderr (a human present plus stdout) and the optional `tui` extra (Textual `>=8.2,<9`); without a terminal it exits 13, without the extra it exits 12 `tool_unavailable` with the install command. The core never imports Textual.

### Views and keys

Three tabs: Attention (the default), Chains and Timeline (the newest 500 entries, paired as in Audit). The header shows the tool name, the badge (the result of the last `doctor` from its cache file, with its age) and one marker per tool whose last read failed (stale, with the age of its data) or was cut short (partial). The footer shows key hints and the status line shows the last action's result. A detail pane shows the selected row's fields only. A selection stays on the same item across refreshes. Every view respects the terminal's colors and never hard-codes backgrounds.

| Key | Action |
|---|---|
| `1`, `2`, `3` | Switch tab. |
| `enter` | Open the selected object in its owning tool's own TUI as a child (see Terminal handoff), when the adapter has a `tui` key; otherwise the status line says it is not available. On Timeline it does nothing. With `--result-file` set on awkit, `enter` writes the result file and exits instead (see Result file). |
| `a` | Actions menu for the selected item (see Actions). |
| `W` | Run the same child in a new tmux window when `$TMUX` is set (see Child TUI). |
| `d` | Run `doctor` and update the badge. |
| `r` | Refresh now. |
| `/` | Filter the current tab: a case-insensitive substring of title, object or tool; Escape clears it. |
| `?` | Help. |
| `q` | Quit. |

States:

| State | Shown |
|---|---|
| Before the first refresh | "Loading". |
| No registered tool | "No tools registered; run `awkit doctor`". |
| Empty Attention | "Nothing needs you". |
| `doctor-last.json` missing, invalid or over 1 MiB | The badge reads "no doctor result". |
| A tool's last read failed | A stale marker with the age, or "never read" when its first read failed. |
| A tool's rows were cut short or dropped | A partial marker with the details. |
| `W` with no tmux, a foreign socket or tmux older than 3.0 | A status line message that it is disabled. |
| Chains | A selection is a node. A node that came from a row of its tool offers `enter` (when the tool has `tui`) and `a`, which lists that tool's actions whose `applies_to` holds the reason of a current Attention item for the same tool and object; a link-only node offers neither. Nodes are ordered by kind (in the vocabulary order), then object. |
| Timeline whose first read started past the beginning of a file | "older records not read". |
| No action applies to the selected item | The status line says "no actions for this item". |

### Refresh

One worker refreshes all tools: reads run concurrently under a semaphore of `dashboard.concurrency` (default 8). A cycle ends when every read has ended; the next cycle starts `dashboard.refresh` (default 15 s, at least 5 s) after the previous start, or at once when the previous cycle ran longer. A manual refresh joins the running cycle. A slow tool therefore delays the cycle by at most its timeout plus 2 s. The Timeline reads audit files by byte offset (see Audit).

### Terminal handoff

A child that needs the terminal (a tool's TUI, `ticket-create create`, an interactive agent session) runs with the dashboard suspended in the same terminal. The dashboard never leaves SIGINT ignored for a child to inherit: for the child's lifetime it installs a no-op handler (exec resets it to the default in the child), and once the child's group is the foreground group the terminal sends Ctrl-C to the child only. It discards pending typeahead on the terminal before the child starts and again after it exits, restores the terminal state it saved, and then redraws. The child starts in its own process group and is made the foreground group as in the pseudocode below (SIGTTOU is ignored only around each `tcsetpgrp` call); SIGTERM and SIGHUP are forwarded with `killpg` of that recorded group only while the child has not been reaped, and the dashboard takes the foreground back after the child exits. A child whose output awkit captures runs in a new session with standard input from `/dev/null`, so it can never read the dashboard's terminal. The dashboard installs a handler for SIGTERM and SIGHUP that restores the terminal before exiting.

```text
handoff(argv):
    save termios; app.suspend()                      # Textual restores cooked mode
    old_int = signal(SIGINT, noop_handler)           # a handler, never SIG_IGN: exec resets it to default
    tcflush(tty, TCIFLUSH)
    child = Popen(argv, process_group=0, pass_fds=(), stdin/stdout/stderr = the terminal)
    with_sigttou_ignored(lambda: tcsetpgrp(tty, child.pid))   # ignore only around the call
    killpg(child.pid, SIGCONT)                       # in case it stopped on SIGTTIN before it was foreground
    on SIGTERM or SIGHUP to the dashboard: under child_lock, if child.returncode is None: killpg(child.pid, sig)
    wait under child_lock
    with_sigttou_ignored(lambda: tcsetpgrp(tty, getpgrp()))
    tcflush(tty, TCIFLUSH); restore termios; signal(SIGINT, old_int); app.resume()
with_sigttou_ignored(f): old = signal(SIGTTOU, SIG_IGN); try f() finally signal(SIGTTOU, old)
```

### Child TUI

An adapter's `tui: {argv}` has an argv such as `[tool, browse, --focus, "{object}"]` (whole-element `{object}` only). `enter` runs it for the selected row's tool under Terminal handoff; when the child exits the dashboard refreshes. In 0.x awkit passes no `--result-file` to a child and reads no child result (a child's intent, such as ticket-queue's `start`, is acted on in 1.x).

`W` runs `tmux new-window -d` followed by the resolved argv (element 0 is the resolved program path, at least two elements, so tmux executes it without `sh -c`), with no `-c`, `-n` or `-t`; `tmux` is resolved by Program resolution and must be version 3.0 or newer (`tmux -V`, read at first use). `W` is disabled when `$TMUX` is unset, names a socket not owned by the user, or tmux is older than 3.0; the child gets the tmux server's environment (documented), never touches the dashboard's terminal, and awkit does not wait.

### Result file

With `--result-file PATH`, `awkit dashboard` and `awkit browse` write on exit 0, under `enter` (for any selected row, without running a child), `{"intent": "open", "selected": [{"tool": "...", "object": "..."}]}` and, under `q`, `{"intent": "back", "selected": []}`; `selected` has at most one item. The temporary file is created in the target directory with `O_CREAT|O_EXCL|O_NOFOLLOW`, an unpredictable name and mode 0600, synced, renamed, and unlinked on failure. Nothing is written otherwise, and a pre-existing file is never read. The caller removes a stale file before launching.

## Actions

An action is an entry of an adapter's `actions` with `id`, `label`, `applies_to` (a list of reasons of the same adapter), an optional `when` (one equality on a row field; the action is hidden when false), `argv` (a template), `destructive` (true when it ends work or leaves the machine) and exactly one form:

- **`recipe`**: `{dry_run: bool, show: [path...], pass: [{name, from, type, flag?}], yes: bool, actor_charset?}`. The argv must contain `--json`. With `dry_run: true` the dry run is the argv plus the `row.` pass values, `--actor` and `--dry-run` (never `--yes`); the loader refuses a separate dry-run argv. `from` is `row.<field>` (used in both runs: with `flag` appended, without it filling the whole-element placeholder `{pass.<name>}`) or `dry_run.<path>` (needs `flag`; real command only), and `type` is `hash`, `object_id`, `int` or `enum` (an `enum` lists its `values`); each passed value is checked against its grammar. A `{pass.<name>}` with no flagless `row.` entry of that name, a flagless entry not used exactly once, and a `dry_run.` entry without `flag` are load errors. The `yes` key is written quoted (`"yes": true`) because YAML 1.1 loaders read a bare `yes` as a boolean. `dry_run: false` is allowed only when `destructive` is false. An `action_plan` override replaces the derived dry run and applies only to actions with `dry_run: true`. `show` paths are read from the dry-run result (from the row when `dry_run` is false).
- **`terminal: true`**: no dry run; awkit's dialog shows the argv (empty body) and `y` hands over the terminal (see Terminal handoff); the only form for a command without `--yes`, including `ticket-create create`. `human_flag` requires `terminal: true`.

Every action, terminal ones too, opens awkit's dialog first, and gets `--actor <actor>` appended unless its argv has `{actor}`. A destructive action must be a recipe with `dry_run: true` or a terminal action. A non-zero dry run is a refusal with no `y`: the dialog shows the exit code, the envelope's `code` and `reason` when stdout is an object with `error`, else the `show` fields over stdout when it is a JSON object (a tool's refusal plan stays visible).

These action kinds are not in 0.x (a recorded deviation): actions that need human-written text (`--prompt-file`, `--reason-file`, `--note-file`), a second chosen object (move before X, pin with expiry), multi-select, continuation of a refused call (escalation scope), and every reserved human flag except one. The reserved flags (`--force`, `--override-escalation`, an enforced-state change, `wtctl baseline accept`) are never passed. The single exception is claude-session's resume with `--allow-tainted`, a human-only override that the bundled adapter declares as a terminal action with `human_flag: --allow-tainted`; the flag appears in the dialog chrome. Reorder in 0.x is done in the owning tool's TUI. The user reaches the rest through the tool's own TUI (`enter`) or CLI. `--yes` never overrides a refusal (exit 20). An action never runs from a read, and nothing is run by a rule in 0.x.

After `y` awkit runs the real command (captured with the read rules, or under Terminal handoff for a terminal action). The status line shows `done` for exit 0; for any other exit the exit code, the envelope's `code` and `reason` when stdout holds one (a tool's exit 20 when the facts moved shows its `reason`), and for exit 12 "the outcome may be partial; check <tool>". The dialog never reopens by itself; the next refresh shows the new state. A child's exit code is never awkit's own.

### Confirmation dialog

```text
on key "a" with row R (snapshot by value):
    if a dialog is open or a dry run is in flight: ignore
    acts = [x for x in actions(R.tool) if R.reason in x.applies_to and (not x.when or eq(R, x.when))]
    if not acts: status "no actions for this item"; return
    x = menu(acts); actor = fit("human:" + me.name, x.recipe.actor_charset)
    rowp = {p.name: check(p.type, R[p.from[4:]]) for p in x.pass if p.from.startswith("row.")}
    if any check failed: status "refused: invalid <name>"; return
    base = fill(x.argv, object=R.id, actor=actor, pass={n: v for n, v in rowp if no flag})
    pre  = [p.flag, rowp[p.name] for p with flag and from row.] + ([] if "{actor}" in x.argv else ["--actor", actor])
    if x.terminal: real = base + pre; body = []
    elif x.recipe.dry_run:
        r = run(base + pre + ["--dry-run"], read rules)            # no --yes; same actor
        doc = r.stdout parsed as a JSON object, else None           # parse_constant refuses NaN and Infinity
        if r.exit != 0:
            refusal(exit=r.exit, code_reason=doc["error"] if doc has "error" else None,
                    body=show(x.recipe.show, doc) if doc and "error" not in doc else []); return
        if doc is None: refusal("the dry run printed no JSON object"); return
        dryp = {p.name: check(p.type, path(p.from[8:], doc)) for p in x.pass if p.from.startswith("dry_run.")}
        if any check failed: refusal("invalid <name>"); return
        real = base + pre + [p.flag, dryp[p.name] for those] + (["--yes"] if x.recipe.yes else [])
        body = show(x.recipe.show, doc)
    else: real = base + pre + (["--yes"] if x.recipe.yes else []); body = show(x.recipe.show, R)
    dialog(chrome = tool, label, R.id, actor, real one element per line, "destructive" when set,
                    human_flag when set, "Run? [y/N]";  body = lines prefixed "| ")
    if size(body) > 64 KiB: show "too large to confirm here; use <tool> directly", no y
    gate: shown_at = monotonic(); tcflush(TCIFLUSH)
          a key event whose own timestamp < shown_at + 0.5 s is dropped
          y accepted only when the body fits the pane or has been scrolled to its end once
          (keys or mouse wheel; lines wrap, never scroll sideways); Enter, paste, any other key = no
    on y: terminal -> run real under Terminal handoff; else run real captured with the read rules
          status: exit 0 "done"; else exit, envelope code and reason when stdout has "error",
                  and for exit 12 "the outcome may be partial; check <tool>"
show(paths, doc): each path's value: a string as is; null, booleans and numbers as JSON text;
                  lists and objects as compact JSON text; then sanitized without the per-field cut
```

An argv that contains `{actor}` gets the actor there and no appended `--actor`.

## Cron

`awkit cron install` runs each registered tool's own `cron install` in lexical order (all registered tools with a `cron` key unless `--tool` narrows it); `uninstall` runs each tool's own `cron uninstall`. awkit never writes the crontab itself. The adapter's `cron` key is `{install: argv, uninstall: argv, start, end, interval_flag?, env_file_flag?, options?: {<name>: [argv items]}}`: it maps awkit's config to the tool's flags.

`cron.intervals.<tool>` is passed verbatim, as one argv element after the adapter's `interval_flag`; awkit checks only the generic grammar of Configuration and the tool itself validates the value (a refused value makes that tool `failed`). `cron.options.<tool>` lists option names, for example `with-start`; the adapter's `cron.options` maps each name to literal argv items (adapter text, never config text). An option name the adapter does not map, or an interval for a tool whose adapter has no `interval_flag`, is `config_invalid` (exit 2 naming the key, at `validate` and at every `cron` command). `uninstall` gets no mapped flags. `cron.env_file` is passed with `env_file_flag` only where the tool has that flag (in the bundled adapters agent-spawn and wtctl) and is otherwise the tool's own config (the tools that read an env file from their own config check it in their own `validate`).

Each installer runs with the environment of `installer_env` (below) and nothing inherited, so the `PATH` a tool bakes into its block holds only directories of Program resolution and no `XDG_*` value reaches a block; every tool's own refusals apply. A registered tool without a `cron` key is skipped with outcome `skipped`. The bundled claude-session adapter has no `cron` key, because agent-spawn's block runs claude-session's reconcile and single sessions need no cron entry. A disabled or absent tool is skipped, also by `uninstall`; remove its block with the tool's own `cron uninstall`. awkit's config is the desired state: the next `awkit cron install` replaces flags given to a tool's own installer by hand.

### Recognizers

Each adapter has one recognizer per tool: `start` (`{exact: text}`, `{prefix: text}` or `{regex: pattern}`) and `end` (an exact line, or `null` for a tool whose block has no end line); each is tested on the line with trailing spaces, tabs and CR removed: `exact` and `end` by equality, `prefix` by prefix, `regex` by Python `re.fullmatch` (compiled at load) on lines of at most 1000 characters, so a longer crontab line is never a start line. Patterns are trusted overlay config like the rest of the overlay. The end line is tested before the start line, because a loose start rule can also match an end line. A line that merely contains a tag in a comment is not a block. A block is present (a start line found), absent, or malformed (an end line without a start, a start without an end where `end` is not null, a duplicate, or interleaved blocks). `doctor cron.block` and the `cron` report use it; awkit runs no tool's dry run, so it never says whether a block is current.

### Install order

```text
INTERVAL = ^(?!-)[A-Za-z0-9*/,-]{1,32}(?: [A-Za-z0-9*/,-]{1,32}){0,6}$     # or an integer 1..99999
def install_argv(tool):
    a = resolve_argv(adapter.cron.install)          # element 0 replaced by the resolved program path
    v = config.cron.intervals.get(tool)             # None, str or int
    if v is not None: a += [adapter.cron.interval_flag, str(v)]
    if config.cron.env_file is not None and adapter.cron.env_file_flag:
        a += [adapter.cron.env_file_flag, config.cron.env_file]
    for name in config.cron.options.get(tool, []):  # config order
        a += adapter.cron.options[name]             # literal argv items, first one a flag
    return a
def uninstall_argv(tool): return resolve_argv(adapter.cron.uninstall)

def installer_env():
    pw = getpwuid(getuid())
    return {"HOME": pw.pw_dir, "USER": pw.pw_name, "LOGNAME": pw.pw_name, "LANG": "C.UTF-8",
            "PATH": ":".join([pw.pw_dir + "/.local/bin", *config.cron.path_extra,
                              "/usr/local/bin", "/usr/bin", "/bin"])}
# no XDG_*, PYTHON*, LD_*, BASH_ENV, ENV, SHELLOPTS or any other variable; values pass safe_path or are fixed

cron OP [--tool T]... [--dry-run]:                         # OP is install or uninstall
    named T absent or disabled -> exit 12 tool_unavailable; named T without adapter -> exit 10
    tools = [t for t in registered tools, lexical, if (not --tool or t in --tool)]
    rows  = [(t, "skipped", None) if not adapter(t).cron else (t, None, argv_for(t, OP)) for t in tools]
    if --dry-run:
        print {dry_run: true, unchanged: null, tools: [{tool, outcome: skipped|planned, argv}]}; exit 0
        # no lock, no crontab read, no audit record, nothing run
    if not flock(cron.lock, LOCK_EX | LOCK_NB): exit 12 unavailable locked        # no waiting
    before = read_crontab()          # failure -> exit 12 crontab_failed|crontab_unusable; nothing run, no audit
    audit attempted {inputs.tools: planned tools, before_sha256: sha256(before)}
    stop = False; install handlers for SIGINT, SIGTERM, SIGHUP that set stop = True
    for (t, outcome, argv) in rows:
        if outcome == "skipped": continue
        if stop: outcome[t] = skipped; continue
        r = run(argv, env=installer_env(), stdin=DEVNULL, new session, stdout cap 8 MiB, stderr cap 64 KiB, timeout 60s)
        # timeout: SIGTERM to the installer's process group, SIGKILL after 2 s, reap
        if r.timed_out: outcome[t] = failed, exit null, message "timeout; the block may be partly written, run awkit doctor"
        elif r.exit == 0: outcome[t] = done
        else: outcome[t] = failed, exit r.exit, message sanitize(stderr text, 1000)
    after = read_crontab() or None on failure
    unchanged = (after is not None and after == before)
    audit outcome {result.outcome: done if every planned tool is done else failed, tools, unchanged, after_sha256}
    print {dry_run: false, unchanged, tools: rows with outcomes}        # with or without --json
    exit 12 cron_partial if any tool failed or was skipped by stop, else 0

def read_crontab():
    r = gateway.run([crontab, "-l"], env={LC_ALL: C, PATH: SYSTEM_PATH}, stdin=DEVNULL, timeout=30s)
    if r.exit == 0:
        if b"\0" in r.stdout or len(r.stdout) > 1 MiB: fail(12, unavailable, crontab_unusable)
        return r.stdout
    if r.exit == 1 and r.stderr.startswith(b"no crontab for"): return b""
    fail(12, unavailable, crontab_failed)
```

`crontab` that does not resolve (Program resolution) is `crontab_failed`. awkit passes no `--yes`, `--actor` or `--json` to installers (the tools write their own cron actors); flag order is the install argv, interval, env file, options.

With `--dry-run` awkit prints each tool's outcome (`planned`, with the exact argv it would run, or `skipped`), runs nothing, takes no lock, reads no crontab and writes no audit record. The crontab is read before and after for the audit hashes and by `doctor`; awkit keeps no copy of it. The lock serializes awkit's `cron` runs only and never waits; each tool's own installer keeps its own write window against a hand edit (see Residual risks). Every non-dry-run `cron` command that reads the crontab writes one pair of audit records (see Audit); its outcome carries `unchanged` when the crontab did not change. `uninstall` runs the same steps with each tool's `uninstall` argv. A signal stops the run between tools; the remaining tools are `skipped` and the exit is 12 `cron_partial`. A lock held exits 12 `unavailable` with `reason: locked` at once.

## Wire

`awkit wire TOOL` writes the notification wiring for one tool: the drop-in `~/.config/<TOOL>/config.d/awkit.yaml` under the home directory of the password database, and nothing else. Its text is fixed (below): the first line is the marker `# awkit managed sha256=<hex>` over the rest of the file, then a `hooks:` map from each hook name the adapter's `wire.hooks` lists (`^(?:post|on)-[a-z][a-z0-9_-]{0,63}$`, never `pre-`: a failing notice hook must not veto a step) to one entry with a string `cmd` run by the tool through `sh -c` (design guide §8) and `async: true`. No `timeout` is written: each tool's default applies. Hook selectors (`states`, `kinds`, `labels`) are out of 0.x. A tool whose adapter lists no hooks, and `wire notice-route`, exit 0 with `nothing_to_wire`. The bundled hook lists come from the verification issue. awkit never edits a `config.yaml`, any other file of a tool, or notice-route's rules: routing `source: <TOOL>` is the user's notice-route config (the README shows the rule), `wire` prints one line saying notice-route needs a rule for that source, and `doctor` warns when notice-route routes none of a wired tool's hooks (`wire.rule`).

```text
# awkit managed sha256=<64 lowercase hex: SHA-256 of every byte after this line's LF>
hooks:
  <hook name>:
    - cmd: "<resolved notice-route path> send --source <TOOL> --stdin-json"
      async: true
  <next hook name>:
    - cmd: "<resolved notice-route path> send --source <TOOL> --stdin-json"
      async: true
```

Lines end in LF, the file ends with an LF and the hooks keep the adapter's order. The path matches `safe_path` and `<TOOL>` the tool grammar, so the double-quoted YAML scalar needs no escape and `sh -c` reads it literally.

`wire` shows the exact drop-in text and applies it after confirmation: a human present answers `y` on `/dev/tty` (prompts and reads go there), or `--yes` skips the question (exit 13 when neither a human is present nor `--yes` is given; `unwire` follows the same rule). Outcomes are `wired`, `replaced`, `unchanged`, `removed` (for `unwire`) and `nothing_to_wire`. A drop-in that exists and is not `owned` (no marker, or a body edited after awkit wrote it) is `drop_in_foreign` (exit 20): awkit never overwrites or removes a file it did not write as it is. Add your own hooks in another drop-in. `wire` with `XDG_CONFIG_HOME` set to a non-default value refuses with exit 20 `xdg_mismatch`, because the tool would not read the drop-in. Values written into `cmd` must match the safe-value grammar (see Configuration; else exit 20 `unsafe_value`). The adapter's `wire.check` is `{argv, ok_exits: [0]}`, required whenever `wire.hooks` is non-empty: a command that loads the tool's config and changes nothing (its `validate`, or a list read). It runs before the write (a failing check refuses, so a pre-existing error is never blamed on the drop-in) and after it (rollback when the exit is not in `ok_exits`), with the read rules.

```text
def owned(data: bytes) -> bool:
    first, sep, rest = data.partition(b"\n")
    m = re.fullmatch(rb"# awkit managed sha256=([0-9a-f]{64})", first)
    return bool(sep) and m is not None and sha256(rest).hexdigest().encode() == m.group(1)
def open_config_d(tool):                  # every step by fd, O_DIRECTORY|O_NOFOLLOW
    walk "/" .. <home> .. "<home>/.config" .. "<home>/.config/<tool>": each owned by the user or root,
        not group- or world-writable, never a symlink, else exit 20 config_unsafe naming it
    "<home>/.config/<tool>" missing -> exit 12 tool_unavailable ("tool has no config directory")
    config.d: openat; create with mode 0700 when missing; same ownership rule
TEMP = ".awkit-" + 16 random hex + ".tmp"   # never matches *.yaml or *.yml

wire TOOL [--yes] [--dry-run]:
    TOOL not registered -> exit 10 or 12 tool_unavailable (Registration)
    hooks = adapter(TOOL).wire.hooks or []
    if TOOL == "notice-route" or not hooks: exit 0, outcome nothing_to_wire
    nr = resolved program of notice-route; unregistered -> exit 12 tool_unavailable ("notice-route is not installed")
    if XDG_CONFIG_HOME set and != <home>/.config: exit 20 xdg_mismatch
    if nr or <home> fails safe_path: exit 20 unsafe_value
    text = render(hooks, nr, TOOL)
    if not flock(wire.lock, LOCK_EX | LOCK_NB): exit 12 unavailable locked
    if any(h.state for h in hooks):
        for U in registered tools, U != TOOL, with a state hook in adapter(U).wire.hooks:
            if owned(read <home>/.config/<U>/config.d/awkit.yaml): exit 20 duplicate_state_hooks
    d = open_config_d(TOOL); old = read awkit.yaml via openat(O_NOFOLLOW) or None
    if old is not None and not owned(old): exit 20 drop_in_foreign
    if old == text: exit 0, outcome unchanged                    # no audit record
    if --dry-run: print {tool, dry_run: true, outcome: wired|replaced, files[text]}; exit 0
    if run(check).exit not in check.ok_exits: exit 12 tool_unavailable ("<tool>'s check fails before wiring")
    confirm: human present -> "y" on /dev/tty; else --yes; else exit 13 human_required
    audit attempted {target: path, before_sha256: sha(old) or null, after_sha256: sha(text)}
    write TEMP in d (O_CREAT|O_EXCL|O_NOFOLLOW, 0600), fsync, renameat(TEMP, "awkit.yaml"), fsync d
    if run(check).exit not in check.ok_exits:
        restore: old is None -> unlinkat("awkit.yaml") else write old through a new TEMP and renameat
        audit outcome {outcome: failed, code: unavailable}; exit 12 unavailable wire_rejected
    audit outcome {outcome: done}; exit 0, outcome wired (old None) or replaced
    on any error after TEMP was created: unlinkat(TEMP)
unwire TOOL [--yes] [--dry-run]:
    same lock and directory steps; absent file -> unchanged; not owned -> exit 20 drop_in_foreign
    --dry-run prints outcome removed; confirm; audit attempted; unlinkat("awkit.yaml"), fsync d; audit outcome; removed
    no check runs (removing awkit's file cannot add a config error)
```

Hooks the user wrote by hand are not seen by the state-hook rule (documented), which reads adapters and awkit's own drop-ins only.

A hook marked `state: true` may be wired for one tool at a time (`duplicate_state_hooks`); the bundled adapters mark agent-spawn's and claude-session's state hooks. A missing notice-route is `tool_unavailable`. The early-tick hooks (`awkit notify-tick`) arrive with the loop (see Roadmap).

## Doctor

`awkit doctor` runs the checks below and prints each as `ok`, `warn` or `fail` with an `id`, a `tool` (null for a global check), a `reason` and `details`. It is read-only and probe-free: it runs each tool's `validate` as the adapter names it (some tools' `validate` reads the network; ticket-work's calls ticketctl) and the local checks, and it is safe to run from cron or from the dashboard. Per registration state: a `registered` tool gets every per-tool check; an `absent` tool gets `adapter.loaded` and `tool.installed`; a `disabled` tool gets `adapter.loaded` only; an `adapter_invalid` tool gets `adapter.loaded` (fail) only. `--tool T` narrows per-tool checks only; `config.safe`, `cron.daemon`, `env.xdg`, `env.variables` and a crontab-read failure always run. `--probe` also runs each tool's `validate --probe` (named by the adapter), one tool at a time, each with `doctor.probe_timeout`, after listing on stderr the argv it will run (also with `--json`); `probe` is ok on exit 0 and fails otherwise with the exit and the envelope's `code`; it never sends a test message. The result is written to `doctor-last.json` in the state directory (temporary file, `fsync`, rename) for the dashboard badge; on read it is capped at 1 MiB and validated, the badge uses only `ts` and `counts`, and any defect means no badge. Check ids are fixed strings with grammar `^[a-z][a-z0-9_.-]{0,63}$`; override ids are `tool.<tool>.*`.

| Id | Fails when | Warns when | Mechanism |
|---|---|---|---|
| `config.safe` | A config file, drop-in, overlay file or parent fails the ownership rule. | None. | `lstat` walk |
| `adapter.loaded` | An adapter fails to load (the reason names the overlay path). | None. | Loader |
| `tool.installed` | `tools.<tool>.enabled: true` is set explicitly and the program does not resolve. | The program does not resolve (the adapter's `install` command is printed). | Program resolution (details name the first rejected candidate and why) |
| `tool.version` | Never. | The version is below `min_version` or cannot be read (`version_unreadable`). | Version reading (below) |
| `tool.validate` | Per the mapping below. | Per the mapping below. | Adapter `doctor.validate` |
| `cron.daemon` | No `cron` or `crond` process runs. | On WSL, pid 1 is not systemd. | `ps -eo comm`, `/proc/1/comm` |
| `cron.block` | The block is malformed (see Recognizers). | The block is absent for a registered tool that has a `cron` key. | Recognizer only (awkit runs no tool's dry run) |
| `cron.env_file` | `cron.env_file` exists but is not a regular user-owned file, is group or world accessible, a parent fails the ownership rule, or `sh -n` fails. | A name in an adapter's `doctor.env` is not assigned with `export` or under `set -a`. | `lstat` walk, `/bin/sh -n`, name scan (values never read into output; the tools that read an env file from their own config check it in their own `validate`) |
| `env.xdg` | None. | `XDG_CONFIG_HOME`, `XDG_STATE_HOME` or `XDG_DATA_HOME` is set to anything other than `<home>/.config`, `<home>/.local/state`, `<home>/.local/share`, because tools then use other directories than awkit reads (audit paths) and writes (drop-ins), and `cron install` does not pass them to installers, so cron jobs use the default directories. Also when `HOME` differs from the password-database home (tools resolve `~` from `HOME`). | Environment |
| `env.variables` | None. | A name in an adapter's `doctor.env` is set neither in awkit's environment nor in the env file. | Name scan |
| `sandbox.tools` | None. | `bwrap` or `socat` needed by a registered tool does not resolve. | Program resolution of the adapter's `doctor.needs` |
| `pair.<id>` | None. | A sibling is below the declared minimum. | The named tool's `tool.version`; skipped when it is not registered |
| `wire.rule` | None. | A wired tool's hook gets no delivering rule from `notice-route test` with the payload `{"tool", "hook"}` (`no_rule`, `rule_drop` or `test_failed`); a rule that needs `repo`, `where` or `labels` cannot match this minimal payload. | `notice-route test --stdin-json --json`, read rules, one call per wired hook |
| `audit.coverage` | None. | A registered tool declares no audit file. | Adapter |
| `probe` | The probe failed. | None. | `--probe` only |
| `tool.<tool>.*` | Per override. | Per override. | `doctor` override |

The `tool.validate` mapping: `doctor.validate` is `{argv, ok_exits: [0], info_exits: [], warnings: <path>?}`. An exit in `ok_exits` is `ok`, or `warn` when the `warnings` path yields a non-empty list; an exit in `info_exits` is `ok` with `reason: info`; any other exit is `fail` with the envelope's `code` (sanitized). A tool with no `validate` has no such check. Normalization beyond this is the `doctor` override operation. The bundled claude-session adapter's `doctor` override reports `claude-session kinds --json`. A notifier whose `validate` exits 12 while `enabled: false` is handled in its adapter (an `info_exits` entry or the `doctor` override).

For `wire.rule`, awkit never interprets notice-route rules: for each registered tool whose drop-in is `owned`, it runs once per hook of the adapter's list `[<notice-route>, "test", "--stdin-json", "--json"]` with stdin `{"tool": "<TOOL>", "hook": "<hook>"}`. The check is `ok` when every hook exits 0 with `reason` null, and `warn` with reason `rule_drop` when a matching rule drops, `no_rule` for exit 22 (the reason notice-route printed is in `details`) and `test_failed` for any other exit.

When the crontab cannot be read (`crontab_failed` or `crontab_unusable`), `doctor` emits one `cron.block` check with `tool: null`, status `fail` and that reason, and no per-tool `cron.block` checks.

Version reading: with `version.package`, awkit reads the first line of the program (at most 512 bytes); when it starts with `#!` and names an absolute interpreter that passes the ownership rule, it runs `[interp, "-I", "-c", "import sys,importlib.metadata as m;print(m.version(sys.argv[1]))", package]` (5 s, read rules). Otherwise, or when that fails, it runs `version.argv` (5 s) and takes the first version-shaped token of stdout, unless it is `0.0.0`. Nothing readable is a `version_unreadable` warning. Versions compare as leading `N.N.N` (missing parts are 0; pre-release and local suffixes are ignored; unparsable is a warning); an installed version below `min_version` is a warning and the tool stays usable. Tags are never read.

Exit 12 `checks_failed` when any check is `fail`.

## Audit

### Reading

`awkit audit` reads each registered tool's public `audit.jsonl` and awkit's own file (source `awkit`, descriptor `phase=attempted` with key `[attempt_id]`; `--tool awkit` selects it) directly (design guide §2, §6). The path comes from the adapter's `audit.path` (default `<home>/.local/state/<tool>/audit.jsonl` under the home directory of the password database; `XDG_STATE_HOME` is ignored, and `doctor` warns when it differs). A line is accepted when it parses as a JSON object with a `ts` that `norm_ts` accepts; every other member is kept as read (sanitized), so tool upgrades never hide records. `awkit audit` reads at most the last 64 MiB of each file (`skipped.truncated` names the tools cut) and the dashboard's first read the last 8 MiB. Lines longer than 1 MiB are skipped and counted in `skipped.lines`, a malformed line is skipped and counted without echoing it, and only LF-terminated lines are consumed (a partial tail stays for the next pass). The dashboard records `(st_dev, st_ino, offset)` per file and rereads from the cap window when the inode changes, the size falls below the offset, or the byte before the offset is no longer an LF (this detects `copytruncate` regrowth). The reader:

```text
CAP_COMMAND = 64 MiB; CAP_FIRST_DASHBOARD_READ = 8 MiB
def read_records(tool, path, cap, st=None):          # st: dashboard (dev, ino, offset) or None
    fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK); s = fstat(fd)    # missing -> nothing
    if not S_ISREG(s.st_mode) or s.st_uid != getuid(): skipped.files += [tool]; return
    if st and (s.st_dev, s.st_ino) == st.id and s.st_size >= st.offset \
          and (st.offset == 0 or pread(fd, 1, st.offset - 1) == b"\n"): start = st.offset
    else:
        start = max(0, s.st_size - cap)
        if start > 0: skipped.truncated += [tool]; start = offset after the first LF at or after start
    for each LF-terminated line from start:            # a partial tail stays for the next pass
        if len(line) > 1 MiB: skipped.lines[tool] += 1; continue
        try: rec = json.loads(line, parse_constant=refuse)
        except (ValueError, RecursionError): skipped.lines[tool] += 1; continue
        if not isinstance(rec, dict) or norm_ts(rec.get("ts")) is None: skipped.lines[tool] += 1; continue
        yield sanitize_tree(rec)
    st.offset = end of the last complete line
sources = [(t, adapter(t).audit) for t in registered tools] + [("awkit", built-in descriptor)]
```

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
    elif att: status = "in_flight" if 0 <= now - ts(att[0]) < 60s else "unknown"      # a future ts is unknown
    else: status = unpaired
    emit entry(tool, key, status, ts=min ts of recs, records=recs)   # any number of records
merge all entries and singles by (normalized ts, tool, file offset of first record)
```

The bundled descriptors, to be confirmed by the verification issue: `phase=attempted` with key `[attempt_id]` (review-watch, review-respond, ticket-create); `result=attempted` with `[attempt_id]` (forgectl, pr-comment, ticket-work) and with `[attempt_id, step]` (ticketctl); `result.status=attempted` (review-run); none for the rest. `--no-pair` prints every record as `single`. Entries have `tool`, `key`, `pairing` (`paired`, `in_flight`, `unknown`, `unpaired` or `single`), `ts` and `records` (one or more).

Filters: `--by A` filters by actor and `--action A` (repeatable) by action. `--pr` and `--ticket` match after normalizing both sides with `pr_norm` and `key_part` (see Links and chains) against the record's `target` string or its `target` object members and the `inputs` string values. `--label` matches records whose target equals the `id` of a row carrying that label in this run's reads (records carry no labels). `--limit` defaults to 200: the newest N entries are printed oldest first. Tools that declare no audit file contribute nothing.

### Own records

awkit appends to `~/.local/state/awkit/audit.jsonl` (schema `schemas/audit.json`) for the actions only it performs: `cron.install`, `cron.uninstall`, `wire` and `unwire`. Fields are `ts`, `phase` (`attempted` or `outcome`), `attempt_id`, `actor`, `actor_source` (`flag`, `tty` or `default`), `stdin_tty`, `action`, `target` (`crontab` or the absolute drop-in path), `inputs` (`tools`, and `before_sha256` and `after_sha256` of the text, never the text) and `result` (`outcome` of `attempted` on the attempted record, and `done`, `failed` or `unknown` on the outcome record; `code`; `unchanged`; per-tool outcomes). There is no `decision_id`. There is one pair per changed file. No record is written for `--dry-run` or for a command whose plan changes nothing (`unchanged`, `nothing_to_wire`); a `cron` command cannot know beforehand, so every non-dry-run cron command writes a pair and the outcome carries `unchanged`. The attempted record is appended (with `fsync`) after planning and before the first change; a failed append stops the command. Readers show an attempted record without an outcome as `unknown`. awkit records no dashboard action: the owning tool's audit, where it has one, is the record (`audit.coverage` lists tools without one).

## Output sanitizing

Every string and every object key that comes from outside awkit (any tool's output, any audit file, cache file, config or adapter string, any tool's version or error text) is sanitized once, where it enters the model and before anything is displayed or printed. The sanitizer allows by Unicode general category; everything else is replaced by a visible marker `<U+XXXX>`:

```text
INVISIBLE = {U+034F, U+115F, U+1160, U+17B4, U+17B5, U+2800, U+3164, U+FFA0}
            | U+180B..U+180F | U+FE00..U+FE0F | U+E0100..U+E01EF
def sanitize(s, limit=None):                   # s already decoded (invalid UTF-8 replaced)
    cut = limit is not None and len(s) > limit
    if limit is not None: s = s[:limit]        # bound the work before the walk
    out, marks, i = [], 3, 0                   # marks == 3: no combining mark may attach here
    while i < len(s):
        ch = s[i]; cat = unicodedata.category(ch)
        if ch == "<" and s[i+1:i+3] == "U+":  out.append("<U+003C>"); marks = 3
        elif ch in INVISIBLE:                  out.append(marker(ch));   marks = 3
        elif cat[0] in "LNPS":                 out.append(ch);           marks = 0
        elif cat[0] == "M" and marks < 3:      out.append(ch);           marks += 1
        elif cat == "Zs":                      out.append(" ");          marks = 0
        else:                                  out.append(marker(ch));   marks = 3
        i += 1
    text = "".join(out)
    if limit is not None and (cut or len(text) > limit): text = text[:limit-1] + "…"
    return text
marker(ch) = f"<U+{ord(ch):04X}>"; limits: title 200, other strings 1000; dialog bodies: no limit (64 KiB cap)
```

Cc, Cf, Cs (lone surrogates), Co, Cn, Zl, Zp and everything not listed are replaced; LF and TAB are replaced like other controls, because there is no multi-line field in 0.x outputs (the wire `text` is awkit's own generated text, not tool text). The output encoding never raises, because no surrogate survives. Ids are grammar-checked before sanitizing and pass unchanged; the badge reads only `ts` and `counts` of `doctor-last.json`, so no cached string is shown and nothing is sanitized twice. A test checks that the input `<U+202E>` never appears in output and that no combining mark follows a marker. This applies to every string, not only the fields a schema marks `x-untrusted`.

The dashboard never interprets markup in displayed text. No string from a tool, adapter, config, cache file or audit file is parsed as markup: every string reaches Textual only as a `Text` or `Content` object built by one helper, including cells, list items, the detail pane, the dialog, the status line, border titles and subtitles, tab and column labels, the header title, tooltips and notifications (`notify` with `markup=False`). Each row render is wrapped so an exception renders a marker row (`<render error>`) instead of ending the app. A test runs a corpus of hostile strings (including markup, every control character and every code point) through every view and every `--json` output. A test walks every widget of every view with the hostile corpus, and a lint check refuses a `str` passed positionally to a Textual constructor in `tui/`.

## Configuration

`~/.config/awkit/config.yaml`, `~/.config/awkit/config.d/*.yaml` (lexical order, maps merged, lists replaced; at most 64 drop-ins) and the overlay `~/.config/awkit/adapters/` (at most 128 adapters) are read only under the home directory of the password database. `XDG_CONFIG_HOME` and every environment variable that would name a path or a command are ignored. A config file, drop-in, adapter file or any of their parent directories that is a symlink, is not owned by the user, or is group- or world-writable is refused (`config_unsafe`, exit 20, naming the path). One strict loader reads config, drop-ins and adapters: a PyYAML `SafeLoader` subclass that refuses anchors, aliases, tags other than the core schema, duplicate keys, NUL and lone surrogates; at most 1 MiB per file, at most 16 MiB in total across config, drop-ins and adapters, and at most 100,000 YAML nodes per file (a nesting that exhausts recursion is `config_invalid`); files are opened with `O_NOFOLLOW` and checked with `fstat` on the descriptor, and parents are walked by descriptor. `--config PATH` exists only on `validate`, which runs nothing: it loads that file plus its sibling `config.d/` and the default overlay, applies the same ownership checks and reports (does not exempt) a failure. Unknown keys and invalid values fail fast naming the key. Every key whose default is "none" accepts `null`. A `tools.<tool>` entry for a tool with no adapter is a `validate` warning and ignored at runtime. Schema: `schemas/config.json`; every key is documented in `config.example.yaml`. The schemas anchor every pattern with `(?![\s\S])` so a trailing line feed never matches; the Pydantic models use `regex_engine="python-re"`, because that look-ahead needs it (the default engine cannot build it), the trailing-line-feed negative test stays for every pattern, and the anchor is never replaced with `$`.

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
| `cron.env_file` | none | A user-owned file (safe-value grammar) passed to the tools whose installer takes an env file (in the bundled adapters agent-spawn and wtctl). |
| `cron.path_extra` | `[]` | Absolute directories (safe-value grammar) searched for tool programs after `~/.local/bin`, and placed in the same position of the installers' `PATH`. |
| `cron.intervals.<tool>` | the tool's own | A string of the interval grammar (below) or an integer from 1 to 99999, passed verbatim to the tool's `interval_flag`; the tool validates it. |
| `cron.options.<tool>` | `[]` | Option names (grammar `^[a-z][a-z0-9_-]{0,31}$`) that the adapter maps; an unmapped name is `config_invalid`. |
| `doctor.probe_timeout` | `60s` | The timeout of one probe. |

There are no `repos:` and no `hooks:` keys in 0.x.

**Interval grammar.** A `cron.intervals.<tool>` string matches the pattern below: its first character is never `-` and single spaces separate words; it is passed as one argv element, so it cannot add a flag.

```text
^(?!-)[A-Za-z0-9*/,-]{1,32}(?: [A-Za-z0-9*/,-]{1,32}){0,6}$
```

**Safe values.** Every path awkit writes into a drop-in `cmd` or passes to a tool's installer must match `^/[A-Za-z0-9._+@/-]{0,4095}$`, with no `//` and no `..` segment (schema def `safe_path`). Values failing it are refused at load (`validate` and every command; exit 2 `config_invalid` naming the key) for `tools.<tool>.bin`, `cron.env_file` and `cron.path_extra`, and at write time (exit 20 `unsafe_value`) for resolved programs and the home directory.

### Program resolution

awkit never searches the process `PATH`. A tool program is `tools.<tool>.bin` (absolute) or the first match of the adapter's `bin` in `<home>/.local/bin`, each `cron.path_extra` entry, `/usr/local/bin`, `/usr/bin` and `/bin`. Helper programs (`crontab`, `tmux`, `sh`, `bwrap`, `socat`, `ps`) come from `/usr/local/bin`, `/usr/bin`, `/bin`, `/usr/sbin` and `/sbin`. A candidate is accepted only when it is a regular file (after following symlinks) with `X_OK`, and the file and every directory from it up to `/` (for both the link and its target) are owned by the user or root and not group- or world-writable. The path awkit passes or writes is the unresolved candidate path (symlinks kept). When no candidate is accepted the program is unresolved (see Registration); a tool installed elsewhere needs `tools.<tool>.bin`.

## Environment variables

Only `AWKIT_DASHBOARD__REFRESH`, `AWKIT_DASHBOARD__CONCURRENCY` and `AWKIT_DASHBOARD__READ_TIMEOUT` override config keys; an environment variable wins over the config file and is validated by the same schema (failure exits 2 `config_invalid` naming the variable). awkit reads `TMUX` (for `W`) and `HOME`-derived paths from the password database, not from `HOME`. Reads, actions, `validate` and checks run with the inherited environment, so the credentials the tools name in their own configs are available to them; cron installers run with the constructed environment of Cron. awkit adds no variable and never prints one.

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
| `~/.local/state/awkit/wire.lock` | The `flock` file of `wire` and `unwire`. |
| `~/.config/<tool>/config.d/awkit.yaml` | A drop-in written by `wire`; its first line carries the hash of the rest. |
| `schemas/defs.json` | Shared schema definitions of the awkit repo (`schemas/config.json` repeats the ones it needs, so it is self-contained). |

There is no `log.jsonl` and no `schemas/log.json` in 0.x (a recorded deviation from the design guide).

## Concurrency

Reads, `attention`, `chains`, `audit`, `validate` and `adapters` keep no locks and can run any number of times at once. `cron install|uninstall` takes the exclusive `cron.lock` and `wire` and `unwire` take `wire.lock`, each without waiting. `wire` and `unwire` replace one file by rename. Two dashboards may run at once.

## Dependencies

| Tool | Binding | Use |
|---|---|---|
| every registered tool | C | The adapter's reads and actions, by CLI and `--json` only. |
| notice-route | C | The destination of `wire`d hooks. |
| `crontab`, a cron daemon | third-party | `cron` (through each tool's own installer), `doctor`. |
| tmux | third-party, optional | `W`. |

awkit imports no tool and reads no tool's `state.db`. The `tui` extra is Textual `>=8.2,<9`. The core uses the standard library, PyYAML (strict loader) and Pydantic (design guide §3).

## Roadmap

Reserved for 1.x and not implemented in 0.x: `awkit tick`, `awkit run`, `awkit notify-tick [--source TOOL]`, `awkit reconcile`, the rules engine with its write-ahead action ledger, the state graph on disk, `repos:` and `hooks:` config keys, link re-verification and the `forge` tag, reading child TUI result files and acting on their intents, the early-tick hooks of `wire`, hook-only attention reasons, notification selectors for state hooks, cross-tool audit correlation, and dashboard actions with human-written text, a second object, multi-select or escalation-scope continuation. The constraints the architecture already fixes (architecture §7.2 to §7.5) apply to them. `design.md` lists the open items.

## Upgrades

An adapter's `min_version` is a floor, not a pin. A tool below it is reported by `doctor` (`tool.version`) and stays usable at the user's risk. A tool newer than the adapter's design is read as usual; a row field that vanished marks the tool stale or partial, never the whole dashboard. The first implementation issue is a verification pass over every tool's current interface that updates the adapters.

## Residual risks

- A process of the same user can write the config, the overlay and the audit files; awkit refuses files other users could write but cannot defend against its own user.
- Labels are not authenticated; the views dim label and branch links, and in 0.x no link-derived value ever enters an argv, but a record that lies in the owning tool is out of scope.
- Each tool's own `cron install` rewrites the crontab with its own small window against a hand edit or another installer; awkit's lock serializes only awkit runs. A hand edit in `crontab -e` that started before an install and is saved after it overwrites what the installers wrote. A `PATH=` line written by gatectl, notice-route, pr-watch, review-watch or ticket-queue applies to every later crontab line; under awkit's installer environment it holds only the program search list.
- awkit relies on each tool honoring `--dry-run`; a tool version that ignored it would act at dry-run time. The dialog's grammars are injection boundaries, not validation: a wrong-length hash is refused by the tool and the status line shows it.
- Adapter regexes (`start.regex`, `branches.pattern`) and overlay files are trusted config like the rest of the overlay.
- `--actor human:<user>` is a claim: a same-user process can make it. The audit record shows how the claim was made.
- A trusted agent that can reach the user's tmux server can send keys to the dashboard and confirm a dialog. Run the dashboard in its own tmux server or a plain terminal; the dialog is not a boundary against it.
- `PYTHONPATH` and similar variables still affect awkit's own imports (overrides are isolated in child processes). Tools installed outside the program search list need `tools.<tool>.bin`.
- The sanitizer cannot make a terminal safe against a bug in the terminal itself.
- `doctor` is advice and not a security boundary.

## Platform notes

Linux and WSL (Ubuntu) are supported in 0.x. On any other platform every command except `validate` and `adapters` exits 20 `unsupported_platform`; macOS is not supported because awkit is not in the architecture's macOS list. On WSL the cron daemon must be running (`doctor` checks), a long-lived tmux or cron environment can hold a stale interop socket, and the Windows filesystem under `/mnt/c` is not used for state. Outside tmux everything works except `W`.
