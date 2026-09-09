"""Cloud runtime: read only prepared, official FAOSTAT crop partitions.

No bulk downloader, CSV parser, extraction or Parquet conversion is reachable
from this module. tools/prepare_data.py performs that maintenance off-server.
"""
from __future__ import annotations
from functools import lru_cache
import gzip
import json
import os
from pathlib import Path
import threading
import duckdb
import pandas as pd
import pyarrow as pa

CATALOG_URL = 'https://bulks-faostat.fao.org/production/datasets_E.json'
SOURCE_URL = 'https://www.fao.org/faostat/en/#data'
DOMAINS = {'QCL':'Producción','PP':'Precios al productor','TCL':'Comercio'}
# Limit simultaneous DuckDB working sets across sessions on a small Cloud VM.
QUERY_LOCK = threading.BoundedSemaphore(1)

class FAOSTATError(RuntimeError):
    pass

@lru_cache(maxsize=2)
def _read_index(path, modified, size):
    with gzip.open(path,'rt',encoding='utf-8') as source:
        index = json.load(source)
    if index.get('schema') != 1:
        raise FAOSTATError('Versión de índice FAOSTAT no compatible')
    return index

class FAOSTATService:
    def __init__(self, prepared_dir=None):
        self.root = Path(prepared_dir or os.getenv('AGRODATA_PREPARED', str(Path(__file__).resolve().parents[1]/'data/prepared')))
        self.warnings = []

    @property
    def index(self):
        path = self.root/'index.json.gz'
        if not path.is_file():
            raise FAOSTATError('Faltan los datos oficiales preparados en data/prepared. Incluye esta carpeta al desplegar; no se descargarán bases masivas durante el arranque.')
        stat = path.stat()
        return _read_index(str(path.resolve()),stat.st_mtime_ns,stat.st_size)

    def cached_metadata(self, code):
        if code not in DOMAINS:
            raise FAOSTATError(f'Dominio no admitido: {code}')
        metadata = self.index['domains'][code]['metadata'].copy()
        metadata['source_file'] = metadata['file']
        metadata['file'] = self.index['release']+'/'+code
        return metadata

    metadata = cached_metadata

    def catalog(self, refresh=False):
        if refresh:
            # Explicit refresh checks only the small official catalogue.
            # Never start bulk downloads within a Streamlit request.
            import requests
            try:
                response = requests.get(CATALOG_URL,timeout=(3,5))
                response.raise_for_status()
                rows = response.json()['Datasets']['Dataset']
                for row in rows:
                    code = row.get('DatasetCode')
                    if code in DOMAINS and row.get('DateUpdate') != self.cached_metadata(code)['updated']:
                        self.warnings.append(f"{code}: FAOSTAT tiene una nueva versión. La versión preparada sigue disponible; actualiza data/prepared con tools/prepare_data.py fuera del servidor Cloud.")
                return rows
            except (requests.RequestException, ValueError, KeyError) as exc:
                self.warnings.append(f'No se pudo actualizar el catálogo: {exc}. Se conserva la versión oficial preparada.')
        return [{'DatasetCode':code, 'DatasetName':self.cached_metadata(code)['name'],
                 'DateUpdate':self.cached_metadata(code)['updated'], 'FileLocation':self.cached_metadata(code)['url']} for code in DOMAINS]

    def area_table(self, code='QCL'):
        return pd.DataFrame(self.index['areas'])

    def available_items(self, code='QCL', areas=None):
        if code != 'QCL':
            return sorted(self.index['domains'][code]['files'])
        selected = None if areas is None else set(areas)
        return sorted({item for area,item,years,harvested in self.index['availability']
                       if harvested and (selected is None or area in selected)})

    def available_years(self, code='QCL', areas=None, items=None, elements=None):
        if code != 'QCL':
            return sorted(self.query(code,areas,items,elements).Year.unique().tolist())
        selected_areas = None if areas is None else set(areas)
        selected_items = None if items is None else set(items)
        return sorted({year for area,item,years,harvested in self.index['availability']
                       if (selected_areas is None or area in selected_areas) and (selected_items is None or item in selected_items)
                       for year in years})

    def dimensions(self, code='QCL'):
        years = self.available_years(code)
        return {'areas':self.area_table().Area.tolist(), 'items':self.available_items(code),
                'min_year':min(years), 'max_year':max(years)}

    @staticmethod
    def filters(areas=None, items=None, elements=None, years=None):
        clauses, params = [], []
        for col, values in (('Area',areas),('Item',items),('Element',elements)):
            if values is not None:
                if not len(values):
                    clauses.append('FALSE')
                else:
                    clauses.append(f'"{col}" IN ({",".join("?" for _ in values)})')
                    params.extend(values)
        if years is not None:
            clauses.append('Year BETWEEN ? AND ?')
            params.extend(years)
        return (' WHERE '+' AND '.join(clauses) if clauses else ''), params

    def query(self, code='QCL', areas=None, items=None, elements=None, years=None):
        domain = self.index['domains'][code]
        if any(values is not None and len(values)==0 for values in (areas,items,elements)):
            return pd.DataFrame(columns=domain['columns'])
        choices = domain['files'] if items is None else items
        paths = [str(self.root/domain['files'][item]['path']) for item in choices if item in domain['files']]
        if not paths:
            return pd.DataFrame(columns=domain['columns'])
        if any(not Path(path).is_file() for path in paths):
            raise FAOSTATError(f'Falta una partición oficial {code}; incluye data/prepared completo al desplegar.')
        where, params = self.filters(areas,items,elements,years)
        # One thread and a bounded working set; closed immediately after the query.
        # Predicate pushdown reads only matching row groups in selected crops.
        with QUERY_LOCK, duckdb.connect(config={'threads':1,'memory_limit':'96MB'}) as con:
            con.read_parquet(paths).create_view('fao')
            rows = con.execute(f'SELECT * FROM fao{where} ORDER BY Area,Item,Element,Year',params).fetch_arrow_table()
            # Compact UTF-8 buffers avoid a separate Python string per cell.
            return rows.to_pandas(types_mapper=lambda kind: pd.StringDtype(storage='pyarrow') if pa.types.is_string(kind) else None)
