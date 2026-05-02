# Nakel Picking - Consolidated Batch Report

Módulo para **Odoo 18** que modifica el reporte PDF de lotes de transferencias (batch/wave picking) para consolidar cantidades y mejorar la experiencia del recolector.

## Características

- **Productos consolidados** por ruta (origen → destino), producto, lote y paquete
- **Columna BULTO**: Cantidad en bultos (ej. "1.5 Bulto x40") usando `uom_po_id`, packaging o UdM de bulto
- **Códigos de barras** embebidos como imágenes base64 (sin problemas de renderización en PDF)
- **Logo y nombre de empresa** en la primera hoja
- **Evita encabezados huérfanos** al final de página
- Compatible con waves, lotes, paquetes y picking multi-ubicación

## Requisitos

- Odoo 18 (Enterprise, módulo `stock_picking_batch`)
- Python: `python-barcode[images]`

```bash
pip install python-barcode[images]
```

## Instalación

1. Copia el módulo en el `addons_path` de Odoo
2. Actualiza la lista de aplicaciones
3. Instala "Nakel Picking - Consolidated Batch Report"

## Uso

1. **Inventario → Operaciones → Lotes/Olas**
2. Abre un lote
3. **Imprimir** → El reporte consolidado reemplaza automáticamente al estándar

### Contenido del reporte

| Sección | Descripción |
|--------|-------------|
| **Página 1** | Logo, nombre empresa, resumen del lote, tabla de traslados con códigos de barras |
| **Página 2+** | Productos consolidados por ruta: Producto, Cantidad, **PLU** (imagen **Code128** del EAN/`barcode` o fallback `default_code`, escaneable), TOTAL (ordenado por categoría) |

Notas:
- La columna **Código de barras de producto** fue removida (no aportaba valor en picking).
- En el **pie** aparecen la **referencia de la wave** (`batch.name`, p. ej. `WAVE/00077`) y la **paginación** `Página X/Y` (flex: wave a la izquierda, página a la derecha).
- Se redujo el **margen superior** para aprovechar mejor la hoja.

### Columna BULTO

Muestra cuántos bultos/cajas tomar. Se calcula a partir de:

1. UdM de la línea (si ya es bulto)
2. `uom_po_id` del producto (UdM de compra)
3. `packaging_ids` (embalajes)
4. UdM tipo bulto en la categoría del producto

Configura en el producto: **Compras → UdM de compra** o **Embalajes**.

## Despliegue

```bash
./deploy.sh odoo-ct-nakel   # o el host que uses
```

Tras copiar archivos, **reinicia Odoo** para cargar el código nuevo:

```bash
sudo systemctl restart odoo
```

Luego en la UI: Aplicaciones → Nakel Picking → Actualizar.

Ver [ACTUALIZACION_CORRECTA.md](ACTUALIZACION_CORRECTA.md) para más detalles.

## Estructura

```
nakel_picking/
├── __init__.py
├── __manifest__.py
├── models/
│   └── stock_picking_batch.py   # _get_consolidated_lines(), _generate_barcode_image()
├── reports/
│   └── stock_picking_batch_report.xml
├── CHANGELOG.md
├── README.md
└── requirements.txt
```

## Licencia

LGPL-3

## Autor

**FWCORP** — [@intaky-dev](https://github.com/intaky-dev) · [@klap50](https://github.com/klap50)
