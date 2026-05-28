# -*- coding: utf-8 -*-
"""
Lógica compartida para publicar templates QWeb Nakel vía XML-RPC.
Fuente canónica de archivos: nakel/qweb/templates/ (ver TEMPLATES_CANONICOS).
"""

import os

# Directorio base: .../nakel/qweb/
_QWEB_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

# Lista canónica: key ir.ui.view = nombre en Odoo; path relativo a qweb/
TEMPLATES_CANONICOS = [
    {
        "key": "account.report_invoice_document_nakel_2024",
        "path": "templates/account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml",
        "name": "Factura Nakel 2024 (QWeb)",
        "model": "account.move",
        "priority": 999,
    },
    {
        "key": "account.report_credit_note_document_nakel_2024",
        "path": "templates/account.report_invoice_document_nakel_2024_NOTA_CREDITO_MEJORADO.xml",
        "name": "Nota de Crédito Nakel 2024 (QWeb)",
        "model": "account.move",
        "priority": 999,
    },
    {
        "key": "stock.report_delivery_document_nakel_2024",
        "path": "templates/stock.report_delivery_document_nakel_2024_MEJORADO.xml",
        "name": "Remito Nakel (QWeb)",
        "model": "stock.picking",
        "priority": 999,
    },
    {
        "key": "sale.report_saleorder_pro_forma",
        "path": "templates/sale.report_saleorder_pro_forma_NAKEL_MEJORADO_V2.xml",
        "name": "Proforma Nakel (QWeb)",
        "model": "sale.order",
        "priority": 999,
    },
    {
        "key": "sale.report_saleorder_document_nakel_2024",
        "path": "templates/sale.report_saleorder_document_nakel_2024.xml",
        "name": "Cotización Nakel 2024 — documento (QWeb)",
        "model": "sale.order",
        "priority": 1000,
    },
    {
        "key": "sale.report_saleorder_nakel_2024",
        "path": "templates/sale.report_saleorder_nakel_2024.xml",
        "name": "Cotización Nakel 2024 — envoltorio (QWeb)",
        "model": "sale.order",
        "priority": 1000,
    },
]

PAPERFORMAT_FACTURA = {
    "name": "A4 Nakel Factura Ajustado",
    "default": False,
    "format": "A4",
    "orientation": "Portrait",
    "margin_top": 5,
    "margin_bottom": 14,
    "margin_left": 6,
    "margin_right": 6,
    "header_line": False,
    "header_spacing": 0,
    "dpi": 90,
}


def ruta_template(rel_path):
    return os.path.join(_QWEB_ROOT, rel_path)


def leer_archivo_template(abs_path):
    """Extrae el fragmento QWeb desde la primera etiqueta <t t-name=."""
    with open(abs_path, "r", encoding="utf-8") as f:
        contenido = f.read()
    if contenido.startswith("\ufeff"):
        contenido = contenido[1:]
    inicio = contenido.find("<t t-name=")
    if inicio == -1:
        return None
    return contenido[inicio:].strip()


def instalar_o_actualizar_vista_qweb(
    models, uid, password, db, key, abs_path, name, priority=999, model=None
):
    arch = leer_archivo_template(abs_path)
    if not arch:
        return False, "No se pudo leer el template o falta <t t-name=>"

    templates = models.execute_kw(
        db,
        uid,
        password,
        "ir.ui.view",
        "search_read",
        [[("key", "=", key), ("type", "=", "qweb")]],
        {"fields": ["id", "name", "key", "priority"]},
    )

    vals = {"arch": arch, "priority": priority}
    if templates:
        tid = templates[0]["id"]
        models.execute_kw(db, uid, password, "ir.ui.view", "write", [[tid], vals])
        return True, f"actualizado id={tid}"
    create_vals = {
        "name": name,
        "type": "qweb",
        "key": key,
        "arch": arch,
        "priority": priority,
    }
    if model:
        create_vals["model"] = model
    new_id = models.execute_kw(db, uid, password, "ir.ui.view", "create", [create_vals])
    return True, f"creado id={new_id}"


