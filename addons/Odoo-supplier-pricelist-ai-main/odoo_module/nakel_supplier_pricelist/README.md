# Módulo Odoo: nakel_supplier_pricelist

Módulo Odoo 18 que permite a Nakel subir listas de precios de proveedores (PDF/Excel/imagen) y procesarlas con un agente IA.

## Instalación

```bash
# En el servidor Odoo dev.nakel.net.ar
cd /opt/odoo/addons   # o ruta equivalente de addons custom
git pull   # o copiar la carpeta nakel_supplier_pricelist/
sudo systemctl restart odoo
```

Luego en Odoo:
1. Ir a **Apps**, click en "Update Apps List"
2. Buscar **"Nakel Supplier Pricelist"** y click "Install"
3. Configurar el módulo (ver sección **Configuración en Odoo (Ajustes)** más abajo).

## Modelos

### `supplier.pricelist.import` (cabecera)

Una instancia por archivo subido. Estados:
- `draft` — recién creada, archivo subido
- `processing` — agente IA procesando
- `review` — terminó, hay líneas para revisar
- `applied` — costos aplicados a Odoo
- `cancelled`

Campos clave:
| Campo | Tipo | Descripción |
|---|---|---|
| `partner_id` | M2O `res.partner` | Proveedor (filtrado por `supplier_rank > 0`) |
| `file` | Binary | El PDF/Excel/imagen subido |
| `file_name` | Char | |
| `file_type` | Selection | pdf / excel / csv / image |
| `date` | Date | Fecha de la lista (la del proveedor) |
| `state` | Selection | Ver arriba |
| `total_lines`, `matched_auto`, `matched_review`, `unmatched`, `applied_lines` | Integer (computed) | Estadísticas |

Acciones (botones):
- `action_process_ai()` — envía el archivo al servicio AI y crea las líneas
- `action_apply_confirmed()` — aplica los costos confirmados a Odoo (`standard_price` + `product.supplierinfo`)
- `action_cancel()`, `action_reset_to_draft()`

### `supplier.pricelist.import.line` (línea)

Una por producto detectado en la lista. Campos:

#### Datos del proveedor
- `supplier_product_name` (Char, required) — el nombre tal cual viene del PDF
- `supplier_presentation` (Char) — la presentación cruda (ej: "6 Estuches x 12 u.")
- `price_with_vat` (Float) — el precio crudo del proveedor
- `vat_included` (Boolean) — true si el precio incluye IVA
- `vat_rate` (Float, default 21.0)
- `price_without_vat` (Float, computed) — precio crudo sin IVA

#### Match con Odoo
- `product_tmpl_id` (M2O `product.template`) — el producto matcheado
- `alternative_ids` (M2M `product.template`) — sugerencias alternativas
- `confidence_score` (Integer 0-100)
- `match_status` (Selection) — auto / confirmed / review / no_match / rejected
- `match_notes` (Char) — explicación del agente (incluye reasoning del LLM)

#### Interpretación comercial (Sprint 3)
- **`unit_count`** (Integer, default 1) — cuántas unidades Odoo hay en el precio del proveedor
- **`unit_price_with_vat`** (Float) — `price_with_vat / unit_count`
- **`unit_price_without_vat`** (Float, computed) — el anterior sin IVA
- **`price_interpretation`** (Char) — explicación de Gemini sobre el cálculo de unit_count
- `has_comparable_cost` (Boolean, computed) — false si `standard_price` es 0 o ≤ 1

#### Comparativa de precios
- `current_cost` (Float, computed) — `product_tmpl_id.standard_price`
- `cost_delta_pct` (Float, computed) — `(unit_price_without_vat - current_cost) / current_cost * 100`
- `cost_delta_display` (Char, computed) — string formateado: `"+5.2%"` o `"—"` si no hay costo comparable
- `delta_color` (Char, computed) — `muted` / `danger` / `warning` / `success`

#### Estado
- `applied` (Boolean) — true si el costo ya fue aplicado a Odoo
- `applied_date` (Datetime)

### `supplier.product.mapping` (memoria de matches)

Tabla de aprendizaje activo. Cada match confirmado por el usuario se guarda como:
- `partner_id` (M2O `res.partner`)
- `supplier_product_name` (Char) — el nombre que usa el proveedor
- `product_tmpl_id` (M2O `product.template`) — el producto Odoo

En el próximo import del mismo proveedor con el mismo nombre, el matcher hace lookup directo (Capa 2) → 98% confidence auto.

## Flujo de uso

