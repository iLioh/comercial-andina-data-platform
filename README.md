# Comercial Andina Data Platform

Plataforma analítica de ventas basada en Data Warehousing, calidad de datos, ETL, consultas OLAP y Power BI para Comercial Andina S.A.

## Objetivo

Construir una prueba de concepto segura y trazable que transforme ventas operacionales en información analítica confiable para Gerencia, Comercial y Operaciones.

## Flujo de datos

```text
Amazon RDS for PostgreSQL
    → Python + Prefect en Amazon ECS Fargate
    → Amazon S3 RAW
    → Amazon Redshift Serverless Staging
    → Data Quality
    → Data Warehouse
    → Consultas OLAP
    → Power BI
```

Los registros inválidos serán enviados a auditoría y Amazon S3 Quarantine. IAM, KMS, Secrets Manager, CloudWatch, GitHub y GitHub Actions funcionarán como capacidades transversales.

## Alcance de la PoC

- Fuente oficial: `oltp.ventas_origen`.
- 10 000 ventas sintéticas.
- 20 productos y 5 categorías.
- 5 regiones.
- 3 años de historia.
- Procesamiento diario D+1.
- Data Warehouse: `dim_fecha`, `dim_producto`, `dim_region` y `fact_ventas`.
- Analítica: `GROUP BY`, `ROLLUP`, `CUBE` y `GROUPING SETS`.
- Consumo mediante Power BI.

## Preparación local

Se requiere Python 3.11 o superior.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
```

La infraestructura y las credenciales no se almacenan dentro del repositorio.