def asegurar_paperformat_factura(models, uid, password, db):
    nombre = PAPERFORMAT_FACTURA["name"]
    existentes = models.execute_kw(
        db,
        uid,
        password,
        "report.paperformat",
        "search",
        [[("name", "=", nombre)]],
        {"limit": 1},
    )
    if existentes:
        pid = existentes[0]
        models.execute_kw(
            db, uid, password, "report.paperformat", "write", [[pid], PAPERFORMAT_FACTURA]
        )
        return pid
    return models.execute_kw(
        db, uid, password, "report.paperformat", "create", [PAPERFORMAT_FACTURA]
    )


def _es_reporte_proveedor(rep):
    rn = (rep.get("report_name") or "").lower()
    nm = (rep.get("name") or "").lower()
    if "vendor" in rn or "original_vendor" in rn:
        return True
    if "factura de proveedor" in nm or "vendor bill" in nm:
        return True
    return False


def _es_accion_nota_credito(rep):
    nm = (rep.get("name") or "").lower()
    rn = (rep.get("report_name") or "").lower()
    if "nota de cr" in nm or "nota de credito" in nm:
        return True
    if "credit note" in nm:
        return True
    if "credit_note" in rn or "creditnote" in rn:
        return True
    return False


def listar_reportes_account_move_pdf(models, uid, password, db):
    return models.execute_kw(
        db,
        uid,
        password,
        "ir.actions.report",
        "search_read",
        [[("model", "=", "account.move"), ("report_type", "=", "qweb-pdf")]],
        {"fields": ["id", "name", "report_name", "model"]},
    )


def ids_reportes_factura_cliente(reports):
    """Reportes de PDF de account.move que deben usar el QWeb de factura Nakel."""
    out = []
    for r in reports:
        if _es_reporte_proveedor(r):
            continue
        if _es_accion_nota_credito(r):
            continue
        out.append(r["id"])
    return out


def ids_reportes_nota_credito(reports):
    out = []
    for r in reports:
        if _es_reporte_proveedor(r):
            continue
        if _es_accion_nota_credito(r):
            out.append(r["id"])
    return out


def escribir_reportes_factura(models, uid, password, db, report_ids, paperformat_id):
    if not report_ids:
        return False, "No se encontraron reportes de factura (revisar heurística o asignar manualmente)"
    valores = {
        "report_name": "account.report_invoice_document_nakel_2024",
        "print_report_name": "'Factura NAKEL - %s' % ((object.name or '').replace('/', '-'))",
        "paperformat_id": paperformat_id,
    }
    models.execute_kw(db, uid, password, "ir.actions.report", "write", [report_ids, valores])
    models.execute_kw(
        db,
        uid,
        password,
        "ir.actions.report",
        "write",
        [report_ids, valores],
        {"context": {"lang": "es_AR"}},
    )
    return True, report_ids


def escribir_reportes_nota_credito(models, uid, password, db, report_ids, paperformat_id):
    if not report_ids:
        return False, "No se encontraron reportes de nota de crédito (puede usar el mismo que factura en tu base)"
    valores = {
        "report_name": "account.report_credit_note_document_nakel_2024",
        "print_report_name": "'Nota de crédito NAKEL - %s' % ((object.name or '').replace('/', '-'))",
        "paperformat_id": paperformat_id,
    }
    models.execute_kw(db, uid, password, "ir.actions.report", "write", [report_ids, valores])
    models.execute_kw(
        db,
        uid,
        password,
        "ir.actions.report",
        "write",
        [report_ids, valores],
        {"context": {"lang": "es_AR"}},
    )
    return True, report_ids


