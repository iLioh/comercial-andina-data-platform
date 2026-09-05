-- Pregunta: ¿Cuánto se vendió y cuántas unidades se colocaron por región?
SELECT
    region,
    SUM(total_venta) AS ventas_totales,
    SUM(cantidad) AS unidades_vendidas
FROM analytics.vw_ventas_analiticas
GROUP BY region
ORDER BY ventas_totales DESC;
