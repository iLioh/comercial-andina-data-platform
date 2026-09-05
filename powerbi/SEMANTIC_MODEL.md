# Modelo semántico y dashboard de Power BI

Power BI se conectará a Azure SQL Database en modo **Import**. Solo se
importarán las vistas del esquema `analytics`; las capas RAW, Staging, auditoría y
las tablas internas del DW no se exponen al reporte.

## Tablas y relaciones

| Vista importada | Uso |
|---|---|
| `vw_fact_ventas` | Cantidad, precio e importe de cada venta válida |
| `vw_dim_fecha` | Calendario, mes, trimestre y año |
| `vw_dim_producto` | Producto y categoría |
| `vw_dim_region` | Región comercial |
| `vw_usuario_region` | Mapeo de acceso para RLS |
| `vw_control_etl` | Indicadores operacionales y conciliación |

Relaciones de filtro simple, uno a muchos:

- `vw_dim_fecha[fecha_key]` → `vw_fact_ventas[fecha_key]`.
- `vw_dim_producto[producto_key]` → `vw_fact_ventas[producto_key]`.
- `vw_dim_region[region_key]` → `vw_fact_ventas[region_key]`.
- `vw_dim_region[region_key]` ↔ `vw_usuario_region[region_key]`; el filtro de
  seguridad debe propagarse desde la tabla de acceso hacia Región.

`vw_dim_fecha` se marcará como tabla de fechas utilizando la columna `fecha`.

## Medidas DAX

```DAX
Total Ventas =
SUM ( vw_fact_ventas[total_venta] )

Total Unidades =
SUM ( vw_fact_ventas[cantidad] )

Número de Ventas =
DISTINCTCOUNT ( vw_fact_ventas[id_venta] )

Ticket Promedio =
DIVIDE ( [Total Ventas], [Número de Ventas] )

Ventas Mes Anterior =
CALCULATE ( [Total Ventas], DATEADD ( vw_dim_fecha[fecha], -1, MONTH ) )

Variación MoM % =
DIVIDE ( [Total Ventas] - [Ventas Mes Anterior], [Ventas Mes Anterior] )

Participación Regional % =
DIVIDE (
    [Total Ventas],
    CALCULATE ( [Total Ventas], REMOVEFILTERS ( vw_dim_region ) )
)
```

Formatear importes en soles (`S/`) y porcentajes con una cifra decimal.

## Páginas del reporte

### 1. Resumen ejecutivo

- Tarjetas: Total Ventas, Total Unidades, Número de Ventas y Ticket Promedio.
- Barras: ventas por región, requisito explícito del laboratorio.
- Línea: evolución mensual, requisito explícito del laboratorio.
- Segmentadores: año, categoría y región.

### 2. Análisis comercial

- Matriz categoría × región, requisito explícito del laboratorio.
- Ranking de productos.
- Participación regional.
- Tooltip con unidades, ticket promedio y variación mensual.

### 3. Calidad y operación

- Lotes ejecutados, registros válidos y rechazados.
- Porcentaje de calidad y conciliación de importes.
- Esta página consumirá una vista de auditoría solo para usuarios administradores.

## Seguridad a nivel de fila

Crear el rol `JefaturaRegional` con esta expresión sobre `vw_usuario_region`:

```DAX
[usuario_correo] = USERPRINCIPALNAME()
```

Validar el rol con **Ver como** y, después de publicar, asignar los usuarios al rol
en Power BI Service. Gerencia y los responsables autorizados se gestionarán por un
rol separado sin restricción regional.

## Criterios de aceptación

- Ningún visual consume `oltp`, RAW ni Staging.
- Los tres visuales exigidos por el laboratorio están presentes.
- Los totales de Power BI coinciden con `audit.etl_control`.
- RLS se prueba con al menos dos usuarios regionales de demostración.
- La actualización está programada después de finalizar el lote D+1.
