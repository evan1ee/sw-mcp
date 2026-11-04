# 13.2 Project Store and Job Journal

> Specification v1.20, section 13.2. Index and section map: [specifications/README.md](../specifications/README.md).

The layout, write rules and retention of the project store (13.1, ADR-033), and the job journal that lets the core service (ADR-041) account for every job after a crash (ADR-032). Where a project and its store are is 12.5.

## 13.2.1 Layout

```
.cad/
├── store.json                    store_version, created_at, project root (ADR-042)
├── index.json                    latest revision per document, drawing and part records; rebuildable
├── config.toml                   project configuration (13.3), optional
├── .gitignore                    written by the store (13.2.5)
├── .lock                         held by the core service while the store is open
├── modules/<module>/<document_id>/<revision>.json     IR module revisions (3.4.5)
├── parts/<part_key>.json         part identity: PDM ID or path + fingerprint, read-graph document, history (13.1)
├── drawings/<drawing_id>.json    drawing record: path, fingerprint, intent, latest layouts, snapshot and report
├── derived/
│   ├── resolved-schemes/<key_hash>.json                  (11.10.1)
│   ├── layouts/<drawing_id>/<seq>-planned.json, <seq>-as-built.json   (11.11)
│   └── plans/<plan_hash>.json                            execution plans
├── snapshots/<drawing_id>/<snapshot_id>.json             Drawing Geometry Snapshots (11.5.1)
├── reports/<report_id>.json
├── jobs/<job_id>/job.json, journal.jsonl
└── backups/<drawing_id>/<timestamp>.SLDDRW               (ADR-046)
```

**IDs** made by the store are a prefix plus a ULID: `job_`, `rep_`, `snap_`, `drw_`. `<part_key>` is `pdm-<id>` for vaulted parts, otherwise `fp-<first 16 hex of the fingerprint>`. `<key_hash>` and `<plan_hash>` are content hashes (3.4.4).

## 13.2.2 Writing

- **One writer.** Only the core service writes. It holds an exclusive OS lock on `.cad/.lock` while it has the store open. A second core, for example on another machine through a network share, fails to open the store with `STORE_LOCKED`.
- **Atomic files.** Every file is written to `<name>.tmp-<random>` in the same folder, flushed to disk, then renamed over the target. No file is ever modified in place except by append to `journal.jsonl`.
- **Immutable revisions.** A module revision file, snapshot or report is written once and never changed (3.4.5). Records that change (`parts/`, `drawings/`, `job.json`, `index.json`) are replaced atomically as a whole.
- **Index.** `index.json` is a cache. On open, if it is missing, unreadable or older than any file it indexes, the store rebuilds it by scanning. Nothing is stored only in the index.
- **Serialized writes per document.** Mutating `store` tools that touch the same document run one after another, and each checks `expected_revision` (13.1) at the moment of writing.

## 13.2.3 Job journal

Each job has `jobs/<job_id>/job.json` (current state, replaced atomically) and `journal.jsonl` (append-only, one JSON object per line):

| Record `type` | Written | Fields beyond `type`, `ts`, `job_id` |
| --- | --- | --- |
| `state` | On every lifecycle transition (8.4) | `from`, `to`, `reason` |
| `batch_sent` | Before an `ops.apply` batch is sent | `batch_seq`, `operation_ids`, `documents` |
| `op_result` | For each operation result received | `operation_id`, `ok`, `error_code` |
| `snapshot` | After a read-back | `snapshot_id`, `sheet` |
| `document` | When the job opens, saves or closes a document (ADR-046) | `path`, `action`, `owned` |
| `note` | Diagnostics worth keeping | `message` |

- A `batch_sent` record is flushed to disk **before** the batch goes to the add-in. Without that record, nothing can have been sent.
- Operation IDs are `<job_id>:<seq>`, unique for ever, so a retried job never repeats an ID (ADR-032).

**After a crash** (Phase 1 behavior; recovery proper is P2, 8.5):
1. The new core reads every `job.json` that is not in a final state (COMMITTED, ABORTED, FAILED).
2. On reconnecting to the add-in, it asks for the operation IDs the add-in completed (`session.completed_operations`, ADR-036) and records them as `op_result` with `recovered: true`.
3. It marks each such job FAILED with `EXEC_INTERRUPTED`, lists the documents it touched as "state unknown" in the job record, and never resumes or resends anything.
4. Queued jobs that never started are marked ABORTED with `EXEC_INTERRUPTED`.

`recover_execution` (Phase 4) builds on the same journal.

## 13.2.4 Retention

| Data | Kept | Setting (13.3) |
| --- | --- | --- |
| Module revisions | For ever | — |
| Part and drawing records | For ever | — |
| Snapshots | The last 10 per drawing, plus every snapshot a kept report refers to | `store.snapshot_keep` |
| Reports and job folders | 7 days after the job ends, plus any report a drawing record refers to | `core.job_retention_days` |
| Planned and as-built layouts | The last 10 per drawing, plus the latest as-built (needed for pin detection, 11.11) | `store.snapshot_keep` |
| Resolved Schemes and plans | While a kept report, drawing record or job refers to them | — |
| Drawing backups | The last 5 per drawing (ADR-046) | `store.backup_keep` |

Clean-up runs when the core starts and once a day. It deletes only files nothing kept refers to.

## 13.2.5 Version control

The store writes `.cad/.gitignore` on creation. By default, `modules/`, `parts/`, `drawings/`, `config.toml` and `store.json` are meant to be committed: they hold authored intent and the records that identify drawings. `derived/`, `snapshots/`, `reports/`, `jobs/`, `backups/`, `index.json` and `.lock` are ignored, because they are regenerable, large or local. A project that wants its reports under version control removes the line from `.gitignore`.
