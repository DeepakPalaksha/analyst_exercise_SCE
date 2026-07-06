# SCE Timed Analyst Exercise — Deliverable

**Customer:** Anonymized commercial, **Puente Hills, CA** (SCE service territory).
The raw CSV lists an Ontario, CA address but Mike confirmed the actual site is
in Puente Hills. Same SCE service area, same climate zone.
**Tariff:** TOU-GS-2 Option D
**Data source:** UtilityAPI 15-minute interval export
**Analysis window:** Calendar year 2024
**Author:** Deepak Palaksha

---

## What's in this folder

| File | Purpose |
|---|---|
| `analyst_exercise.ipynb` | **Main deliverable** — walks Q1–Q8 with Q6b/Q7b/Q8b real-data enhancements |
| `analyst_exercise.html` | Static HTML export (same content, no Python needed to view) |
| `helpers.py` | TOU classifier, bill calc, solar sim, battery sim (rule-based + MILP) |
| `sce_tou_gs2d.json` | Tariff rates extracted from the SCE PDF |
| `Plan_test.md` | Approach and assumptions |
| `Task_test.md` | Q1–Q8 checklist |
| `build_notebook.py` | Programmatic notebook builder (transparent reconstruction) |
| `_load_duration.py` | Load-duration-curve analysis (used to size the battery inverter) |
| `load_duration_curve.png` | Output of the LDC analysis (referenced in Q8) |
| `requirements.txt` | Python dependencies |
| `data_test/` | All inputs (customer meter, tariff PDFs, weather, solar) |

## `data_test/` inputs

| File | Source |
|---|---|
| `intervals_1000000001.csv` | Interviewer-provided 15-min meter data (Apr 2023 – Feb 2025) |
| `Timed Analyst Exercise.txt` / `.docx` | Interviewer instructions |
| `ELECTRIC_SCHEDULES_TOU-GS-2.pdf` | SCE tariff schedule (Advice 5449-E, eff. Jan 1, 2025) |
| `TOU-GS-2 Rate Fact Sheet_WCAG.pdf` | SCE tariff overview |
| `puente_hills_solar_2024.csv` | Real 300 kW AC PVWatts-style profile for Puente Hills |
| `puente_hills_weather_2024.csv` | Hourly weather for Puente Hills 2024 (temp + GHI/DNI/DHI) |

---

## How to run

```bash
# 1. Create a Python environment
python -m venv .venv
.venv\Scripts\activate         # Windows PowerShell
# source .venv/bin/activate    # macOS / Linux

# 2. Install dependencies (includes cvxpy for MILP)
pip install -r requirements.txt

# 3. Launch Jupyter
jupyter lab analyst_exercise.ipynb

# 4. Run all cells (Kernel -> Restart & Run All)
#    Full run takes ~2 minutes (the MILP solve is the slowest step)
```

Or simply open `analyst_exercise.html` in any browser — no Python needed.

The notebook reads everything from `data_test/` — no additional configuration.

---

## Tools used

- **Python 3.11+** with pandas, numpy, matplotlib
- **Jupyter Notebook** for narrative + reproducible cells
- **cvxpy + HIGHS solver** for the MILP battery dispatch (Q8b)
- All logic is transparent: `helpers.py` (~725 LOC) is a single readable module

---

## Two headline assumptions

1. **Rates:** I applied the **Jan 1, 2025** tariff rates (from the provided PDF,
   Advice 5449-E) to 2024 usage data. Actual 2024 billing would use rates in
   effect during that period, which differ by a few percent. Using the provided
   rates as the prescriptive answer.
2. **TOU periods:** The current **4pm-9pm on-peak / mid-peak** window has been
   effective since **March 2019** (SCE Advice 3957-E). So TOU period
   definitions apply consistently across all of 2024.

## Other assumptions (also called out inline in the notebook)

- **Location:** Puente Hills, CA (per Mike; CSV address is Ontario)
- **Service type:** Bundled (Delivery + SCE Generation), not Direct Access / CCA
- **Voltage:** Standard secondary (2–50 kV), no voltage discount
- **No CPP enrollment**, no CARE / Climate Credit / Food Bank discount
- **Q6b (HVAC):** Change-point regression `daily_kWh ~ a + b·CDD65 + c·HDD65`
  using real hourly temperature. Result: **6.0% HVAC** — surprisingly low,
  suggests industrial baseline dominates
- **Q7b (PV):** Real 300 kW AC profile from PVWatts-style dataset. Peak ~232 kW
  (inverter clipping typical), 470 MWh/yr generation, 23% capacity factor
- **NEM 3.0 export credit:** Flat **$0.08/kWh** proxy (real answer would use
  SCE's hourly Net Billing Tariff matrix)
- **Q8 (battery):** 250 kWh at **100 kW** (2.5-hr, chosen from load duration
  curve analysis), 90% RTE
- **Q8b (MILP):** LP dispatch via cvxpy + HIGHS, 12 independent monthly problems

## Structure of the notebook

- **Section 1:** Data loading + sanity checks (35,136 rows, 2024)
- **Q1:** Monthly peak demand
- **Q2:** TRD peaks (in priced windows)
- **Q3:** Monthly energy
- **Q4:** Energy by TOU period
- **Q5:** Full monthly bill (demand vs energy split)
- **Q6:** HVAC first-order estimate (10th-percentile baseline)
- **Q6b:** HVAC via **real weather regression** (CDD65 + HDD65)
- **Q7:** 300 kW PV via **synthetic** clear-sky profile
- **Q7b:** 300 kW PV via **real PVWatts-style** data + NEM 3.0 accounting
- **Q8:** 250 kWh battery via **rule-based** dispatch
- **Q8b:** 250 kWh battery via **MILP** dispatch (upper bound)
- **Section 10:** Summary + "what I would do next"

## What I would do with more time

- Verify tariff rates against SCE's 2024 tariff sheets (rates changed mid-year)
- Extend the analysis to true PV production and temperature of the location data. 
- Use the full **SCE NEM 3.0 hourly export rate matrix** (not the flat proxy)
- Add binary switch variables to make Q8b a proper MILP (LP already good)
- Cross-check computed bill against customer's actual SCE invoice
- Multi-year comparison (data spans April 2023 – February 2025)
- Sensitivity analysis: Option D vs Option E vs CPP-enabled

