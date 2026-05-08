# NAKEL - SIRCAR TXT format fix

## Objetivo

Este addon **no modifica** la localización ni el core. Aplica un **post-proceso** sobre los TXT generados por el módulo de liquidación de impuestos para **SIRCAR (IIBB aplicado)**, corrigiendo el layout para que coincida con el formato validado por AFIP en Nakel.

En particular, corrige el caso donde Odoo genera líneas terminando en:

- `...,907,907`

y AFIP devuelve el error:

- **"El campo tipo de régimen de retención no contiene un valor válido para la jurisdicción y el período..."**

## Qué cambia

Para los archivos generados por **SIRCAR**:

- **Columna 10**: se fuerza a `001` (tipo comprobante).
- **Columna 11**: se conserva tal cual viene (jurisdicción; ej. `907` Chubut, `920` Santa Cruz).

Ejemplo:

- Antes: `00001,1,1,...,907,907`
- Después: `00001,1,1,...,001,907`

## Dónde impacta (scope)

Este módulo actúa únicamente cuando el diario de liquidación cumple:

- `account.journal.settlement_tax == iibb_aplicado_sircar`

Es decir:

- Afecta: `Ret IIBB Aplicadas para SIRCAR.txt` y `Perc IIBB Aplicadas para SIRCAR.txt`
- No afecta: SICORE, SIAP, SIFERE, ARBA, AGIP, etc.

## Cómo lo hace (técnico)

Se hereda `account.journal.get_tax_settlement_files_values()` y se post-procesa `txt_content` **solo** si el diario es SIRCAR aplicado.

Restricción deliberada:

- Solo modifica líneas con **exactamente 11 columnas** (separadas por coma).  
  Si el layout tiene más columnas (p. ej. provincias con campos adicionales), **no se toca** para evitar romper casos especiales.

Código:

- `models/account_journal.py`

## Instalación

1. Asegurar que el path `/home/odoo/SIRCAR` esté incluido en `addons_path` (o mover el addon a `/opt/odoo/custom-addons`).
2. Actualizar lista de apps (modo desarrollador).
3. Instalar el módulo **"NAKEL - SIRCAR TXT format fix"**.

## Validación rápida

1. Generar nuevamente los TXT de SIRCAR desde Odoo.
2. Abrir el archivo y confirmar que el final de cada línea sea:
   - `...,001,907` (Chubut) o `...,001,920` (Santa Cruz)
3. Reintentar carga en aplicativo web/AFIP.

## Limitaciones / supuestos

- Este fix asume que para Nakel el layout requerido por AFIP usa:
  - col10 = `001` (tipo comprobante)
  - col11 = jurisdicción
- Si AFIP cambia el layout o se agrega un caso provincial con columnas extra, puede requerir ajuste.

