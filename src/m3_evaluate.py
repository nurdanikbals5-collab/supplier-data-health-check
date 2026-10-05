"""M3 (step 3) - Compare human labels, AI labels and the synthetic answer key for the 30 sample complaints.

AI labels come from a separate Claude session that saw only prompts/m3_classify_prompt.md and data/m3/ai_input.csv
(no answer key, no human labels). Review rule tested here: the AI may assign a category on its own only when its
confidence is "high" and it names no second category; everything else goes to a human.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ai = pd.read_csv(ROOT / "data" / "m3" / "ai_labels.csv", dtype=str).fillna("")
human = pd.read_excel(ROOT / "excel" / "M3_Complaint_Labeling.xlsx", sheet_name="Label", dtype=str).fillna("")
truth = pd.read_csv(ROOT / "data" / "raw" / "_truth_quality_categories.csv", dtype=str).fillna("")

df = (human.rename(columns={"Notification ID": "notification_id", "Complaint text": "text",
                            "My category": "human_category", "Note (optional)": "human_note"})
      [["notification_id", "text", "human_category", "human_note"]]
      .merge(ai.rename(columns={"category": "ai_category", "second_category": "ai_second_category",
                                "confidence": "ai_confidence", "reason": "ai_reason"}), on="notification_id")
      .merge(truth.rename(columns={"second_category": "true_second_category"}), on="notification_id"))
df["ai_correct"] = df.ai_category == df.true_category
df["human_correct"] = df.human_category == df.true_category
df["needs_review"] = (df.ai_confidence != "high") | (df.ai_second_category != "")

n = len(df)
auto = df[~df.needs_review]
print(f"Complaints: {n} ({(df.ambiguous == 'True').sum()} ambiguous)")
print(f"AI vs answer key:    {df.ai_correct.sum()}/{n}")
print(f"Human vs answer key: {df.human_correct.sum()}/{n}")
print(f"AI vs human agree:   {(df.ai_category == df.human_category).sum()}/{n}")
print(f"Review rule: {df.needs_review.sum()} sent to a human, {len(auto)} auto-assigned "
      f"({auto.ai_correct.sum()}/{len(auto)} correct); ambiguous cases sent to review: "
      f"{(df.needs_review & (df.ambiguous == 'True')).sum()}/{(df.ambiguous == 'True').sum()}")

out = ROOT / "data" / "output" / "m3_comparison.csv"
df.to_csv(out, index=False)
print(f"Details written to {out}")
