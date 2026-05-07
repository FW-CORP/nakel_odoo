# Eliminar archivos con credenciales del historial Git

**Ejecutar desde la raíz del repo nakel_picking.**

## Paso 1: Quitar del tracking y añadir a .gitignore

```bash
cd /media/klap/raid5/proyecto-nakel/nakel/inventario/nakel_picking

# Quitar del índice (los archivos siguen en disco)
git rm --cached diagnosticar_bultos.py explorar_master18_bultos.py analizar_odoo18_api.py

# .gitignore ya los incluye
git add .gitignore
```

## Paso 2: Eliminar del historial (reescribir commits)

```bash
# Elimina estos archivos de TODOS los commits pasados
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch diagnosticar_bultos.py explorar_master18_bultos.py analizar_odoo18_api.py' \
  --prune-empty --tag-name-filter cat -- --all
```

## Paso 3: Limpiar refs y recolectar basura

```bash
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

## Paso 4: Force push (reescribe el remoto)

```bash
git push origin master --force
```

⚠️ **Importante:** Si alguien más tiene el repo clonado, deberá hacer `git fetch origin` y `git reset --hard origin/master` (o re-clonar). El historial cambia.

## Paso 5: Rotar credenciales

Aunque las quites del repo, **cambia las contraseñas** en Odoo y config_nakel.py, ya que pudieron quedar en cachés, forks o clones.
