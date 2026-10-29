# awkit: design

Status: Seeded from awkit architecture v1.4; not yet designed.

## Role and layer

`awkit` is the harness, the top layer (L4). It is the only component aware of the others, and it is optional: everything else works without it. It knows the other tools only through configuration and adapters; tools never adapt to it (architecture section 3.1).

## Responsibilities

From architecture section 7.

### Tool registry and adapters (section 7.1)

- `awkit` reads a **tool registry** from its config (`~/.config/awkit/config.yaml`) listing which tool fills each **role**, e.g. `roles: {githost: forgectl, tickets: ticketctl, notify: notice-route}`. (This is distinct from the **interface registry** in `awkit-docs`.)
- Each registered tool has an **adapter** describing how `awkit` talks to it:
  - **Declarative YAML first:** command templates (e.g. `list: "jobsctl list --json --queue {queue}"`), jq/JSONPath mappings from tool output into the harness model, trigger definitions, and `periodic:` declarations (commands that should run on a schedule).
  - **Escape hatches:** any single operation, or a whole adapter, can instead be a Python function or an external executable speaking a harness-defined stdin/stdout JSON protocol. This protocol belongs to the harness; tools never see it.
- Adapters for our tools and common third-party CLIs ship in the `awkit` repo. A user overlay at `~/.config/awkit/adapters/` adds or overrides adapters (e.g. a private adapter pointing a role at an organization-internal tool). Tool repos never mention the harness.

### Process model: tick and run (section 7.2)

- `awkit tick` does one unit of work: poll adapters that are due, diff their snapshots against the last ones, derive harness events, update the state graph, and evaluate rules.
- Cron runs `awkit tick` periodically (interval in awkit config, default 1 minute).
- `awkit run` (and the dashboard while open) loops `tick` at short intervals and accepts early-tick triggers: per-adapter poll intervals; file watchers on a tool's public files (`log.jsonl`, `audit.jsonl`) or other paths an adapter declares (only while the loop runs; file watching under WSL `/mnt/c` is unreliable), purely as a trigger for an early poll; pushes from tool hooks wired to `awkit notify-tick`.
- **Tick lock:** held for one tick only. Several loops may coexist (cron, `awkit run`, an open dashboard); at most one tick executes at a time and the others serialize. A dashboard opened while `awkit run` is active still runs its own loop.
- **Idempotency:** ticks are idempotent with respect to state; anything missed is caught by the next poll. Rule actions are recorded (with the event id) before execution, with their result after, and skipped if already recorded; a failed action is retried up to N times (configurable). Rule actions run detached or via jobsctl and never block the tick. Events are internal to `awkit` and never required by tools. Every workflow keeps its periodic cron fallback even when rules trigger it early.

### Wiring hooks (section 7.3)

- `awkit wire <tool>` shows the exact hook registrations that would let that tool call `awkit` (e.g. "on `on-merged`, run `awkit notify-tick --source pr-watch`") and applies them on confirmation; `--yes` skips confirmation; `awkit unwire <tool>` reverses it.
- `awkit wire` writes only the drop-in file `~/.config/<tool>/config.d/awkit.yaml`, which the tool merges after its `config.yaml` (hook lists are appended); it never edits `config.yaml`, and `awkit` never edits tool config any other way.
- `awkit` learns about session changes primarily through tools' lifecycle hooks (and otherwise by polling): for agents, the recommended source is agent-spawn's `post-state-change`; claude-session's own hooks serve standalone sessions. Wiring both tools' state hooks to notifications produces duplicates and should be avoided.

### State graph (section 7.4)

- Nodes: ticket, worktree, agent (Claude session), tmux window, job, PR, review draft, gate decision (from `gatectl decisions --json`), notification (from `notice-route history --json`).
- Edges are derived mostly from labels on lower-tool objects (`ticket=KEY`, `pr=host/<full project path>#N`, `repo=host/<full project path>`, `kind=...`, `owner=<tool>`, `job=<id>`, `rw-item=<id>`) plus branch names. `awkit` stores only links it alone can infer, so its state is largely disposable and can be rebuilt from tool outputs.

### Rules (section 7.5)

"When X then Y", evaluated on derived events. Notifications are wired directly from tools' hooks to notice-route by default, so rules do not send notifications unless the user adds such a rule. Examples:

| When | Then |
|---|---|
| pr-watch `comment`, `review_comment` or `review` event on a PR for which agent-spawn has an agent labeled `pr=` | `review-respond respond <pr>` |
| pr-watch: PR merged or closed | `ticket-work sync` |
| pr-watch: the user's PR approved, CI green, mergeable, repo opted in | `gatectl check auto-merge` (its input includes the PR head sha); only if the JSON shows `"enforced": true` and `"decision": "allow"` → `forgectl merge --yes --expected-head <the sha the gate evaluated> --decision-id <id>` (public default: notify only) |
| jobsctl: job held or failed | `review-watch poll` / `review-respond check` / `ticket-work sync` for the owning workflow, so it resolves or reports the job early |

Attention items are not rule actions; the dashboard derives them.

### Dashboard TUI (section 7.6)

