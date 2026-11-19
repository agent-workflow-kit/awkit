# awkit: interface

Status: 0.1.0-design (2026-11-19). This document is the single normative source for awkit's rules. `design.md`, the README and the architecture link to its headings and never restate its tables. Section references (architecture §N, design guide §N) point to `../awkit-docs/architecture.md` and `../awkit-docs/design-guide.md`.

awkit is the harness (layer 4, architecture §7): the optional tool that knows the others only through configuration and adapters. Release 0.x is stateless apart from its own audit file and one small cache: it reads every tool through its documented CLI and `--json` output, shows what needs the user in a dashboard, checks the installation, writes the cron blocks and the notification wiring, and merges the tools' audit files into one timeline. The tick loop, the rules engine, the action ledger and the state graph on disk are 1.x (see Roadmap). Every other tool works without awkit, and awkit works with whatever subset of tools is registered.

## Overview

- **Tool.** A registered program with one adapter. Ours and third-party tools are treated the same.
- **Adapter.** One YAML file per tool that tells awkit how to run the tool, read its output, find its attention items and links, run its actions, write its cron block, find its audit file and check it (see Adapters). Bundled adapters ship in the awkit repo; an overlay directory adds or replaces them.
- **Read.** A named, read-only command of an adapter whose `--json` output is mapped into the model by the path language.
- **Attention item.** One entry of the Attention list: something that needs the user, derived by awkit from reads. Tools never create attention items.
- **Link and chain.** A link joins two objects of different tools; a chain is a ticket, agent, pull request and review linked in a row. Every link carries a source tag (see Links and chains).
- **Action.** A named operation on an object that runs the owning tool's own CLI after the confirmation recipe of its adapter (see Actions).
- **Block.** The tagged crontab block of one tool (see Cron).
- **Check.** One result line of `doctor`.
- **Human present.** Exactly when `/dev/tty` opens for reading and writing. No other test is used.

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
awkit audit [--tool T]... [--pr PR] [--ticket KEY] [--label K=V]... [--actor A] [--since DUR|TS] [--until TS] [--limit N] [--no-pair]
awkit validate [--config PATH]
awkit adapters list
awkit adapters show TOOL
```

`awkit` with no arguments is `awkit dashboard`; `browse` is the same command under the guide's name for a TUI (a recorded deviation: the guide's `<tool> browse` is also accepted). A `TOOL` or `--tool` value is a tool name from the registry (grammar `^[a-z][a-z0-9-]{0,31}$`); an unknown one exits 10. `ID` for `--focus` is `<tool>:<object>` with a tool name and an object id as that tool prints it (see Links and chains). `--pr` is a pull request URL or `host/<full project path>#N`; `--ticket` is `site:KEY` or a bare key when one site is configured; `--label` is `key=value` in the label grammar; `--since` is a duration of the design guide's grammar or an RFC 3339 timestamp. A value that does not match exits 2 `invalid_argument`. `--tool` repeats and ORs; different filters AND.

`attention` and `chains` print what the Attention and Chains tabs show (design guide §10: every TUI action is also a command). `audit` prints the Timeline. `adapters list` prints each loaded adapter with its source (`bundled` or `overlay`), tool, `min_version` and load status; `adapters show` prints one adapter after loading, with the effective values. `validate` loads the config, the drop-ins and every adapter and checks them against the schemas without running any tool; it is the one command that accepts `--config` (see Configuration).

### Global flags

