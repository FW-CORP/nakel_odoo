import logging
import re
from typing import List

from odoo import models

_logger = logging.getLogger(__name__)


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _siap_numeric(value: str, width: int) -> str:
    """
    SIAP suele validar "Numérico Positivo" como:
    - solo dígitos (sin separadores, sin espacios)
    - con decimales implícitos (el layout ya fija la escala)
    """
    digits = _digits_only(value)
    if not digits:
        return "0" * width
    # si viene más largo, tomamos los últimos N dígitos para mantener los decimales implícitos al final
    if len(digits) > width:
        _logger.warning("SIAP numeric truncation: '%s' -> width %s", value, width)
        digits = digits[-width:]
    return digits.zfill(width)


def _siap_normalize_sicore_line(line_body: str) -> str:
    """
    Normaliza campos numéricos para formato SIAP en el layout generado por
    l10n_ar_account_tax_settlement.account_journal.sicore_aplicado_files_values.

    Layout (longitud 145, sin CRLF):
      0:2   Código comprobante
      2:12  Fecha emisión comprobante
      12:28 Número comprobante
      28:44 Importe comprobante          [16]  -> dígitos
      44:48 Código impuesto              [4]
      48:51 Código régimen               [3]
      51:52 Código operación             [1]
      52:66 Base de cálculo              [14]  -> dígitos
      66:76 Fecha emisión retención      [10]
      76:78 Código condición             [2]
      78:79 Retención pract...           [1]
      79:93 Importe ret/percepción       [14]  -> dígitos
      93:99 % exclusión                  [6]   -> dígitos
      99:109 Fecha emisión boletín       [10]
      109:111 Tipo doc retenido          [2]
      111:131 Nro doc retenido           [20]
      131:145 Nro certificado original   [14]
    """
    if len(line_body) < 145:
        return line_body

    importe_comprobante = _siap_numeric(line_body[28:44], 16)
    base_calculo = _siap_numeric(line_body[52:66], 14)
    importe_ret = _siap_numeric(line_body[79:93], 14)
    porc_exclusion = _siap_numeric(line_body[93:99], 6)

    return (
        line_body[:28]
        + importe_comprobante
        + line_body[44:52]
        + base_calculo
        + line_body[66:79]
        + importe_ret
        + porc_exclusion
        + line_body[99:]
    )


def _siap_normalize_sicore_txt(content: str) -> str:
    if not content:
        return content

    out: List[str] = []
    # preservamos CRLF si existiera
    for raw_line in content.splitlines(keepends=True):
        # si viene sin newline al final, keepends=True igual lo respeta como body
        m = re.match(r"^(.*?)(\r\n|\n|\r)?$", raw_line, flags=re.DOTALL)
        if not m:
            out.append(raw_line)
            continue
        body, eol = m.group(1), m.group(2) or ""
        if body:
            body = _siap_normalize_sicore_line(body)
        out.append(body + eol)
    return "".join(out)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def get_tax_settlement_files_values(self, move_lines):
        files = super().get_tax_settlement_files_values(move_lines)

        # Solo post-procesamos SICORE aplicado para compatibilidad SIAP
        self.ensure_one()
        if self.settlement_tax != "sicore_aplicado":
            return files

        normalized = []
        for f in files or []:
            if not isinstance(f, dict):
                normalized.append(f)
                continue
            txt = f.get("txt_content")
            if isinstance(txt, str) and txt:
                f = dict(f)
                f["txt_content"] = _siap_normalize_sicore_txt(txt)
            normalized.append(f)
        return normalized

