"""M2 - Supplier KPIs and data-mining segmentation on top of the golden records from M1.

KPIs per supplier (golden record):
  spend_eur      sum(qty_received * unit_price)
  otd_pct        on-time delivery: share of PO lines delivered on or before the promised date
  avg_delay_days average delay of late lines
  ppm            rejected parts per million received parts
  notifications  number of quality notifications

Segmentation: k-means clustering on (log spend, OTD, log PPM). k is chosen by silhouette score.
Each cluster gets a plain-language label and a suggested purchasing / supplier-quality action.

Outputs (data/output/): supplier_kpis.csv, supplier_segments.csv, segment_summary.csv,
                        docs/supplier_segments.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT, DOCS = ROOT / "data" / "raw", ROOT / "data" / "output", ROOT / "docs"

golden = pd.read_csv(OUT / "golden_suppliers.csv", dtype=str)
po = pd.read_csv(RAW / "purchase_order_lines.csv", dtype={"supplier_id": str})
qn = pd.read_csv(RAW / "quality_notifications.csv", dtype={"supplier_id": str})

# legacy record id -> golden id (this is why clean master data matters: without M1 the KPIs would be split)
legacy_to_golden = {rec.split(":", 1)[1]: g.golden_id
                    for g in golden.itertuples() for rec in g.source_records.split("; ")}
po["golden_id"] = po.supplier_id.map(legacy_to_golden)
qn["golden_id"] = qn.supplier_id.map(legacy_to_golden)
assert po.golden_id.notna().all(), "every PO line must map to a golden supplier"

po["spend"] = po.qty_received * po.unit_price_eur
po["delay"] = (pd.to_datetime(po.delivery_date) - pd.to_datetime(po.promised_date)).dt.days
po["on_time"] = po.delay <= 0

k = po.groupby("golden_id").agg(lines=("po_number", "count"), spend_eur=("spend", "sum"), otd_pct=("on_time", "mean"),
                                received=("qty_received", "sum"), rejected=("qty_rejected", "sum"))
k["avg_delay_days"] = po[~po.on_time].groupby("golden_id").delay.mean()
k["avg_delay_days"] = k.avg_delay_days.fillna(0)
k["ppm"] = k.rejected / k.received * 1e6
k["notifications"] = qn.groupby("golden_id").size()
k["notifications"] = k.notifications.fillna(0).astype(int)
k["otd_pct"] = (k.otd_pct * 100).round(1)
k = k.join(golden.set_index("golden_id")[["name", "country"]])

# ------------------------------------------------------------------ k-means on standardised features
X = np.column_stack([np.log10(k.spend_eur), k.otd_pct, np.log10(k.ppm + 1)])
Xs = StandardScaler().fit_transform(X)
scores = {n: silhouette_score(Xs, KMeans(n, n_init=20, random_state=0).fit_predict(Xs)) for n in range(3, 7)}
best_k = max(scores, key=scores.get)
km = KMeans(best_k, n_init=20, random_state=0).fit(Xs)
k["cluster"] = km.labels_

# k-means is kept as an exploratory data-mining step. With a silhouette score around 0.3 the clusters are only
# weakly separated, so the final, explainable segmentation uses KPI targets (example targets, not MAHLE values).
OTD_TARGET, PPM_TARGET = 85.0, 500.0
spend_median = k.spend_eur.median()

def segment(r):
    if r.ppm > PPM_TARGET and r.otd_pct < OTD_TARGET:
        return "Critical: quality and delivery", "Escalate: supplier development plan, consider second source"
    if r.ppm > PPM_TARGET:
        return "Quality risk", "Supplier Quality: 8D problem solving, tighter incoming inspection"
    if r.otd_pct < OTD_TARGET:
        return "Delivery risk", "Purchasing: review capacity and lead times, agree delivery KPIs"
    if r.spend_eur >= spend_median:
        return "Strategic and reliable", "Partner: long-term agreements, joint cost workshops"
    return "Reliable, lower spend", "Monitor with standard KPIs"

k[["segment", "suggested_action"]] = k.apply(lambda r: pd.Series(segment(r)), axis=1)
seg = k.groupby("segment").agg(suppliers=("name", "count"), spend_eur=("spend_eur", "sum"), median_otd_pct=("otd_pct", "median"),
                               median_ppm=("ppm", "median"), notifications=("notifications", "sum"))
seg["spend_share_pct"] = (seg.spend_eur / seg.spend_eur.sum() * 100).round(1)
seg = seg.sort_values("spend_eur", ascending=False)

k.round({"spend_eur": 0, "ppm": 0, "avg_delay_days": 1}).to_csv(OUT / "supplier_kpis.csv")
k[["name", "country", "cluster", "segment", "suggested_action"]].to_csv(OUT / "supplier_segments.csv")
seg.round({"spend_eur": 0, "median_ppm": 0}).to_csv(OUT / "segment_summary.csv")

# ------------------------------------------------------------------ chart
DOCS.mkdir(exist_ok=True)
fig, ax = plt.subplots(figsize=(10, 5))
for lab, g in k.groupby("segment"):
    ax.scatter(g.otd_pct, g.ppm + 1, s=np.sqrt(g.spend_eur) / 6, alpha=0.7, label=f"{lab} ({len(g)})")
ax.set_yscale("log")
ax.axvline(OTD_TARGET, color="grey", ls="--", lw=1)
ax.axhline(PPM_TARGET, color="grey", ls="--", lw=1)
ax.set_xlabel("On-time delivery (%)")
ax.set_ylabel("Defects (PPM + 1, log scale)")
ax.set_title("Supplier segments (bubble size = spend) - synthetic data")
ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1), title="Segment (suppliers)")
fig.tight_layout()
fig.savefig(DOCS / "supplier_segments.png", dpi=150)

print("k-means silhouette scores by k:", {n: round(v, 3) for n, v in scores.items()}, "-> k =", best_k, "(weak structure; used for exploration only)")
print(f"Final segmentation by KPI targets: OTD >= {OTD_TARGET}%, PPM <= {PPM_TARGET}")
print(seg.round({"spend_eur": 0, "median_ppm": 0}).to_string())
