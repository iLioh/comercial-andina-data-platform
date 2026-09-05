IF OBJECT_ID('reference.productos', 'U') IS NULL
CREATE TABLE reference.productos (
    producto VARCHAR(100) NOT NULL PRIMARY KEY,
    categoria VARCHAR(100) NOT NULL,
    activo BIT NOT NULL DEFAULT 1
);

IF OBJECT_ID('reference.regiones', 'U') IS NULL
CREATE TABLE reference.regiones (
    region VARCHAR(50) NOT NULL PRIMARY KEY,
    activo BIT NOT NULL DEFAULT 1
);

IF OBJECT_ID('staging.stg_ventas_raw', 'U') IS NULL
CREATE TABLE staging.stg_ventas_raw (
    raw_row_key BIGINT IDENTITY(1, 1) PRIMARY KEY,
    id_venta VARCHAR(50), fecha_venta VARCHAR(50), producto VARCHAR(200),
    categoria VARCHAR(200), region VARCHAR(100), cantidad VARCHAR(50),
    precio_unitario VARCHAR(50), batch_id VARCHAR(50) NOT NULL,
    ingestion_timestamp DATETIME2 NOT NULL
);

IF OBJECT_ID('staging.stg_ventas_evaluadas', 'U') IS NULL
CREATE TABLE staging.stg_ventas_evaluadas (
    raw_row_key BIGINT NOT NULL, id_venta BIGINT, fecha_venta DATE,
    producto VARCHAR(100), categoria VARCHAR(100), region VARCHAR(50),
    cantidad INT, precio_unitario DECIMAL(12, 2), total_venta DECIMAL(14, 2),
    batch_id VARCHAR(50) NOT NULL, ingestion_timestamp DATETIME2 NOT NULL,
    dq_errors VARCHAR(1000), es_valido BIT NOT NULL,
    PRIMARY KEY (raw_row_key, batch_id)
);

IF OBJECT_ID('audit.dq_rechazos', 'U') IS NULL
CREATE TABLE audit.dq_rechazos (
    rechazo_key BIGINT IDENTITY(1, 1) PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL, raw_row_key BIGINT NOT NULL,
    id_venta_original VARCHAR(50), fecha_venta_original VARCHAR(50),
    producto_original VARCHAR(200), categoria_original VARCHAR(200),
    region_original VARCHAR(100), cantidad_original VARCHAR(50),
    precio_original VARCHAR(50), reglas_incumplidas VARCHAR(1000) NOT NULL,
    fecha_rechazo DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

IF OBJECT_ID('audit.etl_control', 'U') IS NULL
CREATE TABLE audit.etl_control (
    batch_id VARCHAR(50) NOT NULL PRIMARY KEY,
    fecha_inicio DATETIME2 NOT NULL, fecha_fin DATETIME2,
    registros_origen BIGINT NOT NULL, registros_validos BIGINT NOT NULL,
    registros_rechazados BIGINT NOT NULL, registros_publicados BIGINT NOT NULL,
    importe_origen DECIMAL(18, 2) NOT NULL, importe_publicado DECIMAL(18, 2) NOT NULL,
    estado VARCHAR(20) NOT NULL
);

IF OBJECT_ID('dw.dim_fecha', 'U') IS NULL
CREATE TABLE dw.dim_fecha (
    fecha_key INT NOT NULL PRIMARY KEY, fecha DATE NOT NULL UNIQUE,
    dia INT NOT NULL, mes INT NOT NULL, nombre_mes VARCHAR(20) NOT NULL,
    trimestre INT NOT NULL, anio INT NOT NULL
);

IF OBJECT_ID('dw.dim_producto', 'U') IS NULL
CREATE TABLE dw.dim_producto (
    producto_key BIGINT IDENTITY(1, 1) PRIMARY KEY,
    producto VARCHAR(100) NOT NULL, categoria VARCHAR(100) NOT NULL,
    vigente BIT NOT NULL DEFAULT 1,
    CONSTRAINT uq_dim_producto UNIQUE (producto)
);

IF OBJECT_ID('dw.dim_region', 'U') IS NULL
CREATE TABLE dw.dim_region (
    region_key INT IDENTITY(1, 1) PRIMARY KEY,
    region VARCHAR(50) NOT NULL UNIQUE, vigente BIT NOT NULL DEFAULT 1
);

IF OBJECT_ID('dw.fact_ventas', 'U') IS NULL
CREATE TABLE dw.fact_ventas (
    venta_key BIGINT IDENTITY(1, 1) PRIMARY KEY, id_venta BIGINT NOT NULL UNIQUE,
    fecha_key INT NOT NULL, producto_key BIGINT NOT NULL, region_key INT NOT NULL,
    cantidad INT NOT NULL, precio_unitario DECIMAL(12, 2) NOT NULL,
    total_venta DECIMAL(14, 2) NOT NULL, batch_id VARCHAR(50) NOT NULL,
    fecha_carga DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_fact_fecha FOREIGN KEY (fecha_key) REFERENCES dw.dim_fecha(fecha_key),
    CONSTRAINT fk_fact_producto FOREIGN KEY (producto_key) REFERENCES dw.dim_producto(producto_key),
    CONSTRAINT fk_fact_region FOREIGN KEY (region_key) REFERENCES dw.dim_region(region_key)
);

IF OBJECT_ID('security.usuario_region', 'U') IS NULL
CREATE TABLE security.usuario_region (
    usuario_correo VARCHAR(320) NOT NULL, region VARCHAR(50) NOT NULL,
    activo BIT NOT NULL DEFAULT 1,
    PRIMARY KEY (usuario_correo, region)
);
GO
