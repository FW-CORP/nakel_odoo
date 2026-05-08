# Inyección ventas abril → cotizaciones Odoo (`master_dev`)

Los CSV de esta carpeta (**sin fila de cabecera**) son el mismo formato que el ensayo documentado en
`ventas/Pre-ventas-inyeccion/`, con columnas en este orden:

| Col | Campo lógico | Ejemplo |
|-----|----------------|---------|
| A | Número de operación (transacción) | `135143` — opcional si usás `--agrupar-por-cliente` |
| B | ID vendedor (MSSQL / Gestion) | `9` — no hace falta si usás `--mapeo-archivo-vendedor` |
| C | ID cliente | `413` |
| D | Ruta (no se usa en Odoo) | `2` |
| E | Código artículo “compacto” | `35250` → `352.50` en Odoo |
| F | Cantidad | `1.00` |
| G | (ignorado) | `0` |
| H | Fecha | `31/03/2026` |
| I | Hora | ignorada si `--sin-hora` o si `--agrupar-por-cliente` (`date_order` a las 00:00) |

## Documentación e IDs (todo codificado)

- **Mapeo vendedor / cliente → Odoo:** `ventas/Pre-ventas-inyeccion/mapeo_preventas_master18.json`
  - `vendedores_mssql_a_user_id_odoo`: p. ej. `9` → `res.users` id `106`
  - `clientes_mssql_a_partner_id`: overrides puntuales (id de contacto en Odoo)
  - `clientes_mssql_a_vat` + `clientes_mssql_vat_nombre_contiene`: id cliente MSSQL → CUIT (dígitos) y subcadena del nombre si varios partners comparten el mismo `vat`
  - `res_partner_campo_id_mssql`: `"ref"` → busca `res.partner` con `ref` = id cliente como texto (fallback)
- **Vendedor desde el nombre del archivo:** `ventas/Pre-ventas-inyeccion/mapeo_archivo_a_vendedor_mssql.json` (`patrones`: texto contenido en el **stem** del CSV, en minúsculas → `vendedor_mssql`). El orden importa (primera coincidencia gana). **Chirimonti** debe ir a `vendedor_mssql` **2** → `res.users` **105**; no reutilizar el **6** de Emanuel Vera (Odoo **103**), aunque el CSV traiga columna B = 6. **Omar (Las Heras):** patrón `omar las heras` → MSSQL **5** → Odoo user **91** (*Diaz Omar Humberto*); en los CSV de abril la columna B ya trae **5**, el patrón por archivo evita depender solo de eso.
- **Lote adicional (abril):** CSV en `/home/klap/Descargas/nakel_tempo_abril/mas-pedidos/` — patrones **`arturo deseado`** → MSSQL **16** (Odoo user **86**), **`emanuel perito`** → MSSQL **6** (Odoo **103**, mismo id columna B que Emanuel Vera en Gestion; si Perito fuera otro usuario en Odoo, habría que dar de alta su `ID_VENDEDOR` en Gestion y en `vendedores_mssql_a_user_id_odoo`).
- **Flujo completo y cotizaciones desde SQLite:** `ventas/Pre-ventas-inyeccion/MAPEO_PREVENTAS_MSSQL_MASTER18.md` (sección *Cotizaciones* y columnas Odoo-friendly).

**Odoo destino recomendado para abril:** `--master-dev` → `config_nakel.ODOO_CONFIG_MASTER_DEV` (`nakel.net.ar` / `master_dev`).  
Sin ese flag se usa `ODOO_CONFIG_MASTER18` (`master_18`).

- **Por defecto (sin `--agrupar-por-cliente`):** cada valor de columna A → **una** `sale.order`.
- **Con `--agrupar-por-cliente`:** **una cotización por cliente** (columna C) dentro del archivo; columna A no define grupos. `client_order_ref` = prefijo + slug del nombre de archivo + `-CLI-<id>`.

## Comandos

Siempre **dry-run** antes de `--apply`.

