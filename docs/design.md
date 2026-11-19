# awkit: design

Status: 0.1.0-design (2026-11-19), designed against architecture v1.30. `interface.md` is the single normative source; this file records the decisions and the reasons and links to its headings (architecture §7 and §20, design guide).

## Role and layer

`awkit` is the harness, the top layer (L4). It is the only component aware of the others, and it is optional: everything else works without it. It knows the other tools only through configuration and adapters; tools never adapt to it (architecture §3.1). It must work with whatever subset of tools the user registers.

Release 0.x is stateless apart from its own audit file and a small cache. It reads every tool by CLI and `--json`, shows the Attention, Chains and Timeline views in a dashboard, checks the installation, runs each tool's own cron installer and writes the notification wiring, and merges the tools' audit files. The tick loop, the rules engine, the action ledger and the state graph on disk are 1.x.

## Uses

| Tool | Binding | Used for |
|---|---|---|
| Every registered tool (all 21 designed tools, plus third-party CLIs through overlay adapters) | C (adapter) | Reads, attention, links, actions, cron settings, audit paths and doctor checks, by CLI and `--json` only. No tool's `state.db` is read and no tool is imported. |
| notice-route | C | The destination of the hooks `wire` routes. |
| `crontab`, a cron daemon | third-party | `doctor` and the audit hashes read the table; the tools' own `cron install` write it. |
| tmux | third-party, optional | The `W` key. |

## Decisions

