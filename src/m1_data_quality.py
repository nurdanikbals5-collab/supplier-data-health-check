"""M1 - Data quality checks and golden-record proposal for a supplier master-data
migration from two legacy ERP systems (ERP_A: SAP-like, ERP_B: non-SAP) into SAP S/4HANA.

Data-quality dimensions used:
  completeness  - mandatory field is empty
  validity      - value breaks a format rule (VAT ID pattern, IBAN check digits, postcode length)
  consistency   - value contradicts another field or a standard (VAT prefix vs. country, non-ISO country name)
  uniqueness    - the same supplier exists more than once

Outputs (data/output/):
  dq_issues.csv          one row per issue  -> feeds the Excel ticket tracker (M4)
  dq_summary.csv         issue counts by system and dimension
  match_candidates.csv   record pairs that look like the same supplier, with reason and confidence
  golden_suppliers.csv   one proposed golden record per supplier, with field sources and conflicts
"""
import re
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "output"
OUT.mkdir(parents=True, exist_ok=True)

VAT_RULES = {"DE": r"^DE\d{9}$", "PL": r"^PL\d{10}$", "CZ": r"^CZ\d{8,10}$",
             "FR": r"^FR[0-9A-Z]{2}\d{9}$", "IT": r"^IT\d{11}$", "AT": r"^ATU\d{8}$"}
IBAN_LEN = {"DE": 22, "PL": 28, "CZ": 24, "FR": 27, "IT": 27, "AT": 20}
POSTCODE_LEN = {"DE": 5, "PL": 5, "CZ": 5, "FR": 5, "IT": 5, "AT": 4}
COUNTRY_MAP = {"germany": "DE", "poland": "PL", "czech republic": "CZ", "france": "FR", "italy": "IT", "austria": "AT"}
COUNTRY_ALIASES = {"deutschland": "DE", "polska": "PL", "czechia": "CZ", "frankreich": "FR", "italia": "IT", "österreich": "AT"}
TERMS_MAP = {"net 30": "NT30", "60 days net": "NT60", "45 days": "NT45", "2% 14 days, net 30": "SK14"}
LEGAL_FORMS = r"\b(gmbh|sp\. z o\.o\.|s\.r\.o\.|sas|s\.r\.l\.)"

issues = []


def add(system, rec_id, name, field, dimension, rule, value, severity, action):
    issues.append(dict(system=system, record_id=rec_id, supplier_name=name, field=field, dimension=dimension,
                       rule=rule, value="" if pd.isna(value) else str(value), severity=severity, suggested_action=action))


def iban_ok(v):
    v = v.replace(" ", "")
    if len(v) != IBAN_LEN.get(v[:2], -1):
        return False
    num = "".join(str(int(c, 36)) for c in v[4:] + v[:4])
    return int(num) % 97 == 1


