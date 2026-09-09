# Optimización para Streamlit Community Cloud

Se modificó internamente la carga de datos. No se cambiaron estilos, colores, distribución, nombres, filtros, KPIs ni funciones de gráficas. Las pestañas existentes cargan su contenido al abrirse, sin nuevos botones o navegación.

## Causa encontrada

Antes, `cached_metadata()` llamaba a `ensure()`: el inicio podía descargar y convertir QCL, PP y TCL (más de 22 millones de filas entre los tres dominios). El conversor permitía hasta 1 GB de memoria de trabajo, además de pandas, Streamlit y gráficos. También se ejecutaban todas las pestañas ocultas y se retenían hasta 128 consultas.

Esto es compatible con una caída por recursos y un health check reiniciado, pero no se tuvo acceso a los registros de la instancia Cloud para certificar el motivo exacto de su cierre.

## Solución interna

- Preparación masiva separada en un comando de mantenimiento local, nunca importado ni ejecutado por el dashboard.
- 463 particiones oficiales por cultivo y un índice comprimido de 156.819 bytes. El paquete preparado ocupa unos 40 MB en disco y no se carga entero en RAM.
- Consultas por país/ámbito, cultivo, elementos y periodo; lectura de las particiones elegidas y filtrado dentro de Parquet. Las dimensiones en cascada se resuelven con el índice pequeño.
- Sin llamadas de red en el arranque normal, incluso sin caché de Streamlit o caché de descargas.
- Carga de precios y comercio al necesitarse. El KPI de precio hace solamente su consulta mínima de un país, un cultivo y un año. La tabla consulta su dominio; Excel obtiene los tres dominios bajo demanda.
- Caché limitada por versión y selección, con exclusión de selecciones grandes; DuckDB con un hilo, 96 MB de trabajo y concurrencia acotada. Textos compactos mediante Arrow.
- Excel escribe filas progresivamente en lugar de mantener un objeto por celda en memoria.
- Streamlit 1.55.0 para soporte nativo de ejecución diferida de las mismas pestañas. Documentación: https://docs.streamlit.io/1.55.0/develop/api-reference/layout/st.tabs

## Datos y actualizaciones

Se conservan los datos FAOSTAT ya verificados: QCL versión 2025-12-31, PP 2026-01-09 y TCL 2026-07-24. No se añadieron fuentes de cifras ni observaciones ficticias. El índice registra procedencia, fechas, columnas y hashes de cada partición.

El botón de actualización existente consulta el catálogo pequeño y limpia la caché de consultas. Cuando FAOSTAT publica una versión posterior, la preparación de esa nueva versión se hace **fuera de Cloud**, con `python tools/prepare_data.py`, y se vuelve a desplegar `data/prepared`. Esta separación evita reintroducir la descarga masiva que provocaba el riesgo de caída.

## Validación

Las pruebas cubren arranque sin red, ausencia de descarga masiva, carga diferida, filtros en cascada, continente, región, Ecuador/cacao, selección múltiple, año único, indicadores, errores, CSV y Excel. Se comparan también filas de las particiones con los archivos oficiales originales disponibles localmente.

El contrato visual verifica los hashes de estilos, tema, configuración y analítica; verifica las funciones de panorama, comparadores y comercio mediante su estructura Python. Se comprobaron las mismas pestañas en navegador y las series de precios y comercio al abrirlas.

Medición local con Python 3.12 y caché de consultas vacía: los resultados exactos de la última ejecución se guardan en `cloud-validation.json`. Es una medición en Windows local, no una garantía de tiempos ni memoria en la VM de Community Cloud.

El despliegue real en la cuenta del usuario todavía debe verificarse. El ZIP incluye los archivos necesarios; **no omitir `data/prepared`**, ni sustituirla por la antigua carpeta `data/cache`.
