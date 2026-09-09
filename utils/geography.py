"""Geography uses exact official M49 codes, never fuzzy aggregate names."""
from functools import lru_cache
import country_converter as coco
import pandas as pd

CONTINENT_ES = {"Africa":"África", "America":"América", "Asia":"Asia", "Europe":"Europa", "Oceania":"Oceanía"}

@lru_cache(maxsize=1)
def geography_lookup():
    table = coco.CountryConverter().data[['UNcode','ISOnumeric','ISO3','continent','UNregion']].copy()
    # FAOSTAT retains some territory codes absent from the current UN list.
    # ISO numeric provides an exact-code match, including 158 -> TWN.
    table['UNcode'] = table.UNcode.fillna(table.ISOnumeric)
    table = table.drop(columns='ISOnumeric')
    table = table.rename(columns={'UNcode':'M49','continent':'Continent','UNregion':'Region'})
    table['Continent'] = table.Continent.replace(CONTINENT_ES)
    return table.dropna(subset=['M49']).drop_duplicates('M49')


def enrich_geography(frame):
    result = frame.drop(columns=['ISO3','Continent','Region','M49'], errors='ignore').copy()
    if 'Area Code (M49)' not in result:
        result['ISO3'] = None
        result['Continent'] = 'Sin clasificar'
        result['Region'] = 'Sin clasificar'
        return result
    result['M49'] = pd.to_numeric(result['Area Code (M49)'].astype(str).str.lstrip("'"), errors='coerce')
    result = result.merge(geography_lookup(), on='M49', how='left', validate='many_to_one')
    result[['Continent','Region']] = result[['Continent','Region']].fillna('Sin clasificar')
    return result
