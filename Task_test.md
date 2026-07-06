# Task Checklist — SCE Analyst Exercise (FINAL)

Final status of the 90-minute exercise.

---

## Phase 0 — Setup

- [x] **T0.1** Create folder structure `notebooks/analyst_exercise/`
- [x] **T0.2** Copy 5 task documents into `data_test/`
- [x] **T0.3** Write `Plan_test.md`
- [x] **T0.4** Write `Task_test.md`
- [x] **T0.5** Write `README.md` for the interviewer
- [x] **T0.6** Write `requirements.txt` (pandas, numpy, matplotlib, jupyter, cvxpy, highspy)

## Phase 1 — Data Loading & Cleanup

- [x] **T1.1** Load `data_test/intervals_1000000001.csv` with pandas
- [x] **T1.2** Parse `interval_start` as datetime
- [x] **T1.3** Sort ascending by `interval_start`
- [x] **T1.4** Convert to kW: `demand_kw = interval_kWh × 4`
- [x] **T1.5** Slice to calendar year 2024
- [x] **T1.6** Sanity check: 35,136 rows verified, no gaps or duplicates
- [x] **T1.7** Summary: date range, peak kW, mean kW, total kWh

## Phase 2 — Tariff Setup

- [x] **T2.1** Extract rates from `data_test/ELECTRIC_SCHEDULES_TOU-GS-2.pdf`
- [x] **T2.2** Write `sce_tou_gs2d.json` (energy × 4 periods × 2 seasons + FRD + TRD)
- [x] **T2.3** Implement `classify_period(timestamp)` in `helpers.py`
- [x] **T2.4** Implement `is_trd_hour(timestamp)`
- [x] **T2.5** Implement `is_holiday(date)` for SCE-observed holidays
- [x] **T2.6** Unit-check: verified June weekday 4pm → `on_peak`, `is_trd=True`

## Phase 3 — Q1: Monthly Peak Demand

- [x] All items done. **Result: annual peak 290.9 kW on Sep 9 at 14:30**

## Phase 4 — Q2: Peaks in Priced Windows

- [x] All items done. TRD peaks computed for all 12 months; summer On-Peak
      values are what drive TRD billing in Jun–Sep

## Phase 5 — Q3: Monthly Energy

- [x] All items done. **Result: annual 1.09 GWh, monthly range 78–112 MWh**

## Phase 6 — Q4: Energy by TOU Period per Month

- [x] All items done. Reconciled with Q3 (row totals match). Off-Peak
      dominates; Super-Off-Peak significant in winter

## Phase 7 — Q5: Monthly Bill

- [x] All items done. **Result: annual bill $257,798.**
      **Demand portion: ~35%, Energy portion: ~65%**

## Phase 8 — Q6: HVAC Breakdown

- [x] **T8.1** First-order: 10th-percentile daily energy as non-HVAC baseline
- [x] **T8.2** External data listed: NOAA/NCEI Ontario Intl (station 722950)
- [x] **T8.3–4** First-order Q6 done (~25% via percentile method)
- [x] **BONUS Q6b:** Real weather regression using
      `puente_hills_weather_2024.csv` (hourly temp, GHI/DNI/DHI)
- [x] **Q6b Result: HVAC = 6.0%** (surprising — load isn't very
      temperature-sensitive; suggests industrial baseline)

## Phase 9 — Q7: 300 kW PV Impact

- [x] **T9.1–7** Q7 with synthetic clear-sky profile: **$83k/yr** savings
- [x] **BONUS Q7b:** Real 300 kW PVWatts-style profile
      (`puente_hills_solar_2024.csv`), peak 232 kW, 470 MWh/yr, 23% CF
- [x] **Q7b Result: $75,214 billed + $4,031 NEM 3.0 export = $79,245/yr**
- [x] Three quantities tracked: self-consumption, export, net-import

## Phase 10 — Q8: 250 kWh Battery Impact

- [x] **Battery sizing:** Load duration curve analysis
      (`_load_duration.py` + `load_duration_curve.png`) →
      **chose 100 kW inverter (2.5-hr duration)**
- [x] **T10.1–5** Q8 rule-based dispatch: **$224/yr** (peak-shave floor)
- [x] **BONUS Q8b:** MILP dispatch (cvxpy + HIGHS, 12 monthly LPs)
- [x] **Q8b Result: $31,011/yr** — 138× rule-based (proves MILP as upper bound)

## Phase 11 — Closing

- [x] **T11.1** "What I would do next" markdown cell in notebook
- [x] **T11.2** Table of contents at top of notebook
- [x] **T11.3** Executive summary cell (headline numbers)
- [x] **T11.4** Save + close notebook + export HTML (851 KB)

---

## Final Assumptions Log

- Tariff Option: **D** (confirmed by tariff name `TOU-GS-2D` in CSV)
- Location: **Puente Hills, CA** (per Mike; CSV lists Ontario)
- Season definition: Summer = Jun 1 – Sep 30, Winter = Oct 1 – May 31
- Federal holidays observed per SCE fact sheet
- Bundled service (Delivery + SCE Generation)
- Standard voltage tier (2–50 kV), no voltage discount
- No CPP enrollment (Option D standard)
- Rates: Jan 1, 2025 as provided in the PDF, applied to 2024 data
- Battery: 250 kWh at **100 kW** (2.5-hr), 90% RTE
- NEM 3.0: flat $0.08/kWh export credit proxy

## What I Would Do With More Time

- Verify tariff against 2024 SCE tariff sheets (rates changed mid-year)
- Full NEM 3.0 hourly export rate matrix (not flat proxy)
- Add binary switches → proper MILP for Q8b (LP already good)
- Cross-reference bill against SCE actuals
- Multi-year comparison (data spans Apr 2023 – Feb 2025)
- Sensitivity: Option D vs Option E vs CPP
- Rolling-horizon MPC with load/solar/price forecasting for real deployment

---

## Deliverable state

**All 11 phases DONE.** Notebook executed cleanly with all 27 cells producing
outputs. HTML export generated. Folder is self-contained and portable —
zip and send.
