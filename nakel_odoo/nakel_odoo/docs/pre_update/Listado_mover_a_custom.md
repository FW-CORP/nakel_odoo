# Addons en ruta estándar de Odoo que conviene mover a `custom-addons`

**Criterio:** módulos bajo  
`/usr/lib/python3/dist-packages/odoo/addons/<nombre>/__manifest__.py`  
cuyo `__manifest__.py` **no** figura en el paquete Debian **`odoo`** instalado (`dpkg -L odoo`).  
Son carpetas **huérfanas respecto al paquete**: se mezclan con el core y pueden **perderse o complicar upgrades** si no están en un `addons_path` separado.

**Fecha de relevamiento:** 2026-04-28 (consulta en servidor).

## Lista (7 módulos)

| Módulo | Notas |
|--------|--------|
| `droggol_theme_common` | Tema / utilidades Theme Prime (terceros). |
| `theme_prime` | Tema storefront (terceros). |
| `modulo_rg5329` | Custom / localización negocio. |
| `nakel_fix_pick` | Custom Nakel. |
| `nakel_picking` | Custom Nakel. |
| `nakel_wave_picking_link` | Custom Nakel. |
| `purchase_flete_markup` | Custom (compras / markup). |

## Qué no incluye esta lista

- Repos tipo **OCA** que son un solo clon con **submódulos** bajo una carpeta padre sin `__manifest__.py` en la raíz (`odoo-argentina`, etc.) si están montados distinto: habría que revisar rutas reales y `addons_path`.
- Módulos que **ya** están solo en `/opt/odoo/custom-addons` (p. ej. `nakel_otel`, `nakel_sale_margin`) **no** aparecen aquí porque no están bajo `dist-packages/.../addons/`.

## Pasos recomendados (cuando decidas aplicar cambios)

1. Copiar/mover cada carpeta a `/opt/odoo/custom-addons/` (o la ruta custom acordada).
2. Asegurar que `addons_path` en `odoo.conf` incluya **primero o al menos** esa ruta según tu política (orden importa para overrides).
3. Quitar las carpetas duplicadas de `dist-packages/.../addons/` **solo después** de validar arranque y que los módulos siguen **instalados** en la BD (mismos nombres técnicos).
4. Reiniciar Odoo y actualizar módulos si hace falta.

---

*Documento informativo; no ejecuta cambios en el servidor.*
