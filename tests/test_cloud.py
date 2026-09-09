"""Cloud regression checks use the included official partitions, never fake data."""
import ast
import hashlib
import json
from pathlib import Path
import pandas as pd
import requests
import streamlit as st
from streamlit.testing.v1 import AppTest
from services.faostat import FAOSTATService
from services.lazy import LazyFrames

ROOT = Path(__file__).resolve().parents[1]

def run(app):
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    assert not app.error, [e.value for e in app.error]
    return app

def tab(app, name):
    app.session_state['active_tab'] = name
    return run(app)

def test_startup_offline_and_load_on_demand(monkeypatch):
    st.cache_data.clear()
    queries = []
    original = FAOSTATService.query
    def record(self, code='QCL', areas=None, items=None, elements=None, years=None):
        queries.append((code,areas,items,years))
        return original(self,code,areas,items,elements,years)
    def no_network(*a, **k):
        raise AssertionError('Network/bulk download forbidden during Cloud startup')
    monkeypatch.setattr(FAOSTATService,'query',record)
    monkeypatch.setattr(requests.sessions.Session,'request',no_network)
    from services.bulk import FAOSTATService as BulkService
    monkeypatch.setattr(BulkService,'ensure',no_network)
    app = run(AppTest.from_file(str(ROOT/'app.py'),default_timeout=30))
    assert queries and {q[0] for q in queries} == {'QCL'}
    assert len(app.get('plotly_chart')) == 4
    assert len(app.metric) == 6
    assert not app.text_input and not app.text_area
    assert all(set(q[2]) == {'Cocoa beans'} for q in queries)
    queries.clear()
    app.multiselect(key='f_countries').set_value(['Ecuador'])
    run(app)
    prices = [q for q in queries if q[0] == 'PP']
    assert prices and all(q[3] == (2024,2024) for q in prices)
    assert not any(q[0] == 'TCL' for q in queries)
    assert app.metric[3].value == '5.60 mil USD/t'
    queries.clear()
    tab(app,'🌍 Comercio y precios')
    assert {'PP','TCL'} <= {q[0] for q in queries}
    assert len(app.get('plotly_chart')) == 5
    frames = [x.value for x in app.dataframe if 'Element' in x.value]
    assert frames and all(set(f.Area) == {'Ecuador'} for f in frames)
    queries.clear()
    tab(app,'📋 Datos')
    assert not queries  # The selected QCL table was already queried.
    app.text_input(key='data_search').set_value('Cocoa')
    run(app)
    tab(app,'📊 Panorama')
    tab(app,'📋 Datos')
    assert app.text_input(key='data_search').value == 'Cocoa'

def test_lazy_mapping_and_excel_loads_all_selected_domains():
    service = FAOSTATService()
    base = service.query('QCL',['Ecuador'],['Cocoa beans'],['Production'],(2024,2024))
    frames = LazyFrames(base,service,('Ecuador',),('Cocoa beans',),(2024,2024),{}, {})
    assert list(frames) == ['QCL','PP','TCL']
    assert list(frames.loaded) == ['QCL']
    assert not frames['PP'].empty
    assert set(frames.loaded) == {'QCL','PP'}
    assert all(not frame.empty for _,frame in frames.items())
    assert set(frames.loaded) == {'QCL','PP','TCL'}

def test_visual_contract_unchanged():
    contract = json.loads((ROOT/'tests/visual_contract.json').read_text())
    for filename,digest in contract['files'].items():
        assert hashlib.sha256((ROOT/filename).read_bytes()).hexdigest() == digest
    tree = ast.parse((ROOT/'components/views.py').read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in contract['views']:
            assert hashlib.sha256(ast.dump(node).encode()).hexdigest() == contract['views'][node.name]

def test_partitions_have_no_missing_files_and_small_index():
    service = FAOSTATService()
    assert (service.root/'index.json.gz').stat().st_size < 1_000_000
    for domain in service.index['domains'].values():
        for item,entry in domain['files'].items():
            path = service.root/entry['path']
            assert path.is_file(), item
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']


def test_partition_rows_match_original_official_downloads():
    import pytest
    import duckdb
    from utils.geography import enrich_geography
    cache = ROOT/'data/cache'
    if not (cache/'QCL.json').exists():
        pytest.skip('Optional comparison with original bulk files used for preparation')
    service = FAOSTATService()
    geo = enrich_geography(service.area_table())
    south_america = geo[geo.Region.eq('South America')].Area.tolist()
    africa = geo[geo.Continent.eq('África')].Area.tolist()
    for code, areas, crops, elements in [
        ('QCL',south_america,['Cocoa beans','Bananas'],['Production','Area harvested','Yield']),
        ('QCL',africa,['Cocoa beans','Rice'],['Production','Area harvested','Yield']),
        ('PP',['Ecuador','Colombia'],['Cocoa beans','Bananas'],['Producer Price (USD/tonne)']),
        ('TCL',south_america,['Cocoa beans','Bananas'],['Export quantity','Import quantity','Export value','Import value']),
    ]:
        original = json.loads((cache/f'{code}.json').read_text())
        with duckdb.connect(config={'threads':1,'memory_limit':'96MB'}) as con:
            con.read_parquet(str(cache/original['file'])).create_view('fao')
            where,params = service.filters(areas,crops,elements,(2000,2024))
            if code == 'PP':
                where += " AND Months='Annual value'"
            expected = con.execute(f'SELECT * FROM fao{where} ORDER BY Area,Item,Element,Year',params).df()
        actual = service.query(code,areas,crops,elements,(2000,2024))
        # Arrow uses <NA>; the original object columns use None. Both are missing.
        comparable = actual.astype(object).where(actual.notna(),None)
        pd.testing.assert_frame_equal(comparable,expected,check_dtype=False)
