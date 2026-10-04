"""Generate a synthetic dataset that mimics a supplier master-data migration
from two legacy ERP systems into one SAP S/4HANA system.

ALL DATA IS SYNTHETIC. Company names, tax IDs, IBANs and transactions are
randomly generated and do not describe real organisations.

Outputs (data/raw/):
  erp_a_vendors.csv          - legacy SAP-like vendor master (SAP-style field names)
  erp_b_suppliers.csv        - legacy non-SAP supplier master (different formats)
  purchase_order_lines.csv   - PO lines with promised vs. actual delivery
  quality_notifications.csv  - free-text supplier quality complaints
  _truth_supplier_ids.csv    - hidden answer key (which records are the same real supplier)
"""
import random
import string
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SEED = 7
random.seed(SEED)
OUT = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

# Country rules: ISO code, full name, VAT pattern generator, IBAN length, legal form, cities (postcode prefix)
COUNTRIES = {
    "DE": ("Germany", lambda: "DE" + _digits(9), 22, "GmbH", [("Stuttgart", "70"), ("Munich", "80"), ("Cologne", "50"), ("Leipzig", "04")]),
    "PL": ("Poland", lambda: "PL" + _digits(10), 28, "Sp. z o.o.", [("Krakow", "30"), ("Wroclaw", "50"), ("Poznan", "60")]),
    "CZ": ("Czech Republic", lambda: "CZ" + _digits(8), 24, "s.r.o.", [("Brno", "60"), ("Prague", "11"), ("Ostrava", "70")]),
    "FR": ("France", lambda: "FR" + _digits(11), 27, "SAS", [("Lyon", "69"), ("Lille", "59"), ("Toulouse", "31")]),
    "IT": ("Italy", lambda: "IT" + _digits(11), 27, "S.r.l.", [("Turin", "10"), ("Milan", "20"), ("Bologna", "40")]),
    "AT": ("Austria", lambda: "ATU" + _digits(8), 20, "GmbH", [("Graz", "80"), ("Linz", "40"), ("Vienna", "11")]),
}
POSTCODE_LEN = {"DE": 5, "PL": 5, "CZ": 5, "FR": 5, "IT": 5, "AT": 4}
COMMODITIES = ["Aluminium castings", "Rubber seals", "Plastic housings", "Electronic sensors",
               "Brazed heat exchangers", "Fasteners", "Hoses & connectors", "Valves", "Packaging"]
NAME_A = ["Alpen", "Rhein", "Nord", "Silber", "Kraft", "Vela", "Bora", "Tauro", "Lumen", "Orbis", "Ferro",
          "Polar", "Vento", "Cerro", "Delta", "Nova", "Prima", "Terra", "Aqua", "Volta", "Atlas", "Kappa"]
NAME_B = ["tec", "werk", "metal", "flex", "plast", "tronic", "form", "guss", "seal", "line", "parts", "cast"]
TERMS = [("NT30", "Net 30"), ("NT60", "60 days net"), ("NT45", "45 days"), ("SK14", "2% 14 days, net 30")]


def _digits(n):
    return "".join(random.choice(string.digits) for _ in range(n))


def iban(country, length):
    """Build a syntactically valid IBAN (correct ISO 7064 mod-97 check digits)."""
    bban = _digits(length - 4)
    rearranged = bban + country + "00"
    numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    check = 98 - int(numeric) % 97
    return f"{country}{check:02d}{bban}"


# ---------------------------------------------------------------- real suppliers
suppliers = []
used = set()
for i in range(1, 121):
    while True:
        base = random.choice(NAME_A) + random.choice(NAME_B)
        if base not in used:
            used.add(base)
            break
    cc = random.choices(list(COUNTRIES), weights=[40, 18, 12, 10, 10, 10])[0]
    cname, vatgen, iban_len, legal, cities = COUNTRIES[cc]
    city, prefix = random.choice(cities)
    postcode = prefix + _digits(POSTCODE_LEN[cc] - len(prefix))
    term = random.choice(TERMS)
    suppliers.append(dict(
        true_id=f"S{i:03d}", name=f"{base} {legal}", country=cc, country_name=cname, city=city,
        postcode=postcode, vat=vatgen(), iban=iban(cc, iban_len), term_code=term[0], term_text=term[1],
        commodity=random.choice(COMMODITIES),
        quality_level=random.choices(["good", "average", "poor"], weights=[55, 30, 15])[0],
        delivery_level=random.choices(["good", "average", "poor"], weights=[55, 30, 15])[0],
        spend_level=random.choices(["high", "medium", "low"], weights=[20, 40, 40])[0],
    ))

