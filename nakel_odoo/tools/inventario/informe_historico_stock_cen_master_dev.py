#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Informe histórico de stock en CEN/Existencias (master_dev, solo lectura).

Genera CSV detallado (cada movimiento con motivo) + Markdown ejecutivo.

Uso:
  python3 nakel_odoo/tools/inventario/informe_historico_stock_cen_master_dev.py \\
    --default-code 8209.00 --desde 2026-04-01
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import xmlrpc.client

sys.path.insert(0, "/media/klap/raid5/cursor_files")

from config_nakel import ODOO_CONFIG_MASTER_DEV  # noqa: E402

LOC_EXISTENCIAS = 102


def _out_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "inventario"
        / "correcciones"
        / "OUT"
    )


def _docs_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "inventario" / "incidencias" / "logistica"


def _connect():
    cfg = ODOO_CONFIG_MASTER_DEV
    common = xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/common")
    uid = common.authenticate(cfg["db"], cfg["username"], cfg["password"], {})
    if not uid:
        raise RuntimeError("Autenticación Odoo fallida")
    models = xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/object")
    return cfg["db"], uid, cfg["password"], models


def _search_read(models, db, uid, pwd, model, domain, fields, order=None, limit=0):
    kw: dict = {"fields": fields}
    if order:
        kw["order"] = order
    if limit:
        kw["limit"] = limit
    return models.execute_kw(db, uid, pwd, model, "search_read", [domain], kw)


