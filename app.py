from __future__ import annotations
import pandas as pd
import plotly.express as px
import streamlit as st
from services.faostat import FAOSTATService, FAOSTATError, SOURCE_URL
from services.cached import query, geography, items_for, years_for
from utils.analytics import normalize_yields, aggregate, total, shares_and_ranks
from utils.metrics import annual_change, safe_div
from components.ui import inject_css, metric_card
from components.views import overview, comparisons, commerce, downloads, assistant

st.set_page_config(page_title='AgroData AI', page_icon='🌾', layout='wide')
inject_css()
px.defaults.template = 'plotly_white'
px.defaults.color_discrete_sequence = ['#1f8a62','#2f6fed','#e6a735','#805ad5','#e45756','#37a6a6']
st.markdown('''<div class="hero"><div class="brand-lockup"><div class="brand-mark">🌾</div><div><h1>AgroData AI</h1><p>Inteligencia agrícola mundial · FAOSTAT</p></div></div><div class="hero-status">Datos oficiales · sin imputación local</div></div>''', unsafe_allow_html=True)
svc = FAOSTATService()


def fatal(message):
    st.error(message)
    st.info('Se conserva la última descarga completa. Comprueba la conexión y reintenta.')
    if st.button('Reintentar', key='retry_start'):
        st.cache_data.clear()
        st.rerun()
    st.stop()


try:
    with st.spinner('Preparando producción oficial; la primera descarga puede tardar unos minutos…'):
        qmeta = svc.cached_metadata('QCL')
        version = qmeta['file']
        geo = geography(version, svc)
except Exception as exc:
    fatal(f'No fue posible iniciar FAOSTAT: {exc}')


def reset_below(level):
    keys = {
        'continent':['f_region','f_countries','f_items','f_years'],
        'region':['f_countries','f_items','f_years'],
        'country':['f_items','f_years'],
        'item':['f_years'],
    }
    for key in keys[level]:
        st.session_state.pop(key, None)


with st.sidebar:
    st.header('🔎 Filtros')
    if st.button('↺ Restablecer filtros', width='stretch'):
        for key in list(st.session_state):
            if key.startswith('f_'):
                del st.session_state[key]
        st.rerun()
    if st.button('Actualizar fuente y caché', width='stretch'):
        try:
            svc.catalog(refresh=True)
            st.cache_data.clear()
            st.rerun()
        except FAOSTATError as exc:
            st.error(str(exc))
    continent = st.selectbox('🌎 Continente', ['Todo el mundo'] + sorted(geo.Continent.unique()), key='f_continent', on_change=reset_below, args=('continent',))
    g1 = geo if continent == 'Todo el mundo' else geo[geo.Continent.eq(continent)]
    region = st.selectbox('📍 Región', ['Todas las regiones'] + sorted(g1.Region.unique()), key='f_region', on_change=reset_below, args=('region',))
    g2 = g1 if region == 'Todas las regiones' else g1[g1.Region.eq(region)]
    countries = st.multiselect('🏳️ País(es)', sorted(g2.Area), key='f_countries', placeholder='Todos en el ámbito', on_change=reset_below, args=('country',))
    scope = tuple(sorted(countries or g2.Area.tolist()))
    try:
        options = items_for(version, scope, svc)
    except Exception as exc:
        fatal(f'No fue posible cargar los cultivos: {exc}')
    if not options:
        st.info('No hay cultivos con área cosechada registrada en este ámbito.')
        st.stop()
    default_item = 'Cocoa beans' if 'Cocoa beans' in options else options[0]
    items = tuple(st.multiselect('🌱 Cultivo(s)', options, default=[default_item], key='f_items', on_change=reset_below, args=('item',)))
    if not items:
        st.info('Selecciona al menos un cultivo para consultar datos.')
        st.stop()
    try:
        years = years_for(version, scope, items, svc)
    except Exception as exc:
        fatal(f'No fue posible cargar los años: {exc}')
    if not years:
        st.info('No hay años disponibles para esta selección.')
        st.stop()
    if len(years) == 1:
        yr = (years[0], years[0])
        st.caption(f'📅 Único año disponible: {years[0]}')
    else:
        yr = st.select_slider('📅 Año / periodo', options=years, value=(next((y for y in years if y >= 2000), years[0]), years[-1]), key='f_years')
    aliases = {'Producción':'Production', 'Área cosechada':'Area harvested', 'Rendimiento':'Yield'}
    indicator_es = st.selectbox('📊 Indicador', list(aliases), key='f_indicator')
    indicator = aliases[indicator_es]
    topn = st.selectbox('🏆 Top del ranking', [5,10,20], index=1, key='f_top')
    st.caption('Países vacíos = todo el ámbito. Cultivos y años dependen de los filtros anteriores. Los nombres de productos y regiones conservan la nomenclatura de la fuente.')

try:
    with st.spinner('Consultando la selección…'):
        base = query('QCL', version, scope, items, ('Production','Area harvested','Yield'), yr, svc)
except Exception as exc:
    fatal(f'Error al consultar producción: {exc}')

