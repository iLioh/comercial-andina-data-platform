# Guía de implementación controlada

Esta guía lleva el repositorio desde una estación de trabajo limpia hasta la PoC
desplegada. La ejecución crea recursos con costo; por ese motivo el despliegue es
manual mediante `workflow_dispatch` y no ocurre automáticamente al fusionar código.

## 1. Requisitos

- Cuenta AWS con permisos para CloudFormation, VPC, RDS, S3, KMS, Redshift
  Serverless, ECR, ECS, IAM, Secrets Manager y CloudWatch.
- AWS CLI v2, Git, Docker y Python 3.11 o superior.
- Workspace de Prefect Cloud.
- Power BI Desktop y una licencia/tenant compatible con publicación y RLS.

Trabajar inicialmente en `us-east-1`, que es la región definida para la PoC.

## 2. Preparar y validar localmente

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,aws,orchestration]"
ruff check .
pytest
cfn-lint infra/cloudformation/*.yml
```

En PowerShell, la activación del entorno es:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 3. Preparar autenticación GitHub → AWS

GitHub Actions utiliza OIDC; no se deben crear secretos `AWS_ACCESS_KEY_ID` ni
`AWS_SECRET_ACCESS_KEY`. Debido a que este repositorio fue creado después del 15 de
julio de 2026, su claim `sub` contiene los identificadores numéricos inmutables del
propietario y del repositorio. Antes de crear la relación de confianza en IAM:

1. Abrir **Settings → Actions → OpenID Connect** en GitHub.
2. Copiar el subject claim exacto del entorno `dev`.
3. Crear en IAM el proveedor `https://token.actions.githubusercontent.com` con
   audience `sts.amazonaws.com`.
4. Crear un rol de despliegue cuya confianza compare de forma exacta `aud` y `sub`.
5. Limitar el rol a los stacks `comercial-andina-*`, ECR y `iam:PassRole` solo para
   los roles de esta PoC.

Configurar un Environment protegido llamado `dev` y estas variables:

| Variable de GitHub | Contenido |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | ARN del rol federado de despliegue |
| `AWS_REGION` | `us-east-1` |
| `PREFECT_API_KEY_SECRET_ARN` | ARN del secreto que contiene solo la API key |

Para un entorno regulado real, requerir aprobación manual del Environment, dos
revisores del Pull Request y separación de roles entre despliegue y operación.

## 4. Desplegar AWS mediante GitHub Actions

1. Abrir **Actions → Deploy AWS PoC → Run workflow**.
2. Elegir `dev`.
3. Indicar la URL del workspace de Prefect Cloud.
4. Revisar el plan y ejecutar.

El workflow crea en orden:

1. VPC, dos subredes privadas, dos públicas, S3 endpoint y NAT Gateway.
2. KMS, S3, RDS PostgreSQL privado y Redshift Serverless privado.
3. ECR, imagen Docker inmutable, ECS Fargate y worker de Prefect.

Los stacks resultantes son:

- `comercial-andina-dev-network`;
- `comercial-andina-dev-data`;
- `comercial-andina-dev-compute`.

> El NAT Gateway, RDS, Redshift Serverless y ECS generan costo mientras están
> activos. Etiquetar, monitorear presupuesto y eliminar la PoC cuando termine la
> evaluación.

## 5. Crear el dataset y cargar RDS

Obtener de los outputs de CloudFormation `RdsEndpoint` y `RdsSecretArn`.

```bash
comercial-andina generate \
  --records 10000 \
  --batch-id BATCH-20260901-001

comercial-andina load-rds \
  --host RDS_ENDPOINT \
  --secret-arn RDS_SECRET_ARN \
  --region us-east-1
```

El CSV generado no se versiona. Contiene exactamente las siete columnas del
laboratorio y veinte ventas inválidas controladas para demostrar calidad.

La conexión directa a RDS requiere ejecutarse desde la VPC (por ejemplo mediante
una tarea ECS controlada o una sesión administrativa). RDS no debe hacerse público
para simplificar una carga.

## 6. Inicializar Redshift

Obtener `RedshiftWorkgroup` y `RedshiftSecretArn` y ejecutar:

```bash
comercial-andina bootstrap-redshift \
  --workgroup comercial-andina-dev \
  --secret-arn REDSHIFT_SECRET_ARN \
  --database comercial_andina_dw \
  --region us-east-1
```

Los scripts se aplican en orden numérico: schemas, tablas, catálogos, procedimiento
ETL y vistas analíticas.

## 7. Registrar y programar el flujo Prefect

Crear un work pool de tipo `process` llamado `comercial-andina-ecs`. Desde el
contenedor o una estación autenticada en el mismo workspace:

```bash
prefect work-pool create --type process comercial-andina-ecs
prefect work-pool set-concurrency-limit comercial-andina-ecs 1
prefect deploy --all
```

La programación definida en `prefect.yaml` ejecuta el lote a las 06:00 de
`America/Lima`. Para una prueba controlada:

```bash
comercial-andina run-pipeline --batch-id BATCH-20260901-001
```

## 8. Verificar la publicación

```sql
SELECT * FROM audit.etl_control ORDER BY fecha_inicio DESC;
SELECT * FROM audit.dq_rechazos ORDER BY fecha_rechazo DESC;
SELECT COUNT(*) FROM dw.fact_ventas;
SELECT SUM(total_venta) FROM dw.fact_ventas;
```

El lote de demostración debe mostrar 10 000 filas de origen, 20 registros
rechazados y 9 980 registros válidos/publicados. El conteo válido debe coincidir con
el publicado y el importe publicado debe coincidir con la suma de `fact_ventas`.

Ejecutar después todos los archivos de `sql/olap` y conservar resultados como
evidencia de `GROUP BY`, `ROLLUP`, `CUBE`, `GROUPING SETS` y `GROUPING_ID`.

## 9. Construir Power BI

Seguir `powerbi/SEMANTIC_MODEL.md`. Conectar únicamente al esquema `analytics` de
Redshift, crear las relaciones, medidas, tres visuales obligatorios y RLS. Publicar
el reporte y configurar la actualización después del lote D+1.

## 10. Evidencias de cierre

- Pull Request aprobado y checks de CI/CodeQL correctos.
- Stacks de CloudFormation en estado estable.
- Ejecución Prefect exitosa y reintentos visibles.
- Objeto CSV y manifiesto en S3 RAW.
- Rechazos en `audit.dq_rechazos` y S3 Quarantine.
- Conciliación exitosa en `audit.etl_control`.
- Resultados de todas las consultas OLAP.
- Dashboard, actualización y pruebas RLS de Power BI.
- Capturas sin ARNs completos, cuentas, correos reales ni secretos.

## 11. Desmantelamiento de la PoC

Exportar primero las evidencias permitidas. Eliminar en orden compute, data y
network. S3 y los snapshots se conservan deliberadamente por las políticas
`Retain`/`Snapshot`; su eliminación final debe ser una decisión explícita del
responsable, nunca un paso automático del pipeline.
