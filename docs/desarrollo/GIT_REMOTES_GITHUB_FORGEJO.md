# Git: GitHub (FW-CORP) vs Forgejo (vault privado)

Este documento describe el flujo con **dos remotos** sobre el mismo clon del directorio de trabajo **`cursor_files/nakel`** (vault NAKEL en disco).

| Remoto | URL típica | Rol |
|--------|------------|-----|
| **`origin`** | `git@github.com:FW-CORP/nakel_odoo.git` | **Público / equipo FW-CORP**: árbol **acotado** (addons, qweb, tools, docs del paquete Odoo). Rama `main` es la que se comparte y se clona para trabajo corporativo. |
| **`forgejo`** | `ssh://git@forgejo.int.fwhq.com.ar/klap/cursor_nakel.git` | **Privado**: espejo del **vault completo** (monorepo con `ventas/`, `inventario/`, submódulos, scripts varios, etc.) cuando hace falta backup o trabajo personal sin subir todo a GitHub. |

> Los nombres de remoto (`origin`, `forgejo`) se dan de alta con `git remote add`. Si ya existen, `git remote -v` los lista.

---

## Estado habitual de las ramas (referencia)

- **`main` (local)** suele trackear **`origin/main`**: historial **reducido** tras limpiar el accidente de monorepo en el repo público.
- **`backup/monorepo-accidental-2026-05-09`** (u otra rama que elijas como “vault”): puntero al historial con **árbol ancho** (~decenas de carpetas en la raíz), útil para **Forgejo**.
- En **Forgejo**, la rama **`main`** puede estar **forzada** a esa rama ancha, de modo que el remoto privado refleje “todo el vault commiteado”, no el mismo `main` que GitHub.

Comprobar a qué apunta cada remoto:

```bash
git fetch origin
git fetch forgejo
git log --oneline -1 origin/main
git log --oneline -1 forgejo/main
```

---

## Comandos frecuentes

### Trabajo diario solo en GitHub

```bash
git checkout main
git pull origin main
# ... commits ...
git push origin main
```

### Actualizar solo el backup privado (Forgejo) con la rama “vault completa”

Tras commitear en la rama ancha (ej. `backup/monorepo-accidental-2026-05-09`):

```bash
git push forgejo backup/monorepo-accidental-2026-05-09:main
```

Si querés **reemplazar** por completo `main` en Forgejo por esa rama (historial incluido):

```bash
git push forgejo backup/monorepo-accidental-2026-05-09:main --force-with-lease
```

Usar `--force-with-lease` solo si estás seguro de que nadie más actualizó Forgejo en paralelo.

### Publicar en **ambos** remotos

Depende de qué rama corresponda a cada política:

- **GitHub**: casi siempre `main` acotado → `git push origin main`.
- **Forgejo**: rama vault → `git push forgejo <rama-vault>:main` (o `main` si unificás flujos).

Ejemplo secuencial:

```bash
git push origin main
git push forgejo backup/monorepo-accidental-2026-05-09:main
```

### Mantener `main` local trackeando GitHub (recomendado)

Si al hacer push a Forgejo usaste `git push -u forgejo main`, Git puede haber dejado `main` trackeando Forgejo. Para volver a GitHub como upstream por defecto:

```bash
git branch -u origin/main main
```

---

## Qué entra en Git y qué no (en ambos remotos)

El **mismo** `.gitignore` aplica a todos los commits: no se versionan por defecto cosas como `mssql/`, `backups/`, `db_mssql/`, `.env`, muchos `*.xlsx` / `*.csv`, etc. Eso vale para **GitHub y Forgejo**: el “vault completo en disco” **no** es idéntico al “vault commiteado”.

Para incluir algo ignorado **solo** en el remoto privado, opciones:

- `git add -f ruta` (con cuidado: no forzar secretos), o
- relajar reglas en una rama dedicada (evaluar riesgo).

---

## Repo Git anidado bajo `nakel_odoo/`

Puede existir un `.git` dentro de `nakel_odoo/` apuntando al mismo u otro remoto. Evitá tener **dos** clones del mismo `origin` sin acuerdo: un solo remoto “canónico” en la raíz del vault reduce confusiones. Si migrás todo a la raíz, eliminá o reconfigurá el repo anidado según proceda.

---

## Referencia cruzada

- README raíz del paquete Odoo: `README.md` (sección remotes).
- Historial del accidente monorepo / limpieza: commits y rama `backup/monorepo-accidental-2026-05-09` en este mismo repositorio.

### Bajar commits nuevos de `main` (GitHub) al vault en Forgejo

Si `forgejo/main` sigue la rama ancha y en `origin/main` entraron commits (p. ej. solo docs), incorporalos ahí y volvé a empujar:

```bash
git checkout backup/monorepo-accidental-2026-05-09
git merge origin/main
# resolver conflictos si aparecen
git push forgejo backup/monorepo-accidental-2026-05-09:main
git checkout main
```
