# Política de seguridad

## Alcance

Esta es una prueba de concepto académica con patrones aplicables a entornos
regulados. No deben cargarse datos personales, bancarios ni credenciales reales en
el dataset o en el repositorio.

## Controles

- No se permiten claves AWS estáticas en GitHub ni en archivos `.env` versionados.
- GitHub Actions se autentica en AWS mediante OIDC y credenciales temporales.
- Las contraseñas se almacenan en AWS Secrets Manager.
- RDS y Redshift permanecen en subredes privadas y sin acceso público.
- S3 bloquea acceso público, exige TLS, conserva versiones y cifra con KMS.
- Los roles IAM siguen mínimo privilegio y separan ejecución, ETL y lectura BI.
- Power BI aplica RLS a las jefaturas regionales.
- CloudWatch, Redshift y las tablas `audit` conservan evidencia operacional.

## Reporte de vulnerabilidades

No publique secretos ni detalles explotables en un Issue público. Revoque primero
cualquier credencial expuesta y use un canal privado con el responsable del
proyecto. Esta PoC no representa por sí sola una certificación de cumplimiento
normativo ni una plataforma bancaria productiva.