| # | Decision | Interface |
|---|---|---|
| D-1 | 0.x is stateless first: adapters, `doctor`, `cron`, `wire`, `audit`, then the dashboard that recomputes everything on each refresh. `tick`, `run`, rules, the ledger and `state.db` are 1.x. Reason: this covers the v1 bar and the cron and credential problems, and postpones the automatic-action surface until the tools it acts through exist (12 of 21 tools are skeletons and pr-watch's commands are stubs). | [Overview](interface.md#overview), [Roadmap](interface.md#roadmap) |
| D-2 | Adapters map output with awkit's own small path language (dotted members, `[*]`, one equality filter, an index), standard library only. A read yields rows with a fixed field set; composite ids, parent references, computed reasons and per-tool normalization go to one override protocol, and both override kinds (Python and executable) run as child processes under the read rules. No `jq` binary and no JSONPath library. | [Path language](interface.md#path-language), [Escape hatches](interface.md#escape-hatches) |
| D-3 | Commands are argv lists. Reads have no placeholders; an action's placeholders are a closed set filled by awkit (the row's object, the actor, and typed values passed from the dry run), each a whole argv element and grammar-checked. No shell, and no free tool text in argv or environment. | [Templates and argv rules](interface.md#templates-and-argv-rules) |
| D-4 | An overlay adapter replaces the bundled adapter of the same tool; there is no merging. | [Adapters](interface.md#adapters) |
| D-5 | Drill-in suspends the dashboard (hardened: SIGINT ignored, SIGTERM and SIGHUP forwarded, typeahead flushed before and after, terminal restored) and `W` opens a tmux window. The dashboard runs in whatever terminal started it and has its own SIGTERM and SIGHUP handler. An embedded terminal widget was rejected for 0.x. | [Terminal handoff](interface.md#terminal-handoff) |
| D-6 | Three tabs (Attention, Chains, Timeline) with a doctor badge and per-tool stale markers; one asyncio worker with a semaphore of 8, refreshing every 15 s. | [Views and keys](interface.md#views-and-keys), [Refresh](interface.md#refresh) |
| D-7 | `cron install` and `uninstall` take awkit's own lock and run each registered tool's own `cron install` (or `uninstall`) in lexical order, with flags the adapter maps from awkit's config; awkit never writes the crontab itself. Reason: awkit's own templates cannot reproduce six of the thirteen tools' blocks without reading the tool's own config, so delegating is the only way every block has the tool's correct content. Cost: one crontab rewrite per tool instead of one batched write, and no byte-level preview for a tool without `--dry-run`. This replaces an earlier decision for own templates with goldens and one batched write. | [Cron](interface.md#cron) |
| D-8 | Blocks are recognized, never written, by one recognizer per adapter (a start rule and an end rule or none): the end line is tested before the start line; a tool with no end line (jobsctl) is exempt; a comment mentioning a tag is not a block. `doctor` uses it for present, absent or malformed, and uses a tool's `cron install --dry-run --json` where the adapter declares it. | [Cron](interface.md#cron) |
| D-9 | Configuration is read only under the password-database home, never through `XDG_CONFIG_HOME` or a path-naming variable, and a symlinked, foreign-owned or group- or world-writable file or parent is refused. YAML is loaded strictly (no anchors, aliases or duplicate keys). Programs are never found through the process `PATH`: a configured absolute path or a fixed search list, with ownership checks. `--config` exists only on `validate`. Reason: awkit's config decides which programs run and what the dashboard offers. | [Configuration](interface.md#configuration) |
| D-10 | Actions are declared in adapters with a confirm recipe: the dry run is derived from the action's own argv plus `--dry-run --json`, then shown fields, passed fields and `--yes --actor human:<user>`; the dialog's chrome is awkit's own. A command without `--yes` is `terminal: true` and the tool asks the human itself. Not in 0.x (the user reaches them through the tool's TUI or CLI): actions that need human-written text, a second chosen object (so no reorder), multi-select, continuation of a refused call, and every reserved human flag except claude-session's `--allow-tainted`. | [Actions](interface.md#actions) |
| D-11 | `doctor` is offline and read-only by default; `--probe` runs each tool's live check one at a time and never sends a test message. Versions are read from the tool's own environment (its interpreter's package metadata), else `--version`, because `--version` prints `0.0.0` for many tools. | [Doctor](interface.md#doctor) |
| D-12 | `awkit audit` reads each tool's public `audit.jsonl` directly by byte offset and pairs records within a tool by the key its adapter declares (no cross-tool pairing in 0.x); label filters join to objects the adapters read. | [Reading](interface.md#reading) |
| D-13 | awkit records only what it alone does (`cron.install`, `cron.uninstall`, `wire`, `unwire`); it records no dashboard action: the owning tool's audit, where it has one, is the record, and `doctor` lists tools without one. | [Own records](interface.md#own-records) |
| D-14 | `wire` in 0.x writes only the tool's notification hook drop-in (`post-` and `on-` hooks routed to `notice-route send`) and refuses to wire both agent-spawn's and claude-session's state hooks; it validates after writing and rolls back on rejection. The notice-route rule for the tool's source is the user's own configuration (the README shows it) and `doctor` warns when a wired tool has none. The early-tick hooks come with the loop. | [Wire](interface.md#wire) |
| D-15 | Chain links carry a source tag (`record`, `branch`, `label`); `branch` and `label` links are dimmed. In 0.x no link-derived value ever enters an action's argv and destructive actions rely on the owning tool's own refusals; link re-verification and a `forge` tag return in 1.x with the rules engine. | [Links and chains](interface.md#links-and-chains) |
| D-16 | One sanitizer runs on every string and object key from outside awkit before it enters the model, not only on fields a schema marks untrusted: an allowlist by Unicode general category, everything else shown as `<U+XXXX>`. No displayed text is ever parsed as markup. | [Output sanitizing](interface.md#output-sanitizing) |
| D-17 | No install-all script and no `awkit install`: the interface registry carries an install command and a minimum version per tool, and `doctor` prints them. awkit never runs an installer. | [Doctor](interface.md#doctor) |
| D-18 | The 1.x engine is specified only at roadmap level now: the reserved commands and the architecture constraints. Its rules syntax, retry count, state graph schema and when-to-merge rule are decided in a short design pass once pr-watch and the gate exist and have been run. | [Roadmap](interface.md#roadmap) |
| D-19 | `XDG_*` variables are ignored for awkit's own files. `doctor` warns on any non-default `XDG_CONFIG_HOME`, `XDG_STATE_HOME` or `XDG_DATA_HOME` (tools then use other directories than awkit reads), and `wire` refuses with `xdg_mismatch` when `XDG_CONFIG_HOME` is set to a non-default value. Tools handle XDG themselves in their own cron lines. | [Environment variables](interface.md#environment-variables), [Wire](interface.md#wire) |

My own calls (not asked of the user, listed for review): a tool is registered when its adapter loaded, it is not disabled and its program resolves; order everywhere is lexical by tool name; an absent tool is a warning unless config sets `enabled: true`; `roles` and `me.*` are only validated in 0.x (kept for 1.x); the `attention`, `chains`, `adapters` and `validate` commands exist because the guide requires a command for every TUI view; the last `doctor` result is cached in `doctor-last.json`; `dashboard` also answers to `browse`; awkit is Linux and WSL only in 0.x; `wire` and the config of other tools are written under the password-database home; the environment variables are limited to three `dashboard.*` keys; there are no `hooks:` or `repos:` keys in 0.x.

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
| Overlapping crontab writers lose updates (60 of 60 runs); awkit's one lock serializes awkit runs and the tools' installers run one after another; a window of about 30 ms remains for a foreign writer | Cron spike | Lock test; the window is documented |
| Block grammars differ per tool (end-less jobsctl block, a loose start rule that also matches an end line, a comment that looks like a start line) | Cron spike | Per-tool recognizer tests |
| A crontab with CR, no final newline, non-UTF-8 or 14 MB (about 3 s) is read and recognized without loss | Cron spike | Recognizer tests |
| Polling 20 commands per cycle costs 0.3 percent CPU every 15 s with asyncio | PTY spike | Refresh budget test |
| `--version` prints `0.0.0` for 15 of 21 tools | Inventory | `tool.version` reads the tool's own environment, else `--version` |
| Tools' current interfaces and CLIs differ from the registry rows | Inventory | The first issue: verify every tool's interface and update the adapters |
| Own templates cannot reproduce 6 of 13 blocks (a schema golden exists for memoctl only); each tool's own `cron install` has the correct content | Inventory of the tools' cron sections | Fake tool installers in the cron tests; `live` run |
| `json.loads` accepts a lone surrogate that `.encode('utf-8')` rejects; Textual `Static` parses markup by default | Reviews of the design | Sanitizer code-point enumeration; markup corpus |

## Modules

| Module | Responsibility |
|---|---|
| `gateway` | Every subprocess, file read of tool output and `crontab` call. |
| `config` | The hardened loader and the models. |
| `adapters` | The loader, the path language, argv filling and the override protocol (with `override_host`, the child-process entry point). |
| `readers` | The asyncio refresh worker and the per-tool read results with their age. |
| `sanitize` | The one sanitizer. |
| `model` | Rows with a fixed field set, attention items and chains from reads and links. |
| `actions` | The confirm recipes, the dialog binding and the action runner. |
| `cron` | The delegating installer (lock, per-tool runs, audit hashes) and the block recognizers. |
| `wire` | The drop-in writer. |
| `doctor` | The checks and the cache file. |
| `audit` | The reader, merger, pairing and own writer. |
| `tui` | The Textual views and the child-TUI handoff (the optional extra); the logic modules above never import it. |
| `cli` | Argument parsing and the exit-code mapping. |

## Data model

No database in 0.x. Files: `audit.jsonl`, `doctor-last.json`, `cron.lock` and `crontab.previous` in the state directory (see [Files](interface.md#files)). Everything else is derived on each refresh from tool output.

## Concurrency

See [Concurrency](interface.md#concurrency). Reads take no locks; `cron` takes one `flock` and runs the tools' installers one at a time; `wire` renames one file; the dashboard's refresh cycle never overlaps itself.

## Error handling

A failing tool never fails the dashboard: its data goes stale with an age and a marker. A failing adapter excludes only its tool. A refusal is an exit 20 with a reason. A `cron` run reads the crontab first and changes nothing when the read fails (only the exact empty-table message counts as empty); a tool whose installer fails is reported and the others still run (exit 12). A wire write that cannot be completed leaves the previous file, and the audit record shows `unknown` when the outcome cannot be known.

## Test strategy

- All subprocess and file access through `gateway`; fake tool binaries per repo in `tests/fakebin/`, copied from nothing shared.
- Pilot tests of the Textual views against fake readers (no snapshot tests; no fixed sleeps), including the confirm dialog: hidden typeahead, the scroll gate, a refresh while the dialog is open, and chrome kept apart from body.
- A hostile-string corpus through every view and every `--json` output, including a markup corpus (`[/]`, `[@click=...]`, `[link=...]`, `[b]`, unbalanced brackets) and a lone surrogate through every command; the sanitizer is checked over all 1,114,112 code points.
- Process tests (marker `process`): the terminal handoff (process groups, foreground handback), typeahead flush, SIGINT and SIGTERM, result-file atomicity.
- Cron: fake tool installers run in lexical order under the lock, per-tool block recognizer tests, crontab read failure and empty-table cases, the lock.
- Audit reading: rotated and truncated files, a partial last line, an over-long line, a non-regular file.
- Every schema pattern ends with `(?![\s\S])` and has a trailing-LF negative case.
- Schema validation of every `--json` output, with positive and negative samples.
- A cross-tool smoke suite in `tests/e2e/` that runs the 0.x commands against fake binaries on `PATH` (architecture §17).
- `live` tests, never in CI: `cron install` against a real crontab and real tools with a backup and a byte-identical restore.
- `make verify`, the schema check at CI's pinned version, and `make mdlint` before every pull request.

## Dependencies

The core uses the standard library, PyYAML and Pydantic; Textual `>=8.2,<9` lives only in the `tui` extra. PyYAML is wrapped in a strict `SafeLoader` subclass that refuses anchors, aliases, non-core tags, duplicate keys, NUL and lone surrogates. Pydantic validates the configuration and the adapter models. No `jq`, JSONPath, `croniter` or template library.

## Open items (for the 1.x design pass)

- Rules syntax, the event vocabulary, the retry count and backoff, and the action ledger schema.
- The state graph schema and what is rebuilt.
- The when-to-merge rule: its trigger, the repo opt-in key, the gate policy and input, and who creates the pr-watch watch the rules depend on. Its inputs are weak today: pr-watch's commands are stubs and the merge gate cannot be enforced until a human sets it.
- Rule R1 (`review-respond check --pr`): the flag must exist in review-respond's interface.
- Rule R2 (a merged or closed pull request triggers `ticket-work sync`) has no producer yet, because nothing watches the user's own pull requests.
- `notify-tick` and the early-tick hooks of `wire`.
- Hook-only attention reasons of the tools (for example review-watch poll and post failures), which arrive with `notify-tick`.
- Link re-verification and a `forge` link tag, which come with the rules engine.
- Actions that need human-written text, a second chosen object, multi-select or continuation of a refused call, and reorder with a target.
- Cross-tool audit correlation and the cross-tool `doctor` checks (queue grace times, protect labels, environment names).
- Facts the first implementation issue must confirm per tool: each `cron install`'s flags, interval forms and `--dry-run` support, the hook names and whether a hook `cmd` accepts an argv list, which list commands mutate state, `--limit` maxima, every action's `--dry-run --json` and pass fields, `tui` arguments and result-file intents, audit pairing descriptors, `validate` exit codes and warning paths.
- Reboot recovery as a command.
- Whether the config hash warning (a hardening step left out of 0.x) is wanted.

## Deviations from the design guide

- `awkit dashboard` is also accepted as `awkit browse`.
- No `hooks:` or `repos:` config keys in 0.x; no hooks exposed.
- Config and overlay are read only under the password-database home, with ownership and symlink refusal (as for the notifiers and notice-route).
- Linux and WSL only in 0.x; every command except `validate` and `adapters` refuses elsewhere.
- Durations are `<n><ms|s|m|h|d>` with no bare numbers or fractions, where the guide also accepts other forms.
- No `log.jsonl` in 0.x.
- The dashboard's actions have no awkit command of their own: each is a documented command of the owning tool, shown by `adapters show`.
- Actions needing human-written text, a second chosen object, multi-select or continuation of a refused call, and reserved human flags other than `--allow-tainted`, are not in 0.x.
- `awkit cron` runs the tools' own installers; awkit never writes the crontab.
