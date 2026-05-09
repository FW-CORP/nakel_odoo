# Git: GitHub (FW-CORP) vs Forgejo (vault privado)

Este documento describe el flujo con **dos remotos** sobre el mismo clon del directorio de trabajo **`cursor_files/nakel`** (vault NAKEL en disco).

| Remoto | URL típica | Rol |
|--------|------------|-----|
| **`origin`** | `git@github.com:FW-CORP/nakel_odoo.git` | **Público / equipo FW-CORP**: árbol **acotado** (addons, qweb, tools, docs del paquete Odoo). Rama `main` es la que se comparte y se clona para trabajo corporativo. |
| **`forgejo-odoo`** | `ssh://git@forgejo.int.fwhq.com.ar/klap/nakel_odoo.git` | **Instancia interna**: mismo **contenido que debería tener** `origin` (paquete Odoo). En muchos despliegues es un **Mirror** de GitHub: **solo lectura** desde `git push`; la actualización la hace Forgejo al sincronizar desde el remoto configurado. |
| **`forgejo`** | `ssh://git@forgejo.int.fwhq.com.ar/klap/cursor_nakel.git` | **Privado**: backup del **vault completo** (monorepo ancho). Ahí sí suele poderse **empujar** con `git push` si el repo no es mirror. |

> Alta del remoto del paquete en Forgejo: `git remote add forgejo-odoo ssh://git@forgejo.int.fwhq.com.ar/klap/nakel_odoo.git`

### Por qué `nakel_odoo` en Forgejo sigue viéndose como monorepo

Si el proyecto en Forgejo está marcado como **Mirror** (`Mirror Repository`), **no acepta `git push`**: verás errores del tipo *«Mirror Repository … is read-only»*.

En ese caso el árbol que muestra la web **no lo fijás con push local**, sino con:

1. **Origen del mirror** en la administración de Forgejo: debe ser **`https://github.com/FW-CORP/nakel_odoo.git`** (o el SSH equivalente), no un remoto viejo ni otro repo.
2. **Sincronización**: forzar *sync* / esperar el intervalo de mirror para que Forgejo traiga el **`main` actual de GitHub** (ya **acotado**, sin el monorepo del accidente).
3. Si el mirror se creó cuando GitHub tenía aún el monorepo, puede haber **historial/cache** raro hasta que el próximo sync traiga los commits nuevos; un admin puede revisar la URL de origen y los logs del mirror.

Si necesitás un repo **escribible** en Forgejo con el mismo árbol que GitHub, la opción es crear un repo **normal** (no mirror) y hacer `git push` desde `main`, o clonar desde GitHub y usar ese como fuente.

> **Web:** [Forgejo `klap/nakel_odoo` (rama `main`)](https://forgejo.int.fwhq.com.ar/klap/nakel_odoo/src/branch/main)

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

## Repo Git anidado bajo `nakel_odoo/` (resuelto en disco)

Antes existía un **`nakel_odoo/.git`** separado (mismo `origin` que el repo raíz), lo que hacía un **repo dentro del repo**. Eso ya no aplica: el directorio **`nakel_odoo/.git`** se movió a **`.git_embedded_backup/nakel_odoo.git`** (carpeta ignorada por git en la raíz del vault) para poder recuperar historial local con `git --git-dir=...` si hiciera falta.

- **Canónico:** un solo repositorio en **`/media/klap/raid5/cursor_files/nakel/.git`**. Trabajar con `git status`, `commit` y `push` **solo desde la raíz del vault**.
- **`nakel_odoo/nakel_odoo/`** no es otro repo (no tiene `.git`); es un **árbol duplicado** parcial bajo `nakel_odoo/` que el monorepo ya versiona. No mezclarlo con un segundo `.git`; si en el futuro se unifica o elimina esa duplicación, hacerlo con un cambio grande y consciente (muchos paths en `docs/` y `tools/` lo referencian).

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