ids = [s["true_id"] for s in suppliers]
in_a = set(random.sample(ids, 85))
in_b = set(random.sample(sorted(set(ids) - in_a), 35)) | set(random.sample(sorted(in_a), 40))
by_id = {s["true_id"]: s for s in suppliers}


def name_variant(name):
    """Realistic spelling drift between systems."""
    v = random.choice(["upper", "nolegal", "typo", "space", "same"])
    if v == "upper":
        return name.upper()
    if v == "nolegal":
        return name.rsplit(" ", 1)[0] if " " in name else name
    if v == "typo" and len(name) > 6:
        k = random.randint(1, len(name.split(" ")[0]) - 2)
        return name[:k] + name[k + 1:]
    if v == "space":
        return name.replace(" ", "  ")
    return name


# ---------------------------------------------------------------- ERP A (SAP-like)
rows_a, truth = [], []
lifnr = 100000
for tid in sorted(in_a):
    s = by_id[tid]
    lifnr += random.randint(1, 9)
    rows_a.append(dict(LIFNR=f"{lifnr:010d}", NAME1=s["name"], LAND1=s["country"], ORT01=s["city"],
                       PSTLZ=s["postcode"], STCEG=s["vat"], IBAN=s["iban"], ZTERM=s["term_code"],
                       ERDAT=(date(2012, 1, 1) + timedelta(days=random.randint(0, 4000))).isoformat()))
    truth.append(dict(system="ERP_A", record_id=f"{lifnr:010d}", true_id=tid))

# ---------------------------------------------------------------- ERP B (non-SAP, different conventions)
rows_b = []
for n, tid in enumerate(sorted(in_b), start=1):
    s = by_id[tid]
    vat = s["vat"]
    if random.random() < 0.3:  # spaces in tax IDs
        vat = vat[:2] + " " + vat[2:5] + " " + vat[5:]
    rows_b.append(dict(supplier_code=f"SUP-{n:04d}", company_name=name_variant(s["name"]),
                       country=s["country_name"], city=s["city"], zip=s["postcode"], vat_number=vat,
                       bank_account=s["iban"], payment_terms=s["term_text"], main_commodity=s["commodity"]))
    truth.append(dict(system="ERP_B", record_id=f"SUP-{n:04d}", true_id=tid))

a = pd.DataFrame(rows_a)
b = pd.DataFrame(rows_b)

# ---------------------------------------------------------------- inject data-quality problems
def blank(df, col, k):
    idx = random.sample(list(df.index), k)
    df.loc[idx, col] = None
    return idx

blank(a, "STCEG", 6)          # missing VAT ID
blank(a, "ZTERM", 5)          # missing payment terms
blank(a, "IBAN", 4)           # missing bank details
blank(b, "vat_number", 5)
blank(b, "zip", 3)

for i in random.sample(list(a.index), 4):          # invalid VAT format (too short)
    if pd.notna(a.at[i, "STCEG"]):
        a.at[i, "STCEG"] = a.at[i, "STCEG"][:-2]
for i in random.sample(list(a.index), 3):          # broken IBAN check digits
    if pd.notna(a.at[i, "IBAN"]):
        v = a.at[i, "IBAN"]
        a.at[i, "IBAN"] = v[:2] + ("00" if v[2:4] != "00" else "11") + v[4:]
for i in random.sample(list(b.index), 3):          # wrong country spelling
    b.at[i, "country"] = {"Germany": "Deutschland", "Czech Republic": "Czechia", "Poland": "Polska"}.get(b.at[i, "country"], b.at[i, "country"].upper())
for i in random.sample(list(b.index), 2):          # postcode with wrong length
    if pd.notna(b.at[i, "zip"]):
        b.at[i, "zip"] = b.at[i, "zip"] + "9"

