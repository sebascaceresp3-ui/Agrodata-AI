"""Cache keys include the downloaded dataset version and every filter."""
import streamlit as st
from services.faostat import FAOSTATService

@st.cache_data(ttl=3600, max_entries=12, show_spinner=False)
def _cached_query(code, version, areas, items, elements, years, _svc=None):
    return (_svc or FAOSTATService()).query(code, areas, items, elements, years)

def query(code, version, areas, items, elements, years, _svc=None):
    # Large exports remain available but are not retained in the shared RAM cache.
    combinations = len(areas or ()) * len(items or ()) * (years[1]-years[0]+1 if years else 65)
    if combinations > 50000:
        return (_svc or FAOSTATService()).query(code, areas, items, elements, years)
    return _cached_query(code, version, areas, items, elements, years, _svc)

@st.cache_data(ttl=86400, max_entries=2, show_spinner=False)
def geography(version, _svc):
    from utils.geography import enrich_geography
    table = enrich_geography(_svc.area_table())
    return table[table.ISO3.notna()].drop_duplicates('Area')

@st.cache_data(ttl=86400, max_entries=16, show_spinner=False)
def items_for(version, areas, _svc):
    return _svc.available_items('QCL', areas)

@st.cache_data(ttl=86400, max_entries=16, show_spinner=False)
def years_for(version, areas, items, _svc):
    return _svc.available_years('QCL', areas, items, ['Production','Area harvested','Yield'])
