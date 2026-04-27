# Error de acceso: Cajeros no pueden crear “Asiento contable” (`account.move`)

**Fecha:** 2025-02-19  
**Base:** master_18  
**Síntoma:** Al intentar **retirar dinero de la caja** (caja/POS), el usuario cajero ve un error tipo:

- **No puede crear registros:** `Asiento contable` (`account.move`)

El mensaje suele indicar que la operación está permitida para grupos como **Contabilidad/Facturación** (y/o otros según configuración).

---

## Causa

En Odoo, cuando se retira dinero o se realiza una conciliación/cierre de caja, se generan movimientos contables.  
Para eso, el backend necesita **crear** registros en el modelo **`account.move`**.

Si el cajero no pertenece al grupo **Contabilidad/Facturación** (Accounting / Invoicing), Odoo bloquea la creación y aparece el error.

---

## Solución recomendada (mínimo privilegio)

Asignar a los cajeros el grupo:

- **Contabilidad/Facturación** (**Accounting / Invoicing**)

Con este grupo el cajero puede crear los asientos necesarios para el retiro de dinero.

> Si tu política requiere aún más restricción (solo lectura), habría que validar qué plantillas/reglas usa tu flujo. En la práctica, para este error, el grupo Invoicing es el que habilita `account.move` en la creación.

---

## Cómo aplicar en master_18

### Opción A: script (recomendado)

Script:

- `PERMISOS/asignar_permisos_account_invoicing_cajeros_master18.py`

Uso:

```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS

# dry-run
python3 asignar_permisos_account_invoicing_cajeros_master18.py

# aplicar
python3 asignar_permisos_account_invoicing_cajeros_master18.py --apply
```

### Opción B: manual

En Odoo:
1. Ir a **Configuración → Usuarios**
2. Abrir el usuario **cajero**
3. Marcar en grupos:
   - **Contabilidad → Facturación / Invoicing** (Accounting / Invoicing)
4. El usuario debe **cerrar sesión** y **volver a iniciar**.

---

## Verificación

1. Entrar como cajero.
2. Intentar **retirar dinero de caja**.
3. Confirmar que ya se crea el `account.move` y que el retiro finaliza sin el error.

---

**Última actualización:** 2025-02-19

