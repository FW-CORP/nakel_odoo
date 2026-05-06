# Error de acceso: Cajeros no pueden descargar PDF (account.payment)

**Fecha:** 2025-02-19  
**Base:** master_18  
**Síntoma:** Al intentar descargar el PDF (p. ej. "Venta diaria" en cierre de caja), el cajero recibe:

- **Error de acceso**
- *No puede acceder a los registros 'Pagos' (account.payment).*
- *Esta operación está permitida para los siguientes grupos:*
  - Contabilidad/Facturación
  - Contabilidad/Mostrar funciones de contabilidad: solo lectura

---

## Causa

En Odoo, el modelo **account.payment** (Pagos) tiene reglas de acceso (`ir.model.access`) que permiten solo a usuarios que pertenezcan a:

1. **Contabilidad / Facturación** (Accounting / Invoicing) — acceso completo a pagos.
2. **Contabilidad / Mostrar funciones de contabilidad: solo lectura** (Accounting / Read-only) — solo lectura.

Los usuarios **cajeros** (Point of Sale / User) normalmente **no** tienen ningún grupo de Contabilidad. La acción de descargar el informe/PDF de "Venta diaria" (o similar) en el cierre de caja **lee registros de Pagos** (`account.payment`), por eso Odoo bloquea el acceso.

---

## Solución recomendada

Asignar a los **cajeros** el grupo de **solo lectura** de Contabilidad:

- **Contabilidad / Mostrar funciones de contabilidad: solo lectura**  
  (en inglés: **Accounting / Read-only**)

Ventajas:

- Permite **leer** registros de Pagos y así poder generar/descargar el PDF.
- **No** da permisos de crear, modificar o eliminar pagos ni otras funciones de contabilidad sensibles.
- Es el mínimo privilegio necesario para completar el proceso de cierre y descarga del informe.

No es recomendable dar **Contabilidad/Facturación** a cajeros salvo que realmente deban crear o modificar pagos/facturación.

---

## Cómo aplicar en master_18

### Opción A: Desde la interfaz de Odoo

1. Ir a **Configuración → Usuarios y compañías → Usuarios**.
2. Abrir cada usuario **cajero** (Point of Sale / User).
3. En **Otros**, marcar:
   - **Contabilidad** → **Mostrar funciones de contabilidad: solo lectura**.
4. Guardar.
5. El cajero debe **cerrar sesión y volver a iniciar** para que los permisos se recalculen.

### Opción B: Script automático

En este directorio está el script:

- **`asignar_permisos_account_readonly_cajeros_master18.py`**

Uso:

```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS
# Solo listar cajeros y qué se haría (dry-run)
python3 asignar_permisos_account_readonly_cajeros_master18.py

# Aplicar el grupo "Accounting / Read-only" a todos los cajeros que no lo tengan
python3 asignar_permisos_account_readonly_cajeros_master18.py --apply
```

Requisitos: `config_nakel` con `ODOO_CONFIG_MASTER18` (url, db, username, password).

---

## Verificación

1. Entrar como un usuario cajero en master_18.
2. Ir a Punto de venta → Cerrar caja / flujo donde se descarga el PDF (p. ej. "Venta diaria").
3. Descargar el PDF.
4. No debe aparecer el error de acceso a `account.payment`.

Si el error continúa, el usuario debe **cerrar sesión por completo** y volver a iniciar sesión (caché de permisos).

---

## Referencias en la documentación

- **README.md** (usuarios): conceptos de grupos y `ir.model.access`.
- **ANALISIS_ERROR_FACTURAR_ENCARGADOS.md**: mismo patrón de error por permisos (modelo distinto: `stock.picking`).
- Scripts de asignación de grupos en **PERMISOS/** (ej. `asignar_permisos_ajustes_inventario_fabiana_master18.py`) como referencia de conexión a master_18.

---

**Última actualización:** 2025-02-19
