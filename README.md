# AgroData AI

Dashboard agrícola con datos oficiales de FAOSTAT. Esta revisión modifica los archivos del proyecto original; no incorpora datos de demostración al dashboard.

## Ejecutar

Se probó con Python 3.12. Abre PowerShell en esta carpeta:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Abre http://localhost:8501. No necesitas activar PowerShell ni cambiar su política de ejecución. En macOS/Linux usa `python3 -m venv .venv` y `.venv/bin/python`.

En el equipo donde se realizó esta revisión ya existe un entorno preparado fuera del proyecto, en `../../../work/.venv`. Desde esta carpeta puede iniciarse con:

También puedes abrir `Iniciar_AgroData.cmd`, que detecta el entorno local del proyecto o el entorno preparado durante la revisión.

```powershell
..\..\..\work\.venv\Scripts\python.exe -m streamlit run app.py
```

Esta versión está preparada para Streamlit Community Cloud. **El arranque no descarga ni procesa las bases completas de FAOSTAT.** Incluye `data/prepared`: un índice comprimido de unos 157 KB y particiones por cultivo (unos 40 MB en disco en total). Solo se leen las particiones y filas que corresponden a la selección. No necesita `data/cache` en Cloud.

Para desplegar, sube el contenido del ZIP `AgroData-AI-cloud.zip` al repositorio **incluyendo `data/prepared`**, elige `app.py` como archivo principal y Python 3.12 en Community Cloud. Las dependencias están en `requirements.txt`. No ejecutes `tools/prepare_data.py` como parte del inicio o instalación de la app.

Se conservan diseño, colores, filtros, nombres, navegación, KPIs y funciones que construyen las gráficas. Streamlit 1.55 permite cargar las mismas pestañas al abrirlas. Las series de PP y TCL se leen al abrir Comercio y precios; el KPI de precio consulta únicamente el año final cuando hay un país y un cultivo. La tabla lee su dominio seleccionado y Excel obtiene todos los dominios al pulsar el botón existente.

## Filtros

Continente → Región → País(es) → Cultivo(s) → Año/periodo. Cambiar un nivel restablece los dependientes. Países vacíos significa todos los países del ámbito; cultivos vacíos detiene las consultas. El periodo se obtiene de las observaciones de los cultivos seleccionados en QCL. Puede seleccionarse un único año colocando ambos extremos en él.

Panorama, mapa, comparadores, comercio, precios, tablas y descargas usan la misma selección. El ranking mundial mantiene todos los países como referencia, con los mismos cultivos, indicador y año, y señala las posiciones de los países seleccionados. Los nombres oficiales en inglés se conservan para no introducir correspondencias de productos ambiguas.

## Metodología y límites

- Producción en toneladas y área cosechada en hectáreas. Se excluyen productos agregados y productos sin área cosechada, manteniendo el foco en cultivos primarios y evitando doble conteo.
- Geografía por códigos M49, con correspondencia ISO numérica para territorios cuando es necesaria. `country-converter` aporta la clasificación geográfica, no cifras agrícolas. Se excluyen agregados regionales e históricos sin código vigente. No se confunden China y sus componentes, ni regiones como Southern Africa con países.
- Rendimiento individual: elemento oficial Yield, normalizado a kg/ha. Para varias observaciones se ponderan los rendimientos oficiales por área cosechada. Sin rendimientos y áreas completos no se presenta un agregado. No se reconstruyen rendimientos faltantes con producción/área.
- Participación: producción seleccionada / total oficial World de los mismos cultivos y año. El porcentaje puede ser inferior al 100% aun seleccionando todos los países representables en el mapa. El top no altera el denominador.
- Ranking: países/territorios representables, indicador elegido y último año **seleccionado**. Empates comparten posición. El KPI de posición requiere un país; con varios países, las posiciones individuales están en la tabla mundial.
- Precios: solo Producer Price (USD/tonne), registros Annual value. No se mezclan monedas, índices o meses. El KPI de precio requiere un país y un cultivo; otras selecciones se comparan por separado. Precio no equivale a costo de producción.
- Comercio: importaciones/exportaciones en cantidad y valor, con escalas separadas. El balance requiere ambos flujos; un faltante no se convierte a cero.
- El último año de QCL restringe el periodo común del dashboard, aunque PP tenga observaciones más recientes. No se sustituyen productos con nombres diferentes entre dominios. Las ausencias se muestran explícitamente.
- Las sumas usan únicamente observaciones disponibles: no implican cobertura completa de todos los países/cultivos. Las tasas entre años pueden reflejar cambios de cobertura. El año final no se reemplaza silenciosamente por un año anterior.
- El asistente utiliza reglas locales para preguntas frecuentes; no es un modelo generativo.

