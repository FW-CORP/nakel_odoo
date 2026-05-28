# Olas WAVE + Barcode — Flujo de módulos e impacto en stock

**Fecha:** 2026-05-25  
**Contexto:** Nakel Central (CEN), Odoo 18, olas `WAVE/`, Barcode, inventario desalineado con piso.

Módulos Nakel aplicados en este flujo:

| Módulo | Rol |
|--------|-----|
| `nakel_wave_planner` | Armar ola por zona/vendedor (checklist OV → WAVE) |
| `nakel_wave_picking_link` | Enlace OV ↔ ola (`nakel_wave_batch_id`), salud ola, OUT |
| `nakel_barcode_wave_demand_mode` | Semáforo, Modo demanda OV, Ver faltantes, Agregar a ola |
| `nakel_fix_pick` | Sincronía `picked` / `qty_done` con Barcode |

---

## 1. Flujo operativo completo (supervisor + operario)

```mermaid
flowchart TD
    subgraph PLANIFICAR["1 — Planificar ola"]
        A[OV confirmadas por zona/vendedor] --> B[nakel_wave_planner]
        B --> C[Crear WAVE + agregar PICKs]
        C --> D[nakel_wave_picking_link<br/>nakel_wave_batch_id en OV/PICK/OUT]
    end

    subgraph SEMAFORO["2 — Semáforo cobertura OV"]
        D --> E{Semáforo<br/>demand_mode}
        E -->|ROJO| F[Ver faltantes]
        F --> G[Agregar a la ola<br/>relanzar PICK si falta]
        G --> H{Opcional:<br/>Modo demanda OV}
        H --> E
        E -->|AMARILLO| I[Modo demanda OV]
        I --> J[VERDE OK]
        E -->|VERDE| J
    end

    subgraph BARCODE["3 — Pickeo en piso"]
        J --> K[Barcode — ola WAVE]
        K --> L[Operario escanea / confirma qty real]
        L --> M[nakel_fix_pick<br/>picked + qty_done alineados]
    end

    subgraph ENTREGA["4 — Entrega y factura"]
        M --> N[Validar PICK / ola]
        N --> O[OUT vinculado a OV]
        O --> P[Validar OUT]
        P --> Q[Factura según qty entregada]
    end

    style E fill:#fef3cd
    style J fill:#d4edda
    style F fill:#f8d7da
```

---

## 2. Semáforo — decisión antes de Barcode

```mermaid
flowchart LR
    START([Abrir ola WAVE]) --> CHECK[nakel_barcode_wave_demand_mode<br/>evalúa cobertura OV]

    CHECK --> RED{¿Faltan productos<br/>del pedido en la ola?}
    RED -->|Sí| R[🔴 Cobertura OV<br/>Ver faltantes]
    R --> ADD[Agregar a la ola]
    ADD --> CHECK

    RED -->|No| YEL{¿Reserva Odoo<br/>menor al pedido?}
    YEL -->|Sí| Y[🟡 Modo demanda<br/>Subir quantity a demanda OV]
    Y --> CHECK

    YEL -->|No| G[🟢 Demanda OV OK]
    G --> BC([Barcode])

    style R fill:#f8d7da
    style Y fill:#fff3cd
    style G fill:#d4edda
```

---

## 3. Modo demanda OV — qué toca y qué NO toca

```mermaid
flowchart TB
    subgraph INPUT["Entrada"]
        OV[sale.order.line<br/>product_uom_qty = DEMANDA cliente]
        MOVE[stock.move en PICK<br/>product_uom_qty = demanda move]
        QUANTS[(stock.quant<br/>stock físico Odoo)]
    end

    subgraph DEMAND["Modo demanda OV"]
        DM[nakel_barcode_wave_demand_mode]
        DM --> ML[stock.move.line.quantity<br/>← product_uom_qty del move]
        DM -.->|NO modifica| QD[qty_done]
        DM -.->|NO modifica| PK[picked = False]
        DM -.->|NO mueve| QUANTS
    end

    subgraph BARCODE2["Barcode después"]
        ML --> UI[UI muestra tope:<br/>qty_done / quantity]
        UI --> OP[Operario pickea cantidad REAL]
        OP --> QD2[qty_done = lo pickeado]
    end

    OV --> MOVE
    MOVE --> DM
    QUANTS -.->|reserva estándar<br/>puede ser parcial| MOVE

    style QUANTS fill:#e9ecef
    style DM fill:#fff3cd
```

**Resumen Modo demanda OV:**

| Campo / objeto | ¿Lo modifica? | Efecto |
|----------------|---------------|--------|
| `stock.move.product_uom_qty` | No | Sigue siendo demanda OV |
| `stock.move.line.quantity` | **Sí** | Tope Barcode = pedido OV |
| `stock.move.line.qty_done` | No | Lo pone Barcode al escanear |
| `stock.move.line.picked` | No (False) | No marca verde sin escanear |
| `stock.quant` | **No** | No mueve stock real |
| Reserva Odoo | Bypass SQL en v18 | Evita capa por quants insuficientes |

---

## 4. Mapa de módulos vs capas de Odoo

