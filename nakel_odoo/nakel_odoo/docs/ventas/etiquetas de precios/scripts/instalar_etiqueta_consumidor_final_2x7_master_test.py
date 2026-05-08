#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import xmlrpc.client

sys.path.insert(0, "/media/klap/raid5/cursor_files")

from config_nakel import ODOO_CONFIG_DEV_MASTER_TEST  # noqa: E402


BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


TEMPLATES = [
    {
        "key": "nakel_etiquetas.report_simple_label2x7_consumidor_final",
        "path": "nakel_etiquetas.report_simple_label2x7_consumidor_final.xml",
        "name": "Nakel Etiqueta Consumidor Final — celda 2x7 (QWeb)",
        "model": "product.template",
        "priority": 999,
    },
    {
        "key": "nakel_etiquetas.report_productlabel_consumidor_final",
        "path": "nakel_etiquetas.report_productlabel_consumidor_final.xml",
        "name": "Nakel Etiqueta Consumidor Final — plancha (QWeb)",
        "model": "product.template",
        "priority": 999,
    },
    {
        "key": "nakel_etiquetas.report_producttemplatelabel2x7_consumidor_final",
        "path": "nakel_etiquetas.report_producttemplatelabel2x7_consumidor_final.xml",
        "name": "Nakel Etiqueta Consumidor Final 2x7 — wrapper (QWeb)",
        "model": "product.template",
        "priority": 999,
    },
]


REPORT = {
    "name_es": "Nakel Consumidor Final 2x7 (PDF)",
    "report_name": "nakel_etiquetas.report_producttemplatelabel2x7_consumidor_final",
    "report_file": "nakel_etiquetas.report_producttemplatelabel2x7_consumidor_final",
    "model": "product.template",
    "report_type": "qweb-pdf",
    "binding_type": "report",
    "binding_view_types": "list,form",
    "paperformat_name": "A4 Label Sheet",
}


def _read_template_file(abs_path: str) -> str:
    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()
    if content.startswith("\ufeff"):
        content = content[1:]
    start = content.find("<t t-name=")
    if start == -1:
        raise ValueError(f"No se encontró <t t-name=> en {abs_path}")
    return content[start:].strip()


def upsert_qweb_view(models, db, uid, pwd, *, key, name, abs_path, priority=999, model=None):
    arch = _read_template_file(abs_path)
    rows = models.execute_kw(
        db,
        uid,
        pwd,
        "ir.ui.view",
        "search_read",
        [[("key", "=", key), ("type", "=", "qweb")]],
        {"fields": ["id", "name", "key", "priority"], "limit": 1},
    )
    vals = {"arch": arch, "priority": priority}
    if rows:
        vid = rows[0]["id"]
        models.execute_kw(db, uid, pwd, "ir.ui.view", "write", [[vid], vals])
        return vid, "actualizado"

    create_vals = {"name": name, "type": "qweb", "key": key, "arch": arch, "priority": priority}
    if model:
        create_vals["model"] = model
    vid = models.execute_kw(db, uid, pwd, "ir.ui.view", "create", [create_vals])
    return vid, "creado"


def ensure_paperformat_id(models, db, uid, pwd, name: str) -> int:
    ids = models.execute_kw(db, uid, pwd, "report.paperformat", "search", [[("name", "=", name)]], {"limit": 1})
    if ids:
        return ids[0]
    raise RuntimeError(f"No se encontró report.paperformat name={name!r} (requerido para 2x7 PDF)")


def upsert_report_action(models, db, uid, pwd, *, report_name, vals):
    rows = models.execute_kw(
        db,
        uid,
        pwd,
        "ir.actions.report",
        "search_read",
        [[("report_name", "=", report_name)]],
        {"fields": ["id", "name", "report_name"], "limit": 1},
    )
    if rows:
        rid = rows[0]["id"]
        models.execute_kw(db, uid, pwd, "ir.actions.report", "write", [[rid], vals])
        return rid, "actualizado"
    rid = models.execute_kw(db, uid, pwd, "ir.actions.report", "create", [vals])
    return rid, "creado"


def main():
    cfg = ODOO_CONFIG_DEV_MASTER_TEST
    url, db, user, pwd = cfg["url"], cfg["db"], cfg["username"], cfg["password"]

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, pwd, {})
    if not uid:
        raise RuntimeError(f"Auth fallida en {url} db={db} user={user}")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    print(f"Conectado a {url} / {db} (uid={uid})")

    # 1) Subir/actualizar vistas QWeb
    for t in TEMPLATES:
        abs_path = os.path.join(TEMPLATES_DIR, t["path"])
        vid, status = upsert_qweb_view(
            models,
            db,
            uid,
            pwd,
            key=t["key"],
            name=t["name"],
            abs_path=abs_path,
            priority=t.get("priority", 999),
            model=t.get("model"),
        )
        print(f"QWeb {t['key']}: {status} (id={vid})")

    # 2) Crear/actualizar acción de reporte
    paperformat_id = ensure_paperformat_id(models, db, uid, pwd, REPORT["paperformat_name"])
    vals = {
        "name": REPORT["name_es"],
        "model": REPORT["model"],
        "report_type": REPORT["report_type"],
        "report_name": REPORT["report_name"],
        "report_file": REPORT["report_file"],
        "paperformat_id": paperformat_id,
        "binding_type": REPORT["binding_type"],
        "binding_view_types": REPORT["binding_view_types"],
    }
    rid, status = upsert_report_action(models, db, uid, pwd, report_name=REPORT["report_name"], vals=vals)

    # 3) Re-escribir el nombre también en contexto es_AR (para UI traducida)
    models.execute_kw(
        db,
        uid,
        pwd,
        "ir.actions.report",
        "write",
        [[rid], {"name": REPORT["name_es"]}],
        {"context": {"lang": "es_AR"}},
    )

    print(f"Reporte {REPORT['report_name']}: {status} (id={rid}), paperformat_id={paperformat_id}")
    print("OK")


if __name__ == "__main__":
    main()

