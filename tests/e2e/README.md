# Cross-tool smoke suite

End-to-end smoke tests that run the real `awkit` tools together (architecture section 17).

- Real tools are installed and invoked by name; external programs are replaced by **fake binaries** (`gh`, `glab`, `tmux`, `claude`, ...) in `tests/e2e/fakebin/`, placed first on `PATH`.
- Each fake returns canned output for the invocations a scenario expects and logs every invocation (argv and stdin) so tests can assert on what the tools did.
- Fake bins are copied per repo, never shared with or imported from other repos.
- Scenarios follow the key flows in architecture section 10 (review request, ticket work, review response, attention and notifications).
- Real-world tests (real hosts, real `claude`) are opt-in, manually triggered, and never run in CI.

Status: no scenarios yet; they are written once the tools' interfaces exist.
