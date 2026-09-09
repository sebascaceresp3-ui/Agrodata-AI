"""Aggregations never add yields, currencies or incompatible physical units."""
from __future__ import annotations
import pandas as pd

YIELD_FACTORS = {"kg/ha": 1.0, "hg/ha": 0.1, "100 mg/ha": 0.0001, "t/ha": 1000.0}


def normalize_yields(frame):
    out = frame.copy()
    mask = out.Element.eq("Yield") & out.Unit.isin(YIELD_FACTORS)
    out.loc[mask, "Value"] = out.loc[mask, "Value"] * out.loc[mask, "Unit"].map(YIELD_FACTORS)
    out.loc[mask, "Unit"] = "kg/ha"
    return out


def total(frame, element, year, unit):
    rows = frame[frame.Element.eq(element) & frame.Year.eq(year) & frame.Unit.eq(unit)]
    value = rows.Value.sum(min_count=1)
    return None if pd.isna(value) else float(value)


def yield_summary(frame, groups):
    """Area-weight official yields; no filling of missing yields or missing areas.

    A single observation can use its published yield without an area. For an
    aggregate every crop-country observation must have both yield and positive
    harvested area, otherwise the aggregate is N/D (no partial coverage bias).
    """
    keys = ["Area", "Item", "Year"]
    data = normalize_yields(frame)
    universe = data[data.Element.isin(["Production", "Area harvested", "Yield"])][keys].drop_duplicates()
    ys = data[data.Element.eq("Yield") & data.Unit.eq("kg/ha")][keys + ["Value"]].rename(columns={"Value": "yield"})
    areas = data[data.Element.eq("Area harvested") & data.Unit.eq("ha")][keys + ["Value"]].rename(columns={"Value": "area"})
    paired = universe.merge(ys, on=keys, how="left", validate="one_to_one").merge(areas, on=keys, how="left", validate="one_to_one")
    records = []
    for name, rows in paired.groupby(groups, dropna=False, sort=True):
        name = name if isinstance(name, tuple) else (name,)
        value = None
        if len(rows) == 1 and rows["yield"].notna().all():
            value = float(rows["yield"].iloc[0])
        elif rows["yield"].notna().all() and rows.area.notna().all() and rows.area.gt(0).all():
            value = float((rows["yield"] * rows.area).sum() / rows.area.sum())
        records.append({**dict(zip(groups, name)), "Value": value, "Unit": "kg/ha"})
    return pd.DataFrame(records, columns=groups + ["Value", "Unit"])


def aggregate(frame, element, groups):
    if element == "Yield":
        return yield_summary(frame, groups)
    rows = frame[frame.Element.eq(element)]
    return rows.groupby(groups + ["Unit"], as_index=False, dropna=False).Value.sum(min_count=1)


def shares_and_ranks(frame):
    """Full supplied reference population, including ties; missing != zero."""
    result = frame.dropna(subset=["Value"]).copy()
    result["Ranking"] = result.Value.rank(method="min", ascending=False).astype(int)
    denominator = result.Value.sum(min_count=1)
    result["Participación (%)"] = result.Value / denominator * 100 if pd.notna(denominator) and denominator > 0 else float("nan")
    return result.sort_values(["Ranking", "Area"])
