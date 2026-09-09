"""Report views consume already filtered frames; no independent hidden selections."""
import pandas as pd
import plotly.express as px
import streamlit as st
from components.charts import chart
from utils.analytics import aggregate, normalize_yields, shares_and_ranks
from utils.metrics import annual_change
from utils.exports import csv_bytes, excel_bytes


def overview(base, geo, indicator, label, year, topn, world, scope, world_production):
    data = normalize_yields(base)
    series = data[data.Element.eq(indicator)].copy()
    st.subheader('Evolución histórica por país y cultivo')
    if series.Value.notna().any():
        series['Serie'] = series.Area + ' · ' + series.Item
        if series.Serie.nunique() > 20:
            series = aggregate(base, indicator, ['Item','Year'])
            series['Serie'] = series.Item
            series['Flag'] = 'Agregado local de observaciones oficiales'
            st.caption('Más de 20 series: se muestra el agregado del ámbito por cultivo para mantener legible el gráfico. Los registros individuales siguen en Datos.')
        chart(px.line(series.sort_values('Year'), x='Year', y='Value', color='Serie', markers=True,
                      facet_row='Unit', hover_data=['Item','Unit','Flag'], labels={'Year':'Año','Value':label}), 450)
        yearly = aggregate(base, indicator, ['Year']).dropna(subset=['Value'])
        if yearly.Unit.nunique() == 1 and len(yearly) > 1:
            ordered = yearly.sort_values('Year')
            change = annual_change(ordered.iloc[-1].Value, ordered.iloc[0].Value)
            if change is not None:
                st.info(f'Agregado del ámbito: {change:+.2f}% entre {int(ordered.iloc[0].Year)} y {int(ordered.iloc[-1].Year)}. La cobertura puede variar entre años.')
    else:
        st.info('No hay observaciones para esta serie.')
    latest = aggregate(base[base.Year.eq(year)], indicator, ['Area','Year']).dropna(subset=['Value'])
    st.subheader(f'Ranking del ámbito · {label} · {year}')
    if not latest.empty:
        ranking = shares_and_ranks(latest).head(topn)
        st.dataframe(ranking[['Ranking','Area','Value','Unit']], hide_index=True, width='stretch')
        chart(px.bar(ranking.sort_values('Value'), x='Value', y='Area', orientation='h', labels={'Value':label,'Area':'País'}))
        st.subheader('Mapa del ámbito seleccionado')
        mapped = latest.merge(geo[['Area','ISO3']], on='Area', how='left').dropna(subset=['ISO3'])
        figure = px.choropleth(mapped, locations='ISO3', color='Value', hover_name='Area', hover_data=['Unit'],
                              color_continuous_scale=['#e8f3ef','#52b788','#12664a'], range_color=(0,max(float(mapped.Value.max()),1)) if not mapped.empty else None, labels={'Value':label})
        figure.update_geos(showframe=False, showcoastlines=False, landcolor='#eef1f5')
        chart(figure, 460)
    else:
        st.info('Sin datos para el año final seleccionado; no se sustituye por otro año.')
    st.subheader(f'Ranking mundial · {label} · {year}')
    if not world.empty:
        table = world.copy()
        table['En selección'] = table.Area.isin(scope)
        st.dataframe(table[['Ranking','Area','Value','Unit','En selección']].head(topn), hide_index=True, width='stretch')
        selected_ranks = table[table['En selección']]
        with st.expander('Posiciones mundiales de todos los países seleccionados'):
            st.dataframe(selected_ranks[['Ranking','Area','Value','Unit']], hide_index=True, width='stretch')
        st.caption('Referencia mundial: mismos cultivos, indicador y año; incluye países y territorios con código M49 vigente, sin agregados regionales. Los empates comparten posición.')
    else:
        st.info('No hay referencia mundial disponible para este indicador y año.')
    st.subheader('Participación porcentual de la producción mundial')
    production = aggregate(base[base.Year.eq(year)], 'Production', ['Area'])
    production = production[production.Unit.eq('t')].dropna(subset=['Value'])
    if world_production is not None and world_production > 0 and not production.empty:
        production['Participación (%)'] = production.Value / world_production * 100
        st.dataframe(production.sort_values('Value',ascending=False), hide_index=True, width='stretch')
        chart(px.bar(production.nlargest(topn,'Value').sort_values('Value'), x='Participación (%)', y='Area', orientation='h'))
        st.caption('Denominador: agregado oficial World para todos los cultivos seleccionados. Mostrar solo el top no cambia los porcentajes. La participación se define sobre producción, no sobre rendimiento.')
    else:
        st.info('Participación N/D: falta el total mundial o es cero.')