```bash
SCRIPT=/media/klap/raid5/cursor_files/nakel/ventas/Pre-ventas-inyeccion/inyectar_pedidos_csv_master18.py
MAPEO=/media/klap/raid5/cursor_files/nakel/ventas/Pre-ventas-inyeccion/mapeo_preventas_master18.json
MAPEO_VEND=/media/klap/raid5/cursor_files/nakel/ventas/Pre-ventas-inyeccion/mapeo_archivo_a_vendedor_mssql.json
DIR=/media/klap/raid5/cursor_files/nakel/ventas/inyeccion-ventas-abril

# Dry-run Ariel Choque: master_dev, sin agrupar por transacción, vendedor por nombre de archivo, fecha sin hora
python3 "$SCRIPT" --csv "$DIR/Pedidos Ariel Choque CR.csv" --mapeo "$MAPEO" \
  --sin-cabecera --master-dev --agrupar-por-cliente \
  --mapeo-archivo-vendedor "$MAPEO_VEND" \
  --omitir-lineas-sin-producto \
  --client-order-ref-prefix "VENTAS-ABRIL-" --dry-run

# Mismo flujo, otro vendedor / archivo
python3 "$SCRIPT" --csv "$DIR/Pedidos Emanuel Vera.csv" --mapeo "$MAPEO" \
  --sin-cabecera --master-dev --agrupar-por-cliente \
  --mapeo-archivo-vendedor "$MAPEO_VEND" \
  --omitir-lineas-sin-producto \
  --client-order-ref-prefix "VENTAS-ABRIL-" --dry-run

# Crear cotizaciones (mismo patrón + --apply)
python3 "$SCRIPT" --csv "$DIR/Pedidos Emanuel Vera.csv" --mapeo "$MAPEO" \
  --sin-cabecera --master-dev --agrupar-por-cliente \
  --mapeo-archivo-vendedor "$MAPEO_VEND" \
  --omitir-lineas-sin-producto \
  --client-order-ref-prefix "VENTAS-ABRIL-" --apply
```

**Modo clásico** (una orden por operación, columna B como vendedor, hora de columna I si no pasás `--sin-hora`): omití `--agrupar-por-cliente`, `--mapeo-archivo-vendedor` y `--master-dev` según necesites.

## Archivos en esta carpeta

- `Pedidos Ariel Choque CR.csv`
- `Pedidos Daniel DelgadoCR.csv`
- `Pedidos Emanuel Vera.csv`
- `Pedidos Jose Luis Chirimonti CR1.csv`
- `Pedidos Jose Luis Chirimonti CR2.csv`
- `Pedidos Omar Las Heras 1.csv` / `Pedidos Omar Las Heras 2.csv` / `Pedidos Omar Las Heras3.csv` (Diaz Omar Humberto)

Ejemplo dry-run / apply para uno de los archivos Omar (mismo bloque que el resto, cambiando `--csv`):

```bash
python3 "$SCRIPT" --csv "$DIR/Pedidos Omar Las Heras 1.csv" --mapeo "$MAPEO" \
  --sin-cabecera --master-dev --agrupar-por-cliente \
  --mapeo-archivo-vendedor "$MAPEO_VEND" \
  --omitir-lineas-sin-producto \
  --client-order-ref-prefix "VENTAS-ABRIL-" --dry-run
```

### Más pedidos (`mas-pedidos/`)

Ruta local: `/home/klap/Descargas/nakel_tempo_abril/mas-pedidos/` (mismo formato CSV sin cabecera).

- `Pedidos Arturo Deseado.csv` / `Pedidos Arturo Deseado 2.csv` / `Pedidos Arturo Deseado 3.csv`
- `Pedidos Emanuel Perito 2.csv`

Comando: mismo bloque que arriba, cambiando `--csv` a cada archivo y un prefijo de ref único si querés distinguir lotes (ej. `VENTAS-ABRIL2-`).

Si un **cliente** (columna C) no tiene `ref` en Odoo ni entrada en `clientes_mssql_a_partner_id`, el dry-run marcará error: hay que **agregar el partner** o ampliar el JSON.

**Última actualización:** 2026-04-02
