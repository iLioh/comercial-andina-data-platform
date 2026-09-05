CREATE TABLE IF NOT EXISTS reference.productos (
    producto VARCHAR(100) NOT NULL,
    categoria VARCHAR(100) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (producto)
) DISTSTYLE ALL;

CREATE TABLE IF NOT EXISTS reference.regiones (
    region VARCHAR(50) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (region)
) DISTSTYLE ALL;

CREATE TABLE IF NOT EXISTS staging.stg_ventas_raw (
    raw_row_key BIGINT IDENTITY(1, 1),
    id_venta VARCHAR(50),
    fecha_venta VARCHAR(50),
    producto VARCHAR(200),
    categoria VARCHAR(200),
    region VARCHAR(100),
    cantidad VARCHAR(50),
    precio_unitario VARCHAR(50),
    batch_id VARCHAR(50),
    ingestion_timestamp TIMESTAMP
) DISTSTYLE AUTO;

CREATE TABLE IF NOT EXISTS staging.stg_ventas_evaluadas (
    raw_row_key BIGINT NOT NULL,
    id_venta BIGINT,
    fecha_venta DATE,
    producto VARCHAR(100),
    categoria VARCHAR(100),
    region VARCHAR(50),
    cantidad INTEGER,
    precio_unitario DECIMAL(12, 2),
    total_venta DECIMAL(14, 2),
    batch_id VARCHAR(50) NOT NULL,
    ingestion_timestamp TIMESTAMP NOT NULL,
    dq_errors VARCHAR(1000),
    es_valido BOOLEAN NOT NULL
) DISTSTYLE AUTO SORTKEY (fecha_venta);

CREATE TABLE IF NOT EXISTS audit.dq_rechazos (
    rechazo_key BIGINT IDENTITY(1, 1),
    batch_id VARCHAR(50) NOT NULL,
    raw_row_key BIGINT NOT NULL,
    id_venta_original VARCHAR(50),
    fecha_venta_original VARCHAR(50),
    producto_original VARCHAR(200),
    categoria_original VARCHAR(200),
    region_original VARCHAR(100),
    cantidad_original VARCHAR(50),
    precio_original VARCHAR(50),
    reglas_incumplidas VARCHAR(1000) NOT NULL,
    fecha_rechazo TIMESTAMP NOT NULL DEFAULT GETDATE()
) DISTSTYLE AUTO SORTKEY (fecha_rechazo);

CREATE TABLE IF NOT EXISTS audit.etl_control (
    batch_id VARCHAR(50) NOT NULL,
    fecha_inicio TIMESTAMP NOT NULL,
    fecha_fin TIMESTAMP,
    registros_origen BIGINT NOT NULL,
    registros_validos BIGINT NOT NULL,
    registros_rechazados BIGINT NOT NULL,
    registros_publicados BIGINT NOT NULL,
    importe_origen DECIMAL(18, 2) NOT NULL,
    importe_publicado DECIMAL(18, 2) NOT NULL,
    estado VARCHAR(20) NOT NULL,
    PRIMARY KEY (batch_id)
) DISTSTYLE AUTO SORTKEY (fecha_inicio);

CREATE TABLE IF NOT EXISTS dw.dim_fecha (
    fecha_key INTEGER NOT NULL,
    fecha DATE NOT NULL,
    dia INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    nombre_mes VARCHAR(20) NOT NULL,
    trimestre INTEGER NOT NULL,
    anio INTEGER NOT NULL,
    PRIMARY KEY (fecha_key)
) DISTSTYLE ALL SORTKEY (fecha);

CREATE TABLE IF NOT EXISTS dw.dim_producto (
    producto_key BIGINT IDENTITY(1, 1),
    producto VARCHAR(100) NOT NULL,
    categoria VARCHAR(100) NOT NULL,
    vigente BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (producto_key)
) DISTSTYLE ALL;

CREATE TABLE IF NOT EXISTS dw.dim_region (
    region_key INTEGER IDENTITY(1, 1),
    region VARCHAR(50) NOT NULL,
    vigente BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (region_key)
) DISTSTYLE ALL;

CREATE TABLE IF NOT EXISTS dw.fact_ventas (
    venta_key BIGINT IDENTITY(1, 1),
    id_venta BIGINT NOT NULL,
    fecha_key INTEGER NOT NULL,
    producto_key BIGINT NOT NULL,
    region_key INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    precio_unitario DECIMAL(12, 2) NOT NULL,
    total_venta DECIMAL(14, 2) NOT NULL,
    batch_id VARCHAR(50) NOT NULL,
    fecha_carga TIMESTAMP NOT NULL DEFAULT GETDATE(),
    PRIMARY KEY (venta_key),
    FOREIGN KEY (fecha_key) REFERENCES dw.dim_fecha (fecha_key),
    FOREIGN KEY (producto_key) REFERENCES dw.dim_producto (producto_key),
    FOREIGN KEY (region_key) REFERENCES dw.dim_region (region_key)
) DISTSTYLE AUTO SORTKEY (fecha_key, region_key);

CREATE TABLE IF NOT EXISTS security.usuario_region (
    usuario_correo VARCHAR(320) NOT NULL,
    region VARCHAR(50) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE
) DISTSTYLE ALL SORTKEY (usuario_correo);