def comparisons(base, indicator, label, year):
    st.subheader(f'Comparador de países · {year}')
    latest = base[base.Year.eq(year)]
    if latest.Area.nunique() >= 2:
        for element, title in [('Production','Producción'),('Area harvested','Área cosechada'),('Yield','Rendimiento')]:
            data = aggregate(latest, element, ['Area']).dropna(subset=['Value'])
            st.markdown(f'**{title}**')
            if data.empty:
                st.info('Sin datos suficientes.')
            else:
                chart(px.bar(data, x='Area', y='Value', hover_data=['Unit'], facet_row='Unit', labels={'Area':'País','Value':title}), 320)
        st.caption('Cada indicador conserva su escala y unidad. La comparación usa exactamente los países del filtro principal.')
    else:
        st.info('Selecciona dos o más países para comparar.')
    st.subheader(f'Comparador de cultivos · {label}')
    data = normalize_yields(latest)
    data = data[data.Element.eq(indicator)]
    if data.Item.nunique() >= 2:
        chart(px.bar(data, x='Item', y='Value', color='Area', barmode='group', facet_row='Unit', labels={'Item':'Cultivo','Value':label}))
    else:
        st.info('Selecciona dos o más cultivos para comparar.')


def commerce(trade, prices, year, items, errors):
    st.subheader('Exportaciones e importaciones')
    if trade.empty:
        st.info('Sin datos de comercio para la selección.' if 'TCL' not in errors else 'La consulta de comercio falló; reintenta desde la barra lateral.')
    else:
        for element in ['Export quantity','Import quantity','Export value','Import value']:
            data = trade[trade.Element.eq(element)].copy()
            if data.empty:
                continue
            data['Serie'] = data.Area + ' · ' + data.Item
            if data.Serie.nunique() > 20:
                data = data.groupby(['Item','Year','Unit'],as_index=False).Value.sum(min_count=1)
                data['Serie'] = data.Item
                data['Flag'] = 'Agregado local de observaciones oficiales'
                st.caption('Más de 20 series: cantidades y valores agregados por cultivo para el ámbito seleccionado.')
            st.markdown(f'**{element}**')
            chart(px.line(data.sort_values('Year'), x='Year', y='Value', color='Serie', markers=True, facet_row='Unit', hover_data=['Flag','Unit']))
        flows = trade[trade.Element.isin(['Export value','Import value'])]
        balance = flows.pivot_table(index=['Area','Item','Year','Unit'], columns='Element', values='Value', aggfunc=lambda s:s.sum(min_count=1)).reset_index()
        if {'Export value','Import value'}.issubset(balance.columns):
            balance['Balance comercial'] = balance['Export value'] - balance['Import value']
            st.markdown('**Balance comercial por país y cultivo**')
            st.dataframe(balance, hide_index=True, width='stretch')
        st.dataframe(trade, hide_index=True, width='stretch')
    st.subheader('Precios anuales al productor · USD por tonelada')
    if prices.empty:
        st.info('Sin precios oficiales para esta selección.' if 'PP' not in errors else 'La consulta de precios falló; reintenta desde la barra lateral.')
    else:
        data = prices.copy()
        data['Serie'] = data.Area + ' · ' + data.Item
        chart(px.line(data.sort_values('Year'), x='Year', y='Value', color='Serie', markers=True, hover_data=['Flag'], labels={'Value':'USD/t','Year':'Año'}))
        st.dataframe(prices, hide_index=True, width='stretch')
    for code, data in [('TCL',trade),('PP',prices)]:
        missing = [item for item in items if data[data.Item.eq(item)].Value.notna().sum() == 0]
        if missing:
            st.caption(f'{code}: sin datos para ' + ', '.join(missing) + '. Se requiere coincidencia exacta del producto oficial; no se sustituyen productos.')
    st.caption('Los precios no se suman entre países o cultivos. Solo se usan el elemento USD/tonne y registros Annual value. Precio al productor no equivale a costo de producción.')


def downloads(frames, metadata, years, scope, items):
    st.subheader('Datos oficiales filtrados y descargas')
    code = st.selectbox('Dominio de la tabla y CSV', list(frames), format_func=lambda c:{'QCL':'Producción / área / rendimiento','PP':'Precios al productor','TCL':'Comercio'}[c], key='data_domain')
    data = frames[code]
    search = st.text_input('Buscar en la tabla (texto literal)', key='data_search')
    if search and not data.empty:
        mask = pd.Series(False, index=data.index)
        for column in data.columns:
            mask |= data[column].astype(str).str.contains(search, case=False, regex=False, na=False)
        data = data[mask]
    st.dataframe(data, hide_index=True, width='stretch')
    st.caption(f'{len(data):,} filas. CSV: tabla visible. Excel: todos los dominios con los filtros principales, más procedencia; la búsqueda textual solo afecta al CSV.')
    st.download_button('⬇️ Descargar CSV', csv_bytes(data), f'agrodata_{code}.csv', 'text/csv', on_click='ignore', width='stretch')
    if st.button('Preparar descarga Excel', width='stretch'):
        with st.spinner('Preparando Excel…'):
            tables = {}
            for name, frame in frames.items():
                # Excel supports at most 1,048,576 rows including the header.
                for index, offset in enumerate(range(0, max(len(frame),1), 1_048_575)):
                    tables[f'{name}_{index+1}'] = frame.iloc[offset:offset+1_048_575]
            rows = [{**meta,'file':meta['file'],'periodo':f'{years[0]}–{years[1]}','paises':', '.join(scope),'cultivos':', '.join(items)} for meta in metadata.values()]
            tables['Procedencia'] = pd.DataFrame(rows)
            content = excel_bytes(tables)
        st.download_button('⬇️ Descargar Excel', content, 'agrodata.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', on_click='ignore', width='stretch')
    st.dataframe(pd.DataFrame(metadata.values())[['code','name','updated','source','rows']], hide_index=True, width='stretch')


def assistant(base, indicator, label, year):
    st.subheader('Preguntas sobre la selección')
    st.caption('Asistente local con reglas; no es un modelo generativo. Solo calcula con las observaciones filtradas.')
    question = st.text_area('Pregunta sobre los datos cargados', placeholder='¿Cuál fue el mayor productor?', key='ai_question')
    if st.button('Analizar pregunta') and question.strip():
        question = question.lower()
        element = 'Production' if 'productor' in question else ('Yield' if 'rendimiento' in question else indicator)
        data = aggregate(base, element, ['Area','Year']).dropna(subset=['Value'])
        if 'creci' in question or 'aument' in question:
            yearly = aggregate(base, element, ['Year']).dropna(subset=['Value']).sort_values('Year')
            change = None if len(yearly) < 2 else annual_change(yearly.iloc[-1].Value, yearly.iloc[0].Value)
            st.write('No hay datos suficientes.' if change is None else f'Cambio del agregado filtrado: {change:+.2f}% entre {int(yearly.iloc[0].Year)} y {int(yearly.iloc[-1].Year)}. La cobertura puede variar entre años.')
        elif any(word in question for word in ['mayor','ranking','rendimiento']):
            rows = data[data.Year.eq(year)].sort_values('Value', ascending=False)
            st.write('No hay datos suficientes.' if rows.empty else f'Mayor valor de {element} en el ámbito seleccionado: {rows.iloc[0].Area}, {rows.iloc[0].Value:,.2f} {rows.iloc[0].Unit}, año {year}.')
        else:
            st.write(f'La selección contiene {len(base):,} observaciones. Puedes preguntar por mayor productor, ranking, crecimiento o rendimiento.')
