#!/usr/bin/env python3
"""
Publica los templates QWeb canónicos desde nakel/qweb/templates/ por XML-RPC.

Por defecto apunta a master_dev. Use --instancia master18 (master_18 en dev.nakel)
o --instancia master_test (base master_test en dev.nakel).

Incluye:
  - Vistas QWeb (factura, nota de crédito, remito, proforma, cotización Nakel 2024)
  - Paperformat A4 Portrait
  - Enlace de ir.actions.report por búsqueda (sin IDs fijos por base)
  - Opcional: acción «Cotización en PDF» → template Nakel (sale.report_saleorder_nakel_2024)
"""

import sys
import os
import argparse

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import (
        ODOO_CONFIG_MASTER18,
        ODOO_CONFIG_MASTER_DEV,
        ODOO_CONFIG_DEV_MASTER_TEST,
    )
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

import xmlrpc.client

from nakel_qweb_sync_lib import (
    sincronizar_todos_los_templates,
    sincronizar_paperformat_y_acciones_factura,
    apuntar_accion_cotizacion_pdf_a_template_nakel,
    asegurar_accion_report_remito_nakel,
)


def _config(instancia):
    if instancia == "master18":
        c = ODOO_CONFIG_MASTER18
    elif instancia == "master_test":
        c = ODOO_CONFIG_DEV_MASTER_TEST
    else:
        c = ODOO_CONFIG_MASTER_DEV
    return {
        "url": c["url"],
        "db": c["db"],
        "user": c["username"],
        "pass": c["password"],
    }


def main():
    parser = argparse.ArgumentParser(description="Aplicar templates QWeb Nakel por XML-RPC")
    parser.add_argument(
        "--instancia",
        choices=["master_dev", "master18", "master_test"],
        default="master_dev",
        help="Base destino: master_dev | master18 (master_18) | master_test (dev.nakel)",
    )
    parser.add_argument(
        "--solo-facturas",
        action="store_true",
        help="Solo sube vistas account.move (factura + NC), sin remito ni proforma",
    )
    parser.add_argument(
        "--sin-acciones-report",
        action="store_true",
        help="No toca paperformat ni ir.actions.report de facturas (solo ir.ui.view)",
    )
    parser.add_argument(
        "--sin-apuntar-cotizacion-pdf",
        action="store_true",
        help="No modifica sale.action_report_saleorder (deja PDF Quote apuntando al template Odoo)",
    )
    args = parser.parse_args()

    cfg = _config(args.instancia)

    print("=" * 80)
    print("📦 TEMPLATES QWEB NAKEL →", args.instancia.upper())
    print("=" * 80)
    print(f"📊 Base: {cfg['db']}")
    print(f"🌐 URL: {cfg['url']}")
    print("=" * 80)

    try:
        common = xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/common")
        uid = common.authenticate(cfg["db"], cfg["user"], cfg["pass"], {})
        if not uid:
            print("❌ Error de autenticación")
            return False
        models = xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/object")
    except Exception as e:
        print(f"❌ Error conectando: {e}")
        return False

    print("✅ Conexión OK\n")

    fallo = False
    for key, ok, msg in sincronizar_todos_los_templates(
        models, uid, cfg["pass"], cfg["db"], solo_facturas_y_nc=args.solo_facturas
    ):
        estado = "✅" if ok else "❌"
        print(f"{estado} {key}: {msg}")
        if not ok:
            fallo = True

    if not args.sin_acciones_report:
        print("\n--- Paperformat y acciones de reporte (factura / NC) ---\n")
        for etiqueta, ok, msg in sincronizar_paperformat_y_acciones_factura(
            models, uid, cfg["pass"], cfg["db"]
        ):
            estado = "✅" if ok else "⚠️"
            print(f"{estado} {etiqueta}: {msg}")
            if etiqueta == "reportes_factura" and not ok:
                fallo = True

    if not args.solo_facturas:
        print("\n--- Acción «Remito Nakel» (ir.actions.report) ---\n")
        ok_r, msg_r = asegurar_accion_report_remito_nakel(
            models, uid, cfg["pass"], cfg["db"]
        )
        print(("✅" if ok_r else "❌"), "remito_nakel:", msg_r)
        if not ok_r:
            fallo = True

    if (
        not args.solo_facturas
        and not args.sin_apuntar_cotizacion_pdf
    ):
        print("\n--- Cotización en PDF → Nakel 2024 ---\n")
        ok_c, msg_c = apuntar_accion_cotizacion_pdf_a_template_nakel(
            models, uid, cfg["pass"], cfg["db"]
        )
        print(("✅" if ok_c else "❌"), "cotización_pdf:", msg_c)
        if not ok_c:
            fallo = True

    print("\n" + "=" * 80)
    if fallo:
        print("⚠️  Revisar errores arriba (vistas críticas fallaron).")
        return False
    print("✅ Sincronización completada.")
    print("=" * 80)
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
