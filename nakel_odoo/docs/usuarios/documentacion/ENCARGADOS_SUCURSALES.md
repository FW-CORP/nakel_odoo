# 👥 Encargados de Sucursales - Permisos y Configuración

Documentación específica sobre los encargados de sucursales y sus permisos en Odoo.

## Política de productos (2026-04)

Los usuarios de sucursal que forman parte de los grupos **Inventario → Encargados Belgrano 1–4** **no** deben tener el grupo **Product Creation** ni otro acceso de **create/write** al maestro de productos (`product.template` / `product.product`): códigos de barras, nombres y atributos se gestionan **solo desde Central**. Siguen operando inventario (traslados, stock) con **Inventory / User** y el grupo **Encargados Belgrano N** correspondiente.

### Alcance del script de alineación

El script `scripts/asignar_permisos_modificar_productos_encargados.py` aplica a **todos los miembros activos** de los cuatro grupos **Encargados Belgrano 1 … 4** (incluye encargados `@nakel.ar`, cajeros `@gmail.com` u otros que estén dados de alta en esos grupos), **excepto**:

| Login | Motivo |
|--------|--------|
| `supervision@nakel.ar` | Supervisora; permisos amplios y/o inventario vía otros grupos; **no** se modifican sus grupos con este script. |

Para un solo login (encargados “oficiales” por sucursal): `PERMISOS/corregir_permisos_encargado_master18.py --login … [--master-dev]` (retira Product Creation solo si el login está en el mapa de encargados Belgrano del script).

### Inventario → Reportes (menú)

En `master_dev`, el menú **Inventario → Reporting/Reportes** está restringido por defecto a **Inventory / Administrator** (res.groups id 51). Para habilitarlo a los **Encargados Belgrano 1–4** sin darles ese rol amplio, usar:

```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS
python3 habilitar_menu_reportes_inventario_encargados_master_dev.py        # dry-run
python3 habilitar_menu_reportes_inventario_encargados_master_dev.py --apply
```

Notas:
- Este cambio es de **visibilidad de menú** (`ir.ui.menu.groups_id`). Si un reporte concreto lee modelos sin permiso, puede aparecer `AccessError`.
- El submenú **Locations** sigue restringido por grupos técnicos (propios de multiubicación/owners); habilitarlo es una decisión aparte.

### Entornos Odoo (referencia 2026-04)

- **Productivo / scripts XML-RPC habituales:** base **`master_dev`** en `nakel.net.ar` (credenciales en `config_nakel.py`).
- **Desarrollo:** `dev.nakel.net.ar`, base típica **`master_test`** — credenciales en `.env` del entorno; **no** está cableado en este script por defecto; cuando haga falta alinear permisos allí, reutilizar la misma lógica o parametrizar config.
- La base histórica **master_18** ya **no** se usa; la documentación nueva no la contempla como destino.

---

## 📋 Usuarios Encargados

### Belgrano 1

**Usuario:** Manuel Claudia Isabel  
**Login:** `golosinasbelgrano1@nakel.ar`  
**ID Odoo:** 96  
**Cajas:** C1, C2

**Permisos requeridos:**
- Acceso a inventario de sucursal (traslados, stock)
- **Sin** modificación del maestro de productos en sucursal

**Grupos (referencia):**
- Encargados Belgrano 1 + Inventory / User (y otros que defina negocio; **sin** Product Creation)

---

### Belgrano 2

**Usuario:** Varas Adrian Marcelo  
**Login:** `golosinasbelgrano2@nakel.ar`  
**ID Odoo:** 102  
**Cajas:** C1, C2

**Permisos requeridos:**
- Acceso a inventario de sucursal
- **Sin** modificación del maestro de productos en sucursal

**Grupos (referencia):**
- Encargados Belgrano 2 + Inventory / User (**sin** Product Creation)

---

### Belgrano 3

**Usuario:** Robles Angel Jose  
**Login:** `golosinasbelgrano3@nakel.ar`  
**ID Odoo:** 100  
**Cajas:** C1, C2

**Permisos requeridos:**
- Acceso a inventario de sucursal
- **Sin** modificación del maestro de productos en sucursal

**Grupos (referencia):**
- Encargados Belgrano 3 + Inventory / User (**sin** Product Creation)

---

### Belgrano 4

**Usuario:** Ramos Nancy  
**Login:** `golosinasbelgrano4@nakel.ar`  
**ID Odoo:** 99  
**Cajas:** C1

**Permisos requeridos:**
- Acceso a inventario de sucursal
- **Sin** modificación del maestro de productos en sucursal

**Grupos (referencia):**
- Encargados Belgrano 4 + Inventory / User (**sin** Product Creation)

---

## 🔐 Grupo estándar: Product Creation (histórico)

**Nombre completo:** Product Creation (Extra Rights)

**Qué otorgaba:** lectura, escritura y creación en productos (incluido barcode).

**Estado actual:** **No** se asigna a encargados Belgrano. Si un usuario aún lo tiene por configuración antigua, retirarlo (scripts arriba o manualmente en Usuarios).

---

## 🛠️ Scripts

**Alinear en `master_dev` (todos los miembros de Encargados Belgrano 1–4, menos `supervision@nakel.ar`):**

```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/scripts
python3 asignar_permisos_modificar_productos_encargados.py --verificar-solo
python3 asignar_permisos_modificar_productos_encargados.py --dry-run
python3 asignar_permisos_modificar_productos_encargados.py
```

**Por un solo usuario encargado (mapa interno del script + `--master-dev`):**

```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS
python3 corregir_permisos_encargado_master18.py --login golosinasbelgrano1@nakel.ar --master-dev
```

---

## 📝 Historial de Cambios

### 2026-04-18
- Política: miembros de Encargados Belgrano 1–4 **sin** Product Creation (excepto supervisora excluida del script).
- `asignar_permisos_modificar_productos_encargados.py`: alcance dinámico por grupo + exclusión `supervision@nakel.ar`; resolución de grupos por nombre.
- Entornos: referencia `master_dev`; `master_test` en `dev.nakel.net.ar` y credenciales en `.env` solo como referencia futura (sin scripts obligatorios).
- **master_18** deprecado; no contemplar como destino en procedimientos nuevos.

### 2025-12-27
- Documentación inicial de encargados; en su momento se usó Product Creation para ayuda con barcodes en sucursal (revocado por negocio).

---

**Última actualización:** 2026-04-18 (alcance script + entornos)
