import logging

from odoo import models

_logger = logging.getLogger(__name__)


def _fix_sircar_line(line: str) -> str:
    """
    Ajuste de layout SIRCAR según formato validado por AFIP para Nakel:
    - Col 10 debe ser "001" (tipo comprobante) en lugar de l10n_ar_code.
    - Col 11 debe quedar como jurisdicción (se conserva lo que venga en col 11).

    Nota: trabajamos por post-proceso sin tocar el generador core/localización.
    """
    raw = line.rstrip("\r\n")
    if not raw:
        return line

    cols = raw.split(",")
    # Esperamos 11 columnas. Si no, no tocamos (para no romper casos Córdoba u otros layouts).
    if len(cols) != 11:
        return line

    # col 10 (índice 9): tipo comprobante fijo
    cols[9] = "001"

    return ",".join(cols) + ("\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else ""))


def _fix_sircar_txt(content: str) -> str:
    if not content:
        return content
    return "".join(_fix_sircar_line(l) for l in content.splitlines(keepends=True))


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def get_tax_settlement_files_values(self, move_lines):
        files = super().get_tax_settlement_files_values(move_lines)

        self.ensure_one()
        if self.settlement_tax != "iibb_aplicado_sircar":
            return files

        normalized = []
        for f in files or []:
            if not isinstance(f, dict):
                normalized.append(f)
                continue
            txt = f.get("txt_content")
            if isinstance(txt, str) and txt:
                f = dict(f)
                f["txt_content"] = _fix_sircar_txt(txt)
            normalized.append(f)

        _logger.info("SIRCAR TXT post-processed for journal %s (%s).", self.id, self.display_name)
        return normalized

