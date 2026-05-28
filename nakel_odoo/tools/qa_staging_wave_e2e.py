#!/usr/bin/env python3
"""
E2E destructivo staging: planificador → modo demanda → picker → reabrir → validar.
NAKEL_TARGET=staging_mayo python3 nakel_odoo/tools/qa_staging_wave_e2e.py
"""
import sys

sys.path.insert(0, "/media/klap/raid5/cursor_files")
import config_nakel as cn  # noqa: E402

import xmlrpc.client  # noqa: E402

SALESperson_ID = 90  # Delgado — PICK libres en staging


def connect():
    cfg = cn.ODOO_CONFIG_MASTER_DEV
    common = xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(cfg["db"], cfg["username"], cfg["password"], {})
    if not uid:
        raise SystemExit("Auth failed")
    models = xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/object", allow_none=True)
    return cfg, uid, models


class Odoo:
    def __init__(self, cfg, uid, models):
        self.db, self.uid, self.pwd, self.url = cfg["db"], uid, cfg["password"], cfg["url"]
        self.m = models

    def kw(self, model, method, args=None, **kwargs):
        return self.m.execute_kw(self.db, self.uid, self.pwd, model, method, args or [], kwargs or {})

    def read(self, model, ids, fields):
        return self.kw(model, "read", [[ids] if isinstance(ids, int) else ids], fields=fields)


def audit_wave(odoo, bid, label):
    pick_ids = odoo.kw("stock.picking", "search", [[("batch_id", "=", bid), ("state", "not in", ["done", "cancel"])]])
    batch = odoo.read("stock.picking.batch", bid, ["name", "state", "nakel_demand_coverage_status"])[0]
    lines = odoo.kw("stock.move.line", "search_read", [[("picking_id", "in", pick_ids)]], fields=[
        "quantity", "qty_done", "picked", "move_id",
    ], limit=8000)
    move_ids = list({l["move_id"][0] for l in lines if l.get("move_id")})
    moves = {m["id"]: m for m in odoo.read("stock.move", move_ids, ["product_uom_qty"])} if move_ids else {}
    qty_pos = [l for l in lines if (l.get("quantity") or 0) > 0]
    pre_ok = res_gap = over = 0
    for l in qty_pos:
        d = moves[l["move_id"][0]]["product_uom_qty"]
        q, qd = l.get("quantity") or 0, l.get("qty_done") or 0
        if l.get("picked") and abs(qd - min(q, d)) < 1e-6:
            pre_ok += 1
        if q < d - 1e-6:
            res_gap += 1
        if qd > d + 1e-6:
            over += 1
    print(f"  [{label}] {batch['name']} sem={batch.get('nakel_demand_coverage_status')} "
          f"PICK={len(pick_ids)} lines={len(qty_pos)} pre_verde={pre_ok}/{len(qty_pos)} "
          f"res_gap={res_gap} over={over}")
    return {"batch": batch, "pick_ids": pick_ids, "lines": lines, "moves": moves,
            "pre_ok": pre_ok, "qty_pos": len(qty_pos), "res_gap": res_gap, "over": over}


def rpc_pre_green(odoo, bid):
    """
    Simula reabrir Barcode (_nakel_maybe_barcode_pre_green) vía XML-RPC.

    No corre si sem=missing; no sube qty_done si el operario ya lo bajó.
    """
    batch = odoo.read("stock.picking.batch", bid, ["nakel_demand_coverage_status"])[0]
    if batch.get("nakel_demand_coverage_status") == "missing":
        return {"pickings": 0, "lines_updated": 0, "skipped": "missing"}

    pick_ids = odoo.kw("stock.picking", "search", [[
        ("batch_id", "=", bid), ("state", "not in", ["done", "cancel"]),
    ]])
    updated = 0
    for pid in pick_ids:
        lines = odoo.kw("stock.move.line", "search_read", [[("picking_id", "=", pid)]], fields=[
            "quantity", "qty_done", "picked", "move_id",
        ], limit=5000)
        move_ids = list({l["move_id"][0] for l in lines if l.get("move_id")})
        moves = {m["id"]: m for m in odoo.read("stock.move", move_ids, ["product_uom_qty"])} if move_ids else {}
        for line in lines:
            qty = line.get("quantity") or 0.0
            qd = line.get("qty_done") or 0.0
            move = moves.get(line["move_id"][0]) if line.get("move_id") else None
            if not move:
                continue
            demand = move["product_uom_qty"]
            target = min(qty, demand) if qty > 1e-9 else demand
            if target <= 1e-9:
                continue
            if qd < target - 1e-6:
                if qd <= 1e-9 and not line.get("picked") and qty > 1e-9:
                    pass
                else:
                    continue
            if abs(qd - target) < 1e-6 and line.get("picked") and abs(qty - target) < 1e-6:
                continue
            vals = {"qty_done": target, "picked": True}
            if abs(qty - target) >= 1e-6:
                vals["quantity"] = target
            odoo.kw("stock.move.line", "write", [[line["id"]], vals])
            updated += 1
    return {"pickings": len(pick_ids), "lines_updated": updated}


