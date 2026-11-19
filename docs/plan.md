# awkit: implementation plan

This plan implements [interface.md](interface.md) and [design.md](design.md). Each stage is expanded into bite-sized test-first steps when its issue is picked up; this file does not contain code. Stages are listed in dependency order and each ends with `make verify` green.

## Conventions for every stage

- **Gateway.** Every subprocess, `crontab` call and read of a tool's output goes through `src/awkit/gateway.py`. Tests replace it with fakes; fake tool binaries live in `tests/fakebin/` and are copied per repo, never shared.
- **Pinned sibling schemas.** A sibling's `--json` schema or audit schema used in a test is copied into `tests/` pinned to a version. awkit never imports a sibling.
- **Test split.** Unit and pilot tests run in CI. `process` tests (terminal handoff, signals, typeahead) run in CI under a pseudo-terminal. `live` tests (a real crontab with a backup and a byte-identical restore, a real tool) never run in CI and are deselected by default.
- **Golden files.** Every `--json` output and every cron block has a golden file; a cron golden is copied unchanged from the owning tool's `schemas/` and a test fails on one byte of difference.
- **Spike regressions.** Each behavior in design.md's live-verification table becomes a test in the stage that owns it.
- **Hostile corpus.** Every view and every `--json` output passes the sanitizer corpus test from Stage 1 on.
- **Dependencies.** Each new dependency is justified in design.md; the core uses the standard library, PyYAML and Pydantic; Textual `>=8.2,<9` lives only in the `tui` extra.
- **Before every pull request.** `make verify`, `uvx check-jsonschema --check-metaschema schemas/**/*.json` at CI's pinned version, `make mdlint`, and a grep of the repo files for local paths and private ids.

## Module map

| Module | Stage | Responsibility |
|---|---|---|
| `gateway` | 0 | All subprocess, `crontab` and tool-output access |
| `sanitize` | 1 | The one sanitizer |
| `config` | 1 | Hardened loader, models, `validate` |
| `adapters` | 2 | Loader, path language, templates, overrides |
| `readers` | 2 | Async refresh worker, per-tool results with age |
| `model` | 4 | Attention items, links, chains |
| `cron` | 5 | Block manager, templates, goldens, lock |
| `doctor` | 6 | Checks and the cache file |
| `audit` | 7 | Reader, merger, pairing, own writer |
| `wire` | 8 | The drop-in writer |
| `actions` | 9 | Confirm recipes and the action runner |
| `tui` | 9 | Textual views (optional extra) |
| `cli` | 1 onward | Parsing and exit-code mapping |

## Stage 0: Verify the tools and scaffold

**Goal**: Replace the design's per-tool assumptions with verified facts and have a working skeleton. This is the first issue.
**Success Criteria**: For every registered tool, a written report of its current `docs/interface.md` version, released version, implemented commands, `--json` shapes, hooks, `cron install` block, `validate`, audit file and TUI, compared with the interface registry row; every difference is either fixed in the registry or recorded as an adapter note. The package builds, `awkit --version` works, `gateway` and `fakebin` exist, CI is green.
**Tests**: `awkit --version` and `--help` golden; gateway fake substitution; a script that recomputes the report from each tool's `origin/main` and fails when a registry row is stale.
**Status**: Not Started

## Stage 1: Config, sanitizer and CLI skeleton

**Goal**: The hardened configuration loader, the sanitizer and the command skeleton with exit codes.
**Success Criteria**: `awkit validate` loads config, drop-ins and (empty) adapters under the password-database home; a symlinked, foreign-owned or group- or world-writable file or parent exits 20 `config_unsafe`; `--config` works only on `validate`; unknown keys fail naming the key; every string passes the sanitizer; the error envelope matches the schemas.
**Tests**: ownership, symlink and permission matrix; `XDG_CONFIG_HOME` and path-naming variables ignored; `config.example.yaml` validates; hostile corpus; exit-code table; schema samples.
**Status**: Not Started

## Stage 2: Adapter engine and readers

**Goal**: Load adapters, evaluate the path language, fill templates and run reads concurrently.
**Success Criteria**: Bundled and overlay adapters load (overlay replaces bundled); a bad adapter excludes only its tool; paths evaluate per the table (missing yields null, `[?field=value]`, `[*]`, index); templates are argv lists with grammar-checked parameters and no tool text in argv or environment; the refresh worker runs reads under a semaphore with a timeout and keeps stale data with its age; Python and executable overrides speak `awkit-adapter/1`.
**Tests**: path-language table tests and property tests against a reference implementation; template refusal cases; read timeout, oversize and invalid-JSON cases; override protocol round trips; the refresh budget test (20 fake reads per cycle).
**Status**: Not Started

## Stage 3: Bundled adapters, first batch

**Goal**: Adapters for the implemented tools, written from Stage 0's verified facts.
**Success Criteria**: Adapters for claude-session, termctl, wtctl, jobsctl, agent-spawn, forgectl, pr-comment and the notifiers load and read against pinned fakes; each declares its version source, reads, attention, links, actions, periodic entries, audit path and doctor checks as the tool supports them.
**Tests**: per-adapter golden mapping tests against pinned sibling `--json` samples; the adapter schema.
**Status**: Not Started

