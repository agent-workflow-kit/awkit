# awkit: implementation plan

This plan implements [interface.md](interface.md) and [design.md](design.md). Each stage is expanded into bite-sized test-first steps when its issue is picked up; this file does not contain code. Stages are listed in dependency order and each ends with `make verify` green.

## Conventions for every stage

- **Gateway.** Every subprocess, `crontab` call and read of a tool's output goes through `src/awkit/gateway.py`. Tests replace it with fakes; fake tool binaries live in `tests/fakebin/` and are copied per repo, never shared.
- **Pinned sibling schemas.** A sibling's `--json` schema or audit schema used in a test is copied into `tests/` pinned to a version. awkit never imports a sibling.
- **Test split.** Unit and pilot tests run in CI. `process` tests (terminal handoff, signals, typeahead) run in CI under a pseudo-terminal. `live` tests (a real crontab with a backup and a byte-identical restore, a real tool) never run in CI and are deselected by default.
- **Golden files.** Every `--json` output has a golden file. awkit writes no crontab block, so there are no cron goldens: cron tests use fake tool installers and per-tool recognizer samples.
- **Spike regressions.** Each behavior in design.md's live-verification table becomes a test in the stage that owns it.
- **Hostile corpus.** Every view and every `--json` output passes the sanitizer corpus test from Stage 1 on, including a markup corpus and a lone-surrogate case, and every schema pattern has a trailing-LF negative case.
- **Dependencies.** Each new dependency is justified in design.md; the core uses the standard library, PyYAML and Pydantic; Textual `>=8.2,<9` lives only in the `tui` extra.
- **Before every pull request.** `make verify`, `uvx check-jsonschema --check-metaschema schemas/**/*.json` at CI's pinned version, `make mdlint`, and a grep of the repo files for local paths and private ids.

## Module map

| Module | Stage | Responsibility |
|---|---|---|
| `gateway` | 0 | All subprocess, `crontab` and tool-output access |
| `sanitize` | 1 | The one sanitizer |
| `config` | 1 | Hardened loader, models, `validate` |
| `adapters` | 2 | Loader, path language, argv filling, overrides and `override_host` |
| `readers` | 2 | Async refresh worker, per-tool results with age |
| `model` | 4 | Rows, attention items, links, chains |
| `cron` | 5 | Delegating installer, block recognizers, lock |
| `doctor` | 6 | Checks and the cache file |
| `audit` | 7 | Reader, merger, pairing, own writer, `audit.coverage` |
| `wire` | 8 | The drop-in writer |
| `actions` | 9 | Confirm recipes and the action runner |
| `tui` | 9 | Textual views (optional extra) |
| `cli` | 1 onward | Parsing and exit-code mapping |

## Stage 0: Verify the tools and scaffold

**Goal**: Replace the design's per-tool assumptions with verified facts and have a working skeleton. This is the first issue.
**Success Criteria**: For every registered tool, a written report of its current `docs/interface.md` version, released version, implemented commands, `--json` shapes, hooks, `cron install` block, `validate`, audit file and TUI, compared with the interface registry row; every difference is either fixed in the registry or recorded as an adapter note. The report also settles the carry-forwards: each tool's `cron install` flags (`interval_flag`, `env_file_flag`, the option argv each adapter maps) and recognizer lines; the minimum tmux version that runs `new-window` arguments without `sh -c` (believed 3.0); hook names, that a `{"tool", "hook"}` payload passes `notice-route test` for each wired hook, and which tools' `wire.check` is `validate` and which a list read, with its `ok_exits`; which list commands mutate state and the non-mutating forms; `--limit` maxima, id and `since` forms; every action's `--json`, `--dry-run` and `--actor` support and pass fields; `tui` arguments and `--focus` forms; audit pairing descriptors; `validate` exit codes and warning paths, including notifier `validate` exits when disabled; gatectl shadow-drop visibility; agent-spawn's label shape; the Textual key-event timestamp attribute used by the dwell rule and the markup sinks list against Textual 8.2. The package builds, `awkit --version` works, `gateway` and `fakebin` exist, CI is green.
**Tests**: `awkit --version` and `--help` golden; gateway fake substitution; a script that recomputes the report from each tool's `origin/main` and fails when a registry row is stale.
**Status**: Not Started

## Stage 1: Config, sanitizer and CLI skeleton

**Goal**: The hardened configuration loader, the sanitizer and the command skeleton with exit codes.
**Success Criteria**: `awkit validate` loads config, drop-ins and (empty) adapters under the password-database home with the strict YAML loader; a symlinked, foreign-owned or group- or world-writable file or parent exits 20 `config_unsafe`; `--config` works only on `validate`; unknown keys fail naming the key; a tool program resolves only through a configured absolute path or the fixed search list with ownership checks, never the process `PATH`; every string and key passes the sanitizer (an allowlist by Unicode category); Pydantic models use `regex_engine="python-re"`, because the schemas' `(?![\s\S])` anchors need look-ahead; the error envelope matches the schemas.
**Tests**: ownership, symlink and permission matrix; `XDG_CONFIG_HOME` and path-naming variables ignored; program resolution cases (a writable directory, a symlink, an unowned parent); strict YAML refusals; loader node and size caps, deep nesting; `config.example.yaml` validates; hostile corpus and the code-point enumeration; exit-code table; schema samples.
**Status**: Not Started

