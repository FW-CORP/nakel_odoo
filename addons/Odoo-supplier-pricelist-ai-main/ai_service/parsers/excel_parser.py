"""
Parser de Excel (.xlsx / .xls) y CSV.
Devuelve el contenido como texto tabular para que el LLM lo procese.
"""
import base64
import csv
import io
import logging
from typing import Optional
import openpyxl

logger = logging.getLogger(__name__)


def extract_text_from_excel(file_bytes: bytes, file_name: str = '') -> str:
    """Convierte Excel a texto tabular (TSV-like)."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active  # Primera hoja por defecto
        rows = []
        for row in ws.iter_rows(values_only=True):
            if any(cell is not None for cell in row):
                cells = [str(c).strip() if c is not None else '' for c in row]
                rows.append('\t'.join(cells))
        return '\n'.join(rows)
    except Exception as e:
        logger.error(f'Error leyendo Excel: {e}')
        raise


def extract_text_from_csv(file_bytes: bytes) -> str:
    """Convierte CSV a texto tabular."""
    try:
        # Detecta encoding
        for encoding in ('utf-8', 'latin-1', 'cp1252'):
            try:
                text = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        reader = csv.reader(io.StringIO(text))
        rows = ['\t'.join(row) for row in reader if any(c.strip() for c in row)]
        return '\n'.join(rows)
    except Exception as e:
        logger.error(f'Error leyendo CSV: {e}')
        raise


def extract_text_from_excel_b64(file_b64: str, file_name: str = '') -> str:
    """Extrae texto de Excel/CSV codificado en base64."""
    file_bytes = base64.b64decode(file_b64)
    name_lower = file_name.lower()
    if name_lower.endswith('.csv'):
        return extract_text_from_csv(file_bytes)
    else:
        return extract_text_from_excel(file_bytes, file_name)
