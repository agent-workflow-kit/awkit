# awkit: design

Status: 0.1.0-design (2026-11-19), designed against architecture v1.30. `interface.md` is the single normative source; this file records the decisions and the reasons and links to its headings (architecture §7 and §20, design guide).

## Role and layer

`awkit` is the harness, the top layer (L4). It is the only component aware of the others, and it is optional: everything else works without it. It knows the other tools only through configuration and adapters; tools never adapt to it (architecture §3.1). It must work with whatever subset of tools the user registers.

Release 0.x is stateless apart from its own audit file and a small cache. It reads every tool by CLI and `--json`, shows the Attention, Chains and Timeline views in a dashboard, checks the installation, writes the cron blocks and the notification wiring, and merges the tools' audit files. The tick loop, the rules engine, the action ledger and the state graph on disk are 1.x.

## Uses

| Tool | Binding | Used for |
|---|---|---|
| Every registered tool (all 21 designed tools, plus third-party CLIs through overlay adapters) | C (adapter) | Reads, attention, links, actions, cron blocks, audit paths and doctor checks, by CLI and `--json` only. No tool's `state.db` is read and no tool is imported. |
| notice-route | C | The destination of the hooks `wire` routes. |
| `crontab`, a cron daemon | third-party | `cron`, `doctor`. |
| tmux | third-party, optional | The `W` key. |

## Decisions