- Opened with `awkit dashboard` (or `awkit` with no arguments).
- Cross-tool views only `awkit` can build: the **attention list** ("needs you"), ticket → agent → PR → review chains, and recent events. Attention items are derived from tool records and hooks: agents with `needs_attention` (`agent-spawn list --needs-attention`: unreported, escalated, blocked, failed, lost), held and failed jobs, review drafts awaiting accept, each tool's pending confirmations, and sessions in `needs-input`. Idle sessions are not listed.
- A launcher for the tools' own TUIs. Drilling in **suspends** the dashboard and runs the child TUI in the same pane in the foreground; the dashboard redraws with state intact when the child exits. Targeted drill-in passes arguments such as `--focus KEY-12`. If the child supports `--result-file`, `awkit` reads the result (in the child's vocabulary) and its adapter translates the intent (e.g. `start` → enqueue work, `back` → return to the dashboard, `open` → open another TUI). Children without it just return.
- Actions from the dashboard go through the owning tool's CLI (start work, accept a review, confirm a pending action, attach to an agent, resume, acknowledge, teardown). The dashboard confirms in its own dialog and then passes `--yes --actor human:<user>`. Reorder maps to whichever tool holds the item: ticket-queue for candidates not yet started, jobsctl for enqueued work.

### Other harness commands (section 7.7)

- `awkit audit`: merges every tool's `audit.jsonl` into one timeline, filterable by label, PR or ticket.
- `awkit notify-tick [--source <tool>]`: requests an early tick and returns immediately.
- `awkit cron install|uninstall`: writes crontab entries (explicit `PATH` including `~/.local/bin`, optional user-owned env-file prefix) from each adapter's `periodic:` declarations; there is no hard-coded list. The bundled adapters declare `awkit tick`, `jobsctl run`, `jobsctl reconcile`, `review-watch poll`, `pr-watch poll`, `ticket-work sync`, `ticket-queue refresh`, `review-respond check`, `agent-spawn reconcile` (which runs `claude-session reconcile` first), `memoctl prune` and `notice-route flush`, plus opt-in `ticket-work start --auto` and `agent-spawn prune`. Tools with their own `cron install|uninstall` write the same tagged crontab block per tool (`# <tool> managed`), so one replaces the other.
- **Reboot recovery:** `jobsctl reconcile`, then `agent-spawn reconcile` (which runs `claude-session reconcile`); the workflows then resume through their normal polls.
- `awkit doctor`: checks that registered tools are installed and respond, adapters load, crontab is present, required env vars are set, required binaries resolve in a non-interactive shell (with each kind's `PATH` override applied), and reports the effective kind profiles (`claude-session kinds --json`).

### Cross-tool testing (section 17)

The end-to-end smoke suite lives in this repo: it runs real tools against fake binaries (`gh`, `glab`, `tmux`, `claude`) placed first on `PATH`, returning canned output and logging invocations. Fake bins are copied per repo, not shared. See `tests/e2e/README.md`.

## Uses

`awkit` has no hard dependency on any tool; which tools fill which roles is configuration.

| Dependency | Binding |
|---|---|
| Registered tools (ours and third-party) | C (adapter) by architecture section 7.1; adapter format details TBD, decided in this design session |
| `crontab` | TBD (A/B/C), decided in this design session |
| Third-party libraries (Textual for the dashboard; YAML/Pydantic for config and adapters) | to be justified in this design session (design guide section 3) |

## Architecture sections to read

- Section 3 (core principles: tools never adapt to the harness, layered composition, edge bindings).
- Section 7 (the harness) in full.
- Section 8.4 and 9 (session states and agent lifecycle; the dashboard surfaces them).
- Section 12 (autonomy and gates: when-to-merge rule, `--yes` rules for the dashboard and rules).
- Section 13 (security: what automation may and may not pass on).
- Section 14 (audit: `awkit audit` merges the per-tool logs).
- Section 15 (notifications: direct wiring by default; avoid duplicate state hooks).
- Section 17 (testing: the cross-tool smoke suite lives here).
- Design guide sections 8 (hooks and drop-ins), 10 (TUIs; the dashboard style extends this) and 4.4 (confirmations).

## Constraints (decided)

From architecture section 20: none (the harness contracts are in section 7).

## Open topics

From architecture section 20:

- tool registry/adapter format details
- harness state graph schema
- harness-level reconcile
- rules syntax
- rule-action retry count
- dashboard panels and actions
- dashboard style
- where the dashboard runs
- when-to-merge rule
- TUI internals
- change detection details

## Decisions

| Decision | Rationale | Date |
|---|---|---|

## Questions for the design session

1. What is the exact tool registry and adapter file format (YAML schema for command templates, mappings, triggers and `periodic:`; the Python and external-executable escape-hatch protocol; overlay precedence)?
2. What is the schema of the harness state graph (node and edge types, what is stored versus rebuilt from tool outputs)?
3. What does harness-level reconcile do, and how does it relate to the tools' own `reconcile` commands?
4. What is the rules syntax ("when X then Y" on derived events, conditions, actions)?
5. How many times is a failed rule action retried, and with what backoff?
6. Which panels and actions does the dashboard offer?
7. What is the dashboard style (extending design guide section 10)?
8. Where does the dashboard run (pane, window, session)?
9. What is the when-to-merge rule (inputs, gate policy, public default of notify only)?
10. What are the TUI internals (Textual structure, suspend/resume of child TUIs, result-file handling)?
11. How are changes detected (snapshot diffing, per-adapter poll intervals, file-watch triggers, event ids)?