```mermaid
flowchart TB
    subgraph MODS["Módulos Nakel"]
        WP[nakel_wave_planner]
        WL[nakel_wave_picking_link]
        DM[nakel_barcode_wave_demand_mode]
        FP[nakel_fix_pick]
    end

    subgraph ODOO["Capas Odoo"]
        SO[sale.order / líneas OV]
        BATCH[stock.picking.batch WAVE]
        PICK[stock.picking PICK]
        MOVE[stock.move]
        ML[stock.move.line]
        QUANT[stock.quant]
        OUT[stock.picking OUT]
        INV[account.move factura]
    end

    WP -->|picking_ids| BATCH
    WP -->|opcional demand mode| DM
    WL -->|nakel_wave_batch_id| SO
    WL -->|nakel_wave_batch_id| PICK
    WL -->|propaga| OUT
    DM -->|quantity demanda| ML
    DM -->|semáforo| BATCH
    FP -->|picked, qty_done| ML

    SO --> PICK
    PICK --> MOVE
    MOVE --> ML
    ML -.->|reserva| QUANT
    PICK --> OUT
    OUT -->|qty_done entregado| INV

    style QUANT fill:#ffe6e6
    style INV fill:#e6f3ff
```

---

## 5. Impacto en STOCK — matriz por etapa

| Etapa | Módulo | ¿Mueve stock real (`stock.quant`)? | ¿Qué registra? |
|-------|--------|-------------------------------------|----------------|
| Armar ola (planner) | `nakel_wave_planner` | **No** | Agrupa PICK en `batch_id` |
| Enlace OV/ola | `nakel_wave_picking_link` | **No** | Campo `nakel_wave_batch_id` |
| Semáforo / Ver faltantes | `demand_mode` | **No** | Solo lectura + alertas |
| Agregar a la ola | `demand_mode` | **No** | Crea/agrega PICK (`_action_launch_stock_rule`) |
| Modo demanda OV | `demand_mode` | **No** | Sube `move.line.quantity` (tope UI) |
| Barcode pickeo | Odoo + `nakel_fix_pick` | **No** (aún) | `qty_done`, `picked` |
| Validar PICK | Odoo estándar | **Sí** ↓ origen | Sale de Existencias (según config) |
| Validar OUT | Odoo estándar | **Sí** → cliente | Entrega real |
| Facturar | Odoo ventas | **No** (contabilidad) | Importe = lo entregado |

```mermaid
sequenceDiagram
    participant OV as OV / Pedido
    participant WAVE as Ola WAVE
    participant DM as Modo demanda
    participant BC as Barcode
    participant FP as nakel_fix_pick
    participant Q as stock.quant
    participant OUT as OUT
    participant FAC as Factura

    OV->>WAVE: planner agrega PICK
    Note over WAVE,DM: Sin movimiento de stock
    WAVE->>DM: quantity := demanda OV
    Note over DM,Q: NO toca quants
    DM->>BC: tope = pedido (ej. 10 u)
    BC->>FP: qty_done = real (ej. 8 u)
    Note over BC,Q: Aún sin mover quants
    BC->>OUT: validar PICK
    OUT->>Q: movimiento stock real
    OUT->>FAC: factura 8 u entregadas
```

---

## 6. Cadena de cantidades (dónde puede “trabar” Barcode)

```text
OV pide 10 u
    │
    ▼
stock.move.product_uom_qty = 10        ← demanda OV (verdad comercial)
    │
    ▼
stock.move.line.quantity = ?           ← tope Barcode
    │   ├── Sin modo demanda + reserva parcial → 1  ❌
    │   └── Con modo demanda o reserva OK → 10      ✅
    ▼
stock.move.line.qty_done = ?           ← lo que pickeó el operario (0–10)
    │   └── nakel_fix_pick alinea picked / qty_done
    ▼
Validar PICK → OUT → Factura = qty_done entregado
```

---

## 7. Parámetros del sistema (activación)

| Clave | Valor Nakel CEN | Efecto |
|-------|-----------------|--------|
| `nakel_barcode_wave_demand_mode.enable` | `1` | Semáforo + botones |
| `nakel_barcode_wave_demand_mode.apply_on` | `pick` | Solo CEN/PICK |
| `nakel_barcode_wave_demand_mode.warehouses` | vacío o `14` | Alcance almacén |
| `nakel_barcode_wave_demand_mode.include_so_sibling_picks` | `1` | PICK hermanos OV |
| `nakel_fix_pick.enable` | `1` | Sync picked/qty_done |

---

## 8. Regla operativa (una línea)

```text
Planner arma ola → Semáforo verde → Barcode confirma REALIDAD → OUT mueve stock → Factura lo entregado
```

Modo demanda OV solo alinea **Odoo con el pedido** antes de Barcode; **no sustituye** el pickeo ni mueve stock hasta validar.

---

## Referencias

- [BARCODE_OLA_MODO_DEMANDA_PLAN.md](BARCODE_OLA_MODO_DEMANDA_PLAN.md)
- [nakel_barcode_wave_demand_mode/README.md](../../addons/nakel_barcode_wave_demand_mode/README.md)
- [nakel_wave_planner/README.md](../../addons/nakel_wave_planner/README.md)