def _ov_pick_coverage_ok(odoo, pick):
    """
    True si todos los moves pendientes de la OV están en el PICK candidato
    (no en OUT ni en otro PICK hermano).
    """
    so_id = pick["sale_id"][0]
    sale_lines = odoo.kw("sale.order.line", "search", [[("order_id", "=", so_id)]])
    if not sale_lines:
        return False
    for sl_id in sale_lines:
        moves = odoo.kw("stock.move", "search_read", [[
            ("sale_line_id", "=", sl_id),
            ("state", "not in", ["done", "cancel"]),
        ]], fields=["picking_id", "product_uom_qty"], limit=20)
        if not moves:
            return False
        for mv in moves:
            if (mv.get("product_uom_qty") or 0) <= 1e-9:
                continue
            pid = mv.get("picking_id")
            if not pid:
                return False
            pname = odoo.read("stock.picking", pid[0], ["name"])[0]["name"]
            if not pname.startswith("CEN/PICK/"):
                return False
            if pid[0] != pick["id"]:
                return False
    return True


def create_wave_manual(odoo, max_orders=4):
    """Arma ola con 1 PICK por OV y cobertura OV completa (único PICK pendiente)."""
    picks = odoo.kw("stock.picking", "search_read", [[
        ("name", "ilike", "CEN/PICK/"),
        ("state", "in", ["assigned", "confirmed"]),
        ("batch_id", "=", False),
        ("sale_id", "!=", False),
    ]], fields=["id", "picking_type_id", "sale_id"], limit=120, order="id desc")
    seen_so = set()
    chosen = []
    for p in picks:
        so_id = p["sale_id"][0]
        if so_id in seen_so:
            continue
        if not _ov_pick_coverage_ok(odoo, p):
            continue
        seen_so.add(so_id)
        chosen.append(p)
        if len(chosen) >= max_orders:
            break
    if len(chosen) < 2:
        raise SystemExit("Pocos PICK/OV libres con cobertura completa para ola manual")
    pick_ids = [p["id"] for p in chosen]
    ptype = chosen[0]["picking_type_id"][0]
    bid = odoo.kw("stock.picking.batch", "create", [{
        "is_wave": True,
        "name": "WAVE/QA-E2E-AUTO",
        "picking_type_id": ptype,
        "picking_ids": [(6, 0, pick_ids)],
    }])
    odoo.kw("stock.picking.batch", "action_confirm", [[bid]])
    odoo.kw("stock.picking.batch", "action_nakel_apply_demand_mode", [[bid]])
    return bid, [{"sale_order_id": p["sale_id"]} for p in chosen]


def create_wave_via_planner(odoo, max_orders=4):
    wiz_id = odoo.kw("nakel.wave.planner.wizard", "create", [{
        "salesperson_ids": [(6, 0, [SALESperson_ID])],
        "only_without_wave": True,
        "confirm_wave": True,
        "apply_demand_mode": True,
        "date_filter_mode": "any_pending",
    }])
    odoo.kw("nakel.wave.planner.wizard", "action_search_orders", [[wiz_id]])
    lines = odoo.kw("nakel.wave.planner.line", "search_read", [[("wizard_id", "=", wiz_id)]], fields=[
        "id", "warning_level", "selected", "sale_order_id", "picking_count",
    ], limit=200)
    ok = [l for l in lines if l["warning_level"] == "ok" and l["picking_count"] > 0]
    if len(ok) < 2:
        raise SystemExit(f"Pocas OV ok en planificador: {len(ok)}")
    odoo.kw("nakel.wave.planner.line", "write", [[l["id"] for l in ok], {"selected": False}])
    chosen = ok[:max_orders]
    odoo.kw("nakel.wave.planner.line", "write", [[l["id"] for l in chosen], {"selected": True}])
    res = odoo.kw("nakel.wave.planner.wizard", "action_create_wave", [[wiz_id]])
    bid = res.get("res_id") if isinstance(res, dict) else None
    if not bid:
        raise SystemExit(f"action_create_wave no devolvió res_id: {res}")
    return bid, chosen


