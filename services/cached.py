"""Cache keys include the downloaded dataset version and every filter."""
import streamlit as st
from services.faostat import FAOSTATService

@st.cache_data(ttl=3600, max_entries=128, show_spinner=False)
def query(code, version, areas, items, elements, years, _svc=None):
    return (_svc or FAOSTATService()).query(code, areas, items, elements, years)

@st.cache_data(ttl=86400, max_entries=64, show_spinner=False)
def geography(version, _svc):
    from utils.geography import enrich_geography
    table = enrich_geography(_svc.area_table())
    return table[table.ISO3.notna()].drop_duplicates('Area')

@st.cache_data(ttl=86400, max_entries=128, show_spinner=False)
def items_for(version, areas, _svc):
    return _svc.available_items('QCL', areas)

@st.cache_data(ttl=86400, max_entries=128, show_spinner=False)
def years_for(version, areas, items, _svc):
    return _svc.available_years('QCL', areas, items, ['Production','Area harvested','Yield'])
