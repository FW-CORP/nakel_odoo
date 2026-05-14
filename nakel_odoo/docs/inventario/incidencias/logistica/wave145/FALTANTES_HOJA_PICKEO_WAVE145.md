# WAVE/00145 — Faltantes marcados en hoja de picking (F / X)

Listado operativo para buscar en **PICK / OUT** y **OV**. Los datos de piso vienen de las **fotos de la hoja impresa** (marcas **F** o **X** / resaltado naranja o amarillo). La columna **OV / PICK / OUT** se cruza con **`master_dev`** usando dominio **`nakel_wave_batch_id = 151`** en `stock.picking` (misma ola que `stock.picking.batch` **151** `WAVE/00145`).

**Flujo:** se van sumando páginas al cuadro; cuando termines de pasar la hoja, este archivo sirve de **checklist** antes de **SYNC / validar** la ola en Odoo.

**Importante:** las cantidades de la hoja pueden no coincidir al 100 % con `product_uom_qty` en Odoo si el PDF agrupa líneas o hubo cambios después de armar la ola. Antes de ajustar stock, **verificar en el formulario** del PICK/OUT.

---

## Cuadro unificado (todas las páginas aportadas hasta ahora)

| Pág. | Marca | Código | Producto (texto hoja) | Cant. hoja | Notas piso | OV | PICK | OUT (referencia) |
|-----:|:-----:|--------|----------------------|------------:|-------------|-----|------|-------------------|
| 7/61 | X / F | **3870.15** | YERBA REI VERDE EXPORT TRADICIONAL X500G.-445- | 6 | Faltante total | **S04277** | `CEN/PICK/03996` | `CEN/OUT/02213` |
| 7/61 | X / F | **3870.25** | YERBA REI VERDE PREMIUM X500G.-711- | 11 | Faltante en hoja; en Odoo hay líneas en **dos** OV | **S04277** + **S04295** | `CEN/PICK/04080` + `CEN/PICK/04083` | `CEN/OUT/02213` + `CEN/OUT/02210` |
| 7/61 | X / F | **3870.35** | YERBA REI VERDE PADRON ARGENTINO X500G.-742- | 6 | Faltante total | **S04277** | `CEN/PICK/03996` | `CEN/OUT/02213` |
| 9/61 | X | **4114.10** | PRONTO SHAKE X1L.-563-639- | 24 | Faltante total | **S04114** | `CEN/PICK/03983` | `CEN/OUT/02194` |
| 11/61 | X | **4163.00** | WHISKY WHITE HORSE X750ML | 3 | Faltante total | **S04164** | `CEN/PICK/03987` | `CEN/OUT/02201` |
| 11/61 | X | **4025.36** | GIN GORDON'S X700ML-267 | 2 | Faltante total | **S04277** | `CEN/PICK/03996` | `CEN/OUT/02213` |
| 11/61 | F (−3) | **4092.10** | VODKA SERNOVA WILD BERRIES X700ML.-527- | 9 impreso | Anotación **F 3** = faltan **3** de 9 (salieron **6**) | **S04164** | `CEN/PICK/04073` | `CEN/OUT/02201` |
| 12/61 | X | **8869.60** | GALL.CEREAL MIX AVENA-FRUTILLA X150G.-936- | 24 | Faltante total (único F/X en la página) | **S04282** | `CEN/PICK/03997` | `CEN/OUT/02212` |
| 13/61 | F (−12) | **5023.12** | ELEMENTOS MALBEC X750ML.-028- | 24 impreso | Anotación **F 12** = faltan **12** u. de **24** | **Tres OV** (ver nota **5023.12** abajo) | `04083` / `04073` / `04084` | `02210` / `02201` / `02209` |
| 13/61 | F | **27201** | TRUMPETER MALBEC X750ML. | 12 | **F** en hoja (misma pág. 13) | **S04295** + **S04300** | `CEN/PICK/04083` + `CEN/PICK/04084` | `CEN/OUT/02210` + `CEN/OUT/02209` |
| 14/61 | F | **5033.10** | EMILIA CABERNET SAUVIGNON X750ML.-316- | 6 | Faltante **6** u. (coincide con demanda en hoja) | **S04114** | `CEN/PICK/03983` | `CEN/OUT/02194` |
| 14/61 | F | **5081.18** | UXMAL BRAVIO MALBEC X 750ML | 6 | Faltante **6** u. | **S04300** | `CEN/PICK/04000` | *(sin OUT en ola al leer; ver nota **5081.18**)* |
| 14/61 | F | **1806.00** | BAGGIO NARANJA 18X200ML | 5 (hoja) | Faltante en piso; ver nota **1806.00** | **S04184** | `CEN/PICK/03991` | *(sin OUT en ola al leer)* |
| 15/61 | F | **1809.1** | BAGGIO MANZANA X1L.-336- (8) | 40 | Piso **40** u.; en Odoo = **24** u. (OV **S04184**, `03991`) + **16** u. (OV **S04152**, `03986` / `02200`) | **S04184** + **S04152** | `CEN/PICK/03991` + `CEN/PICK/03986` | `CEN/OUT/02200` (parte **S04152**) |
| 15/61 | F | **1809** | BAGGIO NARANJA X1L.-329- (8) | 16 | En ola figura **1** movimiento **`cancel`** 16 u. (`CEN/PICK/03986`, **S04152**) | **S04152** | `CEN/PICK/03986` | — |
| 15/61 | F | **1812** | BAGGIO NARANJA X1.5L.-606- (8) | 64 (piso) | Ver nota **1812** (suma Odoo vs hoja) | **S04184** + **S04152** (+ **S04366** `cancel`) | `03991` / `03986` / `04008` | `02200` |
| 15/61 | F (−4) | **4106.30** | TERMA LIMON X1350ML.-271- | 6 impreso | **F 4** = faltan **4** u.; en catálogo **no** usar **4106.20** (es **Terma pomelo**) | **S04122** | `CEN/PICK/03984` | `CEN/OUT/02198` |
| 15/61 | F (−18) | **4106.60** | TERMA SERRANO X1350ML.-318- | 30 (piso) | **F 18**; coincide con doc §3 `partially_available` (demanda/reserva) | **S04122** | `CEN/PICK/04070` | `CEN/OUT/02198` |
| 15/61 | F | **5326.30** | JUGO NOEL EN POLVO MANZANA 18X16G.-754- | 1 | Faltante **1** u. | **S04152** | `CEN/PICK/03986` | `CEN/OUT/02200` |
| 16/61 | F (−2) | **152.15** | TANG NARANJA-DURAZNO 20X15G. | 4 impreso | **F 2** = faltan **2** de **4** | **S04184** + **S04152** | `03991` + `03986` | `02200` |
| 17/61 | F (−24) | **1809.05** | BAGGIO NARANJA 100% EXPRIMIDO X1L.-488- (12) | 60 impreso | **F 2B** ≈ faltan **2 bultos** = **24** u. | **S04184** + **S04152** | `04076` / `04072` | `02237` / `02200` |
| 18/61 | F | **8615.10** | POXI-RAN TRANSPARENTE CHICO X23G.-3312- (6) | 6 | Faltante **6** u. | **S04321** | `CEN/PICK/04001` | *(sin OUT en ola al leer)* |
| 18/61 | F | **8616.00** | POXI-RAN MEDIANO X45G.-1308- | 6 | Faltante **6** u. | **S04264** | `CEN/PICK/04079` | `CEN/OUT/02214` |
| 18/61 | F (−15) | **8678.00** | POXIMIX EXTERIOR CHICO X500G.-519- | 16 impreso | **F 15** en hoja; ver nota **8678.00** | **S04200** | `CEN/PICK/03993` | *(sin OUT en ola al leer)* |
| 19/61 | X | **8736.2** | ZOCALO POXIBAND DOBLE 95CM NEGRO X1U.-273- | 12 | Faltante **12** u. (código catálogo **8736.2**) | **S04101** | `CEN/PICK/04064` | `CEN/OUT/02190` |
| 19/61 | X | **8712.00** | WD-40 X311G.-813-2181- | 30 | Demanda **PICK** en ola **30** u. repartida (ver nota **8712.00**) | **S04264** + **S04358** + **S04200** | `03995` / `04004` / `03993` | `02205` (parte **S04358**) |
| 19/61 | X | **8654.00** | FASTIX ALTA TEMPERATURA GRANDE X100ML.-1066- | 26,12 | Misma referencia que §3 `partially_available` **S04200**; hay **más** líneas en otras OV (ver nota **8654.00**) | **S04101** + **S04200** + **S04358** + **S04264** | `04064` / `04078` / `04004` / `03995` | `02190` / `02205` |
| 22/61 | F (−2) | **8220.70** | PEPAS CON CHIPS EL TRIO X500G.-672- | 12 impreso | **F 2** = faltan **2** de **12** | **S04329** | `CEN/PICK/04086` | `CEN/OUT/02207` |
| 22/61 | F | **8220.80** | GLASY EL TRIO X500G.-450- | 10 | Faltante **10** u. (línea completa) | **S04329** | `CEN/PICK/04002` | `CEN/OUT/02207` |
| 22/61 | F | **BIZ0128** | SCONCITOS 9 DE ORO LIMON X180G.-524- | 58 (hoja) | Ver nota **BIZ0128** (suma Odoo vs hoja) | **S04300** + **S04321** + **S04329** | `04000` / `04001` / `04002` | `02207` (parte **S04329**) |
| 23/61 | X | **BIZ0222** | BRIGITTE 9 DE ORO CHOC.RELL.LIMON X120G.-135- | 4 | Faltante **4** u.; en Odoo PICK **16** u. y OUT **4** u. (**S04329**) | **S04329** | `CEN/PICK/04086` | `CEN/OUT/02207` |
| 23/61 | X | **1630** | CUBANITO OBLITA DULCE DE LECHE X48U. | 1 | Faltante **1** u. | **S04114** | `CEN/PICK/04069` | `CEN/OUT/02194` |
| 24/61 | F | **8816** | MAGDALENA GAONA RELL.CHOCOLATE X200G.-918- | 30 | Faltante **30** u. (**10**+**10**+**10** en tres OV) | **S04097** + **S04179** + **S04290** | `04063` / `04075` / `04082` | `02189` / `02236` / `02211` |
| 24/61 | F | **2720** | PALMERITAS HOJALMAR X150G. | 36 | Faltante **36** u. (**18**+**18** en dos OV) | **S04295** + **S04300** | `03999` / `04000` | *(OUT en batch no listado al leer)* |
| 24/61 | F | **2535.05** | VAINILLAS POZO X296G.-104- | 12 | Faltante **12** u. | **S04184** | `03991` | *(sin OUT en ola al leer)* |
| 24/61 | F | **2535.07** | VAINILLAS POZO X444G.-135- | 12 | Faltante **12** u. | **S04184** | `03991` | *(OUT en batch no listado al leer)* |
| 24/61 | F | **2535.1** | MAGDALENA POZO X200G.-364- | 19 | Hoja **19** u.; PICK **9** u. `partially_available` + **10** u. `done` (ver nota **2535.1**) | **S04179** + **S04290** | `03990` / `03998` | `02211` — *(**S04179**: OUT en batch no listado al leer)* |
| 24/61 | F | **2535.2** | MAGDALENA POZO CON CHIPS X200G.-722- | 10 | Faltante **10** u. | **S04179** | `04075` | `02236` |
| 24/61 | F | **2535.5** | MAGDALENA POZO MARMOLADA X200G.-739- | 20 | Faltante **20** u.; reparto **S04179** / **S04290** (ver nota **2535.5**) | **S04179** + **S04290** | `03990` / `03998` | `02211` |
| 25/61 | F | **8357.30** | OREO ORIGINAL X182.5G. | 21 | Faltante **21** u.; ver nota **Pág. 25** | **S04300** | `04084` | `02209` |
| 25/61 | F | **1343** | OBLEA OBLITA MIX FRUTAL X50G.-431- | 12 | Faltante **12** u.; ver nota **Pág. 25** | **S04122** | `03984` | `02198` |
| 25/61 | F | **1392** | OBLEA OBLITA FRUTILLA X100G. | 12 | Faltante **12** u.; ver nota **Pág. 25** | **S04300** | `04084` | `02209` |
| 26/61 | F | **8101.10** | OPERA X92G. | 98 | Hoja **98** u.; PICK activo **14** u. + **`cancel`** **84** u. (ver nota **8101.10**) | **S04114** | `CEN/PICK/03983` | `CEN/OUT/02194` |
| 26/61 | F | **8174.10** | AMOR X108G. | 72 | Faltante **72** u. (= **18**+**18**+**36** en tres OV) | **S04122** + **S04179** + **S04355** | `04070` / `04075` / `04087` | `02198` / `02236` / `02206` |
| 26/61 | F | **8175.10** | MELLIZAS X108G. | 72 | Hoja **72** u.; PICK activos **36** u. + **`cancel`** **36** u. (ver nota **8175.10**) | **S04097** + **S04179** | `03977` / `03990` | `02189` — *(**S04179**: PICK `03990` `confirmed`; OUT en batch no listado al leer)* |
| 26/61 | F | **8880.30** | MANA RELLENA VAINILLA-CHOCOLATE X152G. | 24 | Faltante **24** u. (**12**+**12** en dos OV) | **S04179** + **S04198** | `03990` / `03992` | `02216` — *(**S04179**: PICK `03990` `assigned`; OUT en batch no listado al leer)* |
| 27/61 | F | **2820.83** | GALL.CACHAFAZ GRA/AVE/ALM/MANI X225G.-707- | 6 | Faltante **6** u. | **S04321** | `CEN/PICK/04085` | `CEN/OUT/02208` |
| 27/61 | F | **8869.15** | GALL.CEREAL MIX FRUTILLA Y CHIA X207G. | 24 | Faltante **24** u. | **S04282** | `CEN/PICK/03997` | `CEN/OUT/02212` |
| 27/61 | F | **8153.00** | SURTIDO BAGLEY X400G.-720- | 84 | Hoja **84** u.; **cuatro** PICK **21** u. (`03984`/`03990` activos + `03986`/`03998` **`cancel`**) — ver nota **8153.00** | **S04122** + **S04179** + **S04152** + **S04290** | `03984` / `03990` / `03986` / `03998` | `02198` |
| 28/61 | F | **115** | BIZ.DON SATUR X200G.-328- | 60 | Faltante **60** u. (= **30**+**30** en dos OV) | **S04321** + **S04295** | `04085` / `04083` | `02208` / `02210` |
| 28/61 | F | **8129.00** | CRIOLLITAS TRIPLE 3X100G. | 112 (hoja) | Faltante en piso; ver nota **8129.00** | **S04179** + **S04164** | `03990` / `03987` | `02201` |
| 28/61 | F | **8341.00** | EXPRESS X101G.-461- | 24 | Faltante **24** u. | **S04321** | `CEN/PICK/04001` | *(sin OUT en ola al leer)* |
| 29/61 | F | **1163.50** | KESITAS BOLSA X250G.-033- | 16 | Faltante **16** u. (línea completa) | **S04089** | `CEN/PICK/04062` | `CEN/OUT/02188` |
| 29/61 | F (−6) | **8885.00** | SALADIX PIZZA X100G. | 18 impreso | **F 6** = faltan **6** de **18** | **S04089** | `CEN/PICK/03976` | `CEN/OUT/02188` |
| 29/61 | F | **8885.20** | SALADIX CALABRESA X100G. | 6 | Faltante **6** u. | **S04122** | `CEN/PICK/03984` | `CEN/OUT/02198` |
| 29/61 | F | **3530.15** | MACROBIOTICA MULTICEREAL X102G.-608-345- | 12 | Faltante **12** u. | **S04361** | `CEN/PICK/04007` | `CEN/OUT/02203` |
| 31/61 | F | **7.71** | ALF.TATIN TRIPLE BLANCO X60G.-301- (21) | 21 | Faltante **21** u. (1 bulto) | **S04122** | `CEN/PICK/04070` | `CEN/OUT/02198` |
| 32/61 | F | **9.70** | ALF.OREO TRIPLE X56G. (36) | 36 | En Odoo repartido **18**+**18** (dos OV) | **S04110** + **S04097** | `03982` / `03977` | `02197` / `02189` |
| 32/61 | F | **9.90** | ALF.PEPITOS TRIPLE X57G. (36) | 36 | Faltante **36** u. | **S04198** | `CEN/PICK/03992` | `CEN/OUT/02216` |
| 33/61 | F | **37.00** | ALF.RASTA BLANCO X70G.-013- (18) | 18 | Faltante **18** u. | **S04114** | `CEN/PICK/03983` | `CEN/OUT/02194` |
| 33/61 | F | **37.10** | ALF.RASTA NEGRO X70G.-202- (18) | 36 | Faltante **36** u. en hoja; ver nota **37.10** | **S04097** | `CEN/PICK/03977` | `CEN/OUT/02189` |
| 33/61 | F | **2006** | FLOW CEREAL FRUTAS X23G.-928- (20) | 20 | Faltante **20** u. | **S04198** | `CEN/PICK/04077` | `CEN/OUT/02216` |
| 34/61 | F | **1124.10** | MASTICABLE FRUTALES ARCOR X800G.-208- | 1 | Faltante **1** u. | **S04152** | `CEN/PICK/03986` | `CEN/OUT/02200` |
| 34/61 | F | **2153.40** | BUTTER TOFFEES BONOBON X822G.-853- | 1 | Faltante **1** u. | **S04114** | `CEN/PICK/03983` | `CEN/OUT/02194` |
| 35/61 | F | **631.20** | BUBBALOO HUELLITAS FRUTILLA 12X15G.-572- | 1 | Faltante **1** u. | **S04363** | `CEN/PICK/04093` | `CEN/OUT/02185` |
| 35/61 | F | **501.20** | SUGUS SURTIDO ESPECIAL X700G.-790- | 8 | Hoja **8** u.; PICK activos en ola **6** u. (**2**×**3** OV abajo); **2** u. en mov. **`cancel`** (`03977` **S04097**, `03986` **S04152**) | **S04108** + **S04110** + **S04366** | `03981` / `03982` / `04008` | `02195` / `02197` / `02202` |
| 35/61 | F | **2109.05** | MENTA CHOCOLATE ARCOR X715G.-273- | 8 | Faltante **8** u. (= **2**×**4** OV) | **S04355** + **S04114** + **S04295** + **S04198** | `04087` / `04069` / `04083` / `04077` | `02206` / `02194` / `02210` / `02216` |
| 36/61 | F | **8817.25** | TOPLINE SEVEN X-PLOSIVE MINT X16U. | 21 | Faltante **21** u. | **S04089** + **S04114** + **S04122** + **S04132** + **S04184** + **S04198** + **S04295** + **S04355** | `04062` / `04069` / `04070` / `04071` / `04076` / `04077` / `04083` / `04087` | `02188` / `02194` / `02198` / `02199` / `02237` / `02216` / `02210` / `02206` |
| 36/61 | F | **8817.40** | TOPLINE SEVEN ATOMIC STRONG X16U.-204- | 21 | Hoja **21** u.; PICK activos **14** u. + **`cancel`** **7** u. (ver nota **8817.40**) | **S04089** + **S04132** + **S04184** + **S04295** | `03976` / `03985` / `03991` / `03999` | `02188` / `02199` — *(**S04184**/**S04295**: PICK `03991`/`03999` `confirmed`; OUT en batch no listado al leer)* |
| 36/61 | F | **8817.55** | TOPLINE 7ULTRA RED BERRY X12U.-115- | 1 | Faltante **1** u. | **S04114** | `CEN/PICK/03983` | `CEN/OUT/02194` |
| 36/61 | F | **8817.60** | TOPLINE 7ULTRA CLEAN MINT X12U.-020- | 1 | Una sola línea en hoja (**1** u.; texto catálogo “clean” / “clean mint” es el mismo SKU) | **S04114** | `CEN/PICK/03983` | `CEN/OUT/02194` |
| 36/61 | F | **8818.00** | TOPLINE MENTA X20U. | 3 | Faltante **3** u. (**1**+**2** en dos OV) | **S04097** + **S04355** | `04063` / `04087` | `02189` / `02206` |
| 36/61 | F | **8818.20** | TOPLINE STRONG X20U. | 1 | Faltante **1** u. | **S04097** | `CEN/PICK/03977` | `CEN/OUT/02189` |
| 36/61 | F | **553.40** | BELDENT INFINIT BLUEBERRY 12X14U.-440- | 7 | Hoja **7** u.; PICK en ola **9** u. (ver nota **553.40**) | **S04114** + **S04132** + **S04152** + **S04198** + **S04300** + **S04321** | `04069` / `04071` / `04072` / `04077` / `04084` / `04085` | `02194` / `02199` / `02200` / `02216` / `02209` / `02208` |
| 37/61 | F | **556.10** | BELDENT MENTA CLASICO X20U. | 12 | Hoja **12** u.; PICK activos **7** u. + **`cancel`** **5** u. (ver nota **556.10** / **556.20**) | **S04114** + **S04132** + **S04295** + **S04300** + **S04321** | `03983` / `03985` / `03999` / `04000` / `04001` | `02194` / `02199` / `02208` — *(**S04295**/**S04300**: PICK `03999`/`04000` `confirmed`; OUT en batch no listado al leer)* |
| 37/61 | F | **556.20** | BELDENT MENTOL X20U. | 11 | Hoja **11** u.; PICK activos **6** u. + **`cancel`** **5** u. (misma terna **`cancel`** que **556.10**; sin línea **S04300**) | **S04114** + **S04132** + **S04295** + **S04321** | `03983` / `03985` / `03999` / `04001` | `02194` / `02199` / `02208` — *(**S04295**: PICK `03999` `confirmed`; OUT en batch no listado al leer)* |
| 37/61 | F | **556.70** | BELDENT MENTA FUERTE X20U.-208- | 11 | Faltante **11** u. | **S04089** + **S04114** + **S04122** + **S04132** + **S04164** + **S04198** + **S04321** | `04062` / `04069` / `04070` / `04071` / `04073` / `04077` / `04085` | `02188` / `02194` / `02198` / `02199` / `02201` / `02216` / `02208` |
| 37/61 | F | **4950420** | CHICLE FIERITA RECARGADO TUTTI X50U.-164- | 2 | Faltante **2** u. | **S04114** | `CEN/PICK/03983` | `CEN/OUT/02194` |
| 37/61 | F | **4950422** | CHICLE FIERITA RECARGADO FRUTILLA X50U.-188- | 1 | Faltante **1** u. | **S04152** | `CEN/PICK/03986` | `CEN/OUT/02200` |
| 37/61 | F | **4950425** | CHICLE FIERITA RECARGADO BANANA X50U.-195- | 3 | Faltante **3** u. (**2**+**1** en dos OV) | **S04114** + **S04152** | `04069` / `04072` | `02194` / `02200` |
| 38/61 | F | **8858.15** | COFLER AIREADO MIXTO X55G. (10) | 35 | Faltante **35** u. (= **10**+**10**+**10**+**5** en cuatro OV) | **S04179** + **S04198** + **S04355** + **S04366** | `03990` / `03992` / `04003` / `04008` | `02216` / `02206` / `02202` — *(**S04179**: PICK `03990` **10** u. `assigned`; OUT en batch no listado al leer)* |
| 39/61 | F | **8853.10** | COFLER RELL.DULCE DE LECHE X38G.-965-(20) | 20 | Faltante **20** u. | **S04295** | `CEN/PICK/04083` | `CEN/OUT/02210` |
| 40/61 | F | **1510** | CHOCOLATIN JACK NEGRO 20X14G.-108- | 2 | Faltante **2** u. (**1**+**1** en dos OV) | **S04089** + **S04110** | `03976` / `03982` | `02188` / `02197` |
| 41/61 | F | **1103.10** | CHOCOLATE MISKY LECHE 30X25G. | 6 | Hoja **6** u.; PICK activos **3** u. (`03990`/`03991`/`04000`); **3** u. **`cancel`** (`03984` **S04122**, `03987` **S04164**, `03992` **S04198**) | **S04179** + **S04184** + **S04300** | `03990` / `03991` / `04000` | *(PICK `confirmed`; OUT en batch no listado al leer)* |
| 41/61 | F | **1103.30** | CHOCOLATE MISKY LECHE 21X50G. | 5 | Hoja **5** u.; PICK activos **4** u. + **`cancel`** **1** u. (`03992` **S04198**) | **S04122** + **S04179** + **S04184** + **S04300** | `03984` / `03990` / `03991` / `04000` | `02198` — *(**S04179**/**S04184**/**S04300**: PICK `confirmed`; OUT en batch no listado al leer)* |
| 41/61 | F (−1) | **972.10** | BOMBON DANCING DISPLAY X50U.-100- | 2 impreso | **F1** en piso: faltan **1** u. de **2** impresos en hoja | **S04103** | `CEN/PICK/03979` | `CEN/OUT/02191` |
| 42/61 | F (−18) | **973.80** | MEGA HAMLET MANI X165G.- | 36 impreso | **F18** = faltan **18** u. de **36** impresos en hoja | **S04184** | `CEN/PICK/03991` | *(OUT en batch no listado al leer)* |
| 42/61 | F (−5) | **1053.10** | TAZA MISKY X100G. (10) | 10 impreso | **F5** = faltan **5** u. de **10**; en catálogo el `default_code` puede llevar **espacio** inicial (` 1053.10`) | **S04366** | `CEN/PICK/04008` | `CEN/OUT/02202` |
| 42/61 | F | **1440.00** | UNTABLE MANTECOL X250G.- | 1 | Faltante **1** u. | **S04122** | `CEN/PICK/04070` | `CEN/OUT/02198` |
| 43/61 | F | **CA-840** | BOCADITO DE DDL FANTOCHE X20U.-596- | 2 | Faltante **2** u. | **S04363** | `CEN/PICK/04011` | `CEN/OUT/02185` |
| 43/61 | F | **4950099** | CHUP.FIERITA NITRO SUPER ACIDO X50U.-442- | 1 | Faltante **1** u. | **S04152** | `CEN/PICK/04072` | `CEN/OUT/02200` |
| 43/61 | F | **1310.00** | GALL.CELIENERGY CACAO&MANI X130G.-283- | 6 | Faltante **6** u. | **S04364** | `CEN/PICK/04010` | `CEN/OUT/02186` |
| 43/61 | F | **1310.20** | GALL.CELIENERGY CHOC.BCO DE NUEZ X170G.-838- | 6 | Faltante **6** u. | **S04364** | `CEN/PICK/04092` | `CEN/OUT/02186` |
| 43/61 | F | **T2001** | TREMBLY SURTIDO JELLY X6U.-015- | 6 | Faltante **6** u. | **S04107** | `CEN/PICK/04066` | `CEN/OUT/02192` |
| 45/61 | F | **1015455** | MOGUL DUO MUNDIAL 12X30G.-554- | 2 | Faltante **2** u. | **S04295** | `CEN/PICK/03999` | *(OUT en batch no listado al leer)* |
| 45/61 | F | **1015456** | MOGUL CEREBRITOS 12X30G.-561- | 2 | Faltante **2** u. | **S04114** | `CEN/PICK/03983` | `CEN/OUT/02194` |
| 45/61 | F | **1115.10** | MOGUL FRUTILLAS ACIDAS X500G.-925- | 2 | Faltante **2** u. | **S04198** | `CEN/PICK/04077` | `CEN/OUT/02216` |
| 45/61 | F | **1115.15** | MOGUL DIENTES X500G | 3 | Piso **3** u. faltantes (**F3**); impreso **4** u. En ola **4** u. (**2**+**2**) — ver nota **1115.15** | **S04198** + **S04375** | `04077` / `04095` | `02216` / `02183` |
| 46/61 | F | **1115.50** | MOGUL GUSANITOS ACIDOS X500G. | 2 | Faltante **2** u. | **S04198** | `CEN/PICK/03992` | `CEN/OUT/02216` |
| 46/61 | F | **806.15** | DOCILE GELATINES MORAS X250G.-728- | 4 | Faltante **4** u. | **S04198** | `CEN/PICK/04077` | `CEN/OUT/02216` |
| 46/61 | F | **807.20** | DOCILE GELATINES HUEVO FRITO X1KG.-056- | 2 | Faltante **2** u. | **S04198** | `CEN/PICK/03992` | `CEN/OUT/02216` |
| 46/61 | F | **807.45** | DOCILE GELATINES TIBURON AZUL Y ROJO X1KG.-75 | 2 | Faltante **2** u. | **S04198** | `CEN/PICK/03992` | `CEN/OUT/02216` |
| 47/61 | F | **830.85** | STICK DOCILE TUTTI-FRUTTI ACIDA X1.35KG.-201- | 1 | Faltante **1** u. | **S04132** | `CEN/PICK/04071` | `CEN/OUT/02199` |
| 48/61 | F | **2719.6** | GOMITAS BLANDAS MESSI X30U.-568- | 6 | Hoja **6** u.; PICK activo **1** u. + **`cancel`** **5** u. (ver nota **2719.6**) | **S04089** | `CEN/PICK/03976` | `CEN/OUT/02188` |
| 48/61 | F | **774** | MALV. BUFFYS TWISTER FRESA X200G.-777- | 24 | Faltante **24** u. (= **6**+**12**+**3**+**3** en cuatro OV) | **S04089** + **S04329** + **S04361** + **S04364** | `04062` / `04086` / `04089` / `04092` | `02188` / `02207` / `02203` / `02186` |
| 49/61 | F | **1257.10** | RHODESIA 36X22G. | 5 | Faltante **5** u.; **cinco** líneas de **1** u. en la ola (ver nota **1257.10**) | **S04097** + **S04114** + **S04282** + **S04295** + **S04355** | `03977` / `03983` / `03997` / `03999` / `04003` | `02189` / `02194` / `02212` / `02206` — *(**S04295** `03999`: sin OUT esta ref. al leer)* |
| 49/61 | F | **2125.10** | MENTHO PLUS CHERRY X12U. | 8 | Faltante **8** u.; reparto en **seis** OV (ver nota **2125.10**) | **S04097** + **S04122** + **S04132** + **S04152** + **S04355** + **S04366** | `04063` / `04070` / `04071` / `04072` / `04087` / `04090` | `02189` / `02198` / `02199` / `02200` / `02206` / `02202` |
| 50/61 | F | **623.70** | MENTOS TUTTI FRUTTI X12U.-541- | 1 | Faltante **1** u.; hoja con **≠** sobre cantidad (naranja) | **S04364** | `04010` | `02186` |
| 50/61 | F | **PIPAS-002** | PIPAS EXHIBIDOR GIGANTES 12X50G. | 2 | Faltante **2** u.; hoja con **≠**; en Odoo línea **`cancel`** (ver nota **PIPAS-002**) | **S04107** | `03980` | — |
| 51/61 | F | **PIPAS-005** | PIPAS PELADAS 20X25G.-784- | 3 | Faltante **3** u.; **tres** OV con **1** u. c/u (**S04364** / **S04107** / **S04152**) | **S04364** + **S04107** + **S04152** | `04010` / `03980` / `03986` | `02186` / `02192` / `02200` |
| 51/61 | F (−14) | **PIPAS-016** | PIPAS GIGANTES X160G.-262- | 180 impreso | **F14** = faltan **14** u. de **180** impresos en hoja; multiórdenes (ver nota **PIPAS-016**) | **S04107** + **S04179** + **S04184** + **S04321** + **S04365** + **S04376** | `03980` / `03990` / `03991` / `04001` / `04009` / `04017` | `02192` / `02208` / `02187` / `02184` — *(emparejan **S04107**, **S04321**, **S04365**, **S04376**; **S04179** `03990` y **S04184** `03991` sin OUT en lista de movimientos; hay **`cancel`** en otras OV)* |
| 53/61 | F | **18359** | DETERGENTE MAGISTRAL MARINA X300ML.-121- | 12 | Faltante **12** u. (**6**+**6** en dos OV) | **S04122** + **S04321** | `03984` / `04001` | `02198` / `02208` |
| 53/61 | F | **6350.00** | LUSTRAMUEBLES BLEM ORIGINAL X360ML.-747- | 6 | Faltante **6** u. | **S04365** | `CEN/PICK/04009` | *(OUT en batch no listado al leer)* |
| 53/61 | F | **1725.00** | HIG.CAMPANITA XL D.H 4U.X50M.-849-349(10) | 10 | Faltante **10** u. | **S04122** | `CEN/PICK/03984` | `CEN/OUT/02198` |
| 54/61 | F | **1726.00** | HIG.CAMPANITA PLUS S.H 4U.X30M.-639- (12) | 36 | Faltante **36** u. (**12**+**12**+**12** en tres OV) | **S04122** + **S04290** + **S04365** | `04070` / `04082` / `04091` | `02198` / `02211` / `02187` |
| 54/61 | F | **1727.3** | R.COCINA CAMPANITA PRACTI 1U.X200PAÑOS.-615-(12) | 12 | Faltante **12** u. | **S04366** | `04008` | `02202` |
| 55/61 | F | **399** | CURITAS TELA ELASTICA 24X8U.-747- | 2 | Faltante **2** u. (**1**+**1** en dos OV) | **S04361** + **S04376** | `04089` / `04094` | `02203` / `02184` |
| 55/61 | F | **2441.2** | REXONA WOMAN FUTBOL FANATICAS X150ML.-045-571- | 6 | Faltante **6** u. | **S04132** | `CEN/PICK/03985` | `CEN/OUT/02199` |
| 55/61 | F | **2441.94** | REXONA MEN HOMBRE X150ML.-505-502 | 6 | Faltante **6** u. | **S04114** | `CEN/PICK/03983` | `CEN/OUT/02194` |
| 55/61 | F | **2441.95** | REXONA MEN FOOTBALL FANATICS X150ML.-175-472- | 6 | Faltante **6** u. | **S04114** | `CEN/PICK/03983` | `CEN/OUT/02194` |
| 55/61 | F | **2441.96** | REXONA MEN XTRACOOL X150ML.-674-601- | 12 | Faltante **12** u. (**6**+**6** en dos OV) | **S04114** + **S04132** | `04069` / `04071` | `02194` / `02199` |
| 56/61 | F | **6060.30** | JABON LUX FLOR DE VAINILLA X125G.-646- | 12 | Faltante **12** u. (**6**+**6** en dos OV) | **S04132** + **S04321** | `03985` / `04001` | `02199` / `02208` |
| 56/61 | F | **6060.40** | JABON LUX ROSAS FRANCESAS X125G. | 6 | Faltante **6** u. | **S04321** | `CEN/PICK/04085` | `CEN/OUT/02208` |

