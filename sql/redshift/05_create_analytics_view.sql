CREATE OR REPLACE VIEW analytics.vw_ventas_analiticas AS
SELECT
    fact.id_venta,
    fecha.fecha,
    fecha.mes,
    fecha.nombre_mes,
    fecha.trimestre,
    fecha.anio,
    producto.producto,
    producto.categoria,
    region.region,
    fact.cantidad,
    fact.precio_unitario,
    fact.total_venta,
    fact.batch_id,
    fact.fecha_carga
FROM dw.fact_ventas fact
JOIN dw.dim_fecha fecha ON fecha.fecha_key = fact.fecha_key
JOIN dw.dim_producto producto ON producto.producto_key = fact.producto_key
JOIN dw.dim_region region ON region.region_key = fact.region_key
WITH NO SCHEMA BINDING;

CREATE OR REPLACE VIEW analytics.vw_fact_ventas AS
SELECT
    venta_key,
    id_venta,
    fecha_key,
    producto_key,
    region_key,
    cantidad,
    precio_unitario,
    total_venta,
    batch_id,
    fecha_carga
FROM dw.fact_ventas
WITH NO SCHEMA BINDING;

CREATE OR REPLACE VIEW analytics.vw_dim_fecha AS
SELECT fecha_key, fecha, dia, mes, nombre_mes, trimestre, anio
FROM dw.dim_fecha
WITH NO SCHEMA BINDING;

CREATE OR REPLACE VIEW analytics.vw_dim_producto AS
SELECT producto_key, producto, categoria
FROM dw.dim_producto
WHERE vigente = TRUE
WITH NO SCHEMA BINDING;

CREATE OR REPLACE VIEW analytics.vw_dim_region AS
SELECT region_key, region
FROM dw.dim_region
WHERE vigente = TRUE
WITH NO SCHEMA BINDING;

CREATE OR REPLACE VIEW analytics.vw_usuario_region AS
SELECT acceso.usuario_correo, region.region_key
FROM security.usuario_region acceso
JOIN dw.dim_region region ON LOWER(region.region) = LOWER(acceso.region)
WHERE acceso.activo = TRUE
  AND region.vigente = TRUE
WITH NO SCHEMA BINDING;

CREATE OR REPLACE VIEW analytics.vw_control_etl AS
SELECT
    batch_id,
    fecha_inicio,
    fecha_fin,
    registros_origen,
    registros_validos,
    registros_rechazados,
    registros_publicados,
    importe_origen,
    importe_publicado,
    estado
FROM audit.etl_control
WITH NO SCHEMA BINDING;