`--json`, `--verbose`, `--quiet`, `--version`, `--dry-run` where the command lists it, `--yes` where it lists it, and `--actor STRING` (grammar `^(human|auto):[A-Za-z0-9._@-]{1,64}$`; the default is `human:<user>` when a human is present, else `auto:unknown`, where `<user>` is `me.name` fitted to the grammar: other characters become `_` and the name is cut to 64 characters). Global flags go after the subcommand. There is no `--config` except on `validate`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success. `doctor` exits 0 when no check failed, even with warnings. `cron` and `wire` exit 0 for `unchanged`. |
| 1 | Unexpected internal error. |
| 2 | Usage error (`invalid_argument`, `missing_option`, or an invalid config found by `validate`). |
| 10 | Not found: an unknown tool, object or adapter. |
| 12 | Expected failure. `doctor` found a failed check (`checks_failed`); a lock is held (`unavailable` with `reason: locked`); a tool the command needs is not installed or answered badly (`tool_unavailable`). |
| 13 | A human is needed: `dashboard` or an action that needs a terminal has none, or `wire` without `--yes` has no human present. |
| 20 | Refused with a `reason` (see below). |
| 21 | Ambiguous selector (`details.candidates`). |

Reasons of exit 20: `config_unsafe` (a config, drop-in, adapter or parent directory that is a symlink, not owned by the user, or group- or world-writable), `adapter_invalid`, `malformed_block` (the crontab holds a block without a matching end line where its grammar needs one, a duplicate or an interleaved block), `drop_in_foreign` (the drop-in exists and lacks awkit's first-line marker), `duplicate_state_hooks` (wiring both agent-spawn's and claude-session's state hooks to notifications), `stale_object` (an action's confirmation facts no longer match the object), `link_unverified` (a link could not be confirmed against its authoritative source), `unsupported_platform`. Codes 22 and above are not used in 0.x. Codes 14 to 19 never occur (awkit waits on no session); a child's exit code is reported in the result and never passed through as awkit's own.

## Output by exit code and error envelope

With `--json`, exit 0 prints the result object of the command (member names are those of `schemas/cli/`). Exit 12 from `doctor` prints the same document as exit 0. Every other non-zero exit prints the envelope `{"error": {"code": "<exit-name>", "message": "...", "reason": "...", "details": {...}}}` on stdout and the message on stderr. `reason` is present for exit 20 and the `reason` of exit 12 where the table above names one. Strings that came from a tool are sanitized (see Output sanitizing) in every output.

## Adapters

An adapter is one YAML file `<tool>.yaml` validated by `schemas/adapter.json`. Bundled adapters live in the repo's `adapters/` directory and are read-only data. The overlay directory is `~/.config/awkit/adapters/` under the home directory of the password database (see Configuration). An overlay file with the same `tool` replaces the bundled adapter wholesale; there is no merging. A file that fails to load excludes only its tool: `doctor` reports `adapter.loaded` failed and the other tools keep working.

### Adapter file

| Key | Meaning |
|---|---|
| `tool` | Tool name (the registry key). |
| `binding` | `C` for every adapter (architecture §3.3). |
| `bin` | Default program name; `tools.<tool>.bin` overrides it with an absolute path. |
| `install` | The install command `doctor` prints for a missing tool. |
| `min_version` | The lowest tool version the adapter was written against. |
| `version` | How to read the installed version: `package: <distribution name>` (package metadata) or `argv` of a command that prints it. Package metadata is the default because `--version` is not reliable for every tool. |
| `reads` | Named reads (see Reads). |
| `attention` | Rules that turn reads into Attention items (see Attention). |
| `links` | Label keys and branch patterns that join objects (see Links and chains). |
| `actions` | Actions (see Actions). |
| `periodic` | Cron entries with their block grammar (see Cron). |
| `audit` | The tool's audit file and schema (see Audit). |
| `doctor` | The tool's own `validate` argv and extra checks (see Doctor). |
| `wire` | Hooks to route to notifications (see Wire). |
| `overrides` | Escape hatches (see Escape hatches). |

### Reads

Each read has an `argv` list, `json: true` when the tool prints `--json`, an optional `timeout` (default `dashboard.read_timeout`), and a `map` from the tool's output into model fields with the path language. A read runs with the inherited environment, no standard input, in a new session, and never with a terminal. A read that exits non-zero, exceeds its timeout, prints invalid JSON, or lacks a mapped required field marks the tool stale for that refresh; the previous mapped data stays on screen with its age. Output larger than 8 MiB is a read failure.

