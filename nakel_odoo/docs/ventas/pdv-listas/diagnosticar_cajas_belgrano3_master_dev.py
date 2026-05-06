#!/usr/bin/env python3
"""
Diagnóstico rápido por API (XML-RPC) de cajas POS específicas en Odoo master_dev.

Objetivo:
- Encontrar `pos.config` por nombre (por defecto: Belgrano3-C1 y Belgrano3-C2)
- Inspeccionar últimas `pos.session` asociadas
- Inspeccionar últimas `pos.order` asociadas a esas sesiones
- Buscar `ir.logging` reciente que mencione POS / cajas / sesiones

No modifica nada: solo lectura.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xmlrpc.client
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except Exception as e:  # pragma: no cover
    print(f"❌ No se pudo importar config_nakel. Error: {e}")
    raise


@dataclass(frozen=True)
class OdooConn:
    db: str
    uid: int
    password: str
    models: Any


def _odoo_connect() -> OdooConn:
    url = ODOO_CONFIG_MASTER_DEV["url"].rstrip("/")
    db = ODOO_CONFIG_MASTER_DEV["db"]
    username = ODOO_CONFIG_MASTER_DEV["username"]
    password = ODOO_CONFIG_MASTER_DEV["password"]

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise RuntimeError(f"Fallo autenticación en {db} ({url}).")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return OdooConn(db=db, uid=int(uid), password=password, models=models)


def _search_read(
    c: OdooConn,
    model: str,
    domain: list,
    *,
    fields: list[str],
    limit: int = 0,
    order: str | None = None,
) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {"fields": fields}
    if limit:
        kwargs["limit"] = limit
    if order:
        kwargs["order"] = order
    return c.models.execute_kw(c.db, c.uid, c.password, model, "search_read", [domain], kwargs)


def _existing_fields(c: OdooConn, model: str) -> set[str]:
    # fields_get devuelve un dict {field_name: {meta...}}
    meta = c.models.execute_kw(c.db, c.uid, c.password, model, "fields_get", [], {"attributes": ["type"]})
    return set(meta.keys())


def _filter_fields(existing: set[str], desired: list[str]) -> list[str]:
    return [f for f in desired if f in existing]


def _safe_dt_now() -> datetime:
    # Odoo guarda create_date en UTC; consultamos rangos en UTC.
    return datetime.now(tz=timezone.utc)


def _dt_to_odoo_str(dt: datetime) -> str:
    # Formato típico en Odoo: "YYYY-MM-DD HH:MM:SS" (UTC)
    dt_utc = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt_utc.strftime("%Y-%m-%d %H:%M:%S")


def _flatten_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)


def _domain_ilike_any(field: str, terms: Iterable[str]) -> list:
    # Dominio OR encadenado: ['|', (field, 'ilike', t1), '|', (field,'ilike',t2), ...]
    terms = [t for t in terms if t and t.strip()]
    if not terms:
        return []
    if len(terms) == 1:
        return [(field, "ilike", terms[0])]
    dom: list[Any] = []
    # para n términos, necesitamos n-1 pipes
    for _ in range(len(terms) - 1):
        dom.append("|")
    for t in terms:
        dom.append((field, "ilike", t))
    return dom


def diagnosticar(
    *,
    caja_names: list[str],
    hours: int,
    sessions_limit: int,
    orders_limit: int,
    logs_limit: int,
) -> dict[str, Any]:
    c = _odoo_connect()

    since_dt = _safe_dt_now() - timedelta(hours=hours)
    since_str = _dt_to_odoo_str(since_dt)

    # Cache de campos por modelo (evita fallos por divergencias entre versiones/módulos)
    cfg_fields = _existing_fields(c, "pos.config")
    sess_fields = _existing_fields(c, "pos.session")
    order_fields = _existing_fields(c, "pos.order")
    stline_fields: set[str] = set()
    try:
        stline_fields = _existing_fields(c, "account.bank.statement.line")
    except Exception:
        # Puede no existir/estar permitido según módulos/permisos
        stline_fields = set()

    # 1) POS configs
    pos_configs = _search_read(
        c,
        "pos.config",
        _domain_ilike_any("name", caja_names),
        fields=_filter_fields(
            cfg_fields,
            [
            "id",
            "name",
            "active",
            "company_id",
            "pricelist_id",
            "iface_cashdrawer",
            "iface_print_via_proxy",
            "is_posbox",
            "module_pos_hr",
            "current_session_id",
            "current_session_state",
            ],
        ),
        limit=20,
        order="id desc",
    )

    # 2) Sessions por config
    sessions_by_config: dict[int, list[dict[str, Any]]] = {}
    for cfg in pos_configs:
        cfg_id = cfg["id"]
        sessions = _search_read(
            c,
            "pos.session",
            [("config_id", "=", cfg_id)],
            fields=_filter_fields(
                sess_fields,
                [
                "id",
                "name",
                "state",
                "start_at",
                "stop_at",
                "config_id",
                "user_id",
                "create_date",
                "cash_journal_id",
                "move_id",
                "cash_register_balance_start",
                "cash_register_balance_end_real",
                "cash_register_balance_end",
                "sequence_number",
                "login_number",
                ],
            ),
            limit=sessions_limit,
            order="id desc",
        )
        sessions_by_config[cfg_id] = sessions

    # 2.5) Statement lines por sesión (si existe el modelo/campo)
    stlines_by_session: dict[int, list[dict[str, Any]]] = {}
    if stline_fields:
        for cfg in pos_configs:
            cfg_id = cfg["id"]
            for s in sessions_by_config.get(cfg_id, []):
                sid = s["id"]
                try:
                    stlines = _search_read(
                        c,
                        "account.bank.statement.line",
                        [("pos_session_id", "=", sid)],
                        fields=_filter_fields(
                            stline_fields,
                            [
                                "id",
                                "create_date",
                                "amount",
                                "payment_ref",
                                "ref",
                                "partner_id",
                                "journal_id",
                                "statement_id",
                                "pos_session_id",
                                "transaction_type",
                            ],
                        ),
                        limit=200,
                        order="id desc",
                    )
                    stlines_by_session[sid] = stlines
                except Exception as e:
                    stlines_by_session[sid] = [{"error": str(e)}]

    # 3) Orders por sessions encontradas (últimas)
    orders_by_config: dict[int, list[dict[str, Any]]] = {}
    for cfg in pos_configs:
        cfg_id = cfg["id"]
        sess_ids = [s["id"] for s in sessions_by_config.get(cfg_id, [])]
        if not sess_ids:
            orders_by_config[cfg_id] = []
            continue
        orders = _search_read(
            c,
            "pos.order",
            [("session_id", "in", sess_ids)],
            fields=_filter_fields(
                order_fields,
                [
                "id",
                "name",
                "state",
                "date_order",
                "session_id",
                "amount_total",
                "amount_paid",
                "amount_return",
                "partner_id",
                "user_id",
                "create_date",
                "account_move",
                "is_invoiced",
                # algunos módulos/versiones usan otros campos para devoluciones; evitamos hardcode
                "refund_order_id",
                "refund_order_ids",
                "refunded_order_id",
                "refunded_order_ids",
                ],
            ),
            limit=orders_limit,
            order="id desc",
        )
        orders_by_config[cfg_id] = orders

    # 4) ir.logging (si está disponible / accesible)
    ir_logging: list[dict[str, Any]] = []
    try:
        # Dominio OR simple: create_date >= since AND (message ilike t OR name ilike t)
        # Evitamos dominios OR anidados complejos que pueden quedar mal formados.
        log_terms = [t for t in ["pos", "point_of_sale", *caja_names] if t]
        term = log_terms[0] if log_terms else "pos"
        log_domain: list[Any] = [
            ("create_date", ">=", since_str),
            "|",
            ("message", "ilike", term),
            ("name", "ilike", term),
        ]

        ir_logging = _search_read(
            c,
            "ir.logging",
            log_domain,
            fields=[
                "id",
                "create_date",
                "name",
                "type",
                "level",
                "dbname",
                "message",
                "path",
                "func",
                "line",
            ],
            limit=logs_limit,
            order="id desc",
        )
    except Exception as e:
        ir_logging = [{"error": f"No se pudo leer ir.logging: {e}"}]

    # 5) Resumen de “anomalías” rápidas
    anomalies: list[str] = []
    for cfg in pos_configs:
        cfg_id = cfg["id"]
        sessions = sessions_by_config.get(cfg_id, [])
        if not sessions:
            anomalies.append(f"{cfg.get('name')} (pos.config {cfg_id}): sin sesiones encontradas.")
            continue
        # sesión actual vs estado
        if cfg.get("current_session_id") and cfg.get("current_session_state") not in {False, None, "opened", "opening_control"}:
            anomalies.append(
                f"{cfg.get('name')} (pos.config {cfg_id}): current_session_state={cfg.get('current_session_state')}."
            )
        # varias sesiones abiertas (heurística)
        opened = [s for s in sessions if s.get("state") in {"opened", "opening_control"}]
        if len(opened) > 1:
            anomalies.append(f"{cfg.get('name')} (pos.config {cfg_id}): {len(opened)} sesiones abiertas recientes.")

    return {
        "meta": {
            "db": c.db,
            "url": ODOO_CONFIG_MASTER_DEV["url"],
            "since_utc": since_str,
            "cajas": caja_names,
        },
        "pos_configs": pos_configs,
        "sessions_by_config": sessions_by_config,
        "statement_lines_by_session": stlines_by_session,
        "orders_by_config": orders_by_config,
        "ir_logging": ir_logging,
        "anomalies": anomalies,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico por API de cajas POS en master_dev (solo lectura).")
    parser.add_argument(
        "--caja",
        action="append",
        default=[],
        help="Nombre (o parte) de la caja/pos.config. Se puede repetir. Default: Belgrano3-C1 y Belgrano3-C2",
    )
    parser.add_argument("--hours", type=int, default=48, help="Ventana de logs (UTC) hacia atrás. Default: 48h")
    parser.add_argument("--sessions-limit", type=int, default=8, help="Sesiones por caja. Default: 8")
    parser.add_argument("--orders-limit", type=int, default=30, help="Órdenes por caja. Default: 30")
    parser.add_argument("--logs-limit", type=int, default=200, help="Entradas de ir.logging. Default: 200")
    parser.add_argument("--out", type=str, default="", help="Ruta de salida JSON (opcional).")
    args = parser.parse_args()

    cajas = args.caja or ["Belgrano3-C1", "Belgrano3-C2"]
    report = diagnosticar(
        caja_names=cajas,
        hours=args.hours,
        sessions_limit=args.sessions_limit,
        orders_limit=args.orders_limit,
        logs_limit=args.logs_limit,
    )

    out_path = args.out.strip()
    if not out_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(
            "/media/klap/raid5/cursor_files/reportes",
            f"diagnostico_pos_belgrano3_master_dev_{ts}.json",
        )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Resumen corto por consola (sin volcar todo)
    print(f"✅ Reporte guardado en: {out_path}")
    print("\nResumen rápido:")
    print(f"- POS configs encontrados: {len(report['pos_configs'])}")
    print(f"- Anomalías: {len(report['anomalies'])}")
    for a in report["anomalies"][:20]:
        print(f"  - {a}")
    print(f"- ir.logging: {len(report['ir_logging'])}")

    # Mostrar 10 logs más recientes con nivel WARNING/ERROR si existen
    logs = report["ir_logging"]
    if logs and isinstance(logs, list) and logs and "error" not in logs[0]:
        filt = [l for l in logs if _flatten_text(l.get("level")).upper() in {"WARNING", "ERROR", "CRITICAL"}]
        if filt:
            print("\nLogs WARNING/ERROR recientes (top 10):")
            for l in filt[:10]:
                print(
                    f"- {l.get('create_date')} [{l.get('level')}] {str(l.get('name'))[:60]} :: {str(l.get('message'))[:140]}"
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

