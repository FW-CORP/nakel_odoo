/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { RPCError } from "@web/core/network/rpc";
import { UncaughtPromiseError } from "@web/core/errors/error_service";
import { session } from "@web/session";

/**
 * When Barcode (or backend) still references a deleted stock.move / stock.move.line,
 * Odoo raises MissingError and the default RPC dialog blocks operators.
 *
 * If session flag nakel_fix_pick_soft_missing is true (see ir.config_parameter
 * nakel_fix_pick.barcode_soft_missing), replace the blocking dialog with a short
 * warning and reload the webclient so Barcode re-fetches fresh ids.
 */
function nakelFixPickSoftMissingHandler(env, error, originalError) {
    if (!(error instanceof UncaughtPromiseError)) {
        return false;
    }
    if (!session.nakel_fix_pick_soft_missing) {
        return false;
    }
    if (!(originalError instanceof RPCError)) {
        return false;
    }
    const exName = originalError.exceptionName || "";
    const data = originalError.data;
    const dataMsg = data && typeof data === "object" && data.message != null ? String(data.message) : "";
    const msg = `${originalError.message || ""} ${dataMsg} ${exName}`;
    const model = originalError.model || "";
    const stockRefInMessage = /stock\.move(\.line)?\s*\(/i.test(msg);
    if (model !== "stock.move" && model !== "stock.move.line" && !stockRefInMessage) {
        return false;
    }
    const looksMissing =
        exName.includes("MissingError") ||
        /does not exist|Record does not exist|no existe|fue eliminado|Could not find|Record not found/i.test(
            msg
        );
    if (!looksMissing) {
        return false;
    }
    error.unhandledRejectionEvent?.preventDefault?.();
    env.services.notification.add(
        _t(
            "Inventario (código de barras): referencia desactualizada. Recargando la pantalla para volver a sincronizar."
        ),
        { type: "warning" }
    );
    browser.setTimeout(() => browser.location.reload(), 400);
    return true;
}

registry.category("error_handlers").add("nakelFixPickSoftMissingHandler", nakelFixPickSoftMissingHandler, {
    sequence: 96,
});