## Fuentes y caché

Catálogo: https://bulks-faostat.fao.org/production/datasets_E.json

FAOSTAT: https://www.fao.org/faostat/en/#data

Los datos preparados están en `data/prepared`, relativos al proyecto. Opcionalmente `AGRODATA_PREPARED` puede indicar otra carpeta con un índice y su correspondiente release. Las variables `AGRODATA_CACHE` y `AGRODATA_TIMEOUT` se aplican solamente al preparador local, no al runtime Cloud. `.env.example` es documentación y no se carga automáticamente.

El botón existente **Actualizar fuente y caché** limpia las consultas en memoria y comprueba el catálogo oficial pequeño. Si hay una versión posterior, informa de ella; no lanza descargas masivas en Cloud. Para incorporar nuevas publicaciones se ejecuta fuera del servidor:

```powershell
python tools/prepare_data.py
```

Después se vuelve a desplegar `data/prepared`, con el nuevo índice y su carpeta `release-*`. El script reutiliza descargas oficiales locales válidas, valida datos y publica el índice de forma atómica al terminar. Conserva versiones anteriores; el empaquetador incluye solo la versión apuntada por el índice. Para preparar desde cero reserva espacio y RAM en el equipo de mantenimiento; no ejecutes esta tarea en la VM de la aplicación.

No son datos ficticios: cada partición contiene las observaciones originales y conserva todas sus columnas, códigos, unidades, banderas y notas. La procedencia y fechas originales quedan en el índice, y cada archivo tiene SHA-256. No se infieren ni rellenan ausencias.

Las claves de caché de consultas incluyen versión, dominio y todos los filtros. Se retienen como máximo 12 consultas; selecciones grandes no se guardan en esa caché compartida. DuckDB usa un hilo, 96 MB de memoria de trabajo y un límite de una consulta concurrente. Los textos de los resultados utilizan buffers Arrow para reducir objetos Python. El límite de DuckDB no equivale al consumo total del proceso.

## CSV y Excel

CSV descarga el dominio y búsqueda visibles. La búsqueda es texto literal. **Preparar descarga Excel** genera un libro con QCL, PP, TCL y procedencia usando todos los filtros principales; la búsqueda textual no restringe el Excel. Las tablas que exceden el límite de filas de Excel se dividen en hojas. El archivo se prepara bajo demanda para evitar trabajo en cada cambio de filtro. Textos que Excel interpretaría como fórmulas se escapan.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
# Pruebas de integración: verifican las particiones oficiales incluidas y recorren la interfaz
$env:AGRODATA_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas unitarias tienen ejemplos sintéticos aislados en directorios temporales; nunca se cargan en el dashboard. Las pruebas de integración utilizan exclusivamente observaciones oficiales. Las pruebas Cloud comprueban arranque sin red y carga diferida; la comparación adicional con los archivos originales se omite si no existe la caché de mantenimiento. Consulta `CLOUD.md` para los resultados de esta optimización. `REVISION.md` documenta la revisión anterior.

## Organización

- `app.py`: filtros y coordinación de datos.
- `services/faostat.py`: runtime ligero, índice y consultas a particiones oficiales.
- `services/bulk.py` y `tools/prepare_data.py`: preparación externa al servidor.
- `services/lazy.py`: carga diferida de los dominios utilizados por cada pestaña.
- `services/cached.py`: caché de consultas y dimensiones de Streamlit.
- `utils/analytics.py`: agregaciones, rendimiento y ranking.
- `utils/geography.py`: correspondencia geográfica por códigos.
- `utils/exports.py`: CSV/Excel.
- `components/`: vistas, gráficos y estilos responsive.
- `tests/`: regresiones, errores de fuente e integración oficial.

Se fijaron versiones de dependencias probadas y se retiró Kaleido, que no se utilizaba. `requirements-lock.txt` registra el entorno completo de validación, incluidas las herramientas de prueba.