# duplicates INSIDE ERP A (same supplier created twice)
for tid_row in random.sample(rows_a, 4):
    dup = dict(tid_row)
    lifnr += random.randint(1, 9)
    dup["LIFNR"] = f"{lifnr:010d}"
    dup["NAME1"] = name_variant(dup["NAME1"])
    dup["ERDAT"] = (date(2021, 1, 1) + timedelta(days=random.randint(0, 1500))).isoformat()
    a = pd.concat([a, pd.DataFrame([dup])], ignore_index=True)
    truth.append(dict(system="ERP_A", record_id=dup["LIFNR"],
                      true_id=next(t["true_id"] for t in truth if t["record_id"] == tid_row["LIFNR"])))

# ---------------------------------------------------------------- transactions (for supplier KPIs)
QL = {"good": 0.0001, "average": 0.0008, "poor": 0.005}  # share of rejected parts (100 / 800 / 5,000 ppm)
DL = {"good": 0.92, "average": 0.78, "poor": 0.55}        # probability of on-time delivery
SPEND = {"high": (40, 90), "medium": (15, 40), "low": (4, 15)}
po_rows, qn_rows = [], []
po = 4500000000
DEFECTS = [
    ("Leakage", ["Leak detected at connector during pressure test", "Coolant leakage at brazed joint", "Seal not tight, fluid loss at flange"]),
    ("Dimensional", ["Dimension out of tolerance on bore diameter", "Wall thickness below drawing spec", "Hole position shifted 0.4 mm"]),
    ("Surface", ["Scratches and dents on visible surface", "Corrosion spots found on delivery", "Porosity on casting surface"]),
    ("Packaging/Labeling", ["Wrong label on pallet, part number missing", "Packaging damaged, parts loose in box", "Mixed parts in one container"]),
    ("Documentation", ["Material certificate missing", "Wrong revision on delivery note", "Test report not attached to shipment"]),
]
qn = 200000
for s in suppliers:
    n_lines = random.randint(*SPEND[s["spend_level"]])
    for _ in range(n_lines):
        po += random.randint(1, 30)
        promised = date(2026, 1, 5) + timedelta(days=random.randint(0, 240))
        late = 0 if random.random() < DL[s["delivery_level"]] else random.randint(1, 15)
        qty = random.choice([100, 200, 500, 1000, 2000, 5000])
        price = round(random.uniform(0.5, 120), 2)
        rejected = random.binomialvariate(qty, QL[s["quality_level"]])
        po_rows.append(dict(po_number=po, true_id=s["true_id"], commodity=s["commodity"], promised_date=promised.isoformat(),
                            delivery_date=(promised + timedelta(days=late)).isoformat(), qty_received=qty,
                            qty_rejected=rejected, unit_price_eur=price))
        if rejected and random.random() < 0.35:
            cat, texts = random.choice(DEFECTS)
            qn += 1
            qn_rows.append(dict(notification_id=f"QN{qn}", po_number=po, true_id=s["true_id"],
                                created=(promised + timedelta(days=late + random.randint(0, 5))).isoformat(),
                                description=random.choice(texts), true_category=cat))

# Supplier IDs in transactions: the migrated system only knows legacy IDs, so map to ERP_A if possible, else ERP_B
truth_df = pd.DataFrame(truth)
first_a = truth_df[truth_df.system == "ERP_A"].drop_duplicates("true_id").set_index("true_id")["record_id"]
first_b = truth_df[truth_df.system == "ERP_B"].drop_duplicates("true_id").set_index("true_id")["record_id"]
legacy = lambda t: first_a.get(t, first_b.get(t))
pos = pd.DataFrame(po_rows)
pos.insert(1, "supplier_id", pos.true_id.map(legacy))
qns = pd.DataFrame(qn_rows)
qns.insert(2, "supplier_id", qns.true_id.map(legacy))

a.sample(frac=1, random_state=SEED).to_csv(OUT / "erp_a_vendors.csv", index=False)
b.sample(frac=1, random_state=SEED).to_csv(OUT / "erp_b_suppliers.csv", index=False)
pos.drop(columns="true_id").to_csv(OUT / "purchase_order_lines.csv", index=False)
qns.drop(columns=["true_id", "true_category"]).to_csv(OUT / "quality_notifications.csv", index=False)
truth_df.to_csv(OUT / "_truth_supplier_ids.csv", index=False)
qns[["notification_id", "true_category"]].to_csv(OUT / "_truth_quality_categories.csv", index=False)
print(f"ERP_A vendors: {len(a)} | ERP_B suppliers: {len(b)} | PO lines: {len(pos)} | quality notifications: {len(qns)}")
