# Revisión de AgroData AI

## Cambios realizados

Se modificaron directamente los archivos extraídos del ZIP original en esta carpeta.

- Filtros jerárquicos con reinicio de dependencias, selección múltiple de países/cultivos y años disponibles por selección.
- Consultas y vistas sincronizadas, incluido comercio y precios, que antes conservaban datos de filtros anteriores.
- Selecciones vacías seguras: nunca amplían una consulta a todos los productos.
- Geografía exacta por códigos; eliminación de doble conteo de agregados y corrección de territorios.
- Rendimientos ponderados sin sumar tasas, unidades separadas y faltantes conservados.
- Ranking con empates; participación sobre el total World oficial, independiente del tamaño del top.
- Precios anuales USD/tonne, sin mezclar monedas, meses e índices. Comercio separado en cantidades y valores; balance solo cuando existen ambos flujos.
- Comparadores sincronizados y gráficos con escalas independientes. Resúmenes calculados sobre el agregado del ámbito, no sobre dos filas arbitrarias.
- CSV/Excel con filtros, metadatos y banderas originales; búsqueda literal y Excel bajo demanda.
- Descargas atómicas, validación estricta, recuperación de caché dañada, actualización por versión del catálogo y respaldo ante errores de conexión.
- Parquet y caché de consultas limitada; separación en servicios, analítica, exportaciones y vistas.
- Diseño móvil, tres tarjetas por fila en escritorio, tema verde y leyendas acotadas. Selecciones históricas con más de 20 series se agregan por cultivo y se informa en pantalla.
- Dependencias directas fijadas; Kaleido eliminado por no utilizarse; herramientas de prueba separadas; archivo completo de versiones.

## Verificación realizada

22 pruebas automáticas pasaron con Python 3.12. Se incluyen:

- Recorrido de Continente → Región → País → Cultivo → Año.
- Ecuador y selección múltiple Ecuador/Colombia/Perú, cacao/banano, periodo y año único.
- Cambio de continente, limpieza de selecciones dependientes, reinicio y cultivos vacíos.
- Datos filtrados de QCL, PP y TCL; rendimiento, participación, ranking y precios.
- Lectura de CSV y Excel generados con observaciones oficiales; valores y filas preservados.
- Búsqueda con caracteres como `[` sin interpretación regular.
- Caché nueva, actualización, archivo inválido, Parquet dañado, catálogo inválido y funcionamiento de producción cuando fallan dominios secundarios.

La interfaz se comprobó en navegador de escritorio y a 390 × 844. Se verificaron mapa, cambio de país y eventos reales de descarga CSV/Excel. El servidor respondió correctamente al control de salud. `pip check` no encontró dependencias incompatibles. Esto verifica compatibilidad; no constituye una auditoría de vulnerabilidades de terceros.

Los archivos oficiales completos descargados contenían:

| Dominio | Filas | Versión del catálogo |
|---|---:|---|
| QCL | 4.209.110 | 2025-12-31 |
| PP | 1.319.563 | 2026-01-09 |
| TCL | 17.143.873 | 2026-07-24 |

Fuente: [catálogo oficial FAOSTAT](https://bulks-faostat.fao.org/production/datasets_E.json). Las fechas son las declaradas por la fuente, no fechas inventadas por el dashboard.

Se comprobó Ecuador / Cocoa beans / 2024 contra las filas descargadas: producción 403.698,83 t, área 541.588 ha, rendimiento oficial 745,4 kg/ha y precio anual 5.601,5 USD/t. El ranking de producción en el conjunto de países/territorios representables es 4.º; la participación sobre World es aproximadamente 7,71%.

Medición local de tres consultas consecutivas para Ecuador, Colombia y Perú; cacao y banano; 2000–2024:

| Dominio | Filas seleccionadas | Tiempo aproximado por consulta Parquet |
|---|---:|---:|
| QCL | 430 | 0,05 s |
| PP | 116 | 0,02 s |
| TCL | 566 | 0,50 s |

Los tiempos dependen del equipo y no incluyen descarga inicial, exportación o renderizado. La caché de Streamlit evita repetir estas consultas para combinaciones ya consultadas.

## Pendientes y límites explícitos

No quedaron fallas reproducibles en los escenarios probados. No se probó exhaustivamente cada combinación de todos los países, cultivos y años.

FAOSTAT tiene ausencias y diferencias de cobertura entre dominios; se muestran como N/D. El periodo común sigue QCL, por lo que años exclusivos de PP no aparecen como periodo del dashboard. Los productos entre dominios requieren coincidencia exacta; no se inventó una tabla de equivalencias. Los agregados históricos sin correspondencia geográfica vigente no participan en el mapa/ranking de países. Los cambios temporales pueden reflejar cambios de cobertura. No se agregan costos ni fuentes adicionales no indicadas.

Precio y posición mundial no tienen un KPI único para múltiples países/cultivos cuando no corresponde; se muestran las series y posiciones individuales. Un rendimiento agregado con cobertura incompleta queda N/D.

## Ejecutar

Consulta `README.md`. La carpeta local conserva las descargas oficiales. El ZIP de entrega omite caché, entornos y archivos temporales y puede reconstruir los datos desde FAOSTAT.
