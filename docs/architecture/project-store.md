# 13.2 Project Store and Job Journal

> Specification v1.38, section 13.2. Index and section map: [specifications/README.md](../specifications/README.md).

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
├── reports/<report_id>.json, <report_id>.meta.json
├── jobs/<job_id>/job.json, journal.jsonl, evidence.json (`plan` jobs, 8.9.6)
└── backups/<drawing_id>/<timestamp>.SLDDRW               (ADR-046)
```

**IDs** made by the store are a prefix plus a ULID: `job_`, `rep_`, `snap_`, `drw_`. `<part_key>` is `pdm-<id>` for vaulted parts, otherwise `fp-<first 16 hex of the fingerprint>`. `<key_hash>` and `<plan_hash>` are content hashes (3.4.4).

**Records [Builder's call].** Their schemas are `$defs` of `schemas/store/v0.json`; readers are lenient (ADR-042). Times are UTC ISO 8601 with milliseconds; paths are normalized (12.5).

| File | Contents |
| --- | --- |
| `store.json` | `store_version` (`0.1`), `created_at`, `project_root`. A store whose major version this core does not know fails to open with `STORE_CORRUPT` (`details.reason: store_version`) |
| `index.json` | `built_at`, and `drawings`: `drawing_id` → `{path, fingerprint}`. Phase 1a indexes nothing else; jobs and reports are found by their paths |
| `drawings/<drawing_id>.json` | `drawing_id`, `path`, `fingerprint`, `produced` (`false` for a drawing the system did not make), `drawing_intent` (null in Phase 1a), `latest_snapshot_id`, `latest_report_id`, `updated_at` |
| `reports/<report_id>.json` | The report (11.5.4), exactly as built; nothing is added to it |
| `reports/<report_id>.meta.json` | `report_id`, `execution_id`, `drawing_id`, `snapshot_id`, `created_at`, `job_warnings` (8.4). Written once, before the report, and deleted with it |
| `jobs/<job_id>/job.json` | `job_id`, `job_type`, `state`, `created_at`, `started_at`, `ended_at`, `request_id`, `arguments`, `project_root`, `drawing_id`, `fingerprint`, `progress`, `snapshot_id`, `report_id`, `error`, `warnings`, `documents` (`path`, `owned`, `state`: `known` or `unknown`), `next_op_seq`, and for `plan` jobs `part_result` (below) |
| `parts/<part_key>.json` (part chain MVP) | `part_key`, `path`, `fingerprint`, `produced` (`true` for a part the system built), `graph` (the pinned `part:<id>@<revision>`), `job_id`, `updated_at`. Written only when a `plan` job reaches COMMITTED. `<part_key>` is `fp-<first 16 hex of the fingerprint>` (above). Additive to `schemas/store/v0.json`. From roadmap A3 it also holds `feature_ids` and `measured`, so reconciliation outlives the job folder (8.9.6) |
| `part_result` in `job.json` (part chain MVP) | `path` (the target), `fingerprint`, `feature_ids` (node ID to `feature_id`, 6.5.3), `checks` (10.2.1) and `measured` (the converted `part.measure` values). Additive to `schemas/store/v0.json`; `get_execution_status` returns it (12.4.5) |

**Plan key [Builder's call].** A file `derived/plans/<plan_hash>.json` is named by the hash of the plan's canonical form and by nothing else (6.7.4). The store writes it only if no file of that name exists, and a plan that already exists is reused.

**Matching a drawing** that has no drawing ID property (13.1): a record with the same path is the drawing, and its fingerprint is updated; otherwise a single record with the same fingerprint is the drawing moved, and its path is updated; otherwise a new record is made. Two or more fingerprint matches make a new record and a job warning (`drawing_match_ambiguous`).

**Stores the core knows.** The core lists every store it has opened in `%LOCALAPPDATA%\sw-mcp\known-stores.json` (`store_dir`, `project_root`), written atomically. At start it opens each listed store that still exists, which runs recovery (13.2.3) and clean-up (13.2.4) and lets any front-end find a job or report by ID alone. A store locked by another core is skipped and logged.

## 13.2.2 Writing

- **One writer.** Only the core service writes. It holds an exclusive OS lock on `.cad/.lock` while it has the store open. A second core, for example on another machine through a network share, fails to open the store with `STORE_LOCKED`.
- **Atomic files.** Every file is written to `<name>.tmp-<random>` in the same folder, flushed to disk, then renamed over the target. No file is ever modified in place except by append to `journal.jsonl`.
- **Immutable revisions.** A module revision file, snapshot or report is written once and never changed (3.4.5). Records that change (`parts/`, `drawings/`, `job.json`, `index.json`) are replaced atomically as a whole.
- **Index.** `index.json` is a cache. On open, if it is missing, unreadable or older than any file it indexes, the store rebuilds it by scanning. Nothing is stored only in the index.
- **Serialized writes per document.** Mutating `store` tools that touch the same document run one after another, and each checks `expected_revision` (13.1) at the moment of writing.

**How [Builder's call].** All file effects go through the `FileSystem` port (G2); the store logic is `cad_application.store.FileStore` over that port, and the in-memory `MemoryFileSystem` makes it the `FakeStore` of G2, so tests and production share one store implementation.
- **Lock.** `.lock` is opened and its first byte locked with a non-blocking exclusive byte-range lock (`msvcrt.locking`, `LK_NBLCK`), held until the store closes. Failure to take it is `STORE_LOCKED`. The lock file stays empty, so nothing about the holder is disclosed.
- **Atomic write.** Write `<name>.tmp-<8 random hex>`, flush, `fsync`, then `os.replace` over the target; on any error the temporary file is removed. Leftover `*.tmp-*` files are deleted when the store opens. Immutable files (revisions, snapshots, reports and their meta) are written only if absent; an existing one is never replaced, and an attempt is a programming error.
- **Journal append.** One JSON object and `\n` per record, flushed and `fsync`ed before the call returns. A final line without `\n` is a torn write from a crash and is ignored; any other unreadable line makes that job's records `STORE_CORRUPT`.
- **I/O errors** (register J13). A store file that cannot be read or written for a reason other than the lock (access denied, a full disk, a folder where a file belongs) is `STORE_UNAVAILABLE` (`after_fix`), with `details.reason: io_error` and never the OS message, which can hold paths and user names. A tool call answers it as its error; a running job ends FAILED with it. A file that reads but does not parse, including JSON nested too deeply to decode, is `STORE_CORRUPT`. A `job.json` whose `job_id` differs from its folder name is `STORE_CORRUPT`. Everything written is strict JSON: `NaN` and infinities are refused before writing.
- **Order.** A state change appends its `state` record first and then replaces `job.json`. On open, if the last `state` record and `job.json` disagree, the journal wins and `job.json` is rewritten. Creating a job writes its first `state` record (`from: null`, `to: PLANNED`) before `job.json`.

## 13.2.3 Job journal

Each job has `jobs/<job_id>/job.json` (current state, replaced atomically) and `journal.jsonl` (append-only, one JSON object per line):

| Record `type` | Written | Fields beyond `type`, `ts`, `job_id` |
| --- | --- | --- |
| `state` | On every lifecycle transition (8.4) | `from` (null for the first), `to`, `reason`, and `error` (ADR-037 object) when `to` is FAILED or ABORTED |
| `batch_sent` | Before an `ops.apply` batch is sent | `batch_seq`, `operation_ids`, `documents` |
| `op_result` | For each operation result received | `operation_id`, `ok`, `error_code`, and `recovered: true` when learned after a crash |
| `op_verified` | After an operation's contract is judged (10.2.2) | `operation_id`, `node`, `feature_id`, `observation`, `checks`, `status` |
| `snapshot` | After a read-back | `snapshot_id`, `sheet` |
| `document` | When the job opens, creates, saves or closes a document (ADR-046) | `path`, `action` (`open`, `create`, `save`, `close`), `owned` |
| `publish_intent` | Before a `plan` job renames its working file to the target (8.4.1) | `path`, `fingerprint` |
| `published` | After that rename succeeded (8.4.1) | `path`, `fingerprint` |
| `note` | Diagnostics worth keeping | `message` |

- A `batch_sent` record is flushed to disk **before** the batch goes to the add-in. Without that record, nothing can have been sent.
- Operation IDs are `<job_id>:<seq>`, unique for ever, so a retried job never repeats an ID (ADR-032).

**After a crash** (Phase 1 behavior; recovery proper is P2, 8.5):
1. The new core reads every `job.json` that is not in a final state (COMMITTED, ABORTED, FAILED).
2. On reconnecting to the add-in, it asks for the operation IDs the add-in completed (`session.completed_operations`, ADR-036) and records them as `op_result` with `recovered: true`. Entries in `failed_operations` (8.7) are recorded the same way, with `ok: false` and their `error_code`.
3. It marks each such job FAILED with `EXEC_INTERRUPTED`, lists the documents it touched as "state unknown" in the job record, and never resumes or resends anything.
4. Queued jobs that never started are marked ABORTED with `EXEC_INTERRUPTED`.

**In Phase 1a [Builder's call].** `check_drawing` writes `state`, `batch_sent` and `op_result` (for its `document.open` and `document.close`, 8.7), `document` (`action`: `open` or `close`, with `owned`), `snapshot` and `note`. Steps 1, 3 and 4 run when the store opens, after the order rule in 13.2.2. In step 3, "documents it touched" are those with a `document` `open` record and no `close` record; they become `documents` entries with `state: unknown`. Step 2 runs on the first backend connection after that: only operation IDs that appear in the job's `batch_sent` records and have no `op_result` are recorded. A crash leaves no job running: a job in VALIDATED, EXECUTING or VERIFYING is FAILED, one in PLANNED is ABORTED.

**In the `plan` job (part chain MVP) [Builder's call].** The job writes `state`, `batch_sent`, `op_result`, `op_verified`, `document`, `publish_intent`, `published` and `note` (including the reuse of an existing plan, 6.7.4). A `document` `create` record is written before `part.create` is sent, so the working part counts as touched, with `state: unknown`, even if the core died during `part.create`. Recovery never resumes a `plan` job. If a job has a `publish_intent` record and no `published` record, recovery compares the target file's fingerprint with the recorded one. On a match the job stays FAILED with `EXEC_INTERRUPTED` and gains the warning `published_unconfirmed`, which names the file; the file is never adopted silently, and no part record is written. On a mismatch, or no file, the job is FAILED with `EXEC_INTERRUPTED` and no warning. The journal reader's action mapping and the store schema change together, because an unknown `document` action would otherwise be read as `open`.

**Edge cases [Builder's call]** (register J18).
- Recovery runs once per store per core start, whenever the store is first opened: at start for every listed store, and on the first `open_for` of a store that was not listed (a new store, or one missing from an unreadable list). No job of a store is visible through `status` before its recovery has run.
- The journal wins only with a `state` record whose `from` is the state in `job.json`, or a later record of a chain that starts there; a last record that is not reachable from `job.json` by the 8.4 table makes the job `STORE_CORRUPT`, and recovery leaves it untouched.
- A job in RECOVERY cannot arise in Phase 1. Recovery leaves it untouched, reports it, and clean-up never deletes it; Phase 4 defines it.
- A job folder without `job.json` (a crash between the first `state` record and `job.json`) is an orphan: logged, reported as `EXEC_NOT_FOUND`, never resumed and never deleted by clean-up. Its journal cannot be turned into a job, since the arguments are only in `job.json`.
- An unreadable `known-stores.json` is treated as empty and logged as a warning; it is rewritten on the next store opened. Stores it listed are recovered when next opened (first rule).
- Snapshot results are validated (11.5.1 schema and the canonical form, 3.4.4) before the snapshot file is written; an invalid one fails the job with the issue's code (8.4) and is not stored.

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

Clean-up runs when the core starts and once a day. It deletes only files nothing kept refers to. In Phase 1a it runs for each store right after that store's recovery, and then once a day on the worker thread between jobs, never while a job runs **[Builder's call]**.

**What "refers to" means [Builder's call].** A drawing record refers to its `latest_report_id` and `latest_snapshot_id`; a report's meta file refers to its `snapshot_id`; a job that is not final refers to everything in its record, and its folder is never deleted. A job's age is counted from `ended_at`, a report's from its meta `created_at`. Snapshots are ranked per drawing by ID (ULIDs sort by time). A report or job read after it was deleted returns `EXEC_NOT_FOUND`, the same as an ID that never existed. Clean-up takes `now` from the `Clock` port.

## 13.2.5 Version control

The store writes `.cad/.gitignore` on creation. By default, `modules/`, `parts/`, `drawings/`, `config.toml` and `store.json` are meant to be committed: they hold authored intent and the records that identify drawings. `derived/`, `snapshots/`, `reports/`, `jobs/`, `backups/`, `index.json` and `.lock` are ignored, because they are regenerable, large or local. A project that wants its reports under version control removes the line from `.gitignore`.

The file the store writes, exactly **[Builder's call]**:

```
# Written by sw-mcp (spec 13.2.5). Regenerable, large or local:
derived/
snapshots/
reports/
jobs/
backups/
index.json
.lock
*.tmp-*
```

It is written only when the store is created, never over an existing file.
