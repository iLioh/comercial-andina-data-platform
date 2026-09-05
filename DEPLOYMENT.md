# Despliegue Azure y evidencias

## 1. Prerrequisitos

- Suscripción Azure for Students activa y presupuesto configurado.
- Grupo `rg-comercial-andina-dev` en `chilecentral`.
- Azure CLI, Git, Python 3.11+ y Power BI Desktop.
- Workspace gratuito de Prefect Cloud.
- ACR dedicado de Comercial Andina y Log Analytics centralizado reutilizado para
  reducir tiempo y costo.

## 2. Validación local

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check .
pytest
docker build --tag comercial-andina-etl:local .
```

## 3. Federación GitHub → Azure

Desde Azure Cloud Shell, ejecutar `scripts/configure_github_oidc.sh`. El script crea
o reutiliza `id-github-comercial-andina-dev`, asigna únicamente los roles necesarios
y configura una credencial federada limitada al repositorio y ambiente `dev`. No
genera Client Secret.

Configurar en GitHub **Settings → Environments → dev → Variables**:

| Variable | Valor |
|---|---|
| `AZURE_CLIENT_ID` | salida del script OIDC |
| `AZURE_TENANT_ID` | salida del script OIDC |
| `AZURE_SUBSCRIPTION_ID` | salida del script OIDC |
| `DEPLOYER_PRINCIPAL_ID` | salida del script OIDC |
| `AZURE_RESOURCE_GROUP` | `rg-comercial-andina-dev` |
| `AZURE_LOCATION` | `chilecentral` |
| `AZURE_ACR_NAME` | `acrcomercialandina84621` |
| `AZURE_ACR_RESOURCE_GROUP` | `rg-comercial-andina-dev` |
| `LOG_ANALYTICS_WORKSPACE` | `workspace-rgbancoandinocicd37iy` |
| `LOG_ANALYTICS_RESOURCE_GROUP` | `rg-banco-andino-cicd` |

Configurar como **Environment secrets**:

- `POSTGRES_ADMIN_PASSWORD`: contraseña única de al menos 16 caracteres.
- `SQL_ADMIN_PASSWORD`: contraseña distinta de al menos 16 caracteres.
- `PREFECT_API_KEY`: API key creada en Prefect Cloud.

No mostrar ni guardar estos valores fuera de los almacenes cifrados.

## 4. Despliegue automatizado

1. Integrar la rama Azure mediante Pull Request con CI exitoso.
2. Abrir **Actions → Deploy Azure PoC → Run workflow**.
3. Seleccionar `dev` e ingresar el API URL del workspace de Prefect.
4. El workflow despliega ADLS, Key Vault, PostgreSQL, Azure SQL y Container Apps Jobs.
5. Luego construye la imagen en el runner administrado de GitHub, la publica en
   ACR con OIDC e inicia el job de bootstrap. Este método evita depender de ACR
   Tasks en regiones donde el servicio de compilación remota no está disponible.

## 5. Inicialización y primer pipeline

Comprobar la ejecución de bootstrap:

```bash
az containerapp job execution list \
  --name caj-comercial-andina-bootstrap-dev \
  --resource-group rg-comercial-andina-dev \
  --output table
```

Iniciar el pipeline principal:

```bash
az containerapp job start \
  --name caj-comercial-andina-etl-dev \
  --resource-group rg-comercial-andina-dev
```

El flujo visible en Prefect debe mostrar seis tareas exitosas y la reconciliación:
10 000 registros origen = 9 980 válidos + 20 rechazados.

## 6. Validaciones y OLAP

En Azure SQL consultar `audit.etl_control`, `audit.dq_rechazos`, las tres dimensiones
y `dw.fact_ventas`. Ejecutar en orden los scripts `sql/olap/01` a `05` y conservar
resultados de `GROUP BY`, `ROLLUP`, `CUBE`, `GROUPING SETS` y `GROUPING_ID`.

## 7. Power BI

Conectar Power BI Desktop a `analytics.vw_ventas_analiticas` en modo Import. Crear
las medidas, relaciones, tres páginas y RLS descritas en `powerbi/SEMANTIC_MODEL.md`.

## 8. Evidencias mínimas

- Pull Request y CI exitoso.
- Recursos Azure y despliegue Bicep exitoso.
- RAW, manifiesto y cuarentena en ADLS.
- Flujo Prefect con seis tareas.
- Reconciliación 10 000 = 9 980 + 20.
- Dimensiones y tabla de hechos cargadas.
- Cinco consultas OLAP y su interpretación.
- Dashboard Power BI y prueba de RLS.
- Azure Monitor/Log Analytics y ejecución del Container Apps Job.

## 9. Control de costos

La base Azure SQL se auto-pausa tras 60 minutos sin actividad y Container Apps Jobs
solo ejecuta por lote. Al concluir la exposición, exportar evidencias y eliminar
`rg-comercial-andina-dev` para detener los cargos de la PoC. El ACR dedicado se
elimina junto con el grupo; Log Analytics se conserva porque es un recurso centralizado.
