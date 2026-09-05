-- Requisito del laboratorio: todas las combinaciones región, categoría y mes.
SELECT
    region,
    categoria,
    mes,
    GROUPING(region) AS agrupa_region,
    GROUPING(categoria) AS agrupa_categoria,
    GROUPING(mes) AS agrupa_mes,
    SUM(total_venta) AS ventas_totales
FROM analytics.vw_ventas_analiticas
GROUP BY CUBE (region, categoria, mes)
ORDER BY agrupa_region, agrupa_categoria, agrupa_mes, region, categoria, mes;