### Cruce **`CEN/PICK/03991`** (OV **S04184**) — **Cantidad = 0** vs lista **FALTANTES** de hoja

Criterio acordado: **solo** lo que consta en el [cuadro de arriba](#cuadro-unificado-todas-las-páginas-aportadas-hasta-ahora) cuenta como faltante “real” de piso. El resto de líneas con **0** reservado en Odoo **no** están en esa lista → **podés llevar cantidad hecha a la demanda** (o reservar y pickear) **salvo** que en depósito veas otra cosa.

| Código | Demanda en **03991** | ¿Está en **FALTANTES** (hoja)? | Tu acción (criterio) |
|--------|---------------------:|:------------------------------:|----------------------|
| **1103.30** | 1 | **Sí** (pág. 41; faltante **5** u. en total en varias OV) | **No** completar ciego la línea de **03991**; el código está en **FALTANTES** (ver nota **1103.10** / **1103.30**). |
| **1103.10** | 1 | **Sí** (pág. 41; faltante **6** u. en total) | **No** completar ciego la línea de **03991**; parte del faltante está en **`cancel`** en otros PICK. |
| **1103.40** | 2 | **No** | Completar a demanda (**2**) |
| **8817.40** | 10 | **Sí** (pág. 36; faltante total hoja **21** u. en varias OV) | **No** completar ciego las **10** u. de **03991**: el código está en **FALTANTES**; además hay líneas **`cancel`** en otros PICK (ver nota **8817.40**). |
| **2535.05** | 12 | **Sí** (pág. 24; faltante **12** u.) | **No** completar ciego las **12** u. de **03991**; cuadrar **qty_done** con piso / hoja. |
| **PIPAS-016** | 24 | **Sí** (pág. 51; **F14** sobre **180** u. impresas) | **No** completar ciego las **24** u. de **03991**; el faltante de piso es **14** u. respecto al impreso — ver nota **PIPAS-016** y cuadro **51/61**. |
| **152.15** | 2 | **Sí** (pág. 16; faltan **2** de **4** en total OV) | **No** al **2** completo si en piso faltaron solo **2** en toda la OV: parte puede estar en **`CEN/PICK/03986`**; ajustar **qty_done** según conteo real por línea. |
| **1806.00** | 4 | **Sí** (pág. 14; hoja **5** u.) | Faltante **sí** en lista; cuadrar con hoja (**4** vs **5**) antes de forzar demanda completa. |
| **1809.1** | 24 | **Sí** (pág. 15; faltante total piso **40** u. en **dos** PICK) | Faltante **sí**; en **03991** solo van **24** u. de esa OV — el resto del faltante es **`03986`** (**S04152**). No pongas **40** en esta línea. |
| **1812** | 24 | **Sí** (pág. 15) | Faltante **sí**; misma lógica que **1809.1** (también hay líneas en **`03986`** / otros). Ajustar por albarán, no a ciegas a demanda. |

**Resumen:** **1** código (**1103.40**) **no** está en tu listado de faltantes → según tu regla, **sí** corresponde **completar a la demanda** en **03991** si físicamente están. **9** códigos **sí** están en faltantes (incluye **1103.10** y **1103.30** desde pág. 41, **2535.05** desde pág. 24 y **PIPAS-016** desde pág. 51) → **no** completar ciego a demanda; usar cantidades de hoja y reparto entre **03991** y **03986**.

### Notas técnicas (Odoo vs hoja)

- **8153.00 (pág. 27):** la hoja marca **84** u. En la ola hay **cuatro** movimientos PICK por **21** u.: **`03984`** (**S04122**) `done`, **`03990`** (**S04179**) `confirmed`, **`03986`** (**S04152**) `cancel`, **`03998`** (**S04290**) `cancel`. La suma **21**×**4** = **84** u. coincide con el impreso. Además existe OUT **`02198`** **21** u. (**S04122**) emparejado con **`03984`** — al auditar no sumar **105** mezclando OUT con los cuatro PICK como si fueran todos demanda incremental independiente.
- **8101.10 (pág. 26):** la hoja marca **98** u. En la ola, PICK **no cancel** = **14** u. (**S04114**, `03983` → `02194`). Hay **84** u. en **`cancel`**: **`03984`** (**S04122**) **14**, **`03985`** (**S04132**) **14**, **`03992`** (**S04198**) **28**, **`04003`** (**S04355**) **28**. Suma **14**+**84** = **98** u.
- **8175.10 (pág. 26):** la hoja marca **72** u. PICK **no cancel** = **36** u. (**S04097** `03977` **18** u. `done` + **S04179** `03990` **18** u. `confirmed`). **`cancel`**: **`03984`** (**S04122**) **18**, **`03998`** (**S04290**) **18** = **36** u. Total **36**+**36** = **72** u.
- **2719.6 (pág. 48):** la hoja marca **6** u. En la ola, la única línea **no cancel** es **1** u. (**S04089**, `03976` → `02188`). Hay **5** u. en **`cancel`**: **1** u. **`03977`** (**S04097**), **1** u. **`03982`** (**S04110**), **1** u. **`03983`** (**S04114**), **2** u. **`03985`** (**S04132**). La suma **1**+**5** coincide con el impreso de piso.
- **1257.10 (pág. 49):** la hoja marca **5** u. En `master_dev` hay **cinco** movimientos PICK de **1** u. (`assigned` o `done`) ligados a OV de **WAVE/00145`: **S04097** `03977`, **S04114** `03983`, **S04282** `03997`, **S04295** `03999` (PICK en batch **151**), **S04355** `04003`. Cuatro pares PICK→OUT **`02189` / `02194` / `02212` / `02206`** siguen **`assigned`** en la lectura usada; para **S04295** no apareció OUT de esta referencia en esos movimientos.
- **2125.10 (pág. 49):** la hoja marca **8** u. En la ola: **1**+**1**+**1**+**1**+**1**+**3** en **S04097** `04063`, **S04122** `04070`, **S04132** `04071`, **S04152** `04072`, **S04355** `04087`, **S04366** `04090`; OUTs **`02189` / `02198` / `02199` / `02200` / `02206` / `02202`** emparejados **`assigned`** donde aplica.
- **623.70 (pág. 50):** la hoja marca **1** u. (**≠** sobre cantidad). En `master_dev`: **S04364** — PICK **`04010`** `done`, OUT **`02186`** `assigned`.
- **PIPAS-002 (pág. 50):** la hoja marca **2** u. (**≠**). La única línea en OV de **WAVE/00145** para este código está **`cancel`** en **`CEN/PICK/03980`** (**S04107**); **no** hay OUT activo en esa lectura. Cuadrar con supervisión si el faltante de piso sigue aplicando o si la línea se reprogramó fuera de esta ola.
- **PIPAS-005 (pág. 51):** la hoja marca **3** u. En `master_dev` hay **tres** pares PICK→OUT de **1** u.: **S04364** `04010`→`02186`, **S04107** `03980`→`02192`, **S04152** `03986`→`02200` (estados `done` / `assigned` en la lectura usada).
- **PIPAS-016 (pág. 51):** impreso **180** u.; anotación **F14** = faltan **14** u. En la ola, la demanda en PICK suma **180** u.: **120** u. en líneas **no** `cancel` (**24**+**12**+**24**+**24**+**12**+**24** en **`03990`**/**`04001`**/**`04009`**/**`04017`**/**`03980`**/**`03991`**) y **60** u. **`cancel`** (**12** **`03982`** **S04110**, **24** **`03986`** **S04152**, **24** **`03984`** **S04122**). **No** forzar **qty_done** = **24** en **`03991`** si el faltante real de piso es **14** u. sobre el total impreso; ver § Cruce **03991**.
- **1726.00 / 1727.3 (pág. 54):** en `master_dev` los PICK están **`done`** y los OUT **`assigned`** (cadena lista para cuadrar **qty_done** / Barcode). **1726.00:** tres OV **12**+**12**+**12** (**S04122** `04070`→`02198`, **S04290** `04082`→`02211`, **S04365** `04091`→`02187`). **1727.3:** **S04366** `04008`→`02202`.
- **1115.15 (pág. 45):** en piso se anotó faltante **3** u. con referencia impresa **4** u. (**F3**). En `master_dev` la demanda en la ola suma **4** u. (**2** u. **S04198** `04077` → `02216` + **2** u. **S04375** `04095` → `02183`). Resolver si el **F3** es “faltan **3**” respecto al impreso o corrección distinta antes de bajar líneas.
- **973.80 (pág. 42):** única línea en la ola: **`CEN/PICK/03991`** (**S04184**) por **36** u. (`assigned`). La hoja lleva **F18** (faltan **18** de **36** impresos) → **no** forzar **qty_done** = **36** si en piso faltan solo **18**; convive con otras líneas **S04184** en **03991** (ver § Cruce **03991**).
- **1053.10 (pág. 42):** en `master_dev` el `default_code` del producto puede ser **` 1053.10`** (espacio inicial); al buscar por XML-RPC conviene **`ilike`** o dominio equivalente.
- **1103.10 / 1103.30 (pág. 41):** en **`03991`** (**S04184**) cada uno tiene demanda **1** u., pero en el cuadro de faltantes el piso declaró **6** u. (**1103.10**) y **5** u. (**1103.30**). **1103.10:** PICK **no cancel** activos **3** u. (**S04179** `03990`, **S04184** `03991`, **S04300** `04000`, todos `confirmed`) + **3** u. **`cancel`** en **`03984`** (**S04122**), **`03987`** (**S04164**), **`03992`** (**S04198**). **1103.30:** **4** u. en PICK activos (incluye **S04122** `03984` **done** + **OUT** `02198`) + **1** u. **`cancel`** en **`03992`** (**S04198**). Para **1103.30**, los PICK **`confirmed`** de **S04179** / **S04184** / **S04300** no muestran OUT en el batch en la lectura usada.
- **556.10 / 556.20 (pág. 37):** comparten **5** u. en PICK **`cancel`**: **`03984`** (**S04122**) **2**, **`03987`** (**S04164**) **1**, **`03992`** (**S04198**) **2**. **556.10:** PICK **no cancel** = **7** u. (`03983`/`03985`/`04001` **done** + `03999`/`04000` **confirmed**). **556.20:** **6** u. (igual salvo que **no** hay **`04000`** **S04300**). Cuadrar faltante de piso con líneas activas vs impreso.
- **8817.40 (pág. 36):** la hoja marca **21** u. En la ola, PICK **no cancel** suman **14** u.: **`CEN/PICK/03976`** (**S04089**) **1**, **`03985`** (**S04132**) **1**, **`03991`** (**S04184**) **10**, **`03999`** (**S04295**) **2**. Hay **7** u. en **`cancel`**: **`03983`** (**S04114**) **1**, **`03984`** (**S04122**) **2**, **`03992`** (**S04198**) **2**, **`04003`** (**S04355**) **2**. Las **10** u. de **`03991`** figuran en el cuadro de faltantes → **no** usar la regla “completar a demanda” para ese bloque sin validar piso.
- **553.40 (pág. 36):** la hoja marca faltante **7** u.; los PICK **no cancel** de la ola suman **9** u. repartidas en **seis** OV (**1**+**1**+**1**+**2**+**1**+**3**). Cuadrar con conteo real / impreso antes de bajar cantidades.
- **501.20 (pág. 35):** la hoja marca **8** u.; los PICK **no cancel** de la ola suman **6** u. (**S04108** `03981`, **S04110** `03982`, **S04366** `04008`). Existen **2** u. adicionales en movimientos **`cancel`**: **1** u. en **`CEN/PICK/03977`** (**S04097**) y **1** u. en **`CEN/PICK/03986`** (**S04152**). Cuadrar faltante con **impreso vs líneas activas** antes de bajar stock.
- **37.10 (pág. 33):** además del envío **18** u. activo (**S04097**, `03977` → `02189`), existe movimiento **`cancel`** **18** u. en **`CEN/PICK/03983`** (**S04114**): la demanda “histórica” de la ola suma **36** u.; al corregir OUT/PICK no confundir la línea cancelada con stock pendiente.
- **8129.00 (pág. 28):** la hoja imprime **112** u.; en `master_dev` los movimientos **no cancelados** de la ola suman **22** (**S04179**, `03990`) + **22** (**S04164**, `03987`) + **22** (**OUT** `02201`, **S04164**) = **66** u. contando OUT como movimiento aparte; solo **PICK** = **44** u. Hay líneas **`cancel`** históricas en otros pickings de la misma ola (p. ej. **S04122**, **S04282**). Cuadrar con **venta / impreso** antes de bajar stock.
- **BIZ0128 (pág. 22):** la hoja imprime **58** u.; en `master_dev` hay **tres** PICK por **16** u. (**S04300** `04000`, **S04321** `04001`, **S04329** `04002`) = **48** u., más **OUT** `02207` **16** u. (**S04329**). Si el faltante declarado son las **58** u. del papel, cuadrar con **líneas de venta** / otras olas o cambios posteriores al PDF.
- **8816 (pág. 24):** la hoja marca **30** u.; en la ola hay **tres** PICK **10** u. (**S04097** `04063`, **S04179** `04075`, **S04290** `04082`) emparejados con OUT **`02189` / `02236` / `02211`**.
- **2720 (pág. 24):** la hoja marca **36** u.; en la ola figuran **dos** PICK **18** u. `assigned` (**S04295** `03999`, **S04300** `04000`); en la lectura usada **no** apareció OUT del batch para esas líneas.
- **2535.05 / 2535.07 (pág. 24):** ambos en **`CEN/PICK/03991`** (**S04184**), **12** u. c/u; **2535.05** `confirmed`, **2535.07** `assigned`. Conviven con otras líneas **S04184** en **03991** (ver § Cruce **03991**).
- **2535.1 (pág. 24):** la hoja marca **19** u.; en la ola hay **9** u. `partially_available` en **`03990`** (**S04179**) + **10** u. `done` en **`03998`** (**S04290**) + OUT **`02211`** **10** u. (**S04290**). Antes de **SYNC**, revisar stock en ubicación del PICK y **no** duplicar conteo OUT vs PICK ya hecho.
- **2535.5 (pág. 24):** la hoja marca **20** u.; en la ola hay mezcla **S04179** (`03990`) + **S04290** (`03998` + OUT `02211`). Cuadrar **qty_done** por OV sin asumir el total en una sola línea.
- **Pág. 25 (8357.30 / 1343 / 1392):** en `master_dev`, **8357.30** y **1392** comparten OV **S04300** (PICK **`04084`** `done`, OUT **`02209`** `assigned`). **1343** va por **S04122** (PICK **`03984`** `done`, OUT **`02198`** `assigned`). Cuadrar **qty_done** / Barcode con el faltante de piso antes de validar OUT. El `stock.picking.batch` **151** puede ya no listar estos pickings (batch acotado); el cruce se hizo por **`sale.order`** con **`nakel_wave_batch_id` = WAVE/00145**.
- **8678.00 (pág. 18):** en ola hay **1** movimiento PICK **`confirmed`** por **16** u. (**S04200**, `03993`); la anotación **F 15** en piso puede ser “faltan 15” o corrección respecto a **16** impreso — validar en albarán.
- **8712.00 (pág. 19):** suma de demandas en **PICK** (sin duplicar OUT): **12** u. (**S04264**, `03995`) + **6** (**S04358**, `04004`) + **12** (**S04200**, `03993`) = **30** u., alineado con el faltante total declarado.
- **8654.00 (pág. 19):** en `master_dev` hay **varias** líneas en la ola (p. ej. **S04200** `04078` **12** u. `confirmed` — la del §3 `partially_available` con reserva **2,12** — más **S04101**, **S04358**, **S04264**). El valor **26,12** de la hoja coincide con el **pedido/reserva** documentado en [README §3](README.md) para **S04200**; el resto de unidades conviene cruzar **por OV** en el PICK/OUT.
- **4106.20 vs 4106.30 (pág. 15):** en `master_dev`, **`4106.20`** = *TERMA POMELO*; **Terma limón** es **`4106.30`**. El faltante **F 4** de la hoja se cruzó con **4106.30** + OV **S04122** (`CEN/PICK/03984` → `CEN/OUT/02198`).
- **1809.1 (manzana 1 L):** el código en catálogo es **`1809.1`** (no existe **`1809.10`** con ese producto).
- **1812 (Naranja 1,5 L):** movimientos en ola: **24** u. `confirmed` (**S04184**, `03991`) + **16** u. PICK `done` + **16** u. OUT `assigned` (**S04152**, `03986` / `02200`) + línea **`cancel`** **24** u. (**S04366**, `04008`). Suma **activos** = **56** u.; si la hoja marca **64** u. de faltante, revisar impreso vs pedidos / UoM.
- **1809 (Naranja 1 L):** único rastro en esta ola: movimiento **`cancel`** 16 u. en **`CEN/PICK/03986`** (**S04152**).
- **5081.18 (pág. 14):** en `master_dev` solo aparece movimiento en **`CEN/PICK/04000`** (OV **S04300**), estado **`assigned`**, demanda **6**; **no** hay línea de **OUT** con ese producto y `nakel_wave_batch_id = 151` en la lectura usada (cadena PICK→OUT aún no generada o fuera de este filtro).
- **1806.00 (pág. 14):** la hoja imprime **5** u.; en la ola figura **1** movimiento **`confirmed`** por **4** u. en **`CEN/PICK/03991`** (OV **S04184**). Revisar si el PDF usa otra conversión UoM o si hubo cambio de pedido respecto a la hoja.
- **5023.12 (pág. 13):** en `master_dev` la demanda del producto en la ola suma **24** u. repartidas en **tres** movimientos: **S04295** 6 u. (`CEN/PICK/04083` → `CEN/OUT/02210`), **S04164** **12** u. (`CEN/PICK/04073` → `CEN/OUT/02201`), **S04300** 6 u. (`CEN/PICK/04084` → `CEN/OUT/02209`). La anotación **F 12** en piso **coincide numéricamente** con la línea completa de **S04164**; conviene **confirmar en depósito** si el faltante afecta solo a ese cliente o a otro reparto antes de bajar cantidades en Odoo.
- **4092.10:** en la lectura usada para este cruce, el movimiento activo en la ola para **S04164** figura con **demanda 6** en PICK/OUT (no **9**). Si en la hoja el total **9** incluye otra OV o línea, buscar en Odoo con filtro por **producto + `nakel_wave_batch_id`** y sumar líneas.
- **Playadito X2KG** `[1636.00]` con tachado **7 → 5** manuscrito (pág. 7): **no** estaba en la lista F/X; en la doc de la ola hay línea **`partially_available`** en **`CEN/PICK/04086`** (OV **S04329**) — ver [README.md §3.1](README.md).

---

## Cómo reproducir el cruce (XML-RPC)

Dominio de movimientos: `[('picking_id.nakel_wave_batch_id', '=', 151), ('product_id', '=', <id producto>), ('state', '!=', 'cancel')]`.

Script de exportación masiva por batch (solo lo enganchado a `batch_id`): `nakel_odoo/tools/inventario/export_wave_pickings_ov_csv.py --batch-id 151`.

---

## Origen de las imágenes (referencia interna)

- Pág. 7 / 9: assets del proyecto Cursor (fotos previas de la misma ola).
- Pág. 11: `image-80f5807e-4422-48b6-9f33-259e10c87d6d.png` (Wave WAVE/00145 Página 11/61).
- Pág. 12: `image-7b26886c-333f-4dc2-85ed-153f6d67d9bb.png` (único faltante **8869.60**).
- Pág. 13: `image-63455ec5-fa68-49d7-86a7-85902b409bdc.png` (**5023.12** F 12; **27201** F).
- Pág. 14: `image-8f5160eb-2657-4838-9ef1-7d4779aee43f.png` (**5033.10**, **5081.18**, **1806.00**).
- Pág. 15: `image-00d817fc-5d4b-49fa-a3ee-08b166afd28f.png` (Baggio / Terma / Noel polvo).
- Pág. 16: `image-8b431847-f244-4971-9acd-b394022bb97d.png` (**152.15**).
- Pág. 17: `image-403388fd-4447-4547-a8ea-49a1be5ca058.png` (**1809.05**).
- Pág. 18: `image-19b2c022-eb00-4daa-b7f4-c3995fca4844.png` (**8615.10**, **8616.00**, **8678.00**).
- Pág. 19: `image-c2353573-7055-46a8-a33c-4cc590ff0663.png` (**8736.2**, **8712.00**, **8654.00**).
- Pág. 22: `image-614dad10-ed95-446d-a79c-520cad59476e.png` (**8220.70**, **8220.80**, **BIZ0128**).
- Pág. 23: `image-cdece9b2-8264-488d-afac-41fa8e881552.png` (**BIZ0222**, **1630**).
- Pág. 24: `image-432a2416-5f34-4296-8515-06cea3ea6416.png` (**8816**, **2720**, **2535.05**, **2535.07**, **2535.1**, **2535.2**, **2535.5**).
- Pág. 25: `image-dadd4462-8a16-404f-8dac-f3b3ce12a8f6.png` (**8357.30**, **1343**, **1392**). En la misma foto aparecen marcas **F** en **[1346]** y **[8351.50]**; no estaban en el mensaje — avisar si hay que sumarlos al cuadro.
- Pág. 26: `image-badf7694-6cde-41f6-a756-cb76f9961417.png` (**8101.10**, **8174.10**, **8175.10**, **8880.30**).
- Pág. 27: `image-1c5a777b-a8ac-48c9-a1e9-2409dcdc3afe.png` (**2820.83**, **8869.15**, **8153.00**).
- Pág. 28: `image-1af8456a-1134-47d2-9b78-882a61a83df7.png` (**115**, **8129.00**, **8341.00**).
- Pág. 29: `image-595c5240-baf3-490b-ab8c-1af78b7dba6c.png` (**1163.50**, **8885.00**, **8885.20**, **3530.15**).
- Pág. 31: `image-e5921897-9ca2-445a-9ec0-4ab6061c0145.png` (**7.71**).
- Pág. 32: `image-fbaaa06d-1632-4261-9a31-57605241474a.png` (**9.70**, **9.90**).
- Pág. 33: `image-aa1f0b08-c639-4fb5-bfbf-d113aa918752.png` (**37.00**, **37.10**, **2006**).
- Pág. 34: `image-ae181f71-bdd8-41ad-921d-943407ba783c.png` (**1124.10**, **2153.40**).
- Pág. 35: `image-ad1dcfb9-ea64-47a9-ac1d-2b0d08084872.png` (**631.20**, **501.20**, **2109.05**).
- Pág. 36: `image-486a8297-8b8e-415d-9e76-b884af7b5be6.png` (**8817.25**, **8817.40**, **8817.55**, **8817.60**, **8818.00**, **8818.20**, **553.40**).
- Pág. 37: `image-fb5cdfd6-f356-430f-9c9f-0ac278eada03.png` (**556.10**, **556.20**, **556.70**, **4950420**, **4950422**, **4950425**). En la misma foto aparece **F** en **[635.20]** (Bubbaloo menta); no estaba en el mensaje — si corresponde faltante, sumarlo al cuadro.
- Pág. 38: `image-b0026ee2-e885-44ef-ba76-391d52e80609.png` (**8858.15**).
- Pág. 39: `image-6e9dcd1a-cd7f-4ef6-abbb-2e94dd32e256.png` (**8853.10**). En la misma hoja la foto muestra otros **F** (p. ej. **8853.20**, **8856.80**, **8856.85**, **634.10**); no estaban en el mensaje — avisar si hay que sumarlos al cuadro.
- Pág. 40: `image-698738a3-8a07-48e4-b8f9-032a24f011cf.png` (**1510**).
- Pág. 41: `image-3c271528-1a41-4ce4-a6b3-0dae063e32ef.png` (**1103.10**, **1103.30**, **972.10**).
- Pág. 42: `image-f62a0b0a-3fe8-4147-865f-08d668f8c585.png` (**973.80**, **1053.10**, **1440.00**).
- Pág. 43: `image-48beb212-942b-4dbb-8819-093a43488ecb.png` (**CA-840**, **4950099**, **1310.00**, **1310.20**, **T2001**).
- Pág. 45: `image-51c540e5-64ed-4462-aa1a-ddebc831cad7.png` (**1015455**, **1015456**, **1115.10**, **1115.15**).
- Pág. 46: `image-f7da61e1-8cd5-4794-8e59-f21ab0567b78.png` (**1115.50**, **806.15**, **807.20**, **807.45**).
- Pág. 47: `image-24af9ef5-4928-45bc-9de1-42eb767fba7d.png` (**830.85**).
- Pág. 48: `image-86714adf-9bd2-4e99-880c-78a49ee5cc33.png` (**2719.6**, **774**).
- Pág. 49: `image-7f8b77cb-6c36-4662-aa8e-5b3625fa5011.png` (**1257.10**, **2125.10**).
- Pág. 50: `image-822883c2-9c49-4042-ae79-acd29ddacbf1.png` (**623.70**, **PIPAS-002**).
- Pág. 51: `image-96c5069f-75cc-480c-a36b-5df21a6fa0e1.png` (**PIPAS-005**, **PIPAS-016**).
- Pág. 53: `image-326049c7-0dc9-4aeb-abdc-f18576f1f276.png` (**18359**, **6350.00**, **1725.00**).
- Pág. 54: `image-a1b963ed-6dd9-4e58-94e1-4aa770fd1678.png` (**1726.00**, **1727.3**).
- Pág. 55: `image-5bb7e58e-99aa-4734-a021-83fec1f6e3d2.png` (**399**, **2441.2**, **2441.94**, **2441.95**, **2441.96**).
- Pág. 56: `image-a668d10c-e235-4b77-8bc3-b9e4de6e06c5.png` (**6060.30**, **6060.40**).
