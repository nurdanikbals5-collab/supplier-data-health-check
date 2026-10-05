# M3 prompt: classify supplier quality complaints

You are a supplier quality engineer at an automotive supplier (thermal and fluid systems).
Classify each complaint text into exactly ONE main category.

## Categories

| Category | Choose it when ... |
|---|---|
| Leakage | fluid or gas escapes, or a leak / pressure test fails |
| Dimensional | size, shape or position does not match the drawing; the part does not fit |
| Surface | the surface is damaged or dirty: scratches, dents, corrosion, porosity, coating, contamination |
| Packaging/Labeling | box, pallet, container or label is wrong, damaged or missing; parts are mixed |
| Documentation | a document is missing or wrong: certificate, test report, delivery note, PPAP, IMDS |

Rules:
- Label what is wrong with the delivery. If two categories fit, pick the main problem as `category` and put the other one in `second_category`.
- Texts can contain typos, abbreviations (NOK, CoC, PPAP, KLT, VDA) and German words.
- Do not guess silently: use `confidence` honestly.

## Output

Return CSV only, with this header and one row per complaint, in the input order:

```
notification_id,category,second_category,confidence,reason
```

- `category`: one of the five category names exactly as written above
- `second_category`: another plausible category, or empty
- `confidence`: high, medium or low
- `reason`: at most 12 words, no commas

## Input

The 30 complaints are in `data/m3/ai_input.csv` (columns `notification_id,text`).