```
1. Usuario va a Compras → Listas de Precios de Proveedores → Nuevo
2. Selecciona proveedor y sube el PDF/Excel
3. Click "Procesar con IA" → state cambia a 'processing'
4. AI service procesa (~30 seg a varios minutos según tamaño)
5. State cambia a 'review' con las 3 pestañas:
   - Automáticos (verde, ya matcheados ≥90% confidence)
   - Revisión (amarillo, 60-89%)
   - Sin match (rojo)
6. Usuario revisa cada línea de "Revisión":
   - Confirma el match (cambia a confirmed)
   - O elige otro producto manualmente
   - O lo rechaza
7. Para "Sin match": busca el producto manualmente o lo descarta
8. Click "Aplicar costos confirmados":
   - Para cada línea con match_status in (auto, confirmed):
     - Update product.template.standard_price = unit_price_without_vat
     - Update/create product.supplierinfo (price = unit_price_without_vat, partner_id = ...)
     - Update supplier.product.mapping (memoria)
9. State cambia a 'applied'
10. Las listas de precio se recalculan automáticamente
```

## Vistas

### Form view (`supplier_pricelist_import_views.xml`)
- Header con datos de la lista (proveedor, fecha, archivo)
- 4 stat buttons coloreados (auto, revisión, sin match, aplicados)
- 3 tabs:
  - **Automáticos**: list editable con match_notes visible, confidence, costo actual, Δ%
  - **Revisión**: list editable con M2O del producto Odoo seleccionable, Δ% advertido
  - **Sin match**: list editable, permite asignar producto manualmente

### List view (en menú principal)
- Filtra por estado, proveedor, fecha
- Decoraciones por estado

### Wizard de confirmación (`confirm_wizard.py`)
Cuando el usuario quiere modificar un match en review:
- Muestra el ítem del proveedor
- Muestra el producto Odoo actual
- Muestra el `cost_delta_display` con color
- Permite cambiar el `product_tmpl_id`

## Cálculo de Δ% (cost_delta_pct)

**IMPORTANTE**: el cálculo usa `unit_price_without_vat` (no `price_without_vat` directo).

```python
@api.depends('product_tmpl_id', 'unit_price_without_vat', 'price_without_vat')
def _compute_current_cost(self):
    for rec in self:
        # 1. Sin producto matcheado
        if not rec.product_tmpl_id:
            rec.current_cost = 0.0
            rec.cost_delta_pct = 0.0
            rec.has_comparable_cost = False
            rec.cost_delta_display = '—'
            rec.delta_color = 'muted'
            continue
        
        current = rec.product_tmpl_id.standard_price or 0.0
        rec.current_cost = current
        
        # 2. Sin costo previo confiable (≤ 1, placeholder)
        if current <= self._MIN_VALID_COST:
            rec.cost_delta_pct = 0.0
            rec.has_comparable_cost = False
            rec.cost_delta_display = '—'
            rec.delta_color = 'muted'
            continue
        
        # 3. Cálculo correcto: usar precio UNITARIO
        new_unit_cost = rec.unit_price_without_vat or rec.price_without_vat
        delta = ((new_unit_cost - current) / current) * 100.0
        rec.cost_delta_pct = delta
        rec.has_comparable_cost = True
        sign = '+' if delta > 0 else ''
        rec.cost_delta_display = f'{sign}{delta:.1f}%'
        
        # 4. Color según umbrales de negocio
        if delta >= 30:    rec.delta_color = 'danger'    # suba grande
        elif delta >= 10:  rec.delta_color = 'warning'   # suba moderada
        elif delta <= -10: rec.delta_color = 'success'   # baja
        else:              rec.delta_color = 'muted'     # variación normal
```

### Ejemplos de Δ% bien calculado

| Ítem proveedor | Precio crudo | unit_count | unit_price | costo Odoo | Δ% (correcto) | color |
|---|---|---|---|---|---|---|
| BLANCO X 12 FLOWPACK | $14.190 | 12 | $1.182 | $1.123 | **+5.2%** | muted |
| BLANCO X 6 FLOWPACK | $7.281 | 1 | $7.281 | $5.470 | **+33%** | danger |
| CONITO X 12 | $12.255 | 1 | $12.255 | $11.727 | **+4.5%** | muted |
| AVENA & MIEL | $1.322 | 1 | $1.322 | $1.253 | **+5.5%** | muted |
| MAICENA X 6 | $7.281 | 1 | $7.281 | $6.291 | **+15.7%** | warning |

Sin la división por `unit_count`, los mismos ejemplos darían: BLANCO X 12 = +1163%, BOCADITOS MARROC = +500%+, etc. Todos absurdos.

## API entre Odoo y AI Service

