CREATE OR ALTER PROCEDURE etl.sp_procesar_lote
    @p_batch_id VARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    BEGIN TRANSACTION;
    BEGIN TRY
        DELETE FROM staging.stg_ventas_evaluadas WHERE batch_id = @p_batch_id;
        DELETE FROM audit.dq_rechazos WHERE batch_id = @p_batch_id;
        DELETE FROM dw.fact_ventas WHERE batch_id = @p_batch_id;
        DELETE FROM audit.etl_control WHERE batch_id = @p_batch_id;

        WITH prepared AS (
            SELECT r.*,
                TRY_CONVERT(BIGINT, NULLIF(LTRIM(RTRIM(r.id_venta)), '')) id_typed,
                TRY_CONVERT(DATE, NULLIF(LTRIM(RTRIM(r.fecha_venta)), ''), 23) fecha_typed,
                TRY_CONVERT(INT, NULLIF(LTRIM(RTRIM(r.cantidad)), '')) cantidad_typed,
                TRY_CONVERT(DECIMAL(12,2), NULLIF(LTRIM(RTRIM(r.precio_unitario)), '')) precio_typed,
                COUNT(*) OVER (PARTITION BY LTRIM(RTRIM(r.id_venta))) id_count,
                p.producto producto_catalogo, p.categoria categoria_catalogo,
                g.region region_catalogo
            FROM staging.stg_ventas_raw r
            LEFT JOIN reference.productos p
              ON LOWER(LTRIM(RTRIM(r.producto))) = LOWER(p.producto) AND p.activo = 1
            LEFT JOIN reference.regiones g
              ON LOWER(LTRIM(RTRIM(r.region))) = LOWER(g.region) AND g.activo = 1
            WHERE r.batch_id = @p_batch_id
        ), evaluated AS (
            SELECT *, CONCAT(
                CASE WHEN id_typed IS NULL THEN 'DQ-001,' ELSE '' END,
                CASE WHEN id_count > 1 THEN 'DQ-002,' ELSE '' END,
                CASE WHEN fecha_typed IS NULL OR fecha_typed > CAST(ingestion_timestamp AS DATE)
                     THEN 'DQ-003,' ELSE '' END,
                CASE WHEN NULLIF(LTRIM(RTRIM(producto)), '') IS NULL
                       OR NULLIF(LTRIM(RTRIM(categoria)), '') IS NULL
                       OR NULLIF(LTRIM(RTRIM(region)), '') IS NULL
                     THEN 'DQ-004,' ELSE '' END,
                CASE WHEN cantidad_typed IS NULL OR cantidad_typed <= 0
                     THEN 'DQ-005,' ELSE '' END,
                CASE WHEN precio_typed IS NULL OR precio_typed <= 0
                     THEN 'DQ-006,' ELSE '' END,
                CASE WHEN producto_catalogo IS NULL OR region_catalogo IS NULL
                       OR NOT EXISTS (
                           SELECT 1 FROM reference.productos c
                           WHERE LOWER(c.categoria) = LOWER(LTRIM(RTRIM(prepared.categoria)))
                             AND c.activo = 1)
                     THEN 'DQ-007,' ELSE '' END,
                CASE WHEN producto_catalogo IS NOT NULL
                       AND LOWER(categoria_catalogo) <> LOWER(LTRIM(RTRIM(categoria)))
                     THEN 'DQ-008,' ELSE '' END
            ) errors
            FROM prepared
        )
        INSERT INTO staging.stg_ventas_evaluadas (
            raw_row_key, id_venta, fecha_venta, producto, categoria, region,
            cantidad, precio_unitario, total_venta, batch_id, ingestion_timestamp,
            dq_errors, es_valido
        )
        SELECT raw_row_key, id_typed, fecha_typed,
            NULLIF(LTRIM(RTRIM(producto)), ''), NULLIF(LTRIM(RTRIM(categoria)), ''),
            NULLIF(LTRIM(RTRIM(region)), ''), cantidad_typed, precio_typed,
            CONVERT(DECIMAL(14,2), cantidad_typed * precio_typed),
            batch_id, ingestion_timestamp, errors,
            CASE WHEN errors = '' THEN 1 ELSE 0 END
        FROM evaluated;

        INSERT INTO audit.dq_rechazos (
            batch_id, raw_row_key, id_venta_original, fecha_venta_original,
            producto_original, categoria_original, region_original,
            cantidad_original, precio_original, reglas_incumplidas
        )
        SELECT r.batch_id, r.raw_row_key, r.id_venta, r.fecha_venta, r.producto,
            r.categoria, r.region, r.cantidad, r.precio_unitario, e.dq_errors
        FROM staging.stg_ventas_raw r
        JOIN staging.stg_ventas_evaluadas e
          ON r.raw_row_key = e.raw_row_key AND r.batch_id = e.batch_id
        WHERE r.batch_id = @p_batch_id AND e.es_valido = 0;

        INSERT INTO dw.dim_fecha (fecha_key, fecha, dia, mes, nombre_mes, trimestre, anio)
        SELECT DISTINCT CONVERT(INT, CONVERT(CHAR(8), s.fecha_venta, 112)), s.fecha_venta,
            DAY(s.fecha_venta), MONTH(s.fecha_venta),
            CASE MONTH(s.fecha_venta)
                WHEN 1 THEN 'Enero' WHEN 2 THEN 'Febrero' WHEN 3 THEN 'Marzo'
                WHEN 4 THEN 'Abril' WHEN 5 THEN 'Mayo' WHEN 6 THEN 'Junio'
                WHEN 7 THEN 'Julio' WHEN 8 THEN 'Agosto' WHEN 9 THEN 'Septiembre'
                WHEN 10 THEN 'Octubre' WHEN 11 THEN 'Noviembre' ELSE 'Diciembre' END,
            DATEPART(QUARTER, s.fecha_venta), YEAR(s.fecha_venta)
        FROM staging.stg_ventas_evaluadas s
        WHERE s.batch_id = @p_batch_id AND s.es_valido = 1
          AND NOT EXISTS (SELECT 1 FROM dw.dim_fecha d WHERE d.fecha = s.fecha_venta);

        INSERT INTO dw.dim_producto (producto, categoria)
        SELECT DISTINCT s.producto, s.categoria
        FROM staging.stg_ventas_evaluadas s
        WHERE s.batch_id = @p_batch_id AND s.es_valido = 1
          AND NOT EXISTS (
              SELECT 1 FROM dw.dim_producto d
              WHERE LOWER(d.producto) = LOWER(s.producto) AND d.vigente = 1);

        INSERT INTO dw.dim_region (region)
        SELECT DISTINCT s.region FROM staging.stg_ventas_evaluadas s
        WHERE s.batch_id = @p_batch_id AND s.es_valido = 1
          AND NOT EXISTS (
              SELECT 1 FROM dw.dim_region d
              WHERE LOWER(d.region) = LOWER(s.region) AND d.vigente = 1);

        INSERT INTO dw.fact_ventas (
            id_venta, fecha_key, producto_key, region_key, cantidad,
            precio_unitario, total_venta, batch_id
        )
        SELECT s.id_venta, f.fecha_key, p.producto_key, r.region_key,
            s.cantidad, s.precio_unitario, s.total_venta, s.batch_id
        FROM staging.stg_ventas_evaluadas s
        JOIN dw.dim_fecha f ON f.fecha = s.fecha_venta
        JOIN dw.dim_producto p ON LOWER(p.producto) = LOWER(s.producto) AND p.vigente = 1
        JOIN dw.dim_region r ON LOWER(r.region) = LOWER(s.region) AND r.vigente = 1
        WHERE s.batch_id = @p_batch_id AND s.es_valido = 1
          AND NOT EXISTS (SELECT 1 FROM dw.fact_ventas d WHERE d.id_venta = s.id_venta);

        INSERT INTO audit.etl_control (
            batch_id, fecha_inicio, fecha_fin, registros_origen, registros_validos,
            registros_rechazados, registros_publicados, importe_origen,
            importe_publicado, estado
        )
        SELECT @p_batch_id, MIN(raw.ingestion_timestamp), SYSUTCDATETIME(), COUNT_BIG(*),
            SUM(CASE WHEN e.es_valido = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN e.es_valido = 0 THEN 1 ELSE 0 END),
            (SELECT COUNT_BIG(*) FROM dw.fact_ventas f WHERE f.batch_id = @p_batch_id),
            COALESCE(SUM(TRY_CONVERT(DECIMAL(18,2), raw.cantidad)
                * TRY_CONVERT(DECIMAL(18,2), raw.precio_unitario)), 0),
            COALESCE((SELECT SUM(f.total_venta) FROM dw.fact_ventas f
                      WHERE f.batch_id = @p_batch_id), 0),
            CASE WHEN SUM(CASE WHEN e.es_valido = 1 THEN 1 ELSE 0 END)
                       = (SELECT COUNT_BIG(*) FROM dw.fact_ventas f
                          WHERE f.batch_id = @p_batch_id)
                 THEN 'SUCCESS' ELSE 'FAILED' END
        FROM staging.stg_ventas_raw raw
        JOIN staging.stg_ventas_evaluadas e
          ON raw.raw_row_key = e.raw_row_key AND raw.batch_id = e.batch_id
        WHERE raw.batch_id = @p_batch_id;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO
