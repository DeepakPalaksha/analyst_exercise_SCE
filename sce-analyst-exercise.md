# Chat Log — SCE Timed Analyst Exercise

**Session start:** 2026-07-06 22:45 (UTC+2)
**Deadline:** ~90 minutes to submit
**Deliverable:** `notebooks/analyst_exercise/` self-contained folder

---

## Entry 1 — Setup + Planning

### Prompts
1. User pointed to new task documents in `task_documents/`
2. Asked whether to adapt existing repo or rebuild from scratch
3. Asked to organize with self-contained folder + Plan_test.md + Task_test.md

### Response Summary
- Read all 5 task docs (instructions .txt, .docx; CSV; two tariff PDFs)
- Identified critical technical facts:
  - Tariff is **TOU-GS-2-D** (4 TOU periods, not 3 like our existing repo)
  - Data column is **interval_kWh** (energy per 15 min, not kW)
  - CSV is descending time order; spans Apr 2023 to Feb 2025
  - Q1 asks specifically for calendar year 2024
  - GS-2-D has TWO demand charges: FRD (year-round all-time) + TRD (seasonal weekday windows)
- Recommended: adapt + self-contained portable folder inside `notebooks/analyst_exercise/`
- Created folder structure:
  ```
  notebooks/analyst_exercise/
  ├── Plan_test.md         (approach + assumptions)
  ├── Task_test.md         (Phase 0-11 checklist)
  └── data_test/           (5 files copied from task_documents/)
  ```

### Files Changed
- Created `notebooks/analyst_exercise/Plan_test.md`
- Created `notebooks/analyst_exercise/Task_test.md`
- Copied 5 task documents into `notebooks/analyst_exercise/data_test/`

### Why This Approach
- 1.5-hour hard deadline — no time for full rebuild
- Interviewer wants clean self-contained deliverable, not full repo tour
- Existing repo modules (bill calc, solar, battery, thermal) are useful patterns but not directly reusable (different tariff, different building, different scenarios)
- Portable folder = user can zip and send to interviewer

---

## Entry 2 — Execution (in progress)

To be filled as we build.