## Stage 2: Adapter engine and readers

**Goal**: Load adapters, evaluate the path language, fill argv and run reads concurrently.
**Success Criteria**: Bundled and overlay adapters load (overlay replaces bundled); a bad adapter excludes only its tool; paths evaluate per the interface's grammar and semantics (missing yields null, `[?field=value]`, `[*]`, index; evaluation never raises); a read yields rows with the fixed field set; argv placeholders are the closed set (`{object}`, `{actor}`, `{pass.<name>}`, whole elements only); the refresh worker runs reads under a semaphore with a timeout and size caps, kills the read's process group, and keeps stale data with its age; Python and executable overrides run as child processes speaking `awkit-adapter/1` through `override_host`.
**Tests**: path-language tests and property tests with the interface's Path language text as the oracle; placeholder refusal cases; read timeout, oversize and invalid-JSON cases; duplicate ids, all ids invalid (partial with zero rows), NaN, a nested free field; override protocol round trips; the refresh budget test (20 fake reads per cycle).
**Status**: Not Started

## Stage 3: Bundled adapters, first batch

**Goal**: Adapters for the implemented tools, written from Stage 0's verified facts.
**Success Criteria**: Adapters for claude-session, termctl, wtctl, jobsctl, agent-spawn, forgectl, pr-comment and the notifiers load and read against pinned fakes; each declares its version source, reads, attention, links, actions, cron mapping, audit path and doctor checks as the tool supports them; the claude-session adapter has no `cron` key (agent-spawn's block runs its reconcile).
**Tests**: per-adapter golden mapping tests against pinned sibling `--json` samples; the adapter schema.
**Status**: Not Started

## Stage 4: Attention and chains

**Goal**: The model and the `attention` and `chains` commands.
**Success Criteria**: Attention items for every source of the Stage 3 adapters' tools, ordered as specified; chains with the source tags `record`, `branch` and `label`; `branch` and `label` links dimmed in output; no link-derived value ever enters an argv.
**Tests**: fixture-driven attention and chain goldens; a forged label that never changes an action's argv; order and filter tests; `--ticket` ambiguity; `targets` with bare and site keys, `pr_norm` for both hosts, link-only nodes offer no actions.
**Status**: Not Started

## Stage 5: Cron

**Goal**: `awkit cron install|uninstall` as a delegating installer, plus the block recognizers.
**Success Criteria**: `--dry-run` prints each tool's argv and runs nothing (no lock, no crontab read); otherwise the command takes awkit's lock without waiting (a held lock exits 12 at once), reads the crontab first (only exit 1 with the empty-table message counts as empty; any other failure exits 12 and runs nothing), runs each registered tool's own `cron install` or `uninstall` in lexical order with a constructed environment and the flags its adapter maps from `cron.intervals` (verbatim), `cron.options` and `cron.env_file`, and reads the crontab again for the audit hashes; a tool whose installer fails or times out is reported and the others still run (exit 12, with the per-tool document); a signal stops the run between tools (handlers are installed before the first audit append); awkit never writes the crontab itself; one recognizer per adapter classifies a block as present, absent or malformed (end line tested before start line; jobsctl exempt; comments that mention a tag are not blocks); `doctor` and the reporting use the recognizer.
**Tests**: fake tool installers (success, failure, timeout, order, lock held, signal between tools, `--dry-run` runs nothing); a poisoned `PATH` and `XDG_CONFIG_HOME` never reach the fake installer's environment; crontab read failure and empty-table cases; recognizer unit tests (CR, no final newline, non-UTF-8, a large crontab capped at the documented 1 MiB limit, shared prefixes, malformed, hand-edited, `v1 ...` first lines); `live` install and restore against a real crontab with real tools.
**Status**: Not Started

## Stage 6: Doctor

**Goal**: Every check of the Doctor table and the cache file.
**Success Criteria**: Read-only and probe-free by default (some tools' `validate` reads the network); `--probe` runs one tool at a time and never sends a test message; each check reports `ok`, `warn` or `fail` with a reason (every check of the Doctor table except `audit.coverage`, which Stage 7 adds, and `wire.rule`, which Stage 8 adds); versions come from the tool's own environment, else `--version`; exit 12 only on a failure; `doctor-last.json` is written atomically; install commands are printed for missing tools.
**Tests**: a fake environment per check (missing tool, old version, malformed block, bad env file, no daemon, leaking variable lines); probe ordering and timeouts; cache file round trip; per-state check lists, `--tool` with global checks, unreadable crontab.
**Status**: Not Started

## Stage 7: Audit

**Goal**: The merged timeline and awkit's own records.
**Success Criteria**: Per-tool `audit.jsonl` read by byte offset with safe opening (no symlinks, regular files, partial tail kept), tolerant of missing files and malformed lines, merged by time, paired within a tool by the adapter's pairing descriptor (awkit's own file appears as source `awkit`); filters by tool, pull request, ticket, label, actor, action and time; awkit's `cron` commands write an `attempted` record before any change and an outcome record after (tested here with the Stage 5 fake installers); the `audit.coverage` doctor check lists registered tools that declare no audit file.
**Tests**: pairing with `unknown` standing alone and groups of any size; shrinking and rotated files and a reused inode; hostile lines (depth 20,000, an object or boolean as a pairing key) that are counted and never end the command; filters; a failed first append stops the command; `audit.coverage`.
**Status**: Not Started

## Stage 8: Wire

**Goal**: `awkit wire|unwire`, the notice-route adapter and the `wire.rule` check.
**Success Criteria**: The drop-in (hooks named `post-` or `on-` only, each routed by a string `cmd` to `notice-route send`) is written under the password-database home with the first-line hash marker, by rename, mode 0600; a file that is not awkit's unedited text is `drop_in_foreign`; a second tool's `state: true` hooks wired is `duplicate_state_hooks`; the adapter's check runs before (refusal) and after the write (rollback); `wire.lock` is taken without waiting; a non-default `XDG_CONFIG_HOME` refuses with `xdg_mismatch`; notice-route and tools with nothing to wire exit 0; `unwire` removes only awkit's file; awkit's own `attempted` and outcome records are written for each change; `doctor` warns when `notice-route test` finds no delivering rule for a wired hook.
**Tests**: outcome table; ownership checks on the directory; golden drop-in text, an edited body is foreign, a stray temp file is never read by a tool (name outside `*.yaml`); no write without confirmation or `--yes`; own-record pairs per changed file and none for `unchanged`; rollback on a failed check and on a signal after the rename; a file edited while the prompt waits is never overwritten; no directory created by a dry run; `wire.rule` against a pinned fake notice-route.
**Status**: Not Started

## Stage 9: Actions and dashboard

**Goal**: The Textual dashboard with the confirm recipes.
**Success Criteria**: Attention, Chains and Timeline tabs with the badge and stale markers; keys as specified; the confirm dialog derives the dry run from the action's own argv with the same human actor, shows awkit's own chrome (tool, action, object, actor, the full argv) apart from a scrolling body of sanitized fields, ignores typeahead and accepts `y` only when the whole dialog fits the pane or was scrolled to its end, and then passes `--actor human:<user>` plus the checked fields (and `--yes` only where the action's recipe says so; terminal actions pass neither); terminal actions are confirmed in awkit's dialog first; only the narrowed 0.x action forms exist (no human-written text, second object, multi-select, continuation, or reserved human flag other than `--allow-tainted`); `terminal: true` actions (after the dialog) and `enter` hand over the terminal with the hardening (own process group, foreground handback, no inherited SIGINT ignore); `W` opens a tmux window; no displayed text is parsed as markup; `--result-file` is atomic; the dashboard restores the terminal on SIGTERM and SIGHUP.
**Tests**: Textual pilot tests against fake readers (no fixed sleeps, no wall-clock bounds), including hidden typeahead, the scroll gate and a refresh while the dialog is open; `process` tests for the handoff, typeahead, signals and result file; hostile corpus through every view, the widget walk and the constructor lint; a Python child receives SIGINT and the dashboard survives; a child that stops itself leaves the dashboard usable; SIGTERM reaches the child within 1 s; a no-terminal exit 13 test.
**Status**: Not Started

## Stage 10: Second adapter batch, smoke suite and 1.0 gate

**Goal**: Adapters for the remaining tools as they are implemented, the cross-tool smoke suite and the stability review.
**Success Criteria**: Adapters for pr-watch, review-run, review-watch, review-respond, ticketctl, ticket-queue, ticket-work, ticket-create, gatectl and memoctl verified against each tool's released interface; the smoke suite runs every 0.x command against fake binaries; the 1.0 criteria below hold.
**Tests**: per-adapter goldens; `tests/e2e/` smoke runs; `live` runs against the tools that exist.
**Status**: Not Started

## Version roadmap

- **0.x:** Stages 0 to 9 in order, released as they land; Stage 10 adapters are added as each tool ships.
- **1.0** when: the dashboard, `doctor`, `cron`, `wire` and `audit` are used daily on the author's WSL machine against real tools without a destructive incident; every bundled adapter has been verified against its tool's released interface; the interface and schemas are unchanged for two consecutive minor releases.
- **1.x (additive):** `awkit tick`, `awkit run` and `awkit notify-tick` with the tick lock; the rules engine with the write-ahead action ledger, starting with the cheap early-trigger rules (a merged or closed pull request runs `ticket-work sync`; a held or failed job runs its workflow's poll; a review comment runs `review-respond check`); the stored state graph and `awkit reconcile` (reboot recovery); per-adapter poll intervals and file-watch triggers; the early-tick hooks of `wire`; `repos:` and `hooks:` config keys and awkit's own hooks; the when-to-merge rule behind an enforced gatectl policy; a config hash warning; a per-tool overview grid view; macOS support if wanted.
- **2.0:** nothing planned.