### Path language

Paths are small and total: they either produce a value or a typed error naming the adapter file and the path. They are evaluated by awkit itself with no external program.

| Form | Meaning |
|---|---|
| `a.b.c` | Object member access. A missing member yields `null`. |
| `a[*]` | Every element of an array. |
| `a[?field=value]` | Elements whose member `field` equals the string or number `value`. One equality filter per step; `!=` is also accepted. |
| `a[0]` | One element by index. |
| `a.b[*].c` | Steps compose; arrays flatten one level per `[*]`. |

There are no functions, arithmetic or regular expressions. Whatever this language cannot express is done by a Python or executable override (see Escape hatches). A path that selects nothing yields an empty list or `null`, never an error.

### Templates and argv rules

Commands are argv lists, never shell strings, and awkit never runs a shell for an adapter command. Placeholders have the form `{name}` and are filled in one pass from declared parameters only. A value is checked against its parameter's closed grammar before it is substituted (object ids, repo ids, pull request ids, ticket keys, hashes and enums have fixed grammars); a value that does not match refuses the call. Text that came from a tool, a ticket, a pull request or an agent is never placed in an argv or an environment value; it travels only in files or on standard input.

### Escape hatches

Any single operation, or a whole adapter, can be replaced. `python: module:function` names a function in an importable module; `exec: <absolute path>` names an executable. An executable speaks JSON on standard input and output under the protocol `awkit-adapter/1`, whose request is `{"protocol": "awkit-adapter/1", "operation": "read|attention|links|action", "adapter": "<tool>", "params": {...}}` and whose reply is `{"ok": true, "result": {...}}` or `{"ok": false, "error": {"code": "...", "message": "..."}}`. The protocol belongs to awkit; tools never see it. An override runs under the read rules above. Overrides are loaded only from files that pass the ownership rules of Configuration.

## Attention and chains

### Attention

An attention rule has `read` (the read it uses), `where` (an optional path filter), `reason`, `severity` (`info`, `action` or `error`), `id` and `title` paths, and an optional `since` path. An Attention item has the members `id` (`<tool>:<reason>:<object>`), `tool`, `reason`, `severity`, `title` (sanitized), `object`, `since`, `links` and `actions`. The list is ordered by severity (`error`, `action`, `info`), then `since` ascending, then `id`. Idle sessions are never items. Items disappear when their read stops producing them.

