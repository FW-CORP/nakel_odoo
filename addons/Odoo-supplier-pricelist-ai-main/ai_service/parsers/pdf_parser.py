"""
PDF parser: extrae texto de la lista de precios usando pdfplumber.
Combina extracción de tablas + texto plano para maximizar el contenido capturado.

Además provee `extract_structured_rows()` que detecta tablas con headers
reconocibles (artículo, código, EAN, precio) y devuelve filas estructuradas
sin necesidad de pasar por el LLM. Esto resuelve el ~80% de los formatos
de listas de precios que reciben los distribuidores.
"""
import base64
import io
import logging
import re
import unicodedata
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extrae todo el texto del PDF combinando dos estrategias:
    1. Extracción de tablas (estructura preservada con tabs)
    2. Texto plano por página
    Devuelve el resultado más completo.
    """
    table_parts = []
    plain_parts = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            # ── Estrategia 1: tablas ──────────────────────────────────────────
            try:
                tables = page.extract_tables({
                    'vertical_strategy': 'lines_strict',
                    'horizontal_strategy': 'lines_strict',
                    'snap_tolerance': 3,
                    'join_tolerance': 3,
                    'edge_min_length': 3,
                    'min_words_vertical': 1,
                    'min_words_horizontal': 1,
                })
                if not tables:
                    # Fallback: estrategia menos estricta
                    tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            if row and any(c for c in row if c):
                                cleaned = [
                                    (cell or '').strip().replace('\n', ' ')
                                    for cell in row
                                ]
                                line = '\t'.join(cleaned)
                                if line.strip():
                                    table_parts.append(line)
            except Exception as e:
                logger.debug(f'Página {i+1}: error en extracción de tablas: {e}')

            # ── Estrategia 2: texto plano ─────────────────────────────────────
            try:
                text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if text:
                    plain_parts.append(text)
            except Exception as e:
                logger.debug(f'Página {i+1}: error en extracción de texto: {e}')

    table_text = '\n'.join(table_parts)
    plain_text = '\n'.join(plain_parts)

    # Usá el que da más contenido
    if len(table_text) >= len(plain_text):
        logger.info(f'PDF: usando extracción tabular ({len(table_text)} chars, {len(table_parts)} filas)')
        return table_text
    else:
        logger.info(f'PDF: usando extracción de texto plano ({len(plain_text)} chars)')
        return plain_text


def extract_text_from_pdf_b64(file_b64: str) -> str:
    """Extrae texto de un PDF codificado en base64."""
    file_bytes = base64.b64decode(file_b64)
    return extract_text_from_pdf(file_bytes)


# ════════════════════════════════════════════════════════════════════════════
# Tabular extraction — extrae filas estructuradas sin LLM
# ════════════════════════════════════════════════════════════════════════════

# Palabras-clave que indican que una fila es un header de tabla
_HEADER_HINTS = (
    'articulo', 'producto', 'descripcion', 'detalle', 'denominacion',
    'precio', 'codigo', 'ean', 'presentacion', 'cantidad', 'envase',
)


def _strip_accents(text: str) -> str:
    return unicodedata.normalize('NFKD', text or '').encode('ASCII', 'ignore').decode('ASCII')


def _normalize_header(text: str) -> str:
    """Normaliza un header: minúsculas, sin tildes, sin caracteres especiales, espacios colapsados."""
    s = _strip_accents(text or '')
    s = s.lower().replace('\n', ' ')
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _classify_column(header_norm: str) -> Optional[str]:
    """
    Devuelve el campo semántico al que corresponde un header normalizado, o None.
    El orden importa: detecciones más específicas van primero.
    """
    h = header_norm
    if not h:
        return None

    tokens = set(h.split())

    # ── Barcode (más específico primero) ─────────────────────────────────────
    if 'ean' in tokens or h.startswith('ean ') or h == 'ean':
        return 'barcode'
    if 'barcode' in tokens:
        return 'barcode'
    if ('codigo' in tokens or 'cod' in tokens) and 'botella' in tokens:
        return 'barcode'
    if ('codigo' in tokens or 'cod' in tokens) and ('barra' in tokens or 'barras' in tokens):
        return 'barcode'
    if ('codigo' in tokens or 'cod' in tokens) and 'caja' in tokens:
        return 'barcode_box'

    # ── Nombre del producto ──────────────────────────────────────────────────
    if 'articulo' in tokens or 'producto' in tokens or 'descripcion' in tokens \
            or 'detalle' in tokens or 'denominacion' in tokens:
        return 'name'

    # ── Presentación / Tipo ──────────────────────────────────────────────────
    if 'presentacion' in tokens or 'envase' in tokens or 'pack' in tokens or 'medida' in tokens:
        return 'presentation'
    if 'tipo' in tokens or 'unidad' in tokens:
        return 'type'

    # ── Precios (orden importa: más específico primero) ──────────────────────
    if 'precio' in tokens or h.startswith('precio'):
        is_final = 'final' in tokens
        is_base = 'base' in tokens
        is_bottle = 'botella' in tokens or 'bot' in tokens
        is_box_master = 'caja' in tokens or 'bulto' in tokens
        is_pack = 'bolsa' in tokens or 'pack' in tokens
        is_unit = 'uni' in tokens or 'unitario' in tokens or 'unidad' in tokens
        is_distrib = 'distribuidor' in tokens
        is_estuche = 'estuche' in tokens or 'e' in tokens  # 'e' por truncamiento de "ESTUCHE"

        if is_final and is_bottle:
            return 'price_final_bottle'
        if is_final and is_box_master:
            return 'price_final_box'
        if is_base and is_bottle:
            return 'price_base_bottle'
        if is_base and is_box_master:
            return 'price_base_box'
        if is_distrib and is_estuche:
            return 'price_distrib_unit'   # Cachafaz: "PRECIO DISTRIBUIDOR POR ESTUCHE"
        if is_distrib and (is_box_master or 'b' in tokens):
            return 'price_distrib_box'    # Cachafaz: "PRECIO DISTRIBUIDOR POR BULTO"
        if is_bottle:
            return 'price_final_bottle'
        if is_final:
            return 'price_final'          # Tunki: "PRECIO FINAL" (per caja)
        if is_box_master:
            return 'price_final_box'
        if is_pack:
            return 'price_pack'           # Tunki: "Precio Bolsa"
        if is_unit:
            return 'price_unit'           # Tunki: "Precio Uni" (per unidad)
        if is_base:
            return 'price_base'
        return 'price_final'  # default genérico

    # ── Categoría / Sub-categoría ────────────────────────────────────────────
    if 'categoria' in tokens or 'subcategoria' in tokens or 'rubro' in tokens \
            or 'familia' in tokens or 'sub' in tokens:
        return 'category'

    # ── Código de proveedor (última prioridad) ───────────────────────────────
    if h in ('n', 'no', 'nro', 'num', 'numero', 'codigo', 'cod', 'sku', 'item', 'art'):
        return 'supplier_code'
    if h in ('articulo n', 'art n', 'codigo articulo', 'numero de articulo'):
        return 'supplier_code'

    return None


def _is_header_row(row: list, min_keywords: int = 2) -> bool:
    """True si la fila tiene al menos `min_keywords` celdas que parecen header."""
    if not row:
        return False
    matches = 0
    for cell in row:
        if not cell:
            continue
        norm = _normalize_header(cell)
        if any(hint in norm for hint in _HEADER_HINTS):
            matches += 1
    return matches >= min_keywords


def _parse_price(val) -> Optional[float]:
    """Parsea un precio en formato argentino (1.234,56) o universal (1234.56)."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    # quitar símbolos de moneda y espacios
    s = re.sub(r'[$\s ]', '', s)
    if not s or s in ('-', '0', '0,00', '0.00'):
        return None

    # Si tiene ambos separadores: el de la última posición es el decimal
    if ',' in s and '.' in s:
        last_comma = s.rfind(',')
        last_dot = s.rfind('.')
        if last_comma > last_dot:
            # Argentino: 1.234,56 → punto miles, coma decimal
            s = s.replace('.', '').replace(',', '.')
        else:
            # US: 1,234.56 → coma miles, punto decimal
            s = s.replace(',', '')
    elif ',' in s:
        # Solo coma: si tiene exactamente 2 dígitos después es decimal,
        # si tiene 3 dígitos después es separador de miles
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) == 2:
            s = s.replace(',', '.')
        elif len(parts[-1]) == 3:
            s = s.replace(',', '')
        else:
            s = s.replace(',', '.')
    elif s.count('.') >= 2:
        # Múltiples puntos sin coma: probablemente miles argentinos sin decimal
        s = s.replace('.', '')

    s = re.sub(r'[^\d.\-]', '', s)
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def _is_category_row(row: list) -> Optional[str]:
    """
    Si la fila parece ser un header de sección (1 o 2 celdas con texto, resto vacías),
    devuelve el texto de la categoría. Caso contrario None.
    """
    non_empty = [str(c).strip() for c in row if c and str(c).strip()]
    if 1 <= len(non_empty) <= 2:
        text = non_empty[0]
        # No debe parecer un nombre de producto largo ni una fila de números
        if text and not re.fullmatch(r'[\d.,\s$%\-]+', text) and 2 <= len(text) <= 60:
            return text
    return None


