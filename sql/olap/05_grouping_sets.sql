-- Agregaciones seleccionadas para evitar combinaciones innecesarias.
SELECT
    region,
    categoria,
    mes,
    GROUPING_ID(region, categoria, mes) AS nivel_agrupacion,
    SUM(total_venta) AS ventas_totales
FROM analytics.vw_ventas_analiticas
GROUP BY GROUPING SETS (
    (region, mes),
    (categoria, mes),
    (region),
    ()
)
ORDER BY nivel_agrupacion, region, categoria, mes;
