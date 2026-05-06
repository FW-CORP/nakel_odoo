#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comparar módulos instalados entre dos entornos Odoo (master_dev vs staging).

Uso:
  python3 tools/compare_installed_modules.py --out /media/klap/raid5/cursor_files/reportes/compare_modules_master_dev_vs_staging.csv

Por defecto compara:
  - A: producción master_dev (NAKEL_TARGET vacío)
  - B: staging sg_dev1 (NAKEL_TARGET=staging_sg_dev1)

Devuelve:
  - CSV con módulos que están en un entorno y no en el otro
  - diferencias de version instalada (installed_version) cuando existe en ambos
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import xmlrpc.client
from dataclasses import dataclass
from typing import Any


sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    import config_nakel
except Exception as e:  # pragma: no cover
    raise SystemExit(f"No se pudo importar config_nakel: {e}")


@dataclass(frozen=True)
class OdooConn:
    url: str
    db: str
    uid: int
    password: str
    models: Any


def connect(cfg: dict) -> OdooConn:
    url = str(cfg["url"]).rstrip("/")
    db = str(cfg["db"])
    username = str(cfg["username"])
    password = str(cfg["password"])
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise SystemExit(f"Autenticacion Odoo fallida: url={url} db={db} user={username}")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    return OdooConn(url=url, db=db, uid=int(uid), password=password, models=models)


def search_read(c: OdooConn, model: str, domain: list, *, fields: list[str], limit: int = 0, offset: int = 0, order: str | None = None) -> list[dict]:
    kwargs: dict[str, Any] = {"fields": fields, "offset": int(offset)}
    if limit:
        kwargs["limit"] = int(limit)
    if order:
        kwargs["order"] = order
    return c.models.execute_kw(c.db, c.uid, c.password, model, "search_read", [domain], kwargs)


def fetch_installed_modules(c: OdooConn) -> dict[str, dict[str, str]]:
    """
    Retorna dict por nombre técnico del módulo:
      { 'sale': {'installed_version': '18.0.1.0', 'latest_version': '18.0.1.1', 'state': 'installed'} }
    """
    out: dict[str, dict[str, str]] = {}
    fields = ["name", "state", "installed_version", "latest_version"]
    domain = [("state", "in", ["installed", "to upgrade", "to remove", "to install"])]
    offset = 0
    page = 200
    while True:
        rows = search_read(c, "ir.module.module", domain, fields=fields, limit=page, offset=offset, order="name asc")
        if not rows:
            break
        for r in rows:
            name = str(r.get("name") or "").strip()
            if not name:
                continue
            out[name] = {
                "state": str(r.get("state") or ""),
                "installed_version": str(r.get("installed_version") or ""),
                "latest_version": str(r.get("latest_version") or ""),
            }
        offset += len(rows)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default="/media/klap/raid5/cursor_files/reportes/compare_modules_master_dev_vs_staging.csv")
    args = ap.parse_args()

    # A = master_dev (producción)
    os.environ.pop("NAKEL_TARGET", None)
    cfg_a = config_nakel.ODOO_CONFIG_MASTER_DEV.copy()
    a = connect(cfg_a)
    print(f"A OK: {a.url} db={a.db}")

    # B = staging sg_dev1
    os.environ["NAKEL_TARGET"] = "staging_sg_dev1"
    # recargar selector target
    import importlib

    importlib.reload(config_nakel)
    cfg_b = config_nakel.ODOO_CONFIG_MASTER_DEV.copy()
    b = connect(cfg_b)
    print(f"B OK: {b.url} db={b.db}")

    mods_a = fetch_installed_modules(a)
    mods_b = fetch_installed_modules(b)

    names_a = set(mods_a.keys())
    names_b = set(mods_b.keys())
    only_a = sorted(names_a - names_b)
    only_b = sorted(names_b - names_a)
    both = sorted(names_a & names_b)

    diff_version = []
    for n in both:
        va = (mods_a[n].get("installed_version") or "").strip()
        vb = (mods_b[n].get("installed_version") or "").strip()
        if va != vb:
            diff_version.append(n)

    out_path = args.out
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "module",
                "status",
                "A_state",
                "A_installed_version",
                "B_state",
                "B_installed_version",
            ],
        )
        w.writeheader()
        for n in only_a:
            w.writerow(
                {
                    "module": n,
                    "status": "ONLY_IN_A(master_dev)",
                    "A_state": mods_a[n]["state"],
                    "A_installed_version": mods_a[n]["installed_version"],
                    "B_state": "",
                    "B_installed_version": "",
                }
            )
        for n in only_b:
            w.writerow(
                {
                    "module": n,
                    "status": "ONLY_IN_B(staging_sg_dev1)",
                    "A_state": "",
                    "A_installed_version": "",
                    "B_state": mods_b[n]["state"],
                    "B_installed_version": mods_b[n]["installed_version"],
                }
            )
        for n in diff_version:
            w.writerow(
                {
                    "module": n,
                    "status": "DIFF_INSTALLED_VERSION",
                    "A_state": mods_a[n]["state"],
                    "A_installed_version": mods_a[n]["installed_version"],
                    "B_state": mods_b[n]["state"],
                    "B_installed_version": mods_b[n]["installed_version"],
                }
            )

    print("Resumen:")
    print(f"- A modules: {len(mods_a)}")
    print(f"- B modules: {len(mods_b)}")
    print(f"- only A: {len(only_a)}")
    print(f"- only B: {len(only_b)}")
    print(f"- diff installed_version: {len(diff_version)}")
    print(f"CSV: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