def _fmt_num(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _clasificar(ref: str, loc_from: int, loc_to: int, loc: int) -> tuple[str, str]:
    ref = ref or ""
    if "Cantidad de producto actualizada" in ref:
        if loc_to == loc and loc_from != loc:
            return "AJUSTE_INVENTARIO", "ENTRADA"
        if loc_from == loc:
            return "AJUSTE_INVENTARIO", "SALIDA"
    if ref.startswith("CEN/STOR"):
        return "RECEPCION_STOR", "ENTRADA"
    if ref.startswith("CEN/INT"):
        return "TRASLADO_SUCURSAL", "SALIDA"
    if ref.startswith("CEN/PICK"):
        if loc_from == loc:
            return "PICK_EXPEDICION", "SALIDA"
        return "PICK_EXPEDICION", "ENTRADA"
    if ref.startswith("CEN/OUT"):
        return "OUT_DESPACHO", "SALIDA"
    if loc_to == loc:
        return "ENTRADA_OTRA", "ENTRADA"
    if loc_from == loc:
        return "SALIDA_OTRA", "SALIDA"
    return "OTRO", "NEUTRO"


def _motivo(tipo: str, sentido: str, ref: str, origin: str, loc_from: str, loc_to: str) -> str:
    o = f" Origen: {origin}." if origin else ""
    if tipo == "RECEPCION_STOR":
        return f"Recepción en Central (almacenaje): mercadería ingresa a Existencias ({ref}).{o}"
    if tipo == "PICK_EXPEDICION" and sentido == "SALIDA":
        return f"Picking de preparación: sale de Existencias hacia zona de Salida ({ref}).{o}"
    if tipo == "PICK_EXPEDICION" and sentido == "ENTRADA":
        return f"Devolución / reversa de picking hacia Existencias ({ref}).{o}"
    if tipo == "TRASLADO_SUCURSAL":
        return f"Traslado interno Central → sucursal ({ref}). Destino: {loc_to}.{o}"
    if tipo == "AJUSTE_INVENTARIO" and sentido == "ENTRADA":
        return f"Ajuste de inventario (aplicado): suma unidades a Existencias ({ref})."
    if tipo == "AJUSTE_INVENTARIO" and sentido == "SALIDA":
        return (
            f"Ajuste de inventario (aplicado): resta unidades de Existencias ({ref}). "
            "En Odoo indica corrección respecto al saldo teórico previo, no necesariamente "
            "“dejar” esa cantidad en piso."
        )
    if tipo == "OUT_DESPACHO":
        return f"Salida / entrega a cliente desde Central ({ref}).{o}"
    if sentido == "ENTRADA":
        return f"Entrada a Existencias desde {loc_from} ({ref}).{o}"
    if sentido == "SALIDA":
        return f"Salida de Existencias hacia {loc_to} ({ref}).{o}"
    return ref or tipo


def _delta_saldo(lines: list[dict], loc: int) -> float:
    d = 0.0
    for ln in lines:
        lf, lt = ln["location_id"][0], ln["location_dest_id"][0]
        q = float(ln["quantity"])
        if lt == loc and lf != loc:
            d += q
        elif lf == loc and lt != loc:
            d -= q
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--default-code", required=True)
    ap.add_argument("--desde", default="2026-04-01")
    ap.add_argument("--location-id", type=int, default=LOC_EXISTENCIAS)
    ap.add_argument(
        "--delimiter",
        choices=["comma", "tab", "semicolon"],
        default="comma",
        help="Separador: comma (CSV Excel internacional), tab (TSV), semicolon (Excel ES-AR)",
    )
    args = ap.parse_args()
    delim_map = {"comma": ",", "tab": "\t", "semicolon": ";"}
    delim_char = delim_map[args.delimiter]
    ext = ".tsv" if args.delimiter == "tab" else ".csv"

    db, uid, pwd, models = _connect()
    prods = _search_read(
        models, db, uid, pwd, "product.product",
        [["default_code", "=", args.default_code]],
        ["id", "display_name", "default_code"],
    )
    if not prods:
        print(f"Producto no encontrado: {args.default_code}", file=sys.stderr)
        return 1
    prod = prods[0]
    pid = prod["id"]
    loc = args.location_id

    dom_pre = [
        ["product_id", "=", pid],
        ["state", "=", "done"],
        ["date", "<", f"{args.desde} 00:00:00"],
        "|",
        ["location_id", "=", loc],
        ["location_dest_id", "=", loc],
    ]
    lines_pre = _search_read(
        models, db, uid, pwd, "stock.move.line", dom_pre,
        ["quantity", "location_id", "location_dest_id"],
        limit=0,
    )
    saldo_inicial = _delta_saldo(lines_pre, loc)

    dom = [
        ["product_id", "=", pid],
        ["state", "=", "done"],
        ["date", ">=", f"{args.desde} 00:00:00"],
        "|",
        ["location_id", "=", loc],
        ["location_dest_id", "=", loc],
    ]
    fields = [
        "id", "date", "reference", "origin", "quantity",
        "location_id", "location_dest_id", "picking_id", "picking_code",
        "description_picking", "picking_partner_id",
    ]
    lines = _search_read(
        models, db, uid, pwd, "stock.move.line", dom, fields,
        order="date asc, id asc", limit=0,
    )

    quants = _search_read(
        models, db, uid, pwd, "stock.quant",
        [["product_id", "=", pid], ["location_id", "=", loc]],
        ["quantity", "reserved_quantity"],
        limit=1,
    )
    qty_odoo = float(quants[0]["quantity"]) if quants else 0.0
    res_odoo = float(quants[0]["reserved_quantity"]) if quants else 0.0

    rows: list[dict] = []
    saldo = saldo_inicial
    entradas = 0.0
    salidas = 0.0
    por_tipo: dict[str, dict[str, float]] = defaultdict(
        lambda: {"entradas": 0.0, "salidas": 0.0, "movimientos": 0}
    )

    for ln in lines:
        loc_from_id = ln["location_id"][0]
        loc_to_id = ln["location_dest_id"][0]
        loc_from = ln["location_id"][1]
        loc_to = ln["location_dest_id"][1]
        qty = float(ln["quantity"])
        ref = ln["reference"] or ""
        origin = ln.get("origin") or ""
        tipo, sentido = _clasificar(ref, loc_from_id, loc_to_id, loc)

        delta = 0.0
        if loc_to_id == loc and loc_from_id != loc:
            delta = qty
            entradas += qty
            por_tipo[tipo]["entradas"] += qty
        elif loc_from_id == loc and loc_to_id != loc:
            delta = -qty
            salidas += qty
            por_tipo[tipo]["salidas"] += qty
        else:
            continue
        por_tipo[tipo]["movimientos"] += 1
        saldo += delta

        rows.append({
            "nro": len(rows) + 1,
            "fecha": (ln["date"] or "")[:19].replace("T", " "),
            "tipo_operacion": tipo,
            "sentido": sentido,
            "referencia": ref,
            "origen_documento": origin,
            "cantidad_movimiento": _fmt_num(qty),
            "delta_existencias": _fmt_num(delta),
            "saldo_existencias_corrido": _fmt_num(saldo),
            "ubicacion_origen": loc_from,
            "ubicacion_destino": loc_to,
            "codigo_picking": ln.get("picking_code") or "",
            "motivo": _motivo(tipo, sentido, ref, origin, loc_from, loc_to),
        })

    saldo_teorico = saldo
    brecha = qty_odoo - saldo_teorico

    por_mes: dict[str, dict[str, float]] = defaultdict(
        lambda: {"entradas": 0.0, "salidas": 0.0, "movimientos": 0}
    )
    for r in rows:
        mes = r["fecha"][:7]
        d = float(r["delta_existencias"])
        por_mes[mes]["movimientos"] += 1
        if d > 0:
            por_mes[mes]["entradas"] += d
        else:
            por_mes[mes]["salidas"] += -d

    first_stor = next((r for r in rows if r["tipo_operacion"] == "RECEPCION_STOR"), None)
    picks_antes_stor = (
        sum(1 for r in rows if r["tipo_operacion"] == "PICK_EXPEDICION" and first_stor
            and r["fecha"] < first_stor["fecha"])
        if first_stor
        else 0
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cod = args.default_code.replace("/", "_")
    out = _out_dir()
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / f"historico_cen_{cod}_{args.desde}_{ts}{ext}"
    csv_fields = list(rows[0].keys()) if rows else []

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=csv_fields,
            delimiter=delim_char,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        w.writeheader()
        w.writerow({
            "nro": 0,
            "fecha": args.desde,
            "tipo_operacion": "SALDO_INICIAL",
            "sentido": "—",
            "referencia": "Saldo al inicio del período (movimientos anteriores)",
            "origen_documento": "",
            "cantidad_movimiento": _fmt_num(saldo_inicial),
            "delta_existencias": "0",
            "saldo_existencias_corrido": _fmt_num(saldo_inicial),
            "ubicacion_origen": "CEN/Existencias",
            "ubicacion_destino": "",
            "codigo_picking": "",
            "motivo": (
                f"Stock en CEN/Existencias al {args.desde} según historial Odoo "
                f"(suma de movimientos previos)."
            ),
        })
        w.writerows(rows)

    md_path = _docs_dir() / f"{cod}_HISTORICO_STOCK_CEN.md"
    loc_name = "CEN/Existencias"
    tipo_rows = sorted(por_tipo.items(), key=lambda x: -(x[1]["entradas"] + x[1]["salidas"]))
    tipo_md = "\n".join(
        f"| {t} | {int(v['movimientos'])} | {_fmt_num(v['entradas'])} | {_fmt_num(v['salidas'])} |"
        for t, v in tipo_rows
    )
    mes_md = "\n".join(
        f"| {m} | {int(v['movimientos'])} | {_fmt_num(v['entradas'])} | {_fmt_num(v['salidas'])} |"
        for m, v in sorted(por_mes.items())
    )
    alerta_stor = ""
    if first_stor and picks_antes_stor:
        alerta_stor = f"""
> **Atención auditoría:** hay **{picks_antes_stor} pickings** con salida de Existencias **antes** del primer ingreso STOR ({first_stor['fecha'][:10]}, {first_stor['referencia']}). El saldo corrido arranca en 0 el {args.desde} pero Odoo permitió expedir sin recepción documentada en Existencias en esas fechas (stock negativo o saldo inicial no registrado en movimientos).
"""

    md = f"""# Histórico de stock — {prod['display_name']}

**Código:** `{args.default_code}` · **Producto Odoo id:** {pid}  
**Ubicación analizada:** {loc_name} (id {loc})  
**Período:** desde **{args.desde}** hasta **{datetime.now():%Y-%m-%d %H:%M}** (fecha de generación)  
**Base de datos:** master_dev (`nakel.net.ar`)

---

## 1. Resumen ejecutivo

| Concepto | Unidades |
|----------|--------:|
| **Saldo al {args.desde}** (movimientos anteriores en Existencias) | **{_fmt_num(saldo_inicial)}** |
| **Entradas** en el período (suma movimientos que ingresan a Existencias) | **{_fmt_num(entradas)}** |
| **Salidas** en el período (suma movimientos que salen de Existencias) | **{_fmt_num(salidas)}** |
| **Saldo teórico** al cierre (inicial + entradas − salidas, suma lineal de deltas) | **{_fmt_num(saldo_teorico)}** |
| **Saldo Odoo hoy** (`stock.quant` en Existencias) | **{_fmt_num(qty_odoo)}** |
| **Reservado** (comprometido en pickings, aún en Existencias) | **{_fmt_num(res_odoo)}** |
| **Disponible** (cantidad − reservado) | **{_fmt_num(qty_odoo - res_odoo)}** |
| **Brecha** saldo Odoo − saldo teórico | **{_fmt_num(brecha)}** |

**Movimientos en el período:** {len(rows)} líneas (`stock.move.line`, estado *Hecho*).
{alerta_stor}
### Nota sobre el saldo corrido

La columna **saldo corrido** del CSV es la suma aritmética de deltas (entrada + / salida −). Los **ajustes de inventario** en Odoo fijan la cantidad contada en el quant; por eso el saldo corrido puede **no coincidir** con el `stock.quant` en fechas de conteo (caso 12/05: movimiento −2.206 u vs conteo físico 2.206 u). Para auditoría, use el CSV línea a línea y el saldo Odoo del día en pantalla Inventario.

---

## 2. Entradas y salidas por tipo de operación

| Tipo | Movimientos | Entradas (+) | Salidas (−) |
|------|------------:|-------------:|------------:|
{tipo_md}

### Lectura rápida

- **RECEPCION_STOR:** ingreso de compra / almacenaje a Existencias (ej. `CEN/STOR/00101` **+1.080 u** el 17/04).
- **PICK_EXPEDICION:** preparación de pedidos (Existencias → Salida); no es venta al cliente aún.
- **TRASLADO_SUCURSAL:** envío a B1/B2/B3/B4.
- **AJUSTE_INVENTARIO:** conteos y correcciones IT (mayo 2026: +2.250, +145, −2.206, +2.200 u).

---

## 3. Resumen por mes

| Mes | Movimientos | Entradas (+) | Salidas (−) |
|-----|------------:|-------------:|------------:|
{mes_md}

---

## 4. Primer movimiento en Existencias en el período

"""
    first_in = next(
        (r for r in rows if r["sentido"] == "ENTRADA" and r["tipo_operacion"] != "AJUSTE_INVENTARIO"),
        None,
    )
    if first_in:
        md += (
            f"**{first_in['fecha']}** — {first_in['referencia']}: "
            f"**+{first_in['cantidad_movimiento']} u** ({first_in['motivo']})\n"
        )
    else:
        md += "No hay entradas no-inventario en el período.\n"

    md += f"""
---

## 5. Archivo detallado (cliente técnico)

CSV con **cada movimiento**, motivo en lenguaje operativo, origen del documento (OV/pedido cuando existe), saldo corrido:

`correcciones/OUT/{csv_path.name}`

Columnas: `nro`, `fecha`, `tipo_operacion`, `sentido`, `referencia`, `origen_documento`, `cantidad_movimiento`, `delta_existencias`, `saldo_existencias_corrido`, ubicaciones, `motivo`.

Regenerar:

```bash
python3 nakel_odoo/tools/inventario/informe_historico_stock_cen_master_dev.py \\
  --default-code {args.default_code} --desde {args.desde}
```

---

## 6. Relacionado

- `8209.00_RECONCILIACION_STOCK.md` — análisis del conteo Angel y brecha −120  
- `8209.00_CHOCOLATINA_TRIO_INFORME_ANGEL.md` — informe operativo

*Generado automáticamente desde Odoo master_dev.*
"""
    md_path.write_text(md, encoding="utf-8")

    print(csv_path)
    print(md_path)
    print(
        f"Saldo {args.desde}: {saldo_inicial} | +{entradas} -{salidas} = {saldo_teorico} | "
        f"Odoo hoy: {qty_odoo} (brecha {brecha}) | Movs: {len(rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
