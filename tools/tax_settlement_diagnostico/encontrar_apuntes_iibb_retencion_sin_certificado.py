#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Encuentra apuntes (account.move.line) que rompen iibb_sufrido_files_values (EE):
misma rama que L1098-1104: hay payment_id, balance != 0 (redondeado 2 dec.),
y get_pos_and_number recibe un valor no string (False/None) — típico
withholding_id vacío o l10n_ar.payment.withholding.name vacío.

Solo lectura (XML-RPC).

Uso:
  python3 encontrar_apuntes_iibb_retencion_sin_certificado.py --ids 123,456,789
  python3 encontrar_apuntes_iibb_retencion_sin_certificado.py --file ids.txt

Para obtener IDs: en la lista de Odoo activar depuración, o exportar, o
ir bajando la selección por mitades hasta aislar el lote que falla y pasar
esos IDs aquí.
"""

from __future__ import annotations

import argparse
import sys
import xmlrpc.client

ROOT = "/media/klap/raid5/cursor_files"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError as e:
    raise SystemExit(f"Falta config_nakel en {ROOT}: {e}")


def connect(cfg: dict) -> tuple[xmlrpc.client.ServerProxy, int, str, str]:
    url = str(cfg["url"]).rstrip("/")
    db = str(cfg["db"])
    user = str(cfg["username"])
    pwd = str(cfg["password"])
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    uid = common.authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"Auth fallida: {url} db={db}")
    return models, int(uid), db, pwd


def bal_skip_zero(balance: float | int | None) -> bool:
    """Equivale a float_round(..., 2) == 0.0 del EE para excluir la línea."""
    if balance is None:
        return True
    try:
        return round(float(balance), 2) == 0.0
    except (TypeError, ValueError):
        return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="", help="IDs de account.move.line separados por coma")
    ap.add_argument("--file", default="", help="Archivo con un id por línea")
    args = ap.parse_args()

    ids: list[int] = []
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                ids.append(int(line))
    if args.ids:
        for part in args.ids.split(","):
            part = part.strip()
            if part:
                ids.append(int(part))

    if not ids:
        ap.print_help()
        print("\nNecesitas --ids o --file con IDs de apuntes.", file=sys.stderr)
        return 1

    cfg = ODOO_CONFIG_MASTER_DEV.copy()
    models, uid, db, pwd = connect(cfg)
    print(f"Conectado: {cfg.get('url')} db={db}")
    print(f"Analizando {len(ids)} apunte(s) (rama retención: payment + balance != 0)\n")

    fields = ["id", "payment_id", "withholding_id", "balance", "move_id", "partner_id"]
    rows = models.execute_kw(
        db,
        uid,
        pwd,
        "account.move.line",
        "read",
        [ids],
        {"fields": fields},
    )
    by_id = {r["id"]: r for r in rows}
    missing = [i for i in ids if i not in by_id]
    if missing:
        print(f"ADVERTENCIA: no se pudieron leer ids (permiso o inexistentes): {missing[:20]}")

    problemas: list[str] = []
    for i in ids:
        r = by_id.get(i)
        if not r:
            continue
        pay = r.get("payment_id")
        if not pay:
            continue
        if bal_skip_zero(r.get("balance")):
            continue

        wh = r.get("withholding_id")
        mid = r["move_id"][0] if r.get("move_id") else None
        if not wh:
            problemas.append(
                f"aml_id={i} move_id={mid} payment_id={pay[0]} withholding_id=False "
                f"balance={r.get('balance')!r}  -> get_pos_and_number(False)"
            )
            continue

        wh_id = wh[0]
        wh_rows = models.execute_kw(
            db,
            uid,
            pwd,
            "l10n_ar.payment.withholding",
            "read",
            [[wh_id]],
            {"fields": ["id", "name", "payment_id", "tax_id"]},
        )
        if not wh_rows:
            problemas.append(f"aml_id={i} withholding_id={wh_id} (read vacío)")
            continue
        name = wh_rows[0].get("name")
        if name is False or name is None or (isinstance(name, str) and not name.strip()):
            problemas.append(
                f"aml_id={i} move_id={mid} payment_id={pay[0]} withholding_id={wh_id} "
                f"name={name!r} balance={r.get('balance')!r}"
            )

    if not problemas:
        print(
            "Ninguno de los IDs analizados coincide con la rama problemática "
            "(payment + balance!=0 + withholding sin nombre).\n"
            "Incluí todos los apuntes seleccionados al fallar, o probá por mitades en la UI."
        )
        return 0

    print(f"Apuntes que harían fallar get_pos_and_number (total {len(problemas)}):\n")
    for p in problemas:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
