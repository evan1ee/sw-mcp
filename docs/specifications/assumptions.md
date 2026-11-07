# Assumption Register

> Specification v1.44, companion register to [section 18 (Roadmap)](roadmap.md#assumption-register-builders-call). Index and section map: [specifications/README.md](README.md).

This file records the live verification status and outcomes of the SOLIDWORKS API assumptions listed in [section 18](roadmap.md#assumption-register-builders-call).

| # | Assumption | Status | Tested on | Fallback needed? | Evidence |
| --- | --- | --- | --- | --- | --- |
| A2 | `IFeature.GetID()` is stable across save/reopen, rename and rebuild | **Confirmed** (save, close, reopen and rebuild on the MVP plate) | SOLIDWORKS 2025 SP0.0 (`zh-CN`), Windows 11 (`2026-11-05`) | No (`GetPersistReference3` fallback in 5.3.6 not required for save/reopen) | [Part Chain MVP spike](../superpowers/review/2026-11-05-part-chain-spike.md#5-a2-getid-and-getpersistreference3-across-close-and-reopen) |
| A14 | Commands posted from the add-in's pipe thread through the UI thread's synchronization context run reliably, and are deferred, not lost, while SOLIDWORKS is busy or showing a modal dialog (8.6.2) | **Confirmed** | SOLIDWORKS 2025 SP0.0 (`zh-CN`), Windows 11 (`2026-11-05`) | No (idle-notification queue fallback in 8.6.2 not required) | [Part Chain MVP spike](../superpowers/review/2026-11-05-part-chain-spike.md#a14-and-immediate-reconnect-step-3), [`tests/live/test_live_a14.py`](../../tests/live/test_live_a14.py) |

---

## Detailed Outcomes

### A2 — `IFeature.GetID()` stability across close and reopen

- **Statement:** `IFeature.GetID()` is stable across save/reopen, rename and rebuild (spec 5.3.6).
- **Fallback if it fails:** `IModelDocExtension.GetPersistReference3` (5.3.6).
- **Test and observation (`2026-11-05`):**
  - Built the 100 × 60 × 10 mm four-hole plate on SOLIDWORKS 2025 SP0.0 (`zh-CN` UI), forced a rebuild (`ForceRebuild3(false)`), saved to disk, closed with `CloseDoc(fullPath)`, and reopened with `OpenDoc6`.
  - `IFeature.GetID()` was identical before and after close and reopen across all 20 features in the tree (standard `RefPlane` features `2`, `3`, `4`; origin `5`; `Sketch1` `73`; `Boss-Extrude1` `79`; `Sketch2` `80`; `Cut-Extrude1` `86`).
  - `IModelDocExtension.GetPersistReference3(feature)` returned 20-byte persistent reference IDs (prefix `50-46-00-00-01-00-00-00`) that were also byte-identical after reopen and resolved back to the same features via `GetObjectByPersistReference3`.
- **Conclusion:** A2 holds for the Part Chain MVP (`f<GetID()>` verification binding across build, save, close, and read-only reopen); the `GetPersistReference3` fallback is not needed. Broader persistence across `Save As`, file copy, and external engineer edits remains tracked under K14 in [`open-decisions.md`](open-decisions.md#k14-how-far-native-feature-identity-holds).

### A14 — UI-thread synchronization context dispatch under load and busy SOLIDWORKS

- **Statement:** Commands posted from the add-in's pipe thread through the UI thread's synchronization context (`ControlSynchronizationContext`) run reliably, and are deferred, not lost, while SOLIDWORKS is busy (spec 8.6.2).
- **Fallback if it fails:** Drive the command queue from a SOLIDWORKS idle-notification handler instead (8.6.2).
- **Test and observation (`2026-11-05`):**
  - Executed [`tests/live/test_live_a14.py`](../../tests/live/test_live_a14.py) against the registered in-process add-in over the named pipe (`session.ping`, `document.open`, `document.close` on a scratch part):
    1. **1,000 sequential pings + 20 open/close cycles:** median ping latency 10.6 ms, p99 21.1 ms, max 104.6 ms, zero lost; 40 open/close commands completed with max latency 903 ms.
    2. **Commands while SOLIDWORKS was held busy (back-to-back rebuilds of a 1,600-hole part):** `session.ping` answered in 1 ms on the pipe thread; `document.open` waited 18.2 s while the main thread was busy and then succeeded; `document.close` completed in 103 ms. No command was dropped or deadlocked.
    3. **Immediate reconnect:** 10 consecutive cycles of open, close, dropping the pipe connection, and immediately acquiring a new connection and pinging all succeeded in 22–55 ms.
- **Conclusion:** A14 holds under load, during long rebuilds, and across immediate reconnections; the idle-notification fallback is not needed.
