from __future__ import annotations
import math
import pandas as pd

def annual_change(current, previous):
    if previous in (None, 0) or pd.isna(previous) or pd.isna(current):
        return None
    return (float(current) - float(previous)) / abs(float(previous)) * 100

def cagr(start, end, years):
    if years <= 0 or start is None or end is None or start <= 0 or end < 0:
        return None
    return ((end / start) ** (1 / years) - 1) * 100

def compact(value):
    if value is None or pd.isna(value): return "N/D"
    value = float(value)
    for scale, suffix in ((1e9," mil M"),(1e6," M"),(1e3," mil")):
        if abs(value) >= scale: return f"{value/scale:,.2f}{suffix}"
    return f"{value:,.2f}"

def safe_div(a, b):
    return None if a is None or pd.isna(a) or b in (None, 0) or pd.isna(b) else a / b