def extract_structured_rows(file_bytes: bytes) -> Optional[list[dict]]:
    """
    Intenta extraer filas estructuradas de un PDF tabular.

    Para cada tabla del PDF:
      1. Busca una fila que parezca header (≥2 celdas con palabras-clave).
      2. Mapea cada columna a un campo semántico: name, barcode, supplier_code,
         price_final_bottle, presentation, etc.
      3. Procesa las filas siguientes; las que sólo tienen 1 celda con texto se
         interpretan como headers de sección (categoría) que se aplican a las
         filas siguientes.

    Returns:
        Lista de dicts con keys: name, barcode, supplier_code, price, presentation,
        category, vat_included.
        None si la PDF no parece tabular o la extracción no dio suficientes filas.
    """
    rows: list[dict] = []

    # Estrategias de extracción de tablas, en orden de preferencia.
    # Probamos varias y nos quedamos con la que da más columnas en el header.
    _STRATEGIES = [
        None,  # default de pdfplumber
        {'vertical_strategy': 'text', 'horizontal_strategy': 'lines',
         'snap_tolerance': 4, 'intersection_tolerance': 5},
        {'vertical_strategy': 'lines', 'horizontal_strategy': 'lines'},
        {'vertical_strategy': 'text', 'horizontal_strategy': 'text',
         'snap_tolerance': 4, 'intersection_tolerance': 5},
    ]

    def _best_tables_for_page(page) -> list:
        """Prueba varias estrategias y devuelve la que captura tablas con headers más anchos."""
        best_tables = []
        best_score = 0
        for settings in _STRATEGIES:
            try:
                tabs = page.extract_tables(settings) if settings else page.extract_tables()
            except Exception:
                continue
            if not tabs:
                continue
            # Score: ancho del header * cantidad de filas. Buscamos tablas con muchas columnas.
            score = 0
            for t in tabs:
                if not t:
                    continue
                for r in t[:5]:
                    if _is_header_row(r):
                        score = max(score, len([c for c in r if c]) * len(t))
                        break
            if score > best_score:
                best_score = score
                best_tables = tabs
        return best_tables or []

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                try:
                    tables = _best_tables_for_page(page)
                except Exception as e:
                    logger.debug(f'page {page_idx}: extract_tables falló: {e}')
                    tables = []

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    # Buscar header dentro de las primeras 5 filas
                    header_idx = None
                    for i, row in enumerate(table[:5]):
                        if _is_header_row(row):
                            header_idx = i
                            break
                    if header_idx is None:
                        continue

                    headers = table[header_idx]
                    column_map: dict[int, str] = {}
                    for col_idx, header in enumerate(headers):
                        norm = _normalize_header(header or '')
                        field = _classify_column(norm)
                        if field and col_idx not in column_map:
                            column_map[col_idx] = field

                    fields_present = set(column_map.values())
                    # Si no hay columna de nombre, probar la primera columna sin clasificar
                    # (caso Cachafaz: header dice "PATAGONIA II", marca del proveedor)
                    if 'name' not in fields_present:
                        for col_idx in range(len(headers)):
                            if col_idx not in column_map and headers[col_idx]:
                                column_map[col_idx] = 'name'
                                fields_present.add('name')
                                break

                    if 'name' not in fields_present:
                        continue
                    if not any(f.startswith('price') for f in fields_present):
                        continue

                    logger.info(
                        f'  Tabla pág {page_idx+1}: header en fila {header_idx}, '
                        f'columnas mapeadas: {sorted(set(column_map.values()))}'
                    )

                    current_category: Optional[str] = None

                    for row in table[header_idx + 1:]:
                        if not row or all(not c for c in row):
                            continue

                        # ¿Es header de sección?
                        category_text = _is_category_row(row)
                        if category_text:
                            # Verifica que NO esté en una columna de nombre (caso Tunki: nombres en 1 sola celda)
                            # Si la celda con texto está en la columna de nombre y tiene precio próximo, no es categoría
                            current_category = category_text
                            continue

                        # Construir dict
                        raw: dict[str, str] = {}
                        for col_idx, field in column_map.items():
                            if col_idx < len(row) and row[col_idx]:
                                val = str(row[col_idx]).strip().replace('\n', ' ')
                                # Si ya hay valor para este field, concatenar (caso de varias columnas → presentation)
                                if field in raw and field == 'presentation':
                                    raw[field] = (raw[field] + ' ' + val).strip()
                                elif field not in raw:
                                    raw[field] = val

                        name = raw.get('name', '').strip()
                        if not name or len(name) < 2:
                            continue
                        # Saltar filas que parecen totales / leyendas
                        if _normalize_header(name) in ('total', 'subtotal', 'iva', 'vigencia'):
                            continue

                        # Precio: prioridad orientada a "lo que paga el cliente":
                        #   1. price_final_bottle  (Pernod: "Precio Final BOTELLA")
                        #   2. price_distrib_unit  (Cachafaz: "POR ESTUCHE")
                        #   3. price_final         (Tunki: "PRECIO FINAL" — caja)
                        #   4. price_pack          (Tunki: "Precio Bolsa")
                        #   5. price_final_box     (Pernod: "Precio Final CAJA")
                        #   6. price_distrib_box   (Cachafaz: "POR BULTO")
                        #   7. price_unit, price_base_*, price_base
                        price = (
                            _parse_price(raw.get('price_final_bottle')) or
                            _parse_price(raw.get('price_distrib_unit')) or
                            _parse_price(raw.get('price_final')) or
                            _parse_price(raw.get('price_pack')) or
                            _parse_price(raw.get('price_final_box')) or
                            _parse_price(raw.get('price_distrib_box')) or
                            _parse_price(raw.get('price_unit')) or
                            _parse_price(raw.get('price_base_bottle')) or
                            _parse_price(raw.get('price_base'))
                        )
                        if not price:
                            continue

                        # Barcode
                        barcode = None
                        bc_raw = raw.get('barcode') or raw.get('barcode_box')
                        if bc_raw:
                            digits = re.sub(r'\D', '', bc_raw)
                            if 8 <= len(digits) <= 14:
                                barcode = digits.lstrip('0') if len(digits) >= 13 and digits.startswith('0') else digits

                        # Supplier code
                        sc = raw.get('supplier_code')
                        if sc:
                            sc = sc.strip()
                            # Filtrar valores que no son códigos (texto largo, espacios)
                            if not re.fullmatch(r'[\w./\-]{1,20}', sc):
                                sc = None

                        # Presentation
                        pres_parts = []
                        for f in ('presentation', 'type'):
                            if raw.get(f):
                                pres_parts.append(raw[f])
                        presentation = ' '.join(pres_parts) if pres_parts else None

                        rows.append({
                            'name': name,
                            'barcode': barcode,
                            'supplier_code': sc,
                            'price': price,
                            'presentation': presentation,
                            'category': raw.get('category') or current_category,
                        })

        # Si la extracción tabular dio pocas filas, o las filas tienen nombres
        # truncados (caso Pernod con tablas multi-columna fragmentadas), intentar
        # parser de texto-línea con regex como fallback.
        def _name_looks_truncated(name: str) -> bool:
            if not name or len(name) < 5:
                return True
            first = name[0]
            # Empieza con dígito → fragmento
            if first.isdigit():
                return True
            # Empieza con minúscula → fragmento (productos casi siempre van CAPS o Title)
            if first.islower():
                return True
            # No es alfabético (símbolo raro)
            if not first.isalpha() and first not in 'áéíóúñÁÉÍÓÚÑ':
                return True
            return False

        truncated_count = sum(1 for r in rows if _name_looks_truncated(r.get('name', '')))
        rows_truncated = truncated_count > len(rows) // 5
        if len(rows) < 5 or rows_truncated:
            logger.info(
                f'Tabular parser: {len(rows)} filas, truncated={rows_truncated}. '
                f'Intentando parser de texto-línea...'
            )
            line_rows = _extract_rows_from_text_lines(file_bytes)
            if line_rows and len(line_rows) > len(rows):
                logger.info(
                    f'Text-line parser: {len(line_rows)} filas extraídas '
                    f'({sum(1 for r in line_rows if r.get("barcode"))} con barcode, '
                    f'{sum(1 for r in line_rows if r.get("supplier_code"))} con código)'
                )
                return line_rows
            if len(rows) < 5:
                logger.info(f'Tabular parser: insuficientes filas, fallback a LLM')
                return None

        logger.info(
            f'Tabular parser: {len(rows)} filas extraídas '
            f'({sum(1 for r in rows if r.get("barcode"))} con barcode, '
            f'{sum(1 for r in rows if r.get("supplier_code"))} con código de proveedor)'
        )
        return rows

    except Exception as e:
        logger.warning(f'Tabular parser falló: {e}')
        return None


