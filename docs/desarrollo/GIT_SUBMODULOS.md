# Submódulos en `nakel_odoo`

En [FW-CORP/nakel_odoo](https://github.com/FW-CORP/nakel_odoo) hay carpetas que apuntan a **otros repositorios** (modo git `160000`). GitHub solo muestra el enlace clicable si la ruta está declarada en **`.gitmodules`**. Si falta esa entrada, la web muestra un “archivo” vacío y el click no lleva al repo hijo.

## Submódulos activos (en `main`)

| Carpeta | Repositorio | Uso |
|---------|-------------|-----|
| `usuarios/` | [Nakel-ACL-PERMS](https://github.com/FW-CORP/Nakel-ACL-PERMS) | Permisos / ACL |
| `arca-retenciones/` | [arca-retenciones](https://github.com/FW-CORP/arca-retenciones) | Herramientas fiscales ARCA |
| `inventario/` | [Filtro_olas_nakel](https://github.com/FW-CORP/Filtro_olas_nakel) | Filtros / olas inventario |
| `nakel_scripts/` | [nakel_scripts](https://github.com/FW-CORP/nakel_scripts) | Scripts operativos |
| `etiquetas-de-precios/` | [etiquetas-de-precios](https://github.com/FW-CORP/etiquetas-de-precios) | QWeb / etiquetas 2×7 |

Tras clonar:

```bash
git submodule update --init --recursive
```

## `nakel_picking`: una sola copia en el paquete

El módulo Odoo **`nakel_picking`** vive en el árbol del paquete, no como submódulo en la raíz:

- **Canónico:** `addons/nakel_picking/` (lo que instala Odoo y lo que describe el README).
- **No usar:** entrada `nakel_picking/` en la raíz del repo (era un gitlink al repo [FW-CORP/nakel_picking](https://github.com/FW-CORP/nakel_picking) y duplicaba el mismo código).

El repo independiente `FW-CORP/nakel_picking` puede seguir existiendo como histórico o mirror; el despliegue desde este monorepo debe tomar **`addons/nakel_picking`**.

La copia duplicada `nakel_odoo/addons/nakel_picking/` fue **eliminada** del índice git (mismo contenido que `addons/nakel_picking/`). Cualquier cambio al módulo va solo ahí.

## Clon local opcional en `nakel_picking/`

Si en disco queda una carpeta `nakel_picking/` con su propio `.git` (clon del repo viejo), está en `.gitignore` del padre para no volver a commitearla por error.

## Remotos y mirror Forgejo

Ver [`GIT_REMOTES_GITHUB_FORGEJO.md`](GIT_REMOTES_GITHUB_FORGEJO.md).
