-- Requisito del laboratorio: detalle, subtotal regional y total general.
SELECT
    CASE WHEN GROUPING(region) = 1 THEN 'TOTAL GENERAL' ELSE region END AS region,
    CASE
        WHEN GROUPING(region) = 1 THEN 'TODOS LOS PRODUCTOS'
        WHEN GROUPING(producto) = 1 THEN 'SUBTOTAL REGIÓN'
        ELSE producto
    END AS producto,
    SUM(total_venta) AS ventas_totales
FROM analytics.vw_ventas_analiticas
GROUP BY ROLLUP (region, producto)
ORDER BY GROUPING(region), region, GROUPING(producto), ventas_totales DESC;
