CREATE OR ALTER VIEW analytics.vw_ventas_analiticas AS
SELECT fact.id_venta, fecha.fecha, fecha.mes, fecha.nombre_mes, fecha.trimestre,
    fecha.anio, producto.producto, producto.categoria, region.region,
    fact.cantidad, fact.precio_unitario, fact.total_venta, fact.batch_id,
    fact.fecha_carga
FROM dw.fact_ventas fact
JOIN dw.dim_fecha fecha ON fecha.fecha_key = fact.fecha_key
JOIN dw.dim_producto producto ON producto.producto_key = fact.producto_key
JOIN dw.dim_region region ON region.region_key = fact.region_key;
GO

CREATE OR ALTER VIEW analytics.vw_fact_ventas AS SELECT * FROM dw.fact_ventas;
GO
CREATE OR ALTER VIEW analytics.vw_dim_fecha AS SELECT * FROM dw.dim_fecha;
GO
CREATE OR ALTER VIEW analytics.vw_dim_producto AS
SELECT producto_key, producto, categoria FROM dw.dim_producto WHERE vigente = 1;
GO
CREATE OR ALTER VIEW analytics.vw_dim_region AS
SELECT region_key, region FROM dw.dim_region WHERE vigente = 1;
GO
CREATE OR ALTER VIEW analytics.vw_usuario_region AS
SELECT acceso.usuario_correo, region.region_key
FROM security.usuario_region acceso
JOIN dw.dim_region region ON LOWER(region.region) = LOWER(acceso.region)
WHERE acceso.activo = 1 AND region.vigente = 1;
GO
CREATE OR ALTER VIEW analytics.vw_control_etl AS SELECT * FROM audit.etl_control;
GO