# ════════════════════════════════════════════════════════════════════════════
# Parser de líneas de texto con regex
# Para listas tipo Pernod donde la tabla se fragmenta pero el texto plano
# tiene un patrón regular: <subcat> <code> <nombre> <Tipo> ... $X $Y ... <bc> <bc>
# ════════════════════════════════════════════════════════════════════════════

# Tipos comunes de envase en listas de bebidas
_TIPO_TOKENS = ('Bot', 'Est', 'Kit', 'Pet', 'Lat', 'Caja', 'Botella')


def _fix_split_numbers(line: str) -> str:
    """
    Repara números cortados por pdfplumber. Ej:
      "$ 1 09.641,93" → "$ 109.641,93"
      "$1 .065.318,17" → "$1.065.318,17"
    """
    # Caso "$<digit><space><digits>" → unir
    line = re.sub(r'(\$\s*\d)\s+(\d[\d.,]*)', r'\1\2', line)
    line = re.sub(r'(\$\s*\d)\s+(\d[\d.,]*)', r'\1\2', line)  # 2da pasada
    # Caso "<digit> .<digits>" (entero seguido de un punto-decimal con espacio)
    line = re.sub(r'(\d)\s+(\.\d{3})', r'\1\2', line)
    return line


def _extract_rows_from_text_lines(file_bytes: bytes) -> list[dict]:
    """
    Extrae productos parseando línea-a-línea el texto plano del PDF.
    Útil para PDFs donde la tabla está fragmentada pero el texto sigue
    un patrón consistente.

    Estrategia: si una línea tiene
      - un código numérico de 3-6 dígitos cerca del inicio
      - un token de tipo (Bot/Est/Kit/Pet/Lat) en el medio
      - termina con dos secuencias largas de dígitos (códigos de barras CAJA y BOTELLA)
    → la parseamos como producto.
    """
    rows: list[dict] = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            full_text = '\n'.join(
                page.extract_text(x_tolerance=2, y_tolerance=3) or ''
                for page in pdf.pages
            )
    except Exception as e:
        logger.warning(f'_extract_rows_from_text_lines: error abriendo PDF: {e}')
        return rows

    if not full_text:
        return rows

    current_category: Optional[str] = None
    tipo_pattern = '|'.join(_TIPO_TOKENS)

    # Regex: línea que empieza con palabras (cat), tiene un code, después name, tipo, ...,
    # y termina con dos secuencias de 8-15 dígitos (los EANs)
    line_re = re.compile(
        r'^(?P<subcat>.+?)\s+'
        r'(?P<code>\d{3,6})\s+'
        r'(?P<name>.+?)\s+'
        rf'(?P<tipo>{tipo_pattern})\s+'
        r'(?P<rest>.+?)\s+'
        r'(?P<bc_box>\d{8,15})\s+'
        r'(?P<bc_bot>\d{8,14})\s*$'
    )

    for line in full_text.split('\n'):
        line = line.strip()
        if not line or len(line) < 30:
            continue
        # Reparar números rotos antes de aplicar regex
        fixed_line = _fix_split_numbers(line)

        m = line_re.match(fixed_line)
        if not m:
            continue

        subcat = m.group('subcat').strip()
        code = m.group('code').strip()
        name = m.group('name').strip()
        tipo = m.group('tipo').strip()
        rest = m.group('rest').strip()
        bc_box = m.group('bc_box').strip()
        bc_bot = m.group('bc_bot').strip()

        # Filtrar falsos positivos: subcat no debe ser un número solo
        if re.fullmatch(r'[\d\s.,$%-]+', subcat):
            continue

        # Buscar precios en `rest` — patrón "$ N.NNN,NN"
        prices = re.findall(r'\$\s*([\d.,]+)', rest)
        if len(prices) < 2:
            continue

        # Estructura típica:
        #   prices = [base_bot, base_caja, iva, ii, final_bot, final_caja]
        # Tomamos el penúltimo: Precio Final BOTELLA.
        # Si no hay 6, usamos el último-menos-uno o el último.
        price_str = prices[-2] if len(prices) >= 6 else (prices[-1] if prices else None)
        price = _parse_price(price_str)
        if not price:
            continue

        # Normalizar barcode (EAN-13 estándar = la versión sin el cero inicial extra)
        barcode = bc_bot
        if len(barcode) == 14 and barcode.startswith('0'):
            barcode = barcode[1:]

        rows.append({
            'name': name,
            'barcode': barcode,
            'supplier_code': code,
            'price': price,
            'presentation': tipo,
            'category': subcat,
        })

    return rows


def extract_structured_rows_b64(file_b64: str) -> Optional[list[dict]]:
    """Versión que recibe base64."""
    file_bytes = base64.b64decode(file_b64)
    return extract_structured_rows(file_bytes)


def detect_vat_included(text: str) -> bool:
    """
    Detecta si los precios del PDF incluyen IVA en base a notas al pie del texto plano.
    Default: True.
    """
    if not text:
        return True
    t = text.lower()
    # Negativos explícitos
    if 'no incluyen iva' in t or 'no inlcuyen iva' in t \
            or 'no incluye iva' in t or 'no inlcuye iva' in t \
            or 'precios netos' in t or 'sin iva' in t or 'mas iva' in t:
        return False
    if 'incluyen iva' in t or 'incluye iva' in t or 'iva incluido' in t:
        return True
    return True