def main():
    cfg, uid, models = connect()
    odoo = Odoo(cfg, uid, models)
    results = []

    print("=" * 70)
    print(f"E2E PROCEDIMIENTO COMPLETO — {cfg['url']} / {cfg['db']}")
    mods = {m["name"]: m["installed_version"] for m in odoo.kw("ir.module.module", "search_read", [[(
        "name", "in", ["nakel_barcode_wave_demand_mode", "nakel_fix_pick", "nakel_wave_planner"],
    )]], fields=["name", "installed_version"])}
    print(f"Modulos: {mods}\n")

    # Limpiar olas QA previas
    for bid_old in odoo.kw("stock.picking.batch", "search", [[("name", "ilike", "QA-E2E")]]):
        try:
            odoo.kw("stock.picking.batch", "action_cancel", [[bid_old]])
        except Exception:
            pass

    print("FASE 1 — Planificador → ola + Modo demanda automático")
    try:
        bid, chosen = create_wave_via_planner(odoo, max_orders=3)
        src = "planificador"
    except Exception as e:
        print(f"  Planificador: {str(e)[:120]} → ola manual")
        bid, chosen = create_wave_manual(odoo)
        src = "manual"
    sos = [l.get("sale_order_id", ["", ""])[1] for l in chosen]
    print(f"  Ola id={bid} via={src} OV/picks={len(chosen)} {sos[:4]}")
    st1 = audit_wave(odoo, bid, "1_post_armado")
    sem = st1["batch"].get("nakel_demand_coverage_status")
    if sem == "missing":
        raise SystemExit(
            f"Ola id={bid} sem=missing tras armado — elegí otras OV (moves en OUT u otro PICK)"
        )
    ok1 = sem in ("ok", "needed") and st1["pre_ok"] >= max(1, int(st1["qty_pos"] * 0.8))
    results.append(("1_armado_modo_demanda", ok1, f"sem={sem} pre={st1['pre_ok']}/{st1['qty_pos']}"))

    if sem == "needed":
        print("  Semáforo amarillo → supervisor Modo demanda")
        odoo.kw("stock.picking.batch", "action_nakel_apply_demand_mode", [[bid]])
        st1 = audit_wave(odoo, bid, "1b_post_supervisor_modo")
        sem = st1["batch"].get("nakel_demand_coverage_status")
        ok1b = sem == "ok" and st1["pre_ok"] == st1["qty_pos"]
        results.append(("1b_supervisor_verde", ok1b, f"sem={sem} pre={st1['pre_ok']}/{st1['qty_pos']}"))

    print("\nFASE 2 — Reabrir Barcode (RPC pre-verde idempotente)")
    out = rpc_pre_green(odoo, bid)
    print(f"  PRE_GREEN {out}")
    st2 = audit_wave(odoo, bid, "2_reabrir")
    ok2 = st2["over"] == 0 and st2["pre_ok"] >= max(1, int(st2["qty_pos"] * 0.8))
    results.append(("2_reabrir_pre_verde", ok2, f"pre={st2['pre_ok']}/{st2['qty_pos']} over={st2['over']}"))

    lines = [l for l in st2["lines"] if (l.get("quantity") or 0) > 0 and l.get("picked")]
    lines.sort(key=lambda l: -(st2["moves"][l["move_id"][0]]["product_uom_qty"]))
    if len(lines) < 3:
        print("ERROR pocas lineas"); return 1

    plan = [
        ("3_cero", lines[0], 0),
        ("3_parcial40", lines[1], max(1, round(st2["moves"][lines[1]["move_id"][0]]["product_uom_qty"] * 0.4))),
        ("3_parcial50", lines[2], max(1, round(st2["moves"][lines[2]["move_id"][0]]["product_uom_qty"] * 0.5))),
    ]
    print("\nFASE 3 — Picker (stock real: 0 / parcial / parcial)")
    for name, line, tqd in plan:
        odoo.kw("stock.move.line", "write", [[line["id"]], {"qty_done": float(tqd), "picked": tqd > 0}])
        a = odoo.read("stock.move.line", line["id"], ["qty_done", "quantity"])[0]
        ok = abs((a["qty_done"] or 0) - tqd) < 1e-6
        results.append((name, ok, f"qd={a['qty_done']}"))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} qd={a['qty_done']}")

    print("\nFASE 4 — Reabrir Barcode NO resetea picker")
    rpc_pre_green(odoo, bid)
    for name, line, tqd in plan:
        a = odoo.read("stock.move.line", line["id"], ["qty_done"])[0]
        ok = abs((a["qty_done"] or 0) - tqd) < 1e-6
        results.append((f"4_preserve_{name}", ok, f"esp={tqd} got={a['qty_done']}"))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} preserve qd={a['qty_done']}")

    print("\nFASE 5 — Escaneo duplicado en parcial")
    lid = plan[1][1]["id"]
    a0 = odoo.read("stock.move.line", lid, ["quantity", "qty_done"])[0]
    qd0 = a0["qty_done"] or 0
    odoo.kw("stock.move.line", "write", [[lid], {"quantity": (a0["quantity"] or qd0) * 2}])
    a1 = odoo.read("stock.move.line", lid, ["quantity", "qty_done"])[0]
    ok5 = abs((a1["qty_done"] or 0) - qd0) < 1e-6
    results.append(("5_dup_scan", ok5, f"qd={a1['qty_done']} (esp {qd0})"))
    print(f"  [{'PASS' if ok5 else 'FAIL'}] dup qd={a1['qty_done']}")

    print("\nFASE 6 — Validación ola (parcial sin re-armar Modo demanda)")
    sem6 = odoo.read("stock.picking.batch", bid, ["nakel_demand_coverage_status"])[0]["nakel_demand_coverage_status"]
    err = ""
    try:
        odoo.kw("stock.picking.batch", "action_done", [[bid]])
        blocked = False
    except Exception as e:
        blocked = True
        err = str(e)[:180]
    results.append(("6_validar_parcial_sin_modo", not blocked, f"sem={sem6} err={err if blocked else ''}"))
    print(f"  [{'PASS' if not blocked else 'FAIL'}] validar directo sem={sem6}")
    if blocked:
        print(f"    {err}")
        return 1

    state = odoo.read("stock.picking.batch", bid, ["state", "name"])[0]["state"]
    ok6 = state == "done"
    results.append(("6_state_done", ok6, f"state={state}"))
    print(f"  [{'PASS' if ok6 else 'FAIL'}] state={state}")

    for name, line, tqd in plan:
        qd = odoo.read("stock.move.line", line["id"], ["qty_done"])[0]["qty_done"]
        ok = abs((qd or 0) - tqd) < 1e-6
        results.append((f"6_preserve_{name}", ok, f"esp={tqd} got={qd}"))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} post-validar qd={qd} (esp {tqd})")

    picks = odoo.kw("stock.picking", "search", [[("batch_id", "=", bid)]])
    lines_all = odoo.kw("stock.move.line", "search_read", [[("picking_id", "in", picks)]], fields=["qty_done", "move_id"], limit=8000)
    move_ids = list({l["move_id"][0] for l in lines_all})
    moves = {m["id"]: m for m in odoo.read("stock.move", move_ids, ["product_uom_qty"])} if move_ids else {}
    over = sum(1 for l in lines_all if (l.get("qty_done") or 0) > moves[l["move_id"][0]]["product_uom_qty"] + 1e-6)
    results.append(("7_post_mortem", over == 0, f"over_demand={over}"))
    print(f"\nFASE 7 — Post-mortem over_demand={over}")

    print("\n" + "=" * 70)
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    b = odoo.read("stock.picking.batch", bid, ["name", "state"])[0]
    print(f"\nTOTAL: {passed}/{len(results)} PASS | {b['name']} id={bid} state={b['state']}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
