CREATE OR REPLACE PROCEDURE etl.sp_procesar_lote(p_batch_id VARCHAR)
AS $$
BEGIN
    DELETE FROM staging.stg_ventas_evaluadas WHERE batch_id = p_batch_id;
    DELETE FROM audit.dq_rechazos WHERE batch_id = p_batch_id;
    DELETE FROM dw.fact_ventas WHERE batch_id = p_batch_id;
    DELETE FROM audit.etl_control WHERE batch_id = p_batch_id;

    INSERT INTO staging.stg_ventas_evaluadas (
        raw_row_key,
        id_venta,
        fecha_venta,
        producto,
        categoria,
        region,
        cantidad,
        precio_unitario,
        total_venta,
        batch_id,
        ingestion_timestamp,
        dq_errors,
        es_valido
    )
    WITH prepared AS (
        SELECT
            r.*,
            TRY_CAST(NULLIF(TRIM(r.id_venta), '') AS BIGINT) AS id_venta_typed,
            TRY_CAST(NULLIF(TRIM(r.fecha_venta), '') AS DATE) AS fecha_typed,
            TRY_CAST(NULLIF(TRIM(r.cantidad), '') AS INTEGER) AS cantidad_typed,
            TRY_CAST(NULLIF(TRIM(r.precio_unitario), '') AS DECIMAL(12, 2)) AS precio_typed,
            COUNT(*) OVER (PARTITION BY TRIM(r.id_venta)) AS id_count,
            p.producto AS producto_catalogo,
            p.categoria AS categoria_catalogo,
            g.region AS region_catalogo
        FROM staging.stg_ventas_raw r
        LEFT JOIN reference.productos p
            ON LOWER(TRIM(r.producto)) = LOWER(p.producto)
           AND p.activo = TRUE
        LEFT JOIN reference.regiones g
            ON LOWER(TRIM(r.region)) = LOWER(g.region)
           AND g.activo = TRUE
        WHERE r.batch_id = p_batch_id
    ), evaluated AS (
        SELECT
            id_venta_typed,
            fecha_typed,
            NULLIF(TRIM(producto), '') AS producto_clean,
            NULLIF(TRIM(categoria), '') AS categoria_clean,
            NULLIF(TRIM(region), '') AS region_clean,
            cantidad_typed,
            precio_typed,
            CAST(cantidad_typed * precio_typed AS DECIMAL(14, 2)) AS total_typed,
            batch_id,
            ingestion_timestamp,
            RTRIM(
                CASE WHEN id_venta_typed IS NULL THEN 'DQ-001,' ELSE '' END ||
                CASE WHEN id_count > 1 THEN 'DQ-002,' ELSE '' END ||
                CASE WHEN fecha_typed IS NULL OR fecha_typed > CURRENT_DATE THEN 'DQ-003,' ELSE '' END ||
                CASE WHEN NULLIF(TRIM(producto), '') IS NULL
                       OR NULLIF(TRIM(categoria), '') IS NULL
                       OR NULLIF(TRIM(region), '') IS NULL THEN 'DQ-004,' ELSE '' END ||
                CASE WHEN cantidad_typed IS NULL OR cantidad_typed <= 0 THEN 'DQ-005,' ELSE '' END ||
                CASE WHEN precio_typed IS NULL OR precio_typed <= 0 THEN 'DQ-006,' ELSE '' END ||
                CASE WHEN producto_catalogo IS NULL OR region_catalogo IS NULL
                       OR NOT EXISTS (
                           SELECT 1 FROM reference.productos c
                           WHERE LOWER(c.categoria) = LOWER(TRIM(categoria))
                             AND c.activo = TRUE
                       ) THEN 'DQ-007,' ELSE '' END ||
                CASE WHEN producto_catalogo IS NOT NULL
                       AND LOWER(categoria_catalogo) <> LOWER(TRIM(categoria))
                     THEN 'DQ-008,' ELSE '' END,
                ','
            ) AS errors
        FROM prepared
    )
    SELECT
        raw_row_key,
        id_venta_typed,
        fecha_typed,
        producto_clean,
        categoria_clean,
        region_clean,
        cantidad_typed,
        precio_typed,
        total_typed,
        batch_id,
        ingestion_timestamp,
        errors,
        errors = ''
    FROM evaluated;

    INSERT INTO audit.dq_rechazos (
        batch_id,
        raw_row_key,
        id_venta_original,
        fecha_venta_original,
        producto_original,
        categoria_original,
        region_original,
        cantidad_original,
        precio_original,
        reglas_incumplidas
    )
    SELECT
        r.batch_id,
        r.raw_row_key,
        r.id_venta,
        r.fecha_venta,
        r.producto,
        r.categoria,
        r.region,
        r.cantidad,
        r.precio_unitario,
        e.dq_errors
    FROM staging.stg_ventas_raw r
    JOIN staging.stg_ventas_evaluadas e
      ON r.raw_row_key = e.raw_row_key
     AND r.batch_id = e.batch_id
    WHERE r.batch_id = p_batch_id
      AND e.es_valido = FALSE;

    INSERT INTO dw.dim_fecha (fecha_key, fecha, dia, mes, nombre_mes, trimestre, anio)
    SELECT DISTINCT
        CAST(TO_CHAR(fecha_venta, 'YYYYMMDD') AS INTEGER),
        fecha_venta,
        EXTRACT(DAY FROM fecha_venta),
        EXTRACT(MONTH FROM fecha_venta),
        TRIM(TO_CHAR(fecha_venta, 'Month')),
        EXTRACT(QUARTER FROM fecha_venta),
        EXTRACT(YEAR FROM fecha_venta)
    FROM staging.stg_ventas_evaluadas source
    WHERE source.batch_id = p_batch_id
      AND source.es_valido = TRUE
      AND NOT EXISTS (
          SELECT 1 FROM dw.dim_fecha target
          WHERE target.fecha_key = CAST(TO_CHAR(source.fecha_venta, 'YYYYMMDD') AS INTEGER)
      );

    INSERT INTO dw.dim_producto (producto, categoria)
    SELECT DISTINCT source.producto, source.categoria
    FROM staging.stg_ventas_evaluadas source
    WHERE source.batch_id = p_batch_id
      AND source.es_valido = TRUE
      AND NOT EXISTS (
          SELECT 1 FROM dw.dim_producto target
          WHERE LOWER(target.producto) = LOWER(source.producto)
            AND target.vigente = TRUE
      );

    INSERT INTO dw.dim_region (region)
    SELECT DISTINCT source.region
    FROM staging.stg_ventas_evaluadas source
    WHERE source.batch_id = p_batch_id
      AND source.es_valido = TRUE
      AND NOT EXISTS (
          SELECT 1 FROM dw.dim_region target
          WHERE LOWER(target.region) = LOWER(source.region)
            AND target.vigente = TRUE
      );

    INSERT INTO dw.fact_ventas (
        id_venta,
        fecha_key,
        producto_key,
        region_key,
        cantidad,
        precio_unitario,
        total_venta,
        batch_id
    )
    SELECT
        source.id_venta,
        fecha.fecha_key,
        producto.producto_key,
        region.region_key,
        source.cantidad,
        source.precio_unitario,
        source.total_venta,
        source.batch_id
    FROM staging.stg_ventas_evaluadas source
    JOIN dw.dim_fecha fecha ON fecha.fecha = source.fecha_venta
    JOIN dw.dim_producto producto
      ON LOWER(producto.producto) = LOWER(source.producto)
     AND producto.vigente = TRUE
    JOIN dw.dim_region region
      ON LOWER(region.region) = LOWER(source.region)
     AND region.vigente = TRUE
    WHERE source.batch_id = p_batch_id
      AND source.es_valido = TRUE
      AND NOT EXISTS (
          SELECT 1 FROM dw.fact_ventas target
          WHERE target.id_venta = source.id_venta
      );

    INSERT INTO audit.etl_control (
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
    )
    SELECT
        p_batch_id,
        MIN(raw.ingestion_timestamp),
        GETDATE(),
        COUNT(*),
        SUM(CASE WHEN evaluated.es_valido THEN 1 ELSE 0 END),
        SUM(CASE WHEN evaluated.es_valido = FALSE THEN 1 ELSE 0 END),
        (SELECT COUNT(*) FROM dw.fact_ventas f WHERE f.batch_id = p_batch_id),
        COALESCE(SUM(
            TRY_CAST(raw.cantidad AS DECIMAL(18, 2))
            * TRY_CAST(raw.precio_unitario AS DECIMAL(18, 2))
        ), 0),
        COALESCE((SELECT SUM(f.total_venta) FROM dw.fact_ventas f WHERE f.batch_id = p_batch_id), 0),
        CASE
            WHEN SUM(CASE WHEN evaluated.es_valido THEN 1 ELSE 0 END)
                 = (SELECT COUNT(*) FROM dw.fact_ventas f WHERE f.batch_id = p_batch_id)
            THEN 'SUCCESS'
            ELSE 'FAILED'
        END
    FROM staging.stg_ventas_raw raw
    JOIN staging.stg_ventas_evaluadas evaluated
      ON raw.raw_row_key = evaluated.raw_row_key
     AND raw.batch_id = evaluated.batch_id
    WHERE raw.batch_id = p_batch_id;
END;
$$ LANGUAGE plpgsql;
