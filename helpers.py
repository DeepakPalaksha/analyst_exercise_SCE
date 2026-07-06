"""
Helper functions for the SCE Timed Analyst Exercise (TOU-GS-2 Option D).

Contains:
  - load_and_clean_data:   read raw CSV, sort ascending, convert to kW, slice year
  - is_holiday:            SCE-observed holidays for a given year
  - classify_period:       return TOU period name for a timestamp
  - is_trd_hour:           True if timestamp falls in TRD-eligible hours
  - calculate_monthly_bill: full bill breakdown (energy + FRD + TRD + fixed)
  - simulate_solar:        subtract PV kW from load (300 kW default, PVWatts profile)
  - simulate_battery:      simple rule-based demand shaving
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────
def load_and_clean_data(
    csv_path: str | Path,
    year: int = 2024,
) -> pd.DataFrame:
    """
    Load raw UtilityAPI 15-min interval CSV, clean it up, slice to `year`.

    Returns DataFrame with columns:
        timestamp        (pd.Timestamp, US/Pacific naive, sorted ascending)
        interval_kwh     (float, energy per 15-min interval)
        demand_kw        (float, average kW during interval = kWh * 4)
        month, day_of_week, hour, is_weekend
    """
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["interval_start"], format="mixed")
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df.rename(columns={"interval_kWh": "interval_kwh"})
    df["demand_kw"] = df["interval_kwh"] * 4  # 15-min interval → average kW
    df["month"] = df["timestamp"].dt.month
    df["day_of_week"] = df["timestamp"].dt.dayofweek  # Monday=0, Sunday=6
    df["hour"] = df["timestamp"].dt.hour
    df["date"] = df["timestamp"].dt.date
    df["is_weekend"] = df["day_of_week"] >= 5

    # Slice to calendar year
    mask = (df["timestamp"] >= f"{year}-01-01") & (
        df["timestamp"] < f"{year + 1}-01-01"
    )
    df = df.loc[mask].reset_index(drop=True)
    return df[
        ["timestamp", "interval_kwh", "demand_kw", "month",
         "day_of_week", "hour", "date", "is_weekend"]
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Tariff loading
# ─────────────────────────────────────────────────────────────────────────────
def load_tariff(path: str | Path = None) -> dict:
    """Load the TOU-GS-2 Option D tariff JSON."""
    if path is None:
        path = HERE / "sce_tou_gs2d.json"
    with open(path) as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# Holiday detection
# ─────────────────────────────────────────────────────────────────────────────
_HOLIDAY_CACHE: dict[int, set[date]] = {}


def _observed_date(y: int, m: int, d: int) -> date:
    """SCE rule: if a holiday falls on Sunday, observed the following Monday.
    No shift for Saturday."""
    dt = date(y, m, d)
    if dt.weekday() == 6:  # Sunday → Monday
        return date(y, m, d + 1)
    return dt


def _us_holidays(year: int) -> set[date]:
    """
    SCE-observed holidays per Schedule TOU-GS-2 Special Condition 1:
      New Year's Day, Presidents' Day, Memorial Day, Independence Day,
      Labor Day, Veterans Day, Thanksgiving Day, Christmas.
    """
    if year in _HOLIDAY_CACHE:
        return _HOLIDAY_CACHE[year]

    holidays: set[date] = set()
    # Fixed dates
    for m, d in [(1, 1), (7, 4), (11, 11), (12, 25)]:
        holidays.add(_observed_date(year, m, d))

    # Presidents' Day: third Monday of February
    feb_first = date(year, 2, 1)
    holidays.add(
        date(year, 2, 1 + ((0 - feb_first.weekday()) % 7) + 14)
    )
    # Memorial Day: last Monday of May
    may_last = date(year, 5, 31)
    holidays.add(
        date(year, 5, 31 - ((may_last.weekday() - 0) % 7))
    )
    # Labor Day: first Monday of September
    sep_first = date(year, 9, 1)
    holidays.add(
        date(year, 9, 1 + ((0 - sep_first.weekday()) % 7))
    )
    # Thanksgiving: fourth Thursday of November
    nov_first = date(year, 11, 1)
    holidays.add(
        date(year, 11, 1 + ((3 - nov_first.weekday()) % 7) + 21)
    )

    _HOLIDAY_CACHE[year] = holidays
    return holidays


def is_holiday(dt) -> bool:
    """Return True if the date is an SCE-observed holiday."""
    if isinstance(dt, pd.Timestamp):
        dt = dt.date()
    elif isinstance(dt, datetime):
        dt = dt.date()
    return dt in _us_holidays(dt.year)


# ─────────────────────────────────────────────────────────────────────────────
# TOU period classification
# ─────────────────────────────────────────────────────────────────────────────
def classify_period(ts: pd.Timestamp) -> str:
    """
    Return TOU period for a timestamp under TOU-GS-2 Option D.

    Returns one of:
        'on_peak', 'mid_peak', 'off_peak', 'super_off_peak'

    Rules (from tariff Sheet 8, Special Condition 1):
      Summer (Jun-Sep):
        Weekday: On-Peak 4-9pm; Off-Peak all other hours
        Weekend/Holiday: Mid-Peak 4-9pm; Off-Peak all other hours
      Winter (Oct-May):
        All days: Mid-Peak 4-9pm; Super-Off-Peak 8am-4pm;
                  Off-Peak 9pm-8am
    """
    month = ts.month
    hour = ts.hour
    is_summer = month in (6, 7, 8, 9)
    is_weekday_and_not_holiday = ts.weekday() < 5 and not is_holiday(ts)
    in_4_to_9pm = 16 <= hour < 21
    in_8am_to_4pm = 8 <= hour < 16

    if is_summer:
        if in_4_to_9pm:
            return "on_peak" if is_weekday_and_not_holiday else "mid_peak"
        return "off_peak"
    # Winter
    if in_4_to_9pm:
        return "mid_peak"
    if in_8am_to_4pm:
        return "super_off_peak"
    return "off_peak"


def classify_periods_vec(timestamps: pd.Series) -> pd.Series:
    """Vectorized TOU classifier."""
    return timestamps.apply(classify_period)


def is_trd_hour(ts: pd.Timestamp) -> bool:
    """
    True if timestamp counts toward Time-Related Demand billing.
    TRD applies to:
      - Summer On-Peak weekday hours (4-9pm), OR
      - Winter Mid-Peak weekday hours (4-9pm)
    Weekends/holidays never count for TRD.
    """
    if ts.weekday() >= 5 or is_holiday(ts):
        return False
    hour = ts.hour
    if not (16 <= hour < 21):
        return False
    return True  # any weekday 4-9pm all year (summer On-Peak, winter Mid-Peak)


# ─────────────────────────────────────────────────────────────────────────────
# Bill calculation
# ─────────────────────────────────────────────────────────────────────────────
def calculate_monthly_bill(
    df: pd.DataFrame,
    tariff: dict = None,
) -> pd.DataFrame:
    """
    Compute monthly bill for TOU-GS-2 Option D.

    Assumes df has columns from load_and_clean_data + a 'tou_period' column
    (add via `df['tou_period'] = classify_periods_vec(df['timestamp'])`).

    Returns DataFrame indexed by month with columns:
        energy_kwh
        peak_demand_kw           (all-time max → FRD basis)
        trd_peak_kw              (max in TRD hours → TRD basis)
        energy_charge_usd
        frc_mcam_usd             (FRC + MCAM per-kWh riders)
        frd_charge_usd           (facilities-related demand)
        trd_charge_usd           (time-related demand)
        customer_charge_usd
        total_usd
        demand_portion_usd       (FRD + TRD)
        energy_portion_usd       (energy + FRC/MCAM + customer)
    """
    if tariff is None:
        tariff = load_tariff()

    if "tou_period" not in df.columns:
        df = df.copy()
        df["tou_period"] = classify_periods_vec(df["timestamp"])
        df["is_trd"] = df["timestamp"].apply(is_trd_hour)
    elif "is_trd" not in df.columns:
        df = df.copy()
        df["is_trd"] = df["timestamp"].apply(is_trd_hour)

    energy = tariff["energy_rates_per_kwh"]
    frd_rate = tariff["demand_charges_per_kw"]["facilities_related"]
    trd_summer_rate = tariff["demand_charges_per_kw"][
        "time_related_summer_on_peak"
    ]
    trd_winter_rate = tariff["demand_charges_per_kw"][
        "time_related_winter_mid_peak"
    ]
    customer_charge = tariff["customer_charge_monthly_usd"]
    frc = tariff["fixed_recovery_charge_per_kwh"]
    mcam = tariff["mcam_charge_per_kwh"]

    rows = []
    for month, grp in df.groupby("month"):
        is_summer = month in (6, 7, 8, 9)
        season_key = "summer" if is_summer else "winter"

        # Energy by (season, day_type, period)
        energy_charge = 0.0
        energy_by_period = {}
        for period_name, per_grp in grp.groupby("tou_period"):
            weekday_grp = per_grp[
                ~per_grp["is_weekend"] & ~per_grp["timestamp"].apply(is_holiday)
            ]
            weekend_grp = per_grp[
                per_grp["is_weekend"] | per_grp["timestamp"].apply(is_holiday)
            ]
            wk_kwh = weekday_grp["interval_kwh"].sum()
            we_kwh = weekend_grp["interval_kwh"].sum()

            wk_rate = energy[season_key]["weekday"].get(period_name, 0.0)
            we_rate = energy[season_key]["weekend"].get(period_name, 0.0)
            # Fall back to weekday rate if weekend not defined for this
            # period (e.g. summer on-peak weekday only)
            if we_rate == 0.0 and wk_rate > 0.0:
                we_rate = wk_rate
            if wk_rate == 0.0 and we_rate > 0.0:
                wk_rate = we_rate

            energy_charge += wk_kwh * wk_rate + we_kwh * we_rate
            energy_by_period[period_name] = float(wk_kwh + we_kwh)

        total_kwh = float(grp["interval_kwh"].sum())
        peak_demand_kw = float(grp["demand_kw"].max())

        # TRD peak
        trd_grp = grp[grp["is_trd"]]
        trd_peak_kw = float(trd_grp["demand_kw"].max()) if len(trd_grp) else 0.0
        trd_rate = trd_summer_rate if is_summer else trd_winter_rate

        frc_mcam = total_kwh * (frc + mcam)
        frd_charge = peak_demand_kw * frd_rate
        trd_charge = trd_peak_kw * trd_rate

        total = (
            energy_charge
            + frc_mcam
            + frd_charge
            + trd_charge
            + customer_charge
        )
        demand_portion = frd_charge + trd_charge
        energy_portion = energy_charge + frc_mcam + customer_charge

        rows.append({
            "month": int(month),
            "energy_kwh": total_kwh,
            "peak_demand_kw": peak_demand_kw,
            "trd_peak_kw": trd_peak_kw,
            "energy_charge_usd": round(energy_charge, 2),
            "frc_mcam_usd": round(frc_mcam, 2),
            "frd_charge_usd": round(frd_charge, 2),
            "trd_charge_usd": round(trd_charge, 2),
            "customer_charge_usd": customer_charge,
            "total_usd": round(total, 2),
            "demand_portion_usd": round(demand_portion, 2),
            "energy_portion_usd": round(energy_portion, 2),
        })

    return pd.DataFrame(rows).set_index("month")


# ─────────────────────────────────────────────────────────────────────────────
# Solar simulation (Q7)
# ─────────────────────────────────────────────────────────────────────────────
def synthetic_pv_profile_kw(
    timestamps: pd.Series,
    system_kw_ac: float = 300.0,
    latitude: float = 34.02,  # Puente Hills, CA
) -> np.ndarray:
    """
    First-order synthetic PVWatts-like profile.

    Uses a simple clear-sky sinusoidal model scaled by seasonal factor.
    NOT a substitute for a real PVWatts run, but sufficient for a
    first-order estimate given the time budget.

    For a rigorous answer, use NREL PVWatts API with:
      lat/lon: Ontario CA ≈ 34.06 N, -117.65 W
      tilt: 20°, azimuth: 180° (south)
      losses: 14%, system size: 300 kW AC
    """
    # Day-of-year peak factor: peak in summer solstice (Jun 21 = doy 173)
    doy = timestamps.dt.dayofyear.values
    seasonal = 0.85 + 0.15 * np.cos(2 * np.pi * (doy - 173) / 365)
    # Hour-of-day: sun elevation ≈ sin(pi * (hour - 6) / 12) for 6am-6pm
    hour = timestamps.dt.hour + timestamps.dt.minute / 60.0
    daylight = np.clip(np.sin(np.pi * (hour.values - 6) / 12), 0, None)
    # AC capacity factor typical for SoCal ~19-20%; noon peak ≈ 85% of rated
    cf_peak = 0.85
    return system_kw_ac * cf_peak * daylight * seasonal


def simulate_solar(
    df: pd.DataFrame,
    system_kw_ac: float = 300.0,
) -> pd.DataFrame:
    """
    Apply 300 kW PV to the load. Return a new DataFrame with:
      pv_kw            = solar generation
      net_demand_kw    = max(0, load - pv) (grid import)
      export_kw        = max(0, pv - load) (grid export)
      net_interval_kwh = net_demand_kw / 4
    """
    df = df.copy()
    df["pv_kw"] = synthetic_pv_profile_kw(df["timestamp"], system_kw_ac)
    df["net_demand_kw"] = (df["demand_kw"] - df["pv_kw"]).clip(lower=0)
    df["export_kw"] = (df["pv_kw"] - df["demand_kw"]).clip(lower=0)
    df["net_interval_kwh"] = df["net_demand_kw"] / 4.0
    df["export_interval_kwh"] = df["export_kw"] / 4.0
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Battery simulation (Q8)
# ─────────────────────────────────────────────────────────────────────────────
def simulate_battery(
    df: pd.DataFrame,
    capacity_kwh: float = 250.0,
    power_kw: float = 125.0,
    efficiency: float = 0.90,
) -> pd.DataFrame:
    """
    Very simple rule-based battery dispatch for demand-shaving.

    Rules per interval (per calendar month):
      - Charge during super-off-peak / off-peak overnight (hour < 8),
        rate = -power_kw (up to SoC=100%), *provided* grid_load + charge_rate
        doesn't create a new all-time monthly peak.
      - Discharge during TRD hours (weekday 4-9pm), rate = +power_kw
        (down to SoC=0), aim to shave demand.
      - Idle otherwise.

    Assumptions:
      - Round-trip efficiency = 90%
      - Assumed 125 kW power rating (2-hour battery); adjust if given.

    Returns DataFrame with added columns:
      soc_kwh, battery_kw (positive=discharge, negative=charge),
      net_demand_kw (load - discharge + charge)
    """
    df = df.copy()
    dt_hr = 0.25  # 15 min

    df["battery_kw"] = 0.0
    df["soc_kwh"] = 0.0

    # Process month by month so demand targets reset
    for month in sorted(df["month"].unique()):
        mask = df["month"] == month
        mdf = df.loc[mask].sort_values("timestamp").reset_index()

        # Discharge target: aim to shave down to (peak - power_kw)
        month_peak = float(mdf["demand_kw"].max())
        discharge_threshold = max(month_peak - power_kw, 0.0)
        # Ceiling for overnight charging (avoid creating new peak)
        charge_ceiling = float(mdf["demand_kw"].quantile(0.60))

        soc = 0.0
        battery_kws = []
        socs = []
        for _, row in mdf.iterrows():
            ts = row["timestamp"]
            load_kw = row["demand_kw"]
            hour = ts.hour

            action_kw = 0.0

            # DISCHARGE any time load is near the monthly peak
            # (widened from 4-9pm-only: peaks can occur any hour of day)
            if load_kw > discharge_threshold and soc > 0:
                needed = load_kw - discharge_threshold
                available = soc * efficiency / dt_hr
                action_kw = min(power_kw, needed, available)

            # CHARGE overnight (0-8am) and, in winter, super-off-peak (8am-4pm)
            elif (hour < 8 or (month not in (6, 7, 8, 9)
                               and 8 <= hour < 16)) and soc < capacity_kwh:
                room = (capacity_kwh - soc) / dt_hr
                charge = min(power_kw, room)
                if load_kw + charge < charge_ceiling:
                    action_kw = -charge  # negative = charge

            # Update SoC
            if action_kw > 0:  # discharging
                soc -= action_kw * dt_hr / efficiency
            elif action_kw < 0:  # charging
                soc += (-action_kw) * dt_hr

            soc = max(0.0, min(capacity_kwh, soc))
            battery_kws.append(action_kw)
            socs.append(soc)

        df.loc[mask, "battery_kw"] = battery_kws
        df.loc[mask, "soc_kwh"] = socs

    df["net_demand_kw"] = (df["demand_kw"] - df["battery_kw"]).clip(lower=0)
    df["net_interval_kwh"] = df["net_demand_kw"] / 4.0
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Real data loaders (Q6b, Q7b)
# ─────────────────────────────────────────────────────────────────────────────
def load_real_solar(
    csv_path: str | Path = None,
    system_kw_ac: float = 300.0,
) -> pd.DataFrame:
    """
    Load real PVWatts-style solar profile from CSV.

    The provided file is a 300 kW AC system for Puente Hills, CA at 15-min
    resolution. Peak AC power ~232 kW (inverter clipping typical).

    Returns DataFrame with columns:
        timestamp, pv_kw, pv_interval_kwh
    """
    if csv_path is None:
        csv_path = HERE / "data_test" / "puente_hills_solar_2024.csv"
    solar = pd.read_csv(csv_path)
    solar["timestamp"] = pd.to_datetime(solar["interval_start"])
    solar = solar.sort_values("timestamp").reset_index(drop=True)
    solar = solar.rename(columns={
        "ac_power_kw": "pv_kw",
        "ac_energy_kwh": "pv_interval_kwh",
    })
    return solar[["timestamp", "pv_kw", "pv_interval_kwh"]]


def load_real_weather(
    csv_path: str | Path = None,
) -> pd.DataFrame:
    """
    Load hourly weather data (temperature + GHI/DNI/DHI) for Puente Hills.

    Returns DataFrame with columns:
        timestamp, temp_f, temp_c, ghi_wm2, dni_wm2, dhi_wm2
    """
    if csv_path is None:
        csv_path = HERE / "data_test" / "puente_hills_weather_2024.csv"
    weather = pd.read_csv(csv_path)
    weather["timestamp"] = pd.to_datetime(weather["timestamp"])
    return weather.sort_values("timestamp").reset_index(drop=True)


def apply_real_solar(
    df_load: pd.DataFrame,
    df_solar: pd.DataFrame,
    nem_export_credit_per_kwh: float = 0.08,
) -> pd.DataFrame:
    """
    Merge meter data with real PV profile and compute net demand + export.

    Returns df_load with added columns:
        pv_kw               solar generation at each interval
        net_demand_kw       max(0, load - pv)   ← what grid delivers
        export_kw           max(0, pv - load)   ← what customer sends to grid
        net_interval_kwh    energy from grid (billed at retail)
        export_interval_kwh energy to grid (credited at NEM 3.0 rate)
        nem_export_credit_usd  monetary credit for exports (flat rate proxy)
    """
    df = df_load.copy()
    merged = df.merge(
        df_solar[["timestamp", "pv_kw"]],
        on="timestamp", how="left",
    )
    merged["pv_kw"] = merged["pv_kw"].fillna(0.0)
    merged["net_demand_kw"] = (merged["demand_kw"] - merged["pv_kw"]).clip(lower=0)
    merged["export_kw"] = (merged["pv_kw"] - merged["demand_kw"]).clip(lower=0)
    merged["net_interval_kwh"] = merged["net_demand_kw"] / 4.0
    merged["export_interval_kwh"] = merged["export_kw"] / 4.0
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# MILP battery dispatch (Q8b)
# ─────────────────────────────────────────────────────────────────────────────
def milp_battery_dispatch_monthly(
    month_df: pd.DataFrame,
    capacity_kwh: float = 250.0,
    power_kw: float = 100.0,
    efficiency: float = 0.90,
    tariff: dict = None,
    verbose: bool = False,
) -> dict:
    """
    Solve LP battery dispatch for one calendar month using cvxpy.

    Objective: minimise total monthly bill component that battery affects:
        energy_charge + FRD_rate * peak_kw + TRD_rate * trd_peak_kw

    Variables (continuous, non-negative):
        p_charge[t]      kW charging into battery
        p_discharge[t]   kW discharging from battery
        soc[t]           kWh state of charge
        peak_kw          scalar, FRD monthly peak (max grid over all intervals)
        trd_peak_kw      scalar, TRD peak (max grid over TRD-eligible intervals)

    Constraints:
        grid[t] = load[t] - p_discharge[t] + p_charge[t]
        grid[t] >= 0            (no export from battery)
        grid[t] <= peak_kw       (FRD peak envelope)
        grid[t] <= trd_peak_kw   if t in TRD hours
        soc[t+1] = soc[t] + eta * p_charge[t] * dt - (1/eta) * p_discharge[t] * dt
        0 <= p_charge[t] <= power_kw
        0 <= p_discharge[t] <= power_kw
        0 <= soc[t] <= capacity_kwh

    Note: LP not MILP (no integer variables) - efficiency losses prevent
    simultaneous C/D naturally. If solve is imperfect, add binary switch.
    """
    import cvxpy as cp

    if tariff is None:
        tariff = load_tariff()

    N = len(month_df)
    dt = 0.25  # 15-min intervals

    load = month_df["demand_kw"].to_numpy(dtype=float)
    is_trd = month_df["is_trd"].to_numpy(dtype=bool)

    month = int(month_df["month"].iloc[0])
    is_summer = month in (6, 7, 8, 9)
    season = "summer" if is_summer else "winter"

    # Build rate vector for each interval
    rates = np.zeros(N)
    energy_map = tariff["energy_rates_per_kwh"][season]
    for i, row in enumerate(month_df.itertuples()):
        ts = row.timestamp
        is_wknd_or_hol = row.is_weekend or is_holiday(ts)
        day_key = "weekend" if is_wknd_or_hol else "weekday"
        period = row.tou_period
        day_rates = energy_map[day_key]
        rate = day_rates.get(period)
        if rate is None:
            # Fall back to the other day-type
            other_key = "weekend" if day_key == "weekday" else "weekday"
            rate = energy_map[other_key].get(period, 0.10)
        rates[i] = rate

    # cvxpy variables
    p_charge = cp.Variable(N, nonneg=True)
    p_discharge = cp.Variable(N, nonneg=True)
    soc = cp.Variable(N + 1, nonneg=True)
    peak_kw = cp.Variable(nonneg=True)
    trd_peak_kw = cp.Variable(nonneg=True)

    grid = load - p_discharge + p_charge  # kW per interval

    constraints = [
        # Battery capacity + power limits
        p_charge <= power_kw,
        p_discharge <= power_kw,
        soc <= capacity_kwh,
        # SoC dynamics (vectorized)
        soc[1:] == soc[:-1] + efficiency * p_charge * dt
                 - (1.0 / efficiency) * p_discharge * dt,
        soc[0] == 0.5 * capacity_kwh,           # start half-full
        soc[N] >= 0.1 * capacity_kwh,           # end with reserve
        # Grid constraints
        grid >= 0,                              # no reverse export
        grid <= peak_kw,                        # FRD envelope
    ]

    # TRD peak envelope: only for TRD-eligible intervals
    if is_trd.any():
        trd_indices = np.where(is_trd)[0]
        for idx in trd_indices:
            constraints.append(grid[idx] <= trd_peak_kw)

    # Demand rates
    frd_rate = tariff["demand_charges_per_kw"]["facilities_related"]
    trd_rate = (
        tariff["demand_charges_per_kw"]["time_related_summer_on_peak"]
        if is_summer
        else tariff["demand_charges_per_kw"]["time_related_winter_mid_peak"]
    )

    # Energy cost (linear because grid >= 0)
    frc_mcam_rate = (
        tariff["fixed_recovery_charge_per_kwh"] + tariff["mcam_charge_per_kwh"]
    )
    energy_cost = (rates + frc_mcam_rate) @ grid * dt

    objective = cp.Minimize(
        energy_cost + frd_rate * peak_kw + trd_rate * trd_peak_kw
    )

    problem = cp.Problem(objective, constraints)
    try:
        problem.solve(solver=cp.HIGHS, verbose=verbose)
    except Exception:
        problem.solve(verbose=verbose)  # fallback to default solver

    return {
        "month": month,
        "status": problem.status,
        "objective": problem.value,
        "peak_kw": float(peak_kw.value) if peak_kw.value is not None else None,
        "trd_peak_kw": (
            float(trd_peak_kw.value) if trd_peak_kw.value is not None else None
        ),
        "charge_kw": p_charge.value,
        "discharge_kw": p_discharge.value,
        "soc_kwh": soc.value,
        "grid_kw": (
            load
            - (p_discharge.value if p_discharge.value is not None
               else np.zeros(N))
            + (p_charge.value if p_charge.value is not None
               else np.zeros(N))
        ),
    }


def simulate_battery_milp(
    df: pd.DataFrame,
    capacity_kwh: float = 250.0,
    power_kw: float = 100.0,
    efficiency: float = 0.90,
    tariff: dict = None,
) -> pd.DataFrame:
    """
    Run MILP battery dispatch across all 12 months of the year and produce
    an aggregated dataframe compatible with bill_from_scenario().
    """
    if tariff is None:
        tariff = load_tariff()

    df_out = df.copy()
    df_out["battery_kw"] = 0.0
    df_out["soc_kwh"] = 0.0

    for month in sorted(df_out["month"].unique()):
        mask = df_out["month"] == month
        mdf = df_out.loc[mask].sort_values("timestamp").reset_index()
        result = milp_battery_dispatch_monthly(
            mdf, capacity_kwh, power_kw, efficiency, tariff
        )
        if result["charge_kw"] is None or result["discharge_kw"] is None:
            continue
        # Positive battery_kw = discharging, negative = charging
        battery_kw = result["discharge_kw"] - result["charge_kw"]
        df_out.loc[mask, "battery_kw"] = battery_kw
        df_out.loc[mask, "soc_kwh"] = result["soc_kwh"][:len(mdf)]

    df_out["net_demand_kw"] = (df_out["demand_kw"] - df_out["battery_kw"]).clip(
        lower=0
    )
    df_out["net_interval_kwh"] = df_out["net_demand_kw"] / 4.0
    return df_out


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: bill from arbitrary demand column
# ─────────────────────────────────────────────────────────────────────────────
def bill_from_scenario(
    df: pd.DataFrame,
    demand_col: str = "demand_kw",
    energy_col: str = "interval_kwh",
    tariff: dict = None,
) -> pd.DataFrame:
    """
    Recompute the monthly bill using arbitrary demand + energy columns.
    Useful for Q7 (PV) and Q8 (battery) scenario re-bills.
    """
    tmp = df.copy()
    tmp["demand_kw"] = tmp[demand_col]
    tmp["interval_kwh"] = tmp[energy_col]
    if "tou_period" not in tmp.columns:
        tmp["tou_period"] = classify_periods_vec(tmp["timestamp"])
    if "is_trd" not in tmp.columns:
        tmp["is_trd"] = tmp["timestamp"].apply(is_trd_hour)
    return calculate_monthly_bill(tmp, tariff)
