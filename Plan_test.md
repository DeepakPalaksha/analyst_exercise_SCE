# Plan — SCE Timed Analyst Exercise

**Scope:** Answer Q1–Q8 for an anonymized SCE commercial customer in
**Puente Hills, CA** on tariff **TOU-GS-2-D**, using 15-min interval data
from UtilityAPI.

**Time budget:** ~90 minutes hard cap.

**Deliverable:** A self-contained folder (`notebooks/analyst_exercise/`) that
can be zipped and sent to the interviewer. Contains everything needed to
reproduce the analysis from the raw CSV.

---

## Folder Layout (final)

```
notebooks/analyst_exercise/
├── Plan_test.md               <- this file (approach + assumptions)
├── Task_test.md               <- Q1-Q8 checklist (all DONE)
├── README.md                  <- how to run for the interviewer
├── requirements.txt           <- pandas, numpy, matplotlib, jupyter, cvxpy, highspy
├── analyst_exercise.ipynb     <- main deliverable (27 cells, executed)
├── analyst_exercise.html      <- static HTML export (no Python needed)
├── helpers.py                 <- TOU + bill + solar + battery (rule-based & MILP)
├── build_notebook.py          <- programmatic notebook rebuilder
├── sce_tou_gs2d.json          <- tariff rates extracted from PDF
├── _load_duration.py          <- load-duration analysis (battery sizing)
├── load_duration_curve.png    <- LDC plot referenced in Q8
└── data_test/                 <- everything provided by interviewer + real data
    ├── Timed Analyst Exercise.txt      (instructions)
    ├── Timed Analyst Exercise.docx     (instructions, word format)
    ├── intervals_1000000001.csv        (raw meter data, Apr 2023 - Feb 2025)
    ├── TOU-GS-2 Rate Fact Sheet_WCAG.pdf  (tariff structure overview)
    ├── ELECTRIC_SCHEDULES_TOU-GS-2.pdf    (full electric schedule w/ rates)
    ├── puente_hills_solar_2024.csv        (real 300 kW AC PVWatts profile)
    └── puente_hills_weather_2024.csv      (hourly temp + GHI/DNI/DHI)
```

Nothing outside this folder is required to reproduce the analysis.

---

## Key Facts (from the task)

| Item | Value |
|---|---|
| Customer | Anonymized commercial, **Puente Hills CA** (SCE service area) |
| Tariff | **TOU-GS-2-D** (small/medium business, 20-200 kW) |
| Interval | 15 minutes |
| Column of interest | `interval_kWh` (energy consumed in each 15-min slot) |
| Analysis window | **Calendar year 2024 only** |
| Billing basis | Once per month, calendar month |
| Assumed PV size (Q7) | 300 kW AC, behind the meter |
| Assumed battery size (Q8) | 250 kWh at **100 kW** (2.5-hr, chosen via LDC) |

### TOU-GS-2 Tariff Structure (from Rate Fact Sheet)

- **4 TOU periods**: Super Off-Peak, Off-Peak, Mid-Peak, On-Peak
- **2 seasons**: Summer (Jun 1 – Sep 30), Winter (Oct 1 – May 31)
- **Weekday vs Weekend/Holiday** distinction
- **On-Peak window**: 4 PM – 9 PM summer weekdays
- **Two demand charges**:
  1. **Facilities-Related Demand (FRD)** — highest 15-min kW *any time*
     in the month, applied year round ($24.86/kW)
  2. **Time-Related Demand (TRD)** — highest 15-min kW during summer On-Peak
     weekday hours ($36.33/kW), OR winter Mid-Peak weekday hours ($7.82/kW)
- **Option D** = higher demand $/kW, lower energy $/kWh (vs Option E)

---

## Two Headline Assumptions

1. **Rates:** Jan 1, 2025 rates (from the provided PDF, Advice 5449-E) applied
   to 2024 usage. Actual 2024 rates would differ by a few percent. Using
   provided rates as prescriptive.
2. **TOU periods:** The current 4pm-9pm on-peak / mid-peak window structure
   has been effective since March 2019, so period definitions apply
   consistently across all of 2024.

## Critical Technical Points

1. **Units:** `interval_kWh` is energy per 15 min. Convert to kW with
   `demand_kw = interval_kWh × 4`. Getting this wrong makes every peak
   answer 4x off.

