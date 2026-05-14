#!/usr/bin/env python3
"""
Sincroniza quantity → qty_done y marca picked en líneas, para todos los pickings
pendientes ligados a una ola por `batch_id` o `nakel_wave_batch_id` (misma lógica
operativa que el botón `nakel_sync_ola` / `action_nakel_sync_ola_full`).

**No incluye OUT** (`CEN/OUT/…` / tipo `sequence_code` = OUT): mismo criterio que el botón tras 18.0.1.0.2.

Uso (variables `ODOO_MASTER_DEV_*`; el script carga líneas `KEY=VALUE` desde `.env`):

  python3 nakel_odoo/tools/inventario/sync_qty_done_nakel_wave_batch_xmlrpc.py --batch-id 149

Opcional: `--env-file /ruta/.env` (por defecto intenta el `.env` en la raíz del repo).

Las variables `ODOO_MASTER_DEV_*` suelen apuntar a **`https://nakel.net.ar`** con BD **`master_dev`** (no confundir con `dev.nakel.net.ar`).

No valida albaranes: solo alinea qty_done/picked para que **Validar** refleje lo reservado.
"""
from __future__ import annotations

import argparse
import os
import sys
import xmlrpc.client
from pathlib import Path


def _load_env_file(path: str) -> None:
    """Carga KEY=VALUE desde un .env (ignora líneas sin '=' y comentarios)."""
    if not path or not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)


def _default_env_path() -> Path:
    return Path(__file__).resolve().parents[3] / ".env"


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _split_out_pickings(
    models, db: str, uid: int, pwd: str, pick_ids: list[int]
) -> tuple[list[int], list[tuple[int, str]]]:
    """Devuelve (ids sin OUT, lista de (id, nombre) excluidos como OUT)."""
    if not pick_ids:
        return [], []
    rows = models.execute_kw(
        db,
        uid,
        pwd,
        "stock.picking",
        "read",
        [pick_ids],
        {"fields": ["id", "name", "picking_type_id"]},
    )
    type_ids = list({r["picking_type_id"][0] for r in rows if r.get("picking_type_id")})
    code_by_tid: dict[int, str] = {}
    if type_ids:
        types = models.execute_kw(
            db,
            uid,
            pwd,
            "stock.picking.type",
            "read",
            [type_ids],
            {"fields": ["id", "sequence_code"]},
        )
        for t in types:
            code_by_tid[int(t["id"])] = (t.get("sequence_code") or "").strip()
    kept: list[int] = []
    skipped: list[tuple[int, str]] = []
    for r in rows:
        pid = int(r["id"])
        name = (r.get("name") or "").strip()
        tid = r["picking_type_id"][0] if r.get("picking_type_id") else None
        seq = code_by_tid.get(int(tid), "") if tid else ""
        is_out = seq == "OUT" or name.startswith("CEN/OUT/")
        if is_out:
            skipped.append((pid, name or "?"))
        else:
            kept.append(pid)
    return kept, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch-id", type=int, required=True, help="id de stock.picking.batch (ej. 149 = WAVE/00143)")
    ap.add_argument("--dry-run", action="store_true", help="Solo lista pickings, no escribe")
    ap.add_argument(
        "--env-file",
        default="",
        help="Ruta a .env con ODOO_MASTER_DEV_* (vacío = raíz repo o ./.env)",
    )
    args = ap.parse_args()

    env_path = (args.env_file or "").strip()
    if env_path:
        _load_env_file(env_path)
    else:
        p = _default_env_path()
        if p.is_file():
            _load_env_file(str(p))
        elif Path(".env").is_file():
            _load_env_file(".env")

    url = _env("ODOO_MASTER_DEV_URL")
    db = _env("ODOO_MASTER_DEV_DB")
    user = _env("ODOO_MASTER_DEV_USERNAME")
    pwd = _env("ODOO_MASTER_DEV_PASSWORD")
    if not all([url, db, user, pwd]):
        print(
            "Faltan variables ODOO_MASTER_DEV_URL, ODOO_MASTER_DEV_DB, "
            "ODOO_MASTER_DEV_USERNAME, ODOO_MASTER_DEV_PASSWORD en el entorno.",
            file=sys.stderr,
        )
        return 1

    common = xmlrpc.client.ServerProxy(f"{url.rstrip('/')}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, user, pwd, {})
    if not uid:
        print("Autenticación Odoo fallida.", file=sys.stderr)
        return 1
    models = xmlrpc.client.ServerProxy(f"{url.rstrip('/')}/xmlrpc/2/object", allow_none=True)

    bid = args.batch_id
    pick_ids: list[int] = models.execute_kw(
        db,
        uid,
        pwd,
        "stock.picking",
        "search",
        [
            [
                "|",
                ("batch_id", "=", bid),
                ("nakel_wave_batch_id", "=", bid),
                ("state", "not in", ("done", "cancel")),
            ]
        ],
    )
    if not pick_ids:
        print(f"No hay pickings pendientes para batch_id/nakel_wave_batch_id = {bid}.")
        return 0

    kept_ids, skipped_out = _split_out_pickings(models, db, int(uid), pwd, pick_ids)
    names = models.execute_kw(db, uid, pwd, "stock.picking", "read", [pick_ids], {"fields": ["id", "name", "state"]})
    by_id = {int(r["id"]): r for r in names}
    print(f"Pickings en dominio: {len(pick_ids)} (se sincronizan {len(kept_ids)}, OUT excluidos {len(skipped_out)})")
    for pid, pname in sorted(skipped_out, key=lambda x: x[1]):
        print(f"  (excluido OUT) {pname}  id={pid}")
    for pid in sorted(kept_ids, key=lambda i: (by_id.get(i) or {}).get("name") or ""):
        r = by_id.get(pid) or {}
        print(f"  {r.get('name')}  ({r.get('state')})")

    if not kept_ids:
        print("Nada que sincronizar tras excluir OUT.")
        if args.dry_run:
            print("Dry-run: no se escribió nada.")
        return 0

    if args.dry_run:
        print("Dry-run: no se escribió nada.")
        return 0

    picked_updates = 0
    for pid in kept_ids:
        models.execute_kw(db, uid, pwd, "stock.picking", "action_sync_qty_done_from_quantity", [[pid]])
        line_ids = models.execute_kw(
            db,
            uid,
            pwd,
            "stock.move.line",
            "search",
            [[("picking_id", "=", pid), ("quantity", ">", 0), ("picked", "=", False)]],
        )
        if line_ids:
            models.execute_kw(db, uid, pwd, "stock.move.line", "write", [line_ids, {"picked": True}])
            picked_updates += len(line_ids)

    print(
        f"OK: ejecutado action_sync_qty_done_from_quantity por picking; "
        f"líneas marcadas picked: {picked_updates}. "
        f"Revisá en Odoo y validá los albaranes cuando corresponda."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