## Stage 4: Attention and chains

**Goal**: The model and the `attention` and `chains` commands.
**Success Criteria**: Attention items for every source in the interface table, ordered as specified; chains with source tags; `reverify` refusals with `link_unverified`; unverified links dimmed in output.
**Tests**: fixture-driven attention and chain goldens; a forged-label case that must be refused by a `reverify` action; order and filter tests.
**Status**: Not Started

## Stage 5: Cron

**Goal**: `awkit cron install|uninstall` byte-compatible with each tool's own command.
**Success Criteria**: The block manager parses foreign lines and blocks per tool grammar (end line before start line; jobsctl exempt; comments that mention a tag are not blocks) and produces the specified outcomes; every written block equals its golden; one locked batched write with re-read, compare, retry and read-back; foreign lines are byte-identical; the 1000-byte and `%` rules hold.
**Tests**: block manager unit tests (CR, no final newline, non-UTF-8, 14 MB crontab, shared prefixes, malformed, hand-edited); a concurrency demonstration with a fake `crontab` shim; per-tool goldens; `live` install and restore against a real crontab.
**Status**: Not Started

## Stage 6: Doctor

**Goal**: Every check of the Doctor table and the cache file.
**Success Criteria**: Offline by default; `--probe` runs one tool at a time and never sends a test message; each check reports `ok`, `warn` or `fail` with a reason; exit 12 only on a failure; `doctor-last.json` is written atomically; install commands are printed for missing tools.
**Tests**: a fake environment per check (missing tool, old version, malformed block, bad env file, no daemon, leaking variable lines); probe ordering and timeouts; cache file round trip.
**Status**: Not Started

## Stage 7: Audit

**Goal**: The merged timeline and awkit's own records.
**Success Criteria**: Per-tool `audit.jsonl` read by byte offset, validated, tolerant of missing files and malformed lines, merged by time, paired by `attempt_id`; filters by tool, pull request, ticket, label, actor and time; awkit's `cron` and `wire` commands write an `attempted` record before any change and an outcome record after.
**Tests**: pairing with `unknown` standing alone; shrinking and rotated files; filters; a failed first append stops the command.
**Status**: Not Started

## Stage 8: Wire

**Goal**: `awkit wire|unwire`.
**Success Criteria**: The drop-in is written under the password-database home with the first-line marker, by rename, mode 0600; a foreign file is `drop_in_foreign`; both state-hook sources wired is `duplicate_state_hooks`; tools with nothing to wire exit 0; `unwire` removes only awkit's file.
**Tests**: outcome table; ownership checks on the directory; golden drop-ins; no write without confirmation or `--yes`.
**Status**: Not Started

## Stage 9: Actions and dashboard

**Goal**: The Textual dashboard with the confirm recipes.
**Success Criteria**: Attention, Chains and Timeline tabs with the badge and stale markers; keys as specified; confirm dialog runs the dry run, shows sanitized fields, waits for `y` and passes `--yes --actor human:<user>` plus the fields; `terminal: true` actions hand over the terminal with the hardening; `W` opens a tmux window; `--result-file` is atomic; the dashboard restores the terminal on SIGTERM and SIGHUP.
**Tests**: Textual pilot tests against fake readers (no fixed sleeps, no wall-clock bounds); `process` tests for the handoff, typeahead, signals and result file; hostile corpus through every view; a no-terminal exit 13 test.
**Status**: Not Started

## Stage 10: Second adapter batch, smoke suite and 1.0 gate

**Goal**: Adapters for the remaining tools as they are implemented, the cross-tool smoke suite and the stability review.
**Success Criteria**: Adapters for pr-watch, review-run, review-watch, review-respond, ticketctl, ticket-queue, ticket-work, ticket-create, gatectl, memoctl and notice-route verified against each tool's released interface; the smoke suite runs every 0.x command against fake binaries; the 1.0 criteria below hold.
**Tests**: per-adapter goldens; `tests/e2e/` smoke runs; `live` runs against the tools that exist.
**Status**: Not Started

## Version roadmap

- **0.x:** Stages 0 to 9 in order, released as they land; Stage 10 adapters are added as each tool ships.
- **1.0** when: the dashboard, `doctor`, `cron`, `wire` and `audit` are used daily on the author's WSL machine against real tools without a destructive incident; every bundled adapter has been verified against its tool's released interface; the interface and schemas are unchanged for two consecutive minor releases.
- **1.x (additive):** `awkit tick`, `awkit run` and `awkit notify-tick` with the tick lock; the rules engine with the write-ahead action ledger, starting with the cheap early-trigger rules (a merged or closed pull request runs `ticket-work sync`; a held or failed job runs its workflow's poll; a review comment runs `review-respond check`); the stored state graph and `awkit reconcile` (reboot recovery); per-adapter poll intervals and file-watch triggers; the early-tick hooks of `wire`; `repos:` and `hooks:` config keys and awkit's own hooks; the when-to-merge rule behind an enforced gatectl policy; a config hash warning; a per-tool overview grid view; macOS support if wanted.
- **2.0:** nothing planned.
