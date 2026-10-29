# CLAUDE.md (awkit)

`awkit` is the harness: the optional top-layer (L4) tool that knows about the other tools only through configuration and adapters. Every other tool must work fully standalone without it, and `awkit` itself must work with whatever subset of tools (ours or third-party) the user registers.

**Naming.** Tools have no shared prefix; see design guide §1 naming rules.

## Read first

1. `../awkit-docs/architecture.md`: section 7 (the harness) and the `awkit` entry in section 20; also sections 3 (principles), 12 (autonomy and gates), 14 (audit), 15 (notifications) and 17 (testing, the cross-tool smoke suite lives here).
2. `../awkit-docs/design-guide.md`.
3. `docs/design.md` in this repo.

## Rules

- **Open source, no confidential information.** Never add company names, hostnames, ticket project keys, custom-field IDs, repo or org names, people's names or private skill/plugin names. Organization specifics belong in the user's config and adapter overlay (`~/.config/awkit/adapters/`).
- **Never import sibling repos.** Read their `docs/interface.md` and `schemas/` by path only. Copying a sibling's schema files into tests, pinned to a version, is allowed.
- **The harness adapts to tools, never the reverse.** Never require a tool to change for `awkit`. Talk to tools only through their CLIs and documented `--json` output; never read a tool's `state.db`. `awkit wire` writes only `~/.config/<tool>/config.d/awkit.yaml`; never edit a tool's `config.yaml`.
- **Interface first.** Write `docs/interface.md` and `schemas/` before implementation.
- **Versioning.** Semver. A breaking interface change is, before 1.0, a `feat` commit whose title names the break (never `!` before 1.0), and from 1.0 on a `!` commit; the title becomes the changelog line (details go in the PR body). Either way, update `awkit-docs/interface-registry.md`. Never hand-edit CHANGELOG.md or the version.
- **`make verify` before every commit.**
- **All subprocess and HTTP calls go through `src/awkit/gateway.py`.**
- **Never destroy work.** Never run destructive git commands (reset, checkout of files, clean, restore, force-push). Never kill processes by pattern; signal only an exact PID this tool started (verified by PID plus start time) or a process group it created for a hook.
- Automation never passes `--yes` to bypass a confirm default, except when an enforced gate allows the action or config explicitly enables it (architecture §12.4, design guide §4.4); never passes `--force`; the dashboard passes `--yes --actor human:<user>` after its own confirmation.
- **Minimize dependencies.** Justify each one in `docs/design.md`.

## Workflow

1. Start with a design session that resolves the open topics in `docs/design.md` and records the decisions there.
2. Write `docs/interface.md` and `schemas/`.
3. Implement test-first. Cross-tool end-to-end smoke tests live in `tests/e2e/`.

## Repository workflow

- Work in a git worktree on a branch named `<type>/<short-slug>`, never in the main checkout (design guide section 17).
- PR titles are Conventional Commit headers; they become the squash commit, the version bump and the changelog line (architecture section 18.3). Do not use `!` before 1.0 (a breaking change before then is a `feat` whose title names the break).
- Never use `--no-verify`. Check PR titles, bodies and comments with `guard text` where the private-content guard is installed (architecture section 18.7).
- Never merge a PR without the maintainer's explicit instruction for that PR; merges go through `awkit-ci`'s `scripts/pr-merge` (architecture section 18.6).
- Never hand-edit `CHANGELOG.md` or the version in `pyproject.toml`; the release job owns them.
