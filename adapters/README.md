# Bundled adapters

One YAML file per tool, validated by `schemas/adapter.json`. The format is specified in [docs/interface.md](../docs/interface.md#adapters); an overlay in `~/.config/awkit/adapters/` replaces a bundled adapter of the same tool. Organization-specific adapters never belong in this repo.

No adapters ship yet; the first implementation issue writes them from each tool's verified interface.
