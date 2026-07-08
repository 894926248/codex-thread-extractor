# Development

This repository contains a Codex plugin and skill payload.

## Source Layout

```text
skills/codex-thread-extractor/   portable skill payload
.codex-plugin/                   Codex plugin metadata
scripts/                         repository maintenance scripts
docs/                            public project documentation
```

`SKILL.md` is runtime context. Keep installation notes and release process
outside it.

## Validation

Run this before committing:

```powershell
python scripts\verify_plugin.py
```

It checks:

- Codex plugin manifest
- skill metadata
- Python compilation
- extractor tests
- JSON metadata files

## Local Codex Sync

During development, sync the portable skill payload to the local Codex skills
directory:

```powershell
python scripts\sync_to_codex.py
```

Start a new Codex conversation after syncing.

## Public Release Checklist

Before pushing:

1. Run `python scripts\verify_plugin.py`.
2. Remove generated caches such as `__pycache__/`.
3. Scan for local paths and secrets.
4. Update `RELEASE_NOTES.md` and `docs/releases/<version>.md`.
5. Check `git status --short`.
6. Commit the release notes.
7. Create an annotated tag:

   ```powershell
   git tag -a <version> -m "<version>"
   ```

8. Push the branch and tag:

   ```powershell
   git push origin main
   git push origin <version>
   ```
