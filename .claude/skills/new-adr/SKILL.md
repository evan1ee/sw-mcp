---
name: new-adr
description: Create a new Architecture Decision Record from the template and register it in the ADR index
disable-model-invocation: true
---

Create the ADR described in the arguments:

1. Read `docs/adr/template.md` and `docs/adr/README.md`. Take the next free number (highest `ADR-NNN` in the index + 1; IDs are stable and never reused).
2. Create `docs/adr/ADR-NNN-<kebab-slug>.md` from the template: status, source (spec version), decision, rationale, where it applies (links with section numbers).
3. Add a row to the table in `docs/adr/README.md` and extend the intro sentence listing which version added which ADRs.
4. Mark decisions made without the owner as **[Builder's call]**.
5. If the ADR changes the specification, follow with `/spec-change`.