2. **Data hygiene:**
   - Rows are in **descending** time order in the CSV — sorted ascending
   - File spans Apr 2023 to Feb 2025 — sliced to `2024-01-01 → 2024-12-31`
   - 2024 row count = 366 days × 96 intervals = **35,136** rows (leap year)
   - No gaps or duplicates detected

3. **Peak demand** = max 15-min average kW in the calendar month.

4. **Two independent demand charges** (both billed every month):
   - FRD: `max(demand_kw)` over the month
   - TRD: `max(demand_kw)` over TRD-eligible hours in the month
   - TRD hours = summer On-Peak (weekday) OR winter Mid-Peak (weekday)

5. **Holiday handling** (from Fact Sheet):
   New Year's Day, President's Day, Memorial Day, Independence Day, Labor Day,
   Veterans Day, Thanksgiving Day, Christmas. Sunday → observed Monday.

6. **NEM 3.0 for Q7/Q7b** (PV export credit):
   - In 2024, PV exports earn ~$0.08/kWh (Net Billing Tariff, wholesale-linked)
   - Not the retail rate (NEM 2.0 was ended April 2023)
   - PV first offsets on-site load; any excess counts as export
   - Q7b uses flat $0.08/kWh proxy; a rigorous answer needs the SCE hourly
     export rate matrix

---

## Approach per Question

| Q | Approach | Tool |
|---|---|---|
| Q1 | Group by month, take max demand_kw | pandas |
| Q2 | Classify each interval, filter to TRD hours, group by month, max | pandas + `is_trd_hour` |
| Q3 | Group by month, sum interval_kWh | pandas |
| Q4 | Classify each interval, pivot table month x period, sum | pandas + `classify_period` |
| Q5 | Energy × TOU rate + FRD × FRD_rate + TRD × TRD_rate + fixed | `calculate_monthly_bill` |
| **Q6** | First-order: baseline = 10th-percentile daily energy, HVAC = residual | pandas |
| **Q6b** | Regression: `daily_kWh ~ a + b·CDD65 + c·HDD65` using real weather | numpy.linalg.lstsq |
| **Q7** | Synthetic clear-sky PV profile, subtract from load, rebill | `simulate_solar` |
| **Q7b** | Real 300 kW PVWatts profile, track import/export separately | `apply_real_solar` |
| **Q8** | Rule-based dispatch: discharge near peaks, charge overnight | `simulate_battery` |
| **Q8b** | Monthly LP: min energy + FRD·peak + TRD·trd_peak s.t. SoC/power | cvxpy + HIGHS |

---

## What I Actually Delivered

Q1–Q5 are the "hard" audit points and are fully answered with numbers +
plots + methodology notes. Q6–Q8 are answered **twice each**:

- **Q6, Q7, Q8** = first-order estimate (methodology walkthrough, quick answer)
- **Q6b, Q7b, Q8b** = enhanced answer using real data / MILP optimizer

This progressive-enhancement structure lets the interviewer see the
reasoning path and both a floor and a rigorous number for each hypothetical.

---

## Assumptions Log (final)

- ✓ Tariff Option: **D** (confirmed by tariff name `TOU-GS-2D` in CSV)
- ✓ Season definition: Summer = Jun 1 – Sep 30, Winter = Oct 1 – May 31
- ✓ Federal holidays observed per SCE fact sheet
- ✓ Bundled service (Delivery + SCE Generation)
- ✓ Standard voltage (2–50 kV), no voltage discount
- ✓ No CPP enrollment (Option D standard)
- ✓ Rates: Jan 1 2025 (as provided in the PDF, applied to 2024 data)
- ✓ NEM 3.0 export credit: flat $0.08/kWh proxy for Q7b
- ✓ Battery: 250 kWh at 100 kW (2.5-hr), 90% RTE, LP dispatch

## What I Would Do With More Time

- Cross-reference bill against SCE actuals (need customer's SCE portal access)
- Use the SCE NEM 3.0 hourly export rate matrix (instead of flat $0.08 proxy)
- Add binary switch variables to make Q8b a proper MILP (LP is already
  effective because efficiency losses prevent simultaneous C/D)
- Verify tariff rates against SCE's 2024 tariff sheets (rates change)
- Multi-year comparison (data spans Apr 2023 – Feb 2025)
- Sensitivity analysis on tariff option (D vs E vs CPP)