def norm_name(n):
    n = str(n).lower()
    n = re.sub(LEGAL_FORMS, " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


# ------------------------------------------------------------------ load and harmonise to one target schema
a = pd.read_csv(RAW / "erp_a_vendors.csv", dtype=str)
b = pd.read_csv(RAW / "erp_b_suppliers.csv", dtype=str)

A = pd.DataFrame({"system": "ERP_A", "record_id": a.LIFNR, "name": a.NAME1, "country": a.LAND1, "city": a.ORT01,
                  "postcode": a.PSTLZ, "vat": a.STCEG, "iban": a.IBAN, "terms": a.ZTERM, "created": a.ERDAT})

country_std = b.country.str.strip().str.lower().map(COUNTRY_MAP)            # standard English name
country_b = country_std.fillna(b.country.str.strip().str.lower().map(COUNTRY_ALIASES))  # known local spellings
terms_b = b.payment_terms.str.strip().str.lower().map(TERMS_MAP)
B = pd.DataFrame({"system": "ERP_B", "record_id": b.supplier_code, "name": b.company_name, "country": country_b,
                  "city": b.city, "postcode": b.zip, "vat": b.vat_number.str.replace(" ", "", regex=False),
                  "iban": b.bank_account, "terms": terms_b, "created": None})

# issues that only exist because of ERP_B's conventions (found while harmonising)
for i, r in b.iterrows():
    if pd.isna(country_std[i]):
        mapped = country_b[i]
        add("ERP_B", r.supplier_code, r.company_name, "country", "consistency", "Country is not a standard English name / ISO code",
            r.country, "Medium", f"Map to ISO code {mapped}" if pd.notna(mapped) else "Map to ISO 3166 country code")
    if pd.notna(r.vat_number) and " " in r.vat_number:
        add("ERP_B", r.supplier_code, r.company_name, "vat_number", "consistency", "VAT ID contains spaces",
            r.vat_number, "Low", "Remove spaces during migration")
    if pd.isna(terms_b[i]) and pd.notna(r.payment_terms):
        add("ERP_B", r.supplier_code, r.company_name, "payment_terms", "consistency", "Payment terms text cannot be mapped to a term code",
            r.payment_terms, "Medium", "Agree mapping with Finance")

ALL = pd.concat([A, B], ignore_index=True)
ALL["name_norm"] = ALL.name.map(norm_name)

# ------------------------------------------------------------------ record-level rules (both systems, target schema)
for _, r in ALL.iterrows():
    sysname, rid, nm, cc = r.system, r.record_id, r["name"], r.country
    for field, sev in [("vat", "High"), ("iban", "High"), ("terms", "Medium"), ("postcode", "Medium")]:
        if pd.isna(r[field]) and not (field == "terms" and sysname == "ERP_B" and pd.notna(b.set_index("supplier_code").payment_terms.get(rid))):
            add(sysname, rid, nm, field, "completeness", f"Mandatory field '{field}' is empty", None, sev,
                "Request value from supplier / purchasing")
    if pd.notna(r.vat) and pd.notna(cc) and cc in VAT_RULES and not re.match(VAT_RULES[cc], r.vat):
        if r.vat[:2] != cc:
            add(sysname, rid, nm, "vat", "consistency", "VAT prefix does not match country", r.vat, "High", "Verify country and VAT ID")
        else:
            add(sysname, rid, nm, "vat", "validity", f"VAT ID does not match the {cc} format", r.vat, "High", "Verify VAT ID (e.g. EU VIES check)")
    if pd.notna(r.iban):
        if not iban_ok(r.iban):
            add(sysname, rid, nm, "iban", "validity", "IBAN fails length or check-digit test", r.iban, "High", "Block payments until bank data is confirmed")
        elif pd.notna(cc) and r.iban[:2] != cc:
            add(sysname, rid, nm, "iban", "consistency", "IBAN country differs from supplier country", r.iban, "Medium", "Confirm bank country")
    if pd.notna(r.postcode) and pd.notna(cc) and len(str(r.postcode)) != POSTCODE_LEN.get(cc, len(str(r.postcode))):
        add(sysname, rid, nm, "postcode", "validity", f"Postcode length is wrong for {cc}", r.postcode, "Medium", "Correct postcode")

# ------------------------------------------------------------------ duplicate / match detection
pairs = []
recs = ALL.to_dict("records")
for i in range(len(recs)):
    for j in range(i + 1, len(recs)):
        x, y = recs[i], recs[j]
        if pd.notna(x["vat"]) and x["vat"] == y["vat"]:
            pairs.append((i, j, 100, "Same VAT ID"))
            continue
        if pd.notna(x["iban"]) and x["iban"] == y["iban"]:
            pairs.append((i, j, 100, "Same IBAN"))
            continue
        if x["country"] != y["country"] or pd.isna(x["country"]):
            continue
        score = fuzz.token_sort_ratio(x["name_norm"], y["name_norm"])
        same_place = (pd.notna(x["postcode"]) and x["postcode"] == y["postcode"]) or x["city"] == y["city"]
        if score >= 88 and same_place:
            pairs.append((i, j, score, f"Similar name ({score:.0f}%) + same {'postcode' if x['postcode'] == y['postcode'] else 'city'}"))

match_rows = []
for i, j, score, reason in pairs:
    x, y = recs[i], recs[j]
    same_system = x["system"] == y["system"]
    conf = "High" if score == 100 or score >= 95 else "Medium"
    match_rows.append(dict(record_1=f"{x['system']}:{x['record_id']}", name_1=x["name"], record_2=f"{y['system']}:{y['record_id']}",
                           name_2=y["name"], match_type="duplicate within one system" if same_system else "same supplier in both systems",
                           score=round(score), reason=reason, confidence=conf))
    if same_system:
        add(x["system"], y["record_id"], y["name"], "record", "uniqueness",
            f"Possible duplicate of {x['record_id']} ({reason})", "", "High", "Merge into one record before migration")
matches = pd.DataFrame(match_rows)

# ------------------------------------------------------------------ golden records (union-find over matched pairs)
parent = list(range(len(recs)))
def find(k):
    while parent[k] != k:
        parent[k] = parent[parent[k]]
        k = parent[k]
    return k
for i, j, _, _ in pairs:
    parent[find(i)] = find(j)

ALL["cluster"] = [find(k) for k in range(len(recs))]
issue_keys = {(d["system"], d["record_id"], d["field"]) for d in issues if d["dimension"] in ("validity", "consistency")}
golden = []
for n, (_, grp) in enumerate(ALL.groupby("cluster", sort=False), start=1):
    grp = grp.assign(_a=(grp.system == "ERP_A").astype(int), _filled=grp.notna().sum(axis=1)).sort_values(["_a", "_filled"], ascending=False)
    row = {"golden_id": f"G{n:04d}", "source_records": "; ".join(grp.system + ":" + grp.record_id)}
    conflicts = []
    for field in ["name", "country", "city", "postcode", "vat", "iban", "terms"]:
        good = [v for s, rid, v in zip(grp.system, grp.record_id, grp[field])
                if pd.notna(v) and (s, rid, field) not in issue_keys]
        vals = good or [v for v in grp[field] if pd.notna(v)]
        row[field] = vals[0] if vals else None
        if field in ("vat", "iban", "terms") and len(set(vals)) > 1:
            conflicts.append(field)
    row["conflicts"] = ", ".join(conflicts)
    row["needs_review"] = bool(conflicts) or any(
        (m.confidence == "Medium") for m in matches.itertuples()
        if m.record_1.split(":", 1)[1] in set(grp.record_id) or m.record_2.split(":", 1)[1] in set(grp.record_id))
    golden.append(row)
golden = pd.DataFrame(golden)

# ------------------------------------------------------------------ write outputs
dq = pd.DataFrame(issues).drop_duplicates(subset=["system", "record_id", "field", "rule"]).reset_index(drop=True)
dq.insert(0, "issue_id", [f"DQ-{k:04d}" for k in range(1, len(dq) + 1)])
dq.to_csv(OUT / "dq_issues.csv", index=False)
summary = dq.pivot_table(index="dimension", columns="system", values="issue_id", aggfunc="count", fill_value=0)
summary["total"] = summary.sum(axis=1)
summary.to_csv(OUT / "dq_summary.csv")
matches.to_csv(OUT / "match_candidates.csv", index=False)
golden.to_csv(OUT / "golden_suppliers.csv", index=False)

# ------------------------------------------------------------------ honest evaluation against the hidden answer key
truth = pd.read_csv(RAW / "_truth_supplier_ids.csv", dtype=str)
tid = dict(zip(truth.system + ":" + truth.record_id, truth.true_id))
true_pairs = set()
for t, g in truth.groupby("true_id"):
    keys = list(g.system + ":" + g.record_id)
    true_pairs |= {tuple(sorted((keys[p], keys[q]))) for p in range(len(keys)) for q in range(p + 1, len(keys))}
found_pairs = {tuple(sorted((m.record_1, m.record_2))) for m in matches.itertuples()}
tp = len(found_pairs & true_pairs)
precision = tp / len(found_pairs) if found_pairs else 0
recall = tp / len(true_pairs) if true_pairs else 0

print("Records:", len(A), "in ERP_A +", len(B), "in ERP_B =", len(ALL))
print("Data-quality issues:", len(dq))
print(summary.to_string())
print(f"Match candidates: {len(matches)} | golden records: {len(golden)} (true number of suppliers: {truth.true_id.nunique()})")
print(f"Golden records needing human review: {int(golden.needs_review.sum())}")
print(f"Matching quality vs. answer key: precision {precision:.0%}, recall {recall:.0%} ({tp} of {len(true_pairs)} true pairs found, {len(found_pairs) - tp} false matches)")