# The selected end year is explicit; never silently substitute an older year.
latest = int(yr[1])
data = normalize_yields(base)
selected = data[data.Element.eq(indicator)]
if selected.Value.notna().sum() == 0:
    st.warning('No hay observaciones de este indicador en el periodo. Los valores faltantes permanecen N/D.')

frames, metadata, domain_errors = {'QCL':base}, {'QCL':qmeta}, {}
for code, elements in [('PP', ('Producer Price (USD/tonne)',)), ('TCL', ('Import quantity','Export quantity','Import value','Export value'))]:
    try:
        with st.spinner(f'Preparando {code}: descarga oficial inicial y consultas posteriores en caché…'):
            meta = svc.cached_metadata(code)
            frames[code] = query(code, meta['file'], scope, items, elements, yr, svc)
            metadata[code] = meta
    except Exception as exc:
        frames[code] = pd.DataFrame(columns=base.columns)
        domain_errors[code] = str(exc)

world, world_production, reference_error = pd.DataFrame(), None, None
try:
    worldwide = query('QCL', version, tuple(geo.Area), items, ('Production','Area harvested','Yield'), (latest,latest), svc)
    world = aggregate(worldwide, indicator, ['Area','Year']).dropna(subset=['Value'])
    unit = 'kg/ha' if indicator == 'Yield' else ('ha' if indicator == 'Area harvested' else 't')
    world = shares_and_ranks(world[world.Unit.eq(unit)])
    official_world = query('QCL', version, ('World',), items, ('Production',), (latest,latest), svc)
    world_production = total(official_world, 'Production', latest, 't')
except Exception as exc:
    reference_error = str(exc)

prod = total(base, 'Production', latest, 't')
area_value = total(base, 'Area harvested', latest, 'ha')
yields = aggregate(base, 'Yield', ['Year'])
def yearly_yield(year):
    rows = yields[yields.Year.eq(year)].Value
    return None if rows.empty or pd.isna(rows.iloc[0]) else float(rows.iloc[0])
yield_value = yearly_yield(latest)
share = safe_div(prod, world_production)
share = None if share is None else share * 100
rank = None
if len(countries) == 1 and not world.empty:
    hit = world[world.Area.eq(countries[0])]
    rank = None if hit.empty else int(hit.Ranking.iloc[0])
price_rows = frames['PP']
price_rows = price_rows[price_rows.Year.eq(latest)].dropna(subset=['Value'])
price = float(price_rows.Value.iloc[0]) if len(scope) == 1 and len(items) == 1 and len(price_rows) == 1 else None

st.caption(f"QCL · versión {qmeta['updated'][:10]} · periodo {yr[0]}–{yr[1]} · año de KPIs y ranking: {latest} · {len(scope)} países/territorios · {len(items)} cultivos")
for columns, values in [(st.columns(3), [('🌾 Producción',prod,'t',annual_change(prod,total(base,'Production',latest-1,'t'))),('🌱 Área cosechada',area_value,'ha',annual_change(area_value,total(base,'Area harvested',latest-1,'ha'))),('📈 Rendimiento',yield_value,'kg/ha',annual_change(yield_value,yearly_yield(latest-1)))]), (st.columns(3), [('💰 Precio productor',price,'USD/t',None),('🌎 Participación producción mundial',share,'%',None),('🏆 Ranking mundial · '+indicator_es,rank,'º',None)])]:
    for column, valueset in zip(columns, values):
        with column:
            metric_card(*valueset)
st.caption('Rendimiento: valor oficial por observación; agregado ponderado por área cosechada solo con cobertura completa. Precio KPI: un país y un cultivo; las demás selecciones se muestran por separado. Ranking KPI: un país. Las variaciones requieren el año anterior dentro del periodo seleccionado.')
missing = [item for item in items if base[base.Item.eq(item) & base.Year.eq(latest)].Value.notna().sum() == 0]
if missing:
    st.warning('Sin datos QCL para el año final: ' + ', '.join(missing))
for code, message in domain_errors.items():
    st.warning(f'{code} no disponible: {message}')
if reference_error:
    st.warning('Referencia mundial no disponible: ' + reference_error)
for message in dict.fromkeys(svc.warnings):
    st.warning(message)

tabs = st.tabs(['📊 Panorama','⚖️ Comparadores','🌍 Comercio y precios','📋 Datos','🤖 AgroData AI'])
with tabs[0]:
    overview(base, geo, indicator, indicator_es, latest, topn, world, scope, world_production)
with tabs[1]:
    comparisons(base, indicator, indicator_es, latest)
with tabs[2]:
    commerce(frames['TCL'], frames['PP'], latest, items, domain_errors)
with tabs[3]:
    downloads(frames, metadata, yr, scope, items)
with tabs[4]:
    assistant(base, indicator, indicator_es, latest)
st.markdown(f'Fuente: [FAOSTAT / FAO]({SOURCE_URL}). Las descargas conservan códigos, unidades, banderas y notas originales. N/D no equivale a cero.')
