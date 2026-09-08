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

La primera ejecución descarga QCL (unos 33 MB), PP (11 MB) y TCL (267 MB) desde el catálogo oficial. La extracción necesita espacio temporal adicional; reserva 4 GB libres. Las siguientes ejecuciones consultan archivos Parquet locales. El ZIP de entrega contiene código y pruebas; los datos oficiales se descargan automáticamente. La carpeta de trabajo revisada conserva la caché real ya descargada.

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

La caché está en `data/cache`, relativa al proyecto, salvo que se defina la variable de entorno `AGRODATA_CACHE`. El ejemplo `.env.example` es documentación: no se carga automáticamente. `AGRODATA_TIMEOUT` controla la espera de lectura de la descarga.

El catálogo se actualiza cada 24 horas; **Actualizar fuente y caché** fuerza su revisión. Cada versión se valida y convierte antes de actualizar el manifiesto. Una descarga fallida no reemplaza una válida. Si se utiliza una versión anterior, se muestra su fecha real y una advertencia. Las versiones anteriores se conservan en disco; con la aplicación cerrada se puede eliminar `data/cache` si se desea descargar todo nuevamente.

Las claves de caché de consultas incluyen versión, dominio y todos los filtros. Se conservan todas las columnas originales, códigos, unidades, banderas y notas.

## CSV y Excel

CSV descarga el dominio y búsqueda visibles. La búsqueda es texto literal. **Preparar descarga Excel** genera un libro con QCL, PP, TCL y procedencia usando todos los filtros principales; la búsqueda textual no restringe el Excel. Las tablas que exceden el límite de filas de Excel se dividen en hojas. El archivo se prepara bajo demanda para evitar trabajo en cada cambio de filtro. Textos que Excel interpretaría como fórmulas se escapan.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
# Pruebas de integración: descargan/verifican datos oficiales y recorren la interfaz
$env:AGRODATA_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas unitarias tienen ejemplos sintéticos aislados en directorios temporales; nunca se cargan en el dashboard. Las pruebas de integración utilizan exclusivamente descargas oficiales. Consulta `REVISION.md` para el alcance y los resultados de esta revisión.

## Organización

- `app.py`: filtros y coordinación de datos.
- `services/faostat.py`: descargas, validación, caché persistente y SQL parametrizado.
- `services/cached.py`: caché de consultas y dimensiones de Streamlit.
- `utils/analytics.py`: agregaciones, rendimiento y ranking.
- `utils/geography.py`: correspondencia geográfica por códigos.
- `utils/exports.py`: CSV/Excel.
- `components/`: vistas, gráficos y estilos responsive.
- `tests/`: regresiones, errores de fuente e integración oficial.

Se fijaron versiones de dependencias probadas y se retiró Kaleido, que no se utilizaba. `requirements-lock.txt` registra el entorno completo de validación, incluidas las herramientas de prueba.
