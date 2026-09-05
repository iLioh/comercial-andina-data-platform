# Política de seguridad

## Alcance

Esta PoC procesa únicamente datos sintéticos. Los controles implementados reproducen
patrones profesionales, pero no sustituyen una evaluación regulatoria bancaria.

## Controles implementados

- GitHub Actions se autentica mediante OIDC; no existen secretos de Azure permanentes.
- PostgreSQL y Azure SQL exigen TLS; sus contraseñas se conservan en Key Vault.
- Container Apps usa Managed Identity y permisos RBAC de alcance mínimo.
- ADLS Gen2 bloquea acceso público, Shared Key y tráfico sin HTTPS.
- RAW, manifiestos y cuarentena incluyen `batch_id` y checksum SHA-256.
- Los contenedores ejecutan como usuario no privilegiado.
- Dependabot, CodeQL, Ruff, Pytest, Bicep build y Docker build protegen los PR.
- Azure Monitor, Log Analytics, Prefect y `audit.etl_control` conservan evidencia.

## Tratamiento de secretos

Nunca se deben confirmar, copiar a incidencias o versionar contraseñas, API keys,
tokens, `.env`, cadenas de conexión, identificadores sensibles ni exportaciones reales.
Los secretos del entorno `dev` se almacenan cifrados en GitHub Environments y Azure
Key Vault.

## Evolución para producción bancaria

La PoC habilita temporalmente endpoints públicos restringidos por firewall para poder
demostrar Power BI dentro del tiempo académico. Un despliegue productivo debe añadir
Private Endpoints, VNet integration, Azure Firewall, DNS privado, Defender for Cloud,
claves administradas por el cliente, ambientes dev/qa/prod y aprobación segregada.

## Reporte

No publique vulnerabilidades como issue. Repórtelas privadamente al propietario del
repositorio e incluya componente, impacto, reproducción segura y mitigación propuesta.
