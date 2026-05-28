/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { session } from "@web/session";
import BarcodePickingBatchModel from "@stock_barcode_picking_batch/models/barcode_picking_batch_model";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";

/**
 * Si el módulo está instalado pero la sesión no se recargó, la clave puede faltar:
 * en ese caso respetamos el default del parámetro (activado).
 */
function isConfirmEnabled() {
    const v = session.nakel_barcode_wave_validate_confirm_enabled;
    if (v === false || v === 0 || v === "0" || v === "false") {
        return false;
    }
    return true;
}

function defaultMessage() {
    return _t("¿Realmente querés validar?");
}

function waveMessage() {
    return session.nakel_barcode_wave_validate_confirm_message || _t("¿Realmente querés validar la OLA?");
}

function pickingMessage() {
    return session.nakel_barcode_wave_validate_confirm_message_picking || waveMessage();
}

async function askValidateConfirm(dialogService, { title, body }) {
    if (!dialogService) {
        return true;
    }
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
                title,
                body: body || defaultMessage(),
                confirmLabel: _t("Aceptar"),
                cancelLabel: _t("Cancelar"),
                confirm: () => finish(true),
                cancel: () => finish(false),
            },
            { onClose: () => finish(false) }
        );
    });
}

/**
 * Parchea _validate o, si no existe, validate (según versión / herencia del modelo Barcode).
 */
function patchValidateWithConfirm(Model, config) {
    const methodName =
        typeof Model.prototype._validate === "function"
            ? "_validate"
            : typeof Model.prototype.validate === "function"
              ? "validate"
              : null;
    if (!methodName) {
        console.warn(
            "[nakel_barcode_wave_validate_confirm] No se encontró _validate/validate en",
            Model.name || Model
        );
        return;
    }
    patch(Model.prototype, {
        async [methodName](...args) {
            if (!isConfirmEnabled()) {
                return super[methodName](...args);
            }
            const confirmed = await askValidateConfirm(this.dialogService, {
                title: config.title,
                body: config.getBody ? config.getBody() : config.body,
            });
            if (!confirmed) {
                return;
            }
            return super[methodName](...args);
        },
    });
}

patchValidateWithConfirm(BarcodePickingBatchModel, {
    title: _t("Validar ola"),
    getBody: waveMessage,
});

patchValidateWithConfirm(BarcodePickingModel, {
    title: _t("Validar picking"),
    getBody: pickingMessage,
});
