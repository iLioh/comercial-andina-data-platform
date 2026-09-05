CREATE SCHEMA IF NOT EXISTS oltp;

CREATE TABLE IF NOT EXISTS oltp.ventas_origen (
    id_venta BIGINT PRIMARY KEY,
    fecha_venta DATE,
    producto VARCHAR(100),
    categoria VARCHAR(100),
    region VARCHAR(50),
    cantidad INTEGER,
    precio_unitario NUMERIC(12, 2)
);

COMMENT ON TABLE oltp.ventas_origen IS
'Fuente operacional consolidada y simulada para el laboratorio de Comercial Andina';
