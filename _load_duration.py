"""Quick load-duration-curve analysis to size the battery."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from helpers import load_and_clean_data

HERE = Path(__file__).parent
df = load_and_clean_data(HERE / "data_test" / "intervals_1000000001.csv", 2024)

sorted_kw = np.sort(df["demand_kw"].values)[::-1]
hours = np.arange(len(sorted_kw)) * 0.25  # each interval = 0.25 hr

# Print key percentiles
print("Load duration analysis (2024, 35,136 intervals × 15 min = 8,784 hrs)")
print()
print("Peak = highest 15-min avg kW; 'above' = hours/yr load exceeds threshold")
print()
peak_kw = sorted_kw[0]
for target_below_peak in [0, 25, 50, 75, 100, 125, 150, 200, 250]:
    threshold = peak_kw - target_below_peak
    hours_above = (sorted_kw > threshold).sum() * 0.25
    print(f"  Load > peak - {target_below_peak:>3} kW ({threshold:>6.1f} kW): "
          f"{hours_above:>7.2f} hr/yr")

print()
print("Duration hours of top-N intervals:")
for topN in [4, 20, 96, 480, 2400]:
    if topN <= len(sorted_kw):
        band_top = sorted_kw[0]
        band_bottom = sorted_kw[topN - 1]
        print(f"  Top {topN:>4} intervals ({topN*0.25:>6.1f} hr): "
              f"{band_bottom:.1f}-{band_top:.1f} kW")

# Battery duration analysis: at various kW ratings, how long does 250 kWh
# last discharging into a load that exceeds (peak - kW)?
print()
print("Battery sizing tradeoff (250 kWh fixed):")
print(f"{'kW':>6} {'Duration':>10} {'Shave depth':>13} {'FRD $/yr saved':>16}")
frd_rate = 24.86  # $/kW/mo
for kw in [50, 62.5, 83, 100, 125, 150, 200, 250]:
    duration_hr = 250 / kw
    # Approx: if we can shave up to `kw` kW off the peak, FRD saves that
    frd_savings = kw * frd_rate * 12
    print(f"{kw:>6.1f} {duration_hr:>7.2f} hr {kw:>10.0f} kW {frd_savings:>13,.0f}")

# Plot
fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))

# LDC full
axes[0].plot(hours, sorted_kw, color="#1976D2", linewidth=1.2)
axes[0].fill_between(hours, sorted_kw, alpha=0.15)
axes[0].axhline(peak_kw, color="red", linestyle="--", linewidth=0.8,
                label=f"Peak = {peak_kw:.0f} kW")
axes[0].axhline(peak_kw - 125, color="orange", linestyle=":", linewidth=0.8,
                label=f"Peak - 125 kW = {peak_kw - 125:.0f} kW")
axes[0].axhline(peak_kw - 50, color="green", linestyle=":", linewidth=0.8,
                label=f"Peak - 50 kW = {peak_kw - 50:.0f} kW")
axes[0].set_xlabel("Hours per year at or above threshold")
axes[0].set_ylabel("Demand (kW)")
axes[0].set_title("Load Duration Curve - 2024")
axes[0].legend(fontsize=8)

# LDC zoom: top 500 hours
axes[1].plot(hours[:2000], sorted_kw[:2000], color="#1976D2", linewidth=1.2)
axes[1].axhline(peak_kw - 125, color="orange", linestyle=":", linewidth=0.8)
axes[1].axhline(peak_kw - 83, color="purple", linestyle=":", linewidth=0.8)
axes[1].axhline(peak_kw - 50, color="green", linestyle=":", linewidth=0.8)
axes[1].set_xlabel("Hours per year at or above threshold (zoomed)")
axes[1].set_ylabel("Demand (kW)")
axes[1].set_title("Top 500 hours (out of 8,784)")

fig.tight_layout()
plt.savefig(HERE / "load_duration_curve.png", dpi=110, bbox_inches="tight")
print(f"\nPlot saved to load_duration_curve.png")