| # | Decision | Interface |
|---|---|---|
| D-1 | 0.x is stateless first: adapters, `doctor`, `cron`, `wire`, `audit`, then the dashboard that recomputes everything on each refresh. `tick`, `run`, rules, the ledger and `state.db` are 1.x. Reason: this covers the v1 bar and the cron and credential problems, and postpones the automatic-action surface until the tools it acts through exist (12 of 21 tools are skeletons and pr-watch's commands are stubs). | [Overview](interface.md#overview), [Roadmap](interface.md#roadmap) |
| D-2 | Adapters map output with awkit's own small path language (dotted members, `[*]`, one equality filter, an index), standard library only, with Python and executable overrides for everything else. No `jq` binary and no JSONPath library. | [Path language](interface.md#path-language), [Escape hatches](interface.md#escape-hatches) |
| D-3 | Commands are argv lists with single-pass placeholders filled from declared, grammar-checked parameters; no shell, and no tool text in argv or environment. | [Templates and argv rules](interface.md#templates-and-argv-rules) |
| D-4 | An overlay adapter replaces the bundled adapter of the same tool; there is no merging. | [Adapters](interface.md#adapters) |
| D-5 | Drill-in suspends the dashboard (hardened: SIGINT ignored, SIGTERM and SIGHUP forwarded, typeahead flushed before and after, terminal restored) and `W` opens a tmux window. The dashboard runs in whatever terminal started it and has its own SIGTERM and SIGHUP handler. An embedded terminal widget was rejected for 0.x. | [Terminal handoff](interface.md#terminal-handoff) |
| D-6 | Three tabs (Attention, Chains, Timeline) with a doctor badge and per-tool stale markers; one asyncio worker with a semaphore of 8, refreshing every 15 s. | [Views and keys](interface.md#views-and-keys), [Refresh](interface.md#refresh) |
| D-7 | `cron install` writes a block for every tool whose adapter declares `periodic` entries, including wtctl, gatectl, review-run and claude-session, which the architecture list lacked. Blocks come from awkit's templates pinned by goldens copied from each tool's schemas; awkit never calls a tool's own `cron install`. One lock, one batched read-modify-write, re-read and compare, read-back. | [Cron](interface.md#cron) |
| D-8 | Block matching is per tool: the end line is tested before the start line; a tool with no end line (jobsctl) is exempt; a comment mentioning a tag is not a block. | [Block grammar](interface.md#block-grammar) |
| D-9 | Configuration is read only under the password-database home, never through `XDG_CONFIG_HOME` or a path-naming variable, and a symlinked, foreign-owned or group- or world-writable file or parent is refused. `--config` exists only on `validate`. Reason: awkit turns a config edit into a crontab edit and into dashboard actions. | [Configuration](interface.md#configuration) |
| D-10 | Actions are declared in adapters with a confirm recipe (dry run, shown fields, passed fields, `--yes --actor human:<user>`); a command without `--yes` is `terminal: true` and the tool asks the human itself. | [Actions](interface.md#actions) |
| D-11 | `doctor` is offline and read-only by default; `--probe` runs each tool's live check one at a time and never sends a test message. Versions are read from package metadata because `--version` is unreliable for many tools. | [Doctor](interface.md#doctor) |
| D-12 | `awkit audit` reads each tool's public `audit.jsonl` directly by byte offset and pairs records by `attempt_id`; label filters join to objects the adapters read. | [Reading](interface.md#reading) |
| D-13 | awkit audits only what it alone does (`cron.install`, `cron.uninstall`, `wire`, `unwire`); dashboard actions are audited by the owning tool, so nothing is recorded twice. | [Own records](interface.md#own-records) |
| D-14 | `wire` in 0.x writes only the notification drop-in (hooks routed to `notice-route send`) and refuses to wire both agent-spawn's and claude-session's state hooks; the early-tick hooks come with the loop. | [Wire](interface.md#wire) |
| D-15 | Chain links carry a source tag (`record`, `forge`, `branch`, `label`); unverified links are dimmed and destructive or outward-going actions re-verify them. | [Links and chains](interface.md#links-and-chains) |
| D-16 | One sanitizer runs on every string from any tool before it enters the model, not only on fields a schema marks untrusted. | [Output sanitizing](interface.md#output-sanitizing) |
| D-17 | No install-all script and no `awkit install`: the interface registry carries an install command and a minimum version per tool, and `doctor` prints them. awkit never runs an installer. | [Doctor](interface.md#doctor) |
| D-18 | The 1.x engine is specified only at roadmap level now: the reserved commands and the architecture constraints. Its rules syntax, retry count, state graph schema and when-to-merge rule are decided in a short design pass once pr-watch and the gate exist and have been run. | [Roadmap](interface.md#roadmap) |

My own calls (not asked of the user, listed for review): the `attention`, `chains`, `adapters` and `validate` commands exist because the guide requires a command for every TUI view; the last `doctor` result is cached in `doctor-last.json`; `dashboard` also answers to `browse`; awkit is Linux and WSL only in 0.x; `wire` and the config of other tools are written under the password-database home; the environment variables are limited to three `dashboard.*` keys; there are no `hooks:` or `repos:` keys in 0.x.

## Resolved open topics (architecture §20, awkit)

| Open topic | Where it is resolved |
|---|---|
| Tool registry and adapter format | D-2, D-3, D-4; [Adapters](interface.md#adapters) |
| State graph schema | 0.x has no stored graph; links are recomputed (D-15); the stored schema is 1.x (D-18) |
| Harness-level reconcile | 1.x (D-18); the reboot-recovery order stays `jobsctl reconcile`, then `agent-spawn reconcile` |
| Rules syntax, rule-action retry count | 1.x (D-18) |
| Dashboard panels and actions | D-6, D-10 |
| Dashboard style, where the dashboard runs | D-5, D-6; the style section of design guide v1.15 |
| When-to-merge rule | 1.x (D-18); see Open items |
| TUI internals | D-5, D-6 and the module list below |
| Change detection | 0.x refreshes on a timer; per-adapter intervals, file watches and `notify-tick` are 1.x |
| Install-all | D-17 |

## Live verification

| Behavior | Source | Test in the plan |
|---|---|---|
| A suspended Textual app restores the terminal exactly; SIGINT and SIGTERM need the hardening above; a typed `y` answers a child's first `/dev/tty` read unless input is flushed before and after | PTY spike | Process tests of the terminal handoff |
| `/dev/tty` opens with all three standard streams redirected and fails only with no controlling terminal; a captured child must run in a new session with null input | PTY spike | Process test |
| A result file written in place is unparseable after a kill about two thirds of the time; temp, sync and rename gives valid or missing | PTY spike | Result-file test |
| Overlapping crontab writers lose updates (60 of 60 runs); one `flock` makes awkit-versus-awkit safe; a window of about 30 ms remains for a foreign writer | Cron spike | Lock test; the window is documented |
| Block grammars differ per tool (end-less jobsctl block, a loose start rule that also matches an end line, a comment that looks like a start line) | Cron spike | Per-tool block tests and goldens |
| Foreign lines survive byte for byte (CR, no final newline, non-UTF-8, a 14 MB crontab in about 3 s) | Cron spike | Block manager tests |
| Polling 20 commands per cycle costs 0.3 percent CPU every 15 s with asyncio | PTY spike | Refresh budget test |
| `--version` prints `0.0.0` for 15 of 21 tools | Inventory | `tool.version` reads metadata |
| Tools' current interfaces and CLIs differ from the registry rows | Inventory | The first issue: verify every tool's interface and update the adapters |

## Modules

| Module | Responsibility |
|---|---|
| `gateway` | Every subprocess, file read of tool output and `crontab` call. |
| `config` | The hardened loader and the models. |
| `adapters` | The loader, the path language, template filling and the override protocol. |
| `readers` | The asyncio refresh worker and the per-tool read results with their age. |
| `sanitize` | The one sanitizer. |
| `model` | Attention items and chains from reads and links. |
| `actions` | The confirm recipes and the action runner. |
| `cron` | The block manager, templates and goldens. |
| `wire` | The drop-in writer. |
| `doctor` | The checks and the cache file. |
| `audit` | The reader, merger, pairing and own writer. |
| `tui` | The Textual views (the optional extra); the logic modules above never import it. |
| `cli` | Argument parsing and the exit-code mapping. |

## Data model

No database in 0.x. Files: `audit.jsonl`, `doctor-last.json` and `cron.lock` in the state directory (see [Files](interface.md#files)). Everything else is derived on each refresh from tool output.

## Concurrency

See [Concurrency](interface.md#concurrency). Reads take no locks; `cron` takes one `flock`; `wire` renames one file; the dashboard's refresh cycle never overlaps itself.

## Error handling

A failing tool never fails the dashboard: its data goes stale with an age and a marker. A failing adapter excludes only its tool. A refusal is an exit 20 with a reason. A cron or wire write that cannot be completed leaves the previous file, and the audit record shows `unknown` when the outcome cannot be known.

## Test strategy

- All subprocess and file access through `gateway`; fake tool binaries per repo in `tests/fakebin/`, copied from nothing shared.
- Pilot tests of the Textual views against fake readers (no snapshot tests; no fixed sleeps).
- A hostile-string corpus through every view and every `--json` output.
- Process tests (marker `process`): the terminal handoff, typeahead flush, SIGINT and SIGTERM, result-file atomicity.
- Per-tool cron goldens, the block manager and the lock.
- Schema validation of every `--json` output, with positive and negative samples.
- A cross-tool smoke suite in `tests/e2e/` that runs the 0.x commands against fake binaries on `PATH` (architecture §17).
- `live` tests, never in CI: `cron install` against a real crontab with a backup and a byte-identical restore.
- `make verify`, the schema check at CI's pinned version, and `make mdlint` before every pull request.

## Open items (for the 1.x design pass)

- Rules syntax, the event vocabulary, the retry count and backoff, and the action ledger schema.
- The state graph schema and what is rebuilt.
- The when-to-merge rule: its trigger, the repo opt-in key, the gate policy and input, and who creates the pr-watch watch the rules depend on. Its inputs are weak today: pr-watch's commands are stubs and the merge gate cannot be enforced until a human sets it.
- Rule R1 (`review-respond check --pr`): the flag must exist in review-respond's interface.
- Rule R2 (a merged or closed pull request triggers `ticket-work sync`) has no producer yet, because nothing watches the user's own pull requests.
- `notify-tick` and the early-tick hooks of `wire`.
- Reboot recovery as a command.
- Whether the config hash warning (a hardening step left out of 0.x) is wanted.

## Deviations from the design guide

- `awkit dashboard` is also accepted as `awkit browse`.
- No `hooks:` or `repos:` config keys in 0.x; no hooks exposed.
- Config and overlay are read only under the password-database home, with ownership and symlink refusal (as for the notifiers and notice-route).
- Linux and WSL only in 0.x.
