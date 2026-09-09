"""Opt-in end-to-end tests against official local FAOSTAT downloads (no mocks)."""
import os
from pathlib import Path
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from services.faostat import FAOSTATService
from utils.geography import enrich_geography
from utils.exports import csv_bytes, excel_bytes
from io import BytesIO

pytestmark = pytest.mark.skipif(os.getenv('AGRODATA_INTEGRATION') != '1', reason='Set AGRODATA_INTEGRATION=1 to test official FAOSTAT data')


def clean(app):
    assert not app.exception, [e.message for e in app.exception]
    assert not app.error, [e.value for e in app.error]
    return app


def switch_tab(app, label):
    app.session_state['active_tab'] = label
    return clean(app.run())


def assert_rows(app, countries, crops, years):
    previous = app.session_state['active_tab']
    switch_tab(app, '🌍 Comercio y precios')
    frames = [x.value for x in app.dataframe if {'Area','Item','Element','Year','Value'}.issubset(x.value.columns)]
    assert frames
    for frame in frames:
        assert set(frame.Area) <= set(countries)
        assert set(frame.Item) <= set(crops)
        assert frame.Year.between(*years).all()
    switch_tab(app, previous)


def test_official_downloads_queries_geography_exports():
    service = FAOSTATService()
    geo = enrich_geography(service.area_table())
    countries = geo[geo.ISO3.notna()]
    assert not countries.ISO3.duplicated().any()
    assert 'China' not in countries.Area.tolist()
    assert countries.loc[countries.Area.eq('China, Taiwan Province of'),'ISO3'].iloc[0] == 'TWN'
    assert 'Southern Africa' not in countries.Area.tolist()
    assert 'Cereals, primary' not in service.available_items('QCL',['Ecuador'])
    for code, elements in [('QCL',['Production','Area harvested','Yield']),('PP',['Producer Price (USD/tonne)']),('TCL',['Export quantity','Import quantity','Export value','Import value'])]:
        frame = service.query(code,['Ecuador','Colombia'],['Cocoa beans','Bananas'],elements,(2023,2024))
        assert not frame.empty
        assert set(frame.Area) == {'Ecuador','Colombia'}
        assert set(frame.Item) == {'Cocoa beans','Bananas'}
        assert frame.Year.between(2023,2024).all()
        assert service.query(code,['Ecuador'],[],elements,(2023,2024)).empty
        assert service.query(code,[],['Cocoa beans'],elements,(2023,2024)).empty
        if code == 'PP':
            assert set(frame.Months) == {'Annual value'}
        csv = pd.read_csv(BytesIO(csv_bytes(frame)), dtype=str)
        excel = pd.read_excel(BytesIO(excel_bytes({code:frame})), dtype=str)
        assert len(csv) == len(excel) == len(frame)
        assert set(csv.Area) == set(excel.Area) == {'Ecuador','Colombia'}
        assert csv.Value.astype(float).sum() == pytest.approx(frame.Value.sum())
        assert excel.Value.astype(float).sum() == pytest.approx(frame.Value.sum())


def test_hierarchy_multiselect_views_and_resets():
    app = clean(AppTest.from_file('app.py',default_timeout=120).run())
    clean(app.selectbox(key='f_continent').select('América').run())
    clean(app.selectbox(key='f_region').select('South America').run())
    assert 'Ecuador' in app.multiselect(key='f_countries').options
    assert 'France' not in app.multiselect(key='f_countries').options
    clean(app.multiselect(key='f_countries').set_value(['Ecuador']).run())
    clean(app.multiselect(key='f_items').set_value(['Cocoa beans']).run())
    clean(app.select_slider(key='f_years').set_value((2023,2024)).run())
    assert_rows(app,['Ecuador'],['Cocoa beans'],(2023,2024))
    assert app.metric[0].value == '403.70 mil t'
    assert app.metric[2].value == '745.40 kg/ha'
    assert app.metric[3].value == '5.60 mil USD/t'
    assert app.metric[5].value != 'N/D'
    clean(app.multiselect(key='f_countries').set_value(['Ecuador','Colombia','Peru']).run())
    clean(app.multiselect(key='f_items').set_value(['Cocoa beans','Bananas']).run())
    clean(app.select_slider(key='f_years').set_value((2023,2024)).run())
    assert_rows(app,['Ecuador','Colombia','Peru'],['Cocoa beans','Bananas'],(2023,2024))
    assert app.metric[3].value == 'N/D'
    assert app.metric[5].value == 'N/D'
    clean(app.selectbox(key='f_indicator').select('Rendimiento').run())
    assert not app.exception
    clean(app.select_slider(key='f_years').set_value((2023,2023)).run())
    assert_rows(app,['Ecuador','Colombia','Peru'],['Cocoa beans','Bananas'],(2023,2023))
    switch_tab(app, '📋 Datos')
    # Literal regex characters must not crash table search.
    clean(app.text_input[0].set_value('[').run())
    clean(app.text_input[0].set_value('').run())
    button = next(b for b in app.button if b.label == 'Preparar descarga Excel')
    clean(button.click().run())
    assert len(app.get('download_button')) == 2
    clean(app.selectbox(key='f_continent').select('Europa').run())
    assert app.selectbox(key='f_region').value == 'Todas las regiones'
    assert app.multiselect(key='f_countries').value == []
    assert not {'Ecuador','Colombia','Peru'} & set(app.multiselect(key='f_countries').options)
    clean(app.multiselect(key='f_items').set_value([]).run())
    assert not app.metric and not app.get('plotly_chart')
    clean(next(b for b in app.button if b.label == '↺ Restablecer filtros').click().run())
    assert app.selectbox(key='f_continent').value == 'Todo el mundo'
    assert len(app.metric) == 6


def test_secondary_domain_failure_keeps_production_available(monkeypatch):
    original = FAOSTATService.cached_metadata
    def fail_secondary(self, code):
        if code != 'QCL':
            raise RuntimeError('Fallo de red de prueba')
        return original(self, code)
    monkeypatch.setattr(FAOSTATService, 'cached_metadata', fail_secondary)
    app = clean(AppTest.from_file('app.py', default_timeout=120).run())
    assert len(app.metric) == 6
    assert not app.warning
    switch_tab(app, '🌍 Comercio y precios')
    assert any('falló' in message.value for message in app.info)
    assert app.metric[3].value == 'N/D'