**Llamada desde Odoo (`action_process_ai`):**
```python
import requests, base64

response = requests.post(
    f'{ai_service_url}/api/match',
    json={
        'file_content': base64.b64encode(self.file).decode(),
        'file_name': self.file_name,
        'partner_id': self.partner_id.id,
        'partner_name': self.partner_id.name,
        'catalog': self._build_catalog(),  # construye dict con productos
        'auto_threshold': int(self.env['ir.config_parameter']
                              .sudo().get_param('nakel.auto_threshold', 88)),
    },
    timeout=600,  # imports grandes pueden tomar varios minutos
)
result = response.json()
```

**`_build_catalog()`** construye lista de productos del partner + sus `product.supplierinfo`:
```python
def _build_catalog(self):
    products = self.env['product.template'].search([
        ('purchase_ok', '=', True),
        ('active', '=', True),
    ])
    catalog = []
    for p in products:
        si = p.seller_ids.filtered(lambda s: s.partner_id == self.partner_id)
        mp = self.env['supplier.product.mapping'].search([
            ('partner_id', '=', self.partner_id.id),
            ('product_tmpl_id', '=', p.id),
        ])
        catalog.append({
            'id': p.id,
            'name': p.name,
            'standard_price': p.standard_price,
            'categ_name': p.categ_id.name if p.categ_id else None,
            'barcode': p.barcode or None,
            'supplier_product_code': (si[0].product_code or None) if si else None,
            'supplier_product_name': (si[0].product_name or None) if si else None,
            'known_supplier_names': [n for n in mp.mapped('supplier_product_name') if n],
            'is_known_supplier': bool(si),
        })
    return catalog
```

## Seguridad

`security/ir.model.access.csv` da acceso a:
- `purchase.user` y `purchase.manager` → CRUD en supplier.pricelist.import.*
- `supplier.product.mapping` → solo manager (es memoria interna)

## Configuración en Odoo (Ajustes)

Una vez instalado el módulo, ir a **Ajustes → Listas de Precios IA** (también accesible desde *Compras → Configuración*). Se exponen tres parámetros:

| Campo en la UI | `ir.config_parameter` | Tipo | Default | Descripción |
|---|---|---|---|---|
| **URL del Servicio IA** | `nakel_supplier_pricelist.ai_service_url` | Char | *(vacío)* | URL base donde corre el servicio FastAPI de matching. Ejemplo: `http://192.168.1.10:8001` o `http://ai-service.miempresa.local:8001`. **Sin slash final.** |
| **IVA por defecto (%)** | `nakel_supplier_pricelist.default_vat_rate` | Float | `21.0` | Tasa de IVA usada para descontar de precios "con IVA" cuando el proveedor no especifica otra. |
| **Confianza mínima para auto-aplicar (%)** | `nakel_supplier_pricelist.auto_apply_threshold` | Integer | `90` | Líneas con `confidence_score >= este valor` se marcan como match automático y van directo a la pestaña "Automáticos". El resto cae en "Revisión". |

### Acceso por código / scripts

Para leer/escribir los parámetros desde shell o script:

```python
ICP = env['ir.config_parameter'].sudo()

# Leer
url = ICP.get_param('nakel_supplier_pricelist.ai_service_url')
vat = float(ICP.get_param('nakel_supplier_pricelist.default_vat_rate', '21.0'))
thr = int(ICP.get_param('nakel_supplier_pricelist.auto_apply_threshold', '90'))

# Escribir
ICP.set_param('nakel_supplier_pricelist.ai_service_url', 'http://192.168.1.10:8001')
ICP.set_param('nakel_supplier_pricelist.default_vat_rate', '21.0')
ICP.set_param('nakel_supplier_pricelist.auto_apply_threshold', '90')
```

### Notas

- El servicio IA debe ser **accesible por red desde el host de Odoo** (firewall/VPN/red interna).
- Si la URL apunta a otro host, conviene fijar un `timeout` razonable en el cliente HTTP (el módulo usa `timeout=600` por defecto en `action_process_ai`).
- La `GEMINI_API_KEY` **no se configura desde Odoo**: vive en el `.env` del servicio FastAPI (ver `ai_service/README.md`).

## Update del módulo

Cuando hay cambios en el modelo (nuevos campos como `unit_count`, `unit_price_with_vat`, `price_interpretation`):

```bash
# En el servidor Odoo
sudo systemctl stop odoo
sudo -u odoo ./odoo-bin -d prueba --update=nakel_supplier_pricelist --stop-after-init
sudo systemctl start odoo
```

O desde la UI: **Apps → Nakel Supplier Pricelist → Upgrade**.

## Dependencias

`__manifest__.py`:
```python
{
    'name': 'Nakel Supplier Pricelist',
    'version': '18.0.1.2.0',
    'depends': ['base', 'product', 'purchase', 'mail'],
    ...
}
```

Externamente: requiere el AI service corriendo en la URL configurada.
