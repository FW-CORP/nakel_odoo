/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { session } from "@web/session";
import BarcodePickingBatchModel from "@stock_barcode_picking_batch/models/barcode_picking_batch_model";

function isEnabled() {
    return Boolean(session.nakel_barcode_wave_validate_confirm_enabled);
}

function confirmMessage() {
    return (
        session.nakel_barcode_wave_validate_confirm_message ||
        _t("¿Realmente querés validar la OLA?")
    );
}

/**
 * Diálogo Aceptar / Cancelar antes de validar una ola (stock.picking.batch) en Barcode.
 */
async function askValidateWaveConfirm(dialogService) {
    return new Promise((resolve) => {
        let settled = false;
        const finish = (accepted) => {
            if (settled) {
                return;
            }
            settled = true;
            resolve(accepted);
        };
        dialogService.add(
            ConfirmationDialog,
            {
                title: _t("Validar ola"),
                body: confirmMessage(),
                confirmLabel: _t("Aceptar"),
                cancelLabel: _t("Cancelar"),
                confirm: () => finish(true),
                cancel: () => finish(false),
            },
            { onClose: () => finish(false) }
        );
    });
}

patch(BarcodePickingBatchModel.prototype, {
    async _validate() {
        if (!isEnabled()) {
            return super._validate(...arguments);
        }
        const confirmed = await askValidateWaveConfirm(this.dialogService);
        if (!confirmed) {
            return;
        }
        return super._validate(...arguments);
    },
});
