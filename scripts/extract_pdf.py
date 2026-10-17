"""One-off extractor: SHS list PDF -> data/schools_real.csv (one row per school)."""
import csv
import re
import sys
from collections import Counter

import pdfplumber

PDF = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "data/schools_real.csv"

PROG_X = [("agric", 467), ("business", 510), ("technical", 543), ("home_economics", 600),
          ("visual_arts", 645), ("general_arts", 677), ("science", 708)]
X_CAT, X_REGION, X_GENDER, X_STATUS, X_PROG = 220, 270, 345, 395, 460

REGION_MAP = {
    "EASTERN": "Eastern", "G. ACCRA": "Greater Accra", "ASHANTI": "Ashanti", "CENTRAL": "Central",
    "NORTHERN": "Northern", "WESTERN": "Western", "VOLTA": "Volta", "OTI": "Oti",
    "SAVANNAH": "Savannah", "U. EAST": "Upper East", "U. WEST": "Upper West",
    "BONO EAST": "Bono East", "NORTH EAST": "North East", "WESTERN NORTH": "Western North",
    "AHAFO": "Ahafo", "B. AHAFO": "Bono", "BRONG AHAFO": "Bono",
}


def nearest_prog(x):
    return min(PROG_X, key=lambda p: abs(p[1] - x))[0]


def join(ws, lo, hi):
    return " ".join(w["text"] for w in ws if lo <= w["x0"] < hi)


def main():
    rows = []
    with pdfplumber.open(PDF) as pdf:
        for page in pdf.pages[1:17]:
            lines = {}
            for w in page.extract_words():
                if w["top"] < 118:
                    continue
                lines.setdefault(round(w["top"]), []).append(w)
            for k in sorted(lines):
                ws = sorted(lines[k], key=lambda w: w["x0"])
                name = join(ws, 0, X_CAT)
                cat = join(ws, X_CAT, X_REGION)
                region = join(ws, X_REGION, X_GENDER)
                gender = join(ws, X_GENDER, X_STATUS)
                progs = {nearest_prog((w["x0"] + w["x1"]) / 2) for w in ws
                         if w["x0"] >= X_PROG and w["text"].upper() == "YES"}
                if cat.startswith("CAT"):
                    rows.append({"name": name, "cat": cat, "region": region, "gender": gender,
                                 "status": join(ws, X_STATUS, X_PROG), "progs": progs})
                elif rows and name and not cat and not region and not gender:
                    rows[-1]["name"] += " " + name
                    rows[-1]["progs"] |= progs

    out = []
    for r in rows:
        region = re.sub(r"\s+", " ", r["region"]).strip()
        out.append({
            "school": re.sub(r"\s+", " ", r["name"]).strip(" ."),
            "category": r["cat"].replace("CAT.", "").strip(),
            "region": REGION_MAP.get(region.upper(), region),
            "gender": r["gender"].strip().lower(),
            "residency": "day/boarding" if "boarding" in r["status"].lower() else "day",
            **{p: "yes" if p in r["progs"] else "no" for p, _ in PROG_X},
        })

    fields = ["school", "category", "region", "gender", "residency"] + [p for p, _ in PROG_X]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)
    print(len(out), Counter(o["category"] for o in out))
    print(Counter(o["region"] for o in out))
    print(Counter(o["gender"] for o in out), Counter(o["residency"] for o in out))


main()
