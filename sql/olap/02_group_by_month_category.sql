-- Pregunta: ¿Cómo evolucionaron las ventas mensuales por categoría?
SELECT
    anio,
    mes,
    categoria,
    SUM(total_venta) AS ventas_totales
FROM analytics.vw_ventas_analiticas
GROUP BY anio, mes, categoria
ORDER BY anio, mes, categoria;