def sincronizar_todos_los_templates(models, uid, password, db, solo_facturas_y_nc=False):
    """
    Sube/actualiza todas las vistas QWeb desde TEMPLATES_CANONICOS.
    Si solo_facturas_y_nc=True, solo account.move templates (factura + NC).
    """
    resultados = []
    for cfg in TEMPLATES_CANONICOS:
        if solo_facturas_y_nc and cfg["model"] != "account.move":
            continue
        abs_path = ruta_template(cfg["path"])
        ok, msg = instalar_o_actualizar_vista_qweb(
            models,
            uid,
            password,
            db,
            cfg["key"],
            abs_path,
            cfg["name"],
            priority=cfg.get("priority", 999),
            model=cfg.get("model"),
        )
        resultados.append((cfg["key"], ok, msg))
    return resultados


def asegurar_accion_report_remito_nakel(models, uid, password, db):
    """
    Enlaza la acción PDF del remito Nakel al modelo stock.picking (menú Imprimir del albarán),
    nombre «Remito Nakel», y paperformat «A4 Nakel Factura Ajustado» (márgenes como factura;
    el formato A4 por defecto suele traer margin_top ~52 y desperdicia papel).
    """
    report_name = "stock.report_delivery_document_nakel_2024"
    paperformat_id = asegurar_paperformat_factura(models, uid, password, db)
    mids = models.execute_kw(
        db, uid, password, "ir.model", "search", [[["model", "=", "stock.picking"]]], {"limit": 1}
    )
    if not mids:
        return False, "ir.model stock.picking no encontrado"
    mid = mids[0]
    reps = models.execute_kw(
        db,
        uid,
        password,
        "ir.actions.report",
        "search_read",
        [[["report_name", "=", report_name]]],
        {"fields": ["id", "name"], "limit": 5},
    )
    if not reps:
        return False, f"ir.actions.report con report_name={report_name!r} no encontrado"
    rid = reps[0]["id"]
    vals = {
        "name": "Remito Nakel",
        "binding_model_id": mid,
        "binding_type": "report",
        "binding_view_types": "list,form",
        "paperformat_id": paperformat_id,
    }
    models.execute_kw(db, uid, password, "ir.actions.report", "write", [[rid], vals])
    return True, (
        f"ir.actions.report id={rid} → Remito Nakel, binding stock.picking, "
        f"paperformat_id={paperformat_id} (A4 Nakel Factura Ajustado)"
    )


def sincronizar_paperformat_y_acciones_factura(models, uid, password, db):
    """Paperformat + enlace dinámico de ir.actions.report (sin IDs fijos por base)."""
    log = []
    paperformat_id = asegurar_paperformat_factura(models, uid, password, db)
    log.append(("paperformat", True, f"id={paperformat_id}"))

    reports = listar_reportes_account_move_pdf(models, uid, password, db)
    ids_inv = ids_reportes_factura_cliente(reports)
    ids_nc = ids_reportes_nota_credito(reports)

    ok_i, msg_i = escribir_reportes_factura(models, uid, password, db, ids_inv, paperformat_id)
    log.append(("reportes_factura", ok_i, msg_i))

    ok_n, msg_n = escribir_reportes_nota_credito(models, uid, password, db, ids_nc, paperformat_id)
    log.append(("reportes_nota_credito", ok_n, msg_n))

    return log


def apuntar_accion_cotizacion_pdf_a_template_nakel(models, uid, password, db):
    """
    Cambia sale.action_report_saleorder (menú «Cotización en PDF» / PDF Quote) para que use
    sale.report_saleorder_nakel_2024 sin borrar las vistas estándar sale.report_saleorder.
    """
    rows = models.execute_kw(
        db,
        uid,
        password,
        "ir.model.data",
        "search_read",
        [[("module", "=", "sale"), ("name", "=", "action_report_saleorder")]],
        {"fields": ["res_id"], "limit": 1},
    )
    if not rows:
        return False, "ir.model.data sale.action_report_saleorder no encontrado"
    rid = rows[0]["res_id"]
    models.execute_kw(
        db,
        uid,
        password,
        "ir.actions.report",
        "write",
        [
            [rid],
            {
                "report_name": "sale.report_saleorder_nakel_2024",
                "report_file": "sale.report_saleorder_nakel_2024",
            },
        ],
    )
    return True, "sale.action_report_saleorder id=%s -> report_name sale.report_saleorder_nakel_2024" % rid
