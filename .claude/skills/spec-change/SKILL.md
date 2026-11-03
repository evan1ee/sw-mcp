---
name: spec-change
description: Apply a change to the specification in docs/ with version bump, header updates and CHANGELOG entry
disable-model-invocation: true
---

Apply the spec change described in the arguments, following AGENTS.md "Source of truth":

1. Read `docs/README.md` and `docs/specifications/README.md` (section map and current version), then the topic file being changed. Check `docs/adr/README.md`: do not contradict an ADR. If the change needs a different decision, add or amend an ADR first (use `/new-adr`).
2. Edit the topic file. Keep section numbers stable; never renumber.
3. Bump the version (minor) in `docs/specifications/README.md` and in the header line of every spec file, and update `SPEC.md` / date if they carry the version.
4. Add a "What changed in X.Y" entry at the top of `docs/specifications/CHANGELOG.md`, matching the existing entries' style.
5. If the change resolves or reveals a gap, update `docs/specifications/open-decisions.md`.
6. Grep for stale version strings (`rg "1\.16"` with the old version) and for broken section references.
7. Show the diff summary. Do not commit unless asked.