The bundled adapters derive items from these sources (the first release builds them from each tool's interface at the time; `design.md` lists the verification issue):

| Tool | Source | Reasons |
|---|---|---|
| agent-spawn | `list --needs-attention` | `unreported`, `escalated`, `blocked`, `failed`, `timeout`, `lost`, `launch_failed`, `session_missing` |
| claude-session | sessions in `needs-input` | `needs_input` |
| jobsctl | held and failed jobs | `held`, `job_failed` |
| review-watch | drafts awaiting accept, `post-attention` reasons | `draft_awaiting_accept`, `escalated`, `stale`, `failed`, `round_limit`, `daily_limit`, `poll_failed`, `submit_failed`, `post_failed` |
| ticket-work, review-respond | `pending`, attention list | `pending_confirmation`, `attention` |
| ticket-queue | `boards`, `claims`, `list --skipped --query "failures > 0"` | `board_status`, `claim_state`, `skipped_failures` |
| ticket-create | drafts in `ready`, orphaned `drafting` rows | `ready_to_create`, `orphan` |
| gatectl | policies that dropped to shadow | `policy_shadowed` |
| notice-route | `validate` warnings (`flush_stale`) | `flush_stale` |

### Links and chains

Nodes are tickets, worktrees, agents, tmux windows, jobs, pull requests, review drafts, gate decisions and notifications. Edges come from labels on lower-tool objects (`ticket`, `pr`, `repo`, `kind`, `owner`, `job`, `rw-item`, `draft`, `consumer`) and from branch names, as the adapters' `links` declare. Each link has a source tag:

| Tag | Meaning |
|---|---|
| `record` | A tool's own stored id for the other object (for example a pull request id a workflow stored). |
| `forge` | Confirmed through the authoritative source (the forge or the ticket system) during this refresh. |
| `branch` | Derived from a branch name that matches an adapter pattern. |
| `label` | Derived from a label only. |

Labels are not authenticated against processes of the same user. The views show `branch` and `label` links dimmed, and `chains --json` prints the tag of every link. An action marked `reverify` in its adapter first re-checks every link it uses against the authoritative source (`record` and `forge` links count as verified) and refuses with exit 20 `link_unverified` when it cannot. A link is never the only basis of a teardown, a merge-related step, the resume of a tainted session or an accept.

## Dashboard

`awkit dashboard` needs a terminal and the optional `tui` extra (Textual `>=8.2,<9`); without a terminal it exits 13, without the extra it exits 12 `tool_unavailable` with the install command. The core never imports Textual.

### Views and keys

Three tabs: Attention (the default), Chains and Timeline (recent records of the merged audit). The header shows the tool name, the badge (the result of the last `doctor` from its cache file, with its age) and one stale marker per tool whose last read failed, with the age of its data. The footer shows key hints and the status line shows the last action's result. A detail pane shows the selected item. A selection stays on the same item across refreshes. Every view has explicit empty and error states, respects the terminal's colors and never hard-codes backgrounds.

| Key | Action |
|---|---|
| `1`, `2`, `3` | Switch tab. |
| `enter` | Open the selected object in its owning tool's own TUI as a child (see Terminal handoff), with `--focus`. |
| `a` | Actions menu for the selected item (see Actions). |
| `W` | Open the same child in a new tmux window when `$TMUX` is set. |
| `d` | Run `doctor` and update the badge. |
| `r` | Refresh now. |
| `/` | Filter the current tab by text. |
| `?` | Help. |
| `q` | Quit. |

### Refresh

One worker refreshes all tools: reads run concurrently under a semaphore of `dashboard.concurrency` (default 8), the whole cycle runs every `dashboard.refresh` (default 15 s) and never overlaps itself, and a manual refresh joins the running cycle. One slow tool delays only itself. The Timeline reads audit files by byte offset (see Audit).

### Terminal handoff

A child that needs the terminal (a tool's TUI, `ticket-create create`, an interactive agent session) runs with the dashboard suspended in the same terminal: the dashboard ignores SIGINT for the child's lifetime, forwards SIGTERM and SIGHUP to the child's process group, discards pending typeahead on the terminal before the child starts and again after it exits, restores the terminal state it saved, and then redraws. A child whose output awkit captures runs in a new session with standard input from `/dev/null`, so it can never read the dashboard's terminal. The dashboard installs a handler for SIGTERM and SIGHUP that restores the terminal before exiting. A child launched with `W` runs in a new tmux window and never touches the dashboard's terminal; awkit passes the window the argv and no untrusted text, and does not wait.

### Result file

With `--result-file PATH`, `awkit browse` writes `{"intent": "open|back", "selected": [{"tool": "...", "object": "..."}]}` on exit 0, written to a temporary file in the same directory, synced and renamed, with mode 0600. It writes nothing otherwise and never reads a pre-existing file. The caller removes a stale file before launching.

## Actions

An action is an entry of an adapter's `actions` with `id`, `label`, `applies_to` (a reason or object kind), `argv` (a template), `destructive` (true when it ends work or leaves the machine), `reverify`, and one of:

- **A recipe**: `dry_run` (an argv that makes no change and prints the plan), `show` (paths into the dry-run result to display), `pass` (flags and the dry-run fields passed back, such as a plan hash, an expected head, an expected base or a content hash), and `yes: true` when the tool takes `--yes`.
- **`terminal: true`**: no dialog; awkit hands the terminal to the tool (see Terminal handoff) and the tool asks the human itself. This is the only form for a command without `--yes`, including `ticket-create create`.

For a recipe, awkit runs the dry run, shows the sanitized `show` fields in its own dialog, waits for an explicit `y`, then runs the real command with `--yes --actor human:<user>` (the user fitted to the tool's own character set where the adapter says so) and the passed fields. If the real command refuses because the facts moved (a tool's own exit 20), awkit shows its `reason` and does nothing else. awkit never passes `--force`, `--allow-tainted`, `--override-escalation`, an enforced-state change or any other flag the architecture reserves to a human unless the adapter's action is that very human operation and the dialog names it (architecture §12.4); the bundled adapters define such actions only where the architecture lists the dashboard as the path (taint override, escalation override, `wtctl baseline accept`, `gatectl` enforcement). `--yes` never overrides a refusal (exit 20). An action never runs from a read, and nothing is run by a rule in 0.x.

## Cron

`awkit cron install` writes one block per tool into the user's crontab from the `periodic` entries of the adapters of the tools it covers (all registered tools unless `--tool` narrows it); `uninstall` removes them. There is no hard-coded list. A tool's own `cron install` writes the same block, so either replaces the other's.

### Block grammar

Each `periodic` entry belongs to one block per tool, declared by `block`: `first_line` (the exact first line, e.g. `# <tool> managed ...`), `end_line` (the exact last line, or `null` for a tool whose block has none, which the architecture exempts for jobsctl), `match` (`exact`, `prefix` or `regex`: how a start line is recognized), `strict` (when true, a block that differs from the template in any line is `replaced`, and an uninstall refuses foreign lines inside the block), and `lines` (templates for the schedule and command lines). The line templates take `{minute}`, `{bin}` (the absolute path of the tool, from `tools.<tool>.bin` or the filtered `PATH` at install time), `{path}` (the `PATH` the cron line carries: the user's `.local/bin`, `cron.path_extra` and the system directories, built from the password-database home), `{env_prefix}` (`set -a && . '<env_file>' && set +a && ` when `cron.env_file` is set and the entry says `env_file: true`, else empty) and the entry's own parameters. Every template is pinned by a golden file copied unchanged from the owning tool's `schemas/`; a test fails when the output differs by one byte.

Matching is per tool. An end line is tested before a start line, because a loose start rule can also match an end line. A line that merely contains a tag in a comment is not a block. A block with no end line where the grammar requires one, a second block of one tool, and interleaved blocks are `malformed`.

### Install order

1. Take an exclusive `flock` on `cron.lock` in the state directory; a held lock exits 12 `unavailable` with `reason: locked`.
2. Read the crontab (`crontab -l`; no crontab yet is an empty one), parse it into foreign lines and blocks, and compute the plan.
3. For each tool: `installed` (no block yet; appended at the end in registry order), `replaced` (a block that differs; replaced in place), `unchanged`, or `malformed` (exit 20, nothing written).
4. Re-read the crontab and compare it with step 2. If it differs, restart from step 2 (at most 3 times, then exit 12 `locked`).
5. Write the whole table with `crontab -`, read it back and compare with the intended text.

Foreign lines are preserved byte for byte, including CRLF endings, a missing final newline and non-UTF-8 bytes. `--dry-run` prints the per-tool outcome and the unified text change and writes nothing. `uninstall` reports `removed` or `unchanged` per tool. Both write one pair of audit records per command (see Audit). The step between 4 and 5 leaves a window of about 30 ms in which a tool's own `cron install` or a hand edit (neither uses awkit's lock) can be overwritten (see Residual risks).

### Line rules

A written line is at most 1000 bytes. A `%` in a command is written as `\%`. The `PATH` and `XDG_*` variables a tool's block sets as separate lines are written as that tool's grammar says, and `doctor` warns about them because a variable line also applies to every later line of the crontab; inline variables are used where the tool's grammar allows them.

## Wire

`awkit wire TOOL` writes the notification wiring for one tool: the drop-in `~/.config/<TOOL>/config.d/awkit.yaml` under the home directory of the password database. Its first line is `# awkit managed`, and it holds only `hooks:` entries (design guide §5, §8) that run `notice-route send --source <TOOL> --stdin-json` for the hooks the adapter's `wire` lists (for example `post-attention`, `post-pending`, `post-escalate`, `post-fail`), each with `async: true`. A tool whose adapter lists none (memoctl, ticket-create, review-respond) exits 0 with `nothing_to_wire`. It also writes the notice-route rule drop-in the adapter of notice-route provides. awkit never edits a `config.yaml` or any other file of a tool.

`wire` shows the exact drop-in text and applies it after confirmation: a human present answers `y`, or `--yes` skips the question (exit 13 when neither a human is present nor `--yes` is given). Outcomes are `wired`, `replaced`, `unchanged`, `removed` (for `unwire`) and `nothing_to_wire`. A drop-in that exists without the first-line marker is `drop_in_foreign` (exit 20): awkit never overwrites a file it did not write. Wiring both agent-spawn's and claude-session's state hooks to notifications is `duplicate_state_hooks` (exit 20). The file is written to a temporary file in the same directory, synced and renamed, mode 0600, after the ownership checks of Configuration on the directory.

The early-tick hooks (`awkit notify-tick`) arrive with the loop (see Roadmap).

## Doctor

`awkit doctor` runs the checks below and prints each as `ok`, `warn` or `fail` with an id, a `reason` and `details`. It is offline and read-only: it runs only each tool's offline `validate --json` and the local checks, never a probe, and it is safe to run from cron or from the dashboard. `--probe` also runs each tool's `validate --probe` (named by the adapter), one tool at a time, each with `doctor.probe_timeout`, after printing what it will call; it never sends a test message. The result is written to `doctor-last.json` in the state directory (atomically) for the dashboard badge.

| Id | Checks |
|---|---|
| `config.safe` | The config, drop-ins, overlay and their parents pass the ownership rules; `XDG_CONFIG_HOME` that differs from the home is a warning. |
| `adapter.loaded` | Every adapter loads and validates. |
| `tool.installed` | The tool resolves (an absolute `bin`, or a name on a filtered `PATH`) and answers; a missing tool prints the adapter's `install` command. |
| `tool.version` | The installed version (package metadata or tag) is at least `min_version`. |
| `tool.validate` | The tool's own offline `validate --json` reports no failure; its warnings are warnings. |
| `cron.daemon` | A cron daemon is running (a read-only process check; on WSL also whether the service is enabled). |
| `cron.block` | Each expected block is present and current (`unchanged`), absent (`installed` would write it) or malformed. |
| `cron.path` | Every `{bin}` is absolute, exists and is executable in a safe directory; the cron `PATH` holds each sibling tool's directory; a shim directory of a version manager (fnm, nvm) is flagged. |
| `cron.env_file` | The env file exists, is a regular file with mode 0600 owned by the user, not a symlink, parses as POSIX sh (`sh -n`), and holds each variable name the adapters list. |
| `cron.lines` | No line is over 1000 bytes; `%` is escaped; variable lines that leak into later entries are warned. |
| `env.variables` | Variables the adapters require are set in a non-interactive shell. |
| `sandbox.tools` | `bwrap` (usable with user namespaces) and `socat` where a registered tool needs them; the effective kind profiles of `claude-session kinds --json`. |
| `pair.<rule>` | Sibling rules the adapters declare (for example a tool needs a sibling at a minimum version; a sandboxed profile must not allow a notifier send). |
| `audit.coverage` | Tools that write no audit file, so the Timeline has nothing from them. |
| `probe.<tool>` | Only with `--probe`: the tool's live check. |

Exit 12 `checks_failed` when any check is `fail`.

## Audit

### Reading

`awkit audit` reads each registered tool's public `audit.jsonl` directly (design guide §2, §6). The path comes from the adapter's `audit.path` (default `~/.local/state/<tool>/audit.jsonl` under the home directory of the password database; the tool's own state-directory rules apply) and each line is validated against the schema the adapter names. A missing file contributes nothing; a malformed line is skipped and counted. The dashboard keeps a byte offset per file in memory and reads only appended bytes; a file that shrinks is read again from the start. Records are merged by `ts`. A record that has an `attempt_id` is paired with the other record sharing it (`attempted` and its outcome); an `attempted` record with no outcome is shown as `unknown` and stands alone. `--no-pair` prints records unpaired. `--pr` and `--ticket` match a record's `target` and `inputs`; `--label` joins a record's target to the objects the adapters read (records carry no labels). Tools that write no audit file (pr-watch, ticket-queue, the notifiers, notice-route, memoctl) contribute nothing.

### Own records

awkit appends to `~/.local/state/awkit/audit.jsonl` (schema `schemas/audit.json`) for the actions only it performs: `cron.install`, `cron.uninstall`, `wire` and `unwire`. Each command writes an `attempted` record before it changes anything and an outcome record after, sharing an `attempt_id`; a failed first append stops the command before any change. Fields are `ts`, `actor`, `action`, `target` (the crontab or the drop-in path), `inputs` (the tools and the `before_sha256` and `after_sha256` of the text, never the text), `decision_id` (absent) and `result`. Dashboard actions write no awkit record: the owning tool records them with `actor_source` and `stdin_tty` showing they came from the dashboard.

## Output sanitizing

Every string that comes out of any tool's output, any audit file or any tool's version or error text is sanitized once, where it enters the model and before anything is displayed or printed: C0 and C1 control characters, escape sequences, bidirectional overrides, zero-width and format characters, tag characters and other invisible code points are replaced with a visible marker of the form `<U+XXXX>`, invalid UTF-8 is replaced, and each field is cut at a per-field limit (title 200 code points, other strings 1000) with a visible ellipsis. This applies to every string, not only the fields a schema marks `x-untrusted`. A test runs a corpus of hostile strings through every view and every `--json` output.

## Configuration

`~/.config/awkit/config.yaml`, `~/.config/awkit/config.d/*.yaml` (lexical order, maps merged, lists replaced) and the overlay `~/.config/awkit/adapters/` are read only under the home directory of the password database. `XDG_CONFIG_HOME` and every environment variable that would name a path or a command are ignored. A config file, drop-in, adapter file or any of their parent directories that is a symlink, is not owned by the user, or is group- or world-writable is refused (`config_unsafe`, exit 20, naming the path). `--config PATH` exists only on `validate`, which runs nothing. Unknown keys and invalid values fail fast naming the key. Schema: `schemas/config.json`; every key is documented in `config.example.yaml`.

| Key | Default | Meaning |
|---|---|---|
| `me.name` | OS user | The `<user>` of `human:<user>`. |
| `me.github`, `me.gitlab`, `me.jira` | none | Account names; passed to tools only where an adapter says so. |
| `roles.<role>` | none | Role to tool, for example `githost: forgectl`, `tickets: ticketctl`, `notify: notice-route`. |
| `tools.<tool>.enabled` | true | A disabled tool is skipped everywhere. |
| `tools.<tool>.bin` | none | An absolute path that overrides the adapter's program name. |
| `dashboard.refresh` | `15s` | The refresh interval (at least `5s`). |
| `dashboard.concurrency` | `8` | The most concurrent reads (1 to 16). |
| `dashboard.read_timeout` | `10s` | The default read timeout. |
| `cron.env_file` | none | A user-owned file the cron lines source. |
| `cron.path_extra` | `[]` | Absolute directories added to the cron `PATH`. |
| `cron.intervals.<tool>` | the adapter's | Overrides an entry's schedule (a cron expression or one of the entry's accepted shorthands). |
| `doctor.probe_timeout` | `60s` | The timeout of one probe. |

There are no `repos:` and no `hooks:` keys in 0.x.

## Environment variables

Only `AWKIT_DASHBOARD__REFRESH`, `AWKIT_DASHBOARD__CONCURRENCY` and `AWKIT_DASHBOARD__READ_TIMEOUT` override config keys. awkit reads `TMUX` (for `W`) and `HOME`-derived paths from the password database, not from `HOME`. Reads and actions run with the inherited environment, so the credentials the tools name in their own configs are available to them; awkit adds no variable and never prints one.

## Hooks

awkit exposes no hooks in 0.x (a recorded deviation from the design guide's `pre-` and `post-` rule). awkit consumes other tools' hooks through `wire`.

## Labels

awkit creates no long-lived objects and has no `label` command. It reads labels as described in Links and chains.

## Files

| Path | Content |
|---|---|
| `~/.config/awkit/config.yaml`, `config.d/`, `adapters/` | Configuration and overlay (user-owned, never group- or world-writable). |
| `~/.local/state/awkit/audit.jsonl` | awkit's own audit records. |
| `~/.local/state/awkit/doctor-last.json` | The last `doctor` result, for the dashboard badge. |
| `~/.local/state/awkit/cron.lock` | The `flock` file of `cron` commands. |
| `~/.config/<tool>/config.d/awkit.yaml` | A drop-in written by `wire`. |

## Concurrency

Reads, `attention`, `chains`, `audit`, `validate` and `adapters` keep no locks and can run any number of times at once. `cron install|uninstall` takes the exclusive lock above. `wire` and `unwire` replace one file by rename. Two dashboards may run at once.

## Dependencies

| Tool | Binding | Use |
|---|---|---|
| every registered tool | C | The adapter's reads and actions, by CLI and `--json` only. |
| notice-route | C | The destination of `wire`d hooks. |
| `crontab`, a cron daemon | third-party | `cron`, `doctor`. |
| tmux | third-party, optional | `W`. |

awkit imports no tool and reads no tool's `state.db`. The `tui` extra is Textual `>=8.2,<9`. The core uses the standard library, PyYAML and Pydantic (design guide §3).

## Roadmap

Reserved for 1.x and not implemented in 0.x: `awkit tick`, `awkit run`, `awkit notify-tick [--source TOOL]`, `awkit reconcile`, the rules engine with its write-ahead action ledger, the state graph on disk, `repos:` and `hooks:` config keys, and the early-tick hooks of `wire`. The constraints the architecture already fixes (architecture §7.2 to §7.5) apply to them. `design.md` lists the open items.

## Upgrades

An adapter's `min_version` is a floor, not a pin. A tool below it is reported by `doctor` (`tool.version`) and stays usable at the user's risk. A tool newer than the adapter's design is read as usual; a mapped required field that vanished marks the tool stale, never the whole dashboard. The first implementation issue is a verification pass over every tool's current interface that updates the adapters.

## Residual risks

- A process of the same user can write the config, the overlay and the audit files; awkit refuses files other users could write but cannot defend against its own user.
- Labels are not authenticated; the views dim unverified links and destructive actions re-verify them, but a record that lies in the authoritative source is out of scope.
- A tool's own `cron install` or a hand edit can lose an update inside the roughly 30 ms window of `cron install`.
- `--actor human:<user>` is a claim: a same-user process can make it. The audit record shows how the claim was made.
- The sanitizer cannot make a terminal safe against a bug in the terminal itself.
- `doctor` is advice and not a security boundary.

## Platform notes

Linux and WSL (Ubuntu) are supported in 0.x. macOS is not: awkit is not in the architecture's macOS list. On WSL the cron daemon must be running (`doctor` checks), a long-lived tmux or cron environment can hold a stale interop socket, and the Windows filesystem under `/mnt/c` is not used for state. Outside tmux everything works except `W`.
