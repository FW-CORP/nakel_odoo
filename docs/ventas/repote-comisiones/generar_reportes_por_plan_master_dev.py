#!/usr/bin/env python3
"""
Genera reportes de comisiones por plan (master_dev) y deja salidas prolijas en OUT/.

Planes esperados (master_dev):
- Plan 1: sale.commission.plan(1) 40% fijo + 60% variable prorrateado
- Plan 2: sale.commission.plan(2)
  - Vera (res.users 103): 40/60
  - resto (93,105,112): 30/70
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import xmlrpc.client
from datetime import date, datetime

sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except Exception as e:  # pragma: no cover
    raise SystemExit(f"No se pudo importar config_nakel / ODOO_CONFIG_MASTER_DEV: {e}")


HERE = os.path.dirname(os.path.abspath(__file__))
EXPORT_SCRIPT = os.path.join(HERE, "exportar_comisiones_40_60_master_dev_csv.py")
UNIFY_SCRIPT = os.path.join(HERE, "unificar_reportes_comisiones_csv.py")
XLSX_SCRIPT = os.path.join(HERE, "generar_xlsx_comisiones_unificado.py")
OUT_BASE = os.path.join(HERE, "OUT")


def connect():
    cfg = ODOO_CONFIG_MASTER_DEV
    url = cfg["url"].rstrip("/")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    uid = common.authenticate(cfg["db"], cfg["username"], cfg["password"], {})
    if not uid:
        raise SystemExit("Autenticación Odoo fallida (master_dev)")
    return models, int(uid), cfg["db"], cfg["password"], cfg


def search_read(models, db, uid, pwd, model: str, domain: list, fields: list[str], *, limit: int = 200, order: str = ""):
    kwargs = {"fields": fields, "limit": int(limit)}
    if order:
        kwargs["order"] = order
    return models.execute_kw(db, uid, pwd, model, "search_read", [domain], kwargs)


def slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "sin_nombre"


def run_cmd(argv: list[str]) -> None:
    proc = subprocess.run(argv, stdout=sys.stdout, stderr=sys.stderr)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def list_users_for_plan(models, db, uid, pwd, plan_id: int) -> list[int]:
    rows = search_read(
        models,
        db,
        uid,
        pwd,
        "sale.commission.plan.user",
        [("plan_id", "=", int(plan_id))],
        ["user_id"],
        limit=500,
        order="id asc",
    )
    out: list[int] = []
    for r in rows:
        u = r.get("user_id")
        if isinstance(u, (list, tuple)) and u:
            out.append(int(u[0]))
        elif isinstance(u, int):
            out.append(int(u))
    return sorted(set(out))


def plan_name(models, db, uid, pwd, plan_id: int) -> str:
    rows = search_read(models, db, uid, pwd, "sale.commission.plan", [("id", "=", int(plan_id))], ["name"], limit=1)
    return (rows[0].get("name") if rows else f"plan_{plan_id}") or f"plan_{plan_id}"


def export_for_users(
    *,
    plan_id: int,
    date_from: str,
    date_to: str,
    out_dir: str,
    user_ids: list[int],
    fixed_rate: float,
    variable_rate: float,
) -> None:
    if not user_ids:
        return
    run_cmd(
        [
            sys.executable,
            EXPORT_SCRIPT,
            "--plan-id",
            str(plan_id),
            "--from",
            date_from,
            "--to",
            date_to,
            "--out-dir",
            out_dir,
            "--only-users",
            ",".join(str(x) for x in user_ids),
            "--split-by-user",
            "--fixed-rate",
            str(fixed_rate),
            "--variable-rate",
            str(variable_rate),
        ]
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", default="", help="YYYY-MM-DD (inicio). Vacío = mes actual.")
    ap.add_argument("--to", dest="date_to", default="", help="YYYY-MM-DD (fin). Vacío = hoy.")
    ap.add_argument("--plans", default="1,2", help="Planes a generar (CSV). Default: 1,2")
    args = ap.parse_args()

    today = date.today()
    if args.date_from.strip() and args.date_to.strip():
        dfrom = datetime.strptime(args.date_from, "%Y-%m-%d").date()
        dto = datetime.strptime(args.date_to, "%Y-%m-%d").date()
    else:
        dfrom = today.replace(day=1)
        dto = today

    stamp = f"{dfrom.isoformat()}_{dto.isoformat()}"
    plan_ids = [int(x.strip()) for x in args.plans.split(",") if x.strip()]

    models, uid, db, pwd, cfg = connect()
    print(f"✅ Conexión OK: {cfg['url']} | db={db} | uid={uid}")
    print(f"Periodo: {dfrom.isoformat()} → {dto.isoformat()}")
    print(f"Planes: {plan_ids}")

    os.makedirs(OUT_BASE, exist_ok=True)

    for plan_id in plan_ids:
        pname = plan_name(models, db, uid, pwd, plan_id)
        pdir = os.path.join(OUT_BASE, f"plan_{plan_id}_{slug(pname)}", stamp)
        os.makedirs(pdir, exist_ok=True)

        users = list_users_for_plan(models, db, uid, pwd, plan_id)
        print(f"\n## Plan {plan_id}: {pname}")
        print(f"Usuarios asignados (sale.commission.plan.user): {users}")
        if not users:
            print("⚠️ Sin usuarios asignados; no genero reporte.")
            continue

        if plan_id == 1:
            export_for_users(
                plan_id=plan_id,
                date_from=dfrom.isoformat(),
                date_to=dto.isoformat(),
                out_dir=pdir,
                user_ids=users,
                fixed_rate=0.40,
                variable_rate=0.60,
            )
        elif plan_id == 2:
            vera_id = 103
            vera = [vera_id] if vera_id in users else []
            rest = [u for u in users if u != vera_id]
            if vera:
                export_for_users(
                    plan_id=plan_id,
                    date_from=dfrom.isoformat(),
                    date_to=dto.isoformat(),
                    out_dir=pdir,
                    user_ids=vera,
                    fixed_rate=0.40,
                    variable_rate=0.60,
                )
            if rest:
                export_for_users(
                    plan_id=plan_id,
                    date_from=dfrom.isoformat(),
                    date_to=dto.isoformat(),
                    out_dir=pdir,
                    user_ids=rest,
                    fixed_rate=0.30,
                    variable_rate=0.70,
                )
        else:
            # default (si agregan planes futuros): 40/60
            export_for_users(
                plan_id=plan_id,
                date_from=dfrom.isoformat(),
                date_to=dto.isoformat(),
                out_dir=pdir,
                user_ids=users,
                fixed_rate=0.40,
                variable_rate=0.60,
            )

        # Unificar a UNIFICADO dentro del mismo pdir
        run_cmd([sys.executable, UNIFY_SCRIPT, "--report-dir", pdir, "--stamp", stamp])

        # XLSX por plan, usando los UNIFICADO del pdir
        xlsx_out = os.path.join(pdir, f"comisiones_plan_{plan_id}_{stamp}.xlsx")
        run_cmd([sys.executable, XLSX_SCRIPT, "--report-dir", pdir, "--stamp", stamp, "--out", xlsx_out])

        print(f"✅ OUT plan {plan_id}: {pdir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

