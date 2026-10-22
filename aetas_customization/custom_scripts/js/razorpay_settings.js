frappe.ui.form.on('Razorpay Settings', {
    refresh: function (frm) {
        if (frm.is_new()) {
            return;
        }

        frm.add_custom_button(__('Register Webhook'), function () {
            frappe.confirm(
                __('This will (re)register the Razorpay webhook for boutique {0} and generate a new webhook secret. Continue?', [frm.doc.boutique]),
                function () {
                    frappe.call({
                        method: 'aetas_customization.aetas_customization.api.webhook_registration.register_webhook_manually',
                        args: { razorpay_settings: frm.doc.name },
                        freeze: true,
                        freeze_message: __('Registering webhook...'),
                        callback: function () {
                            frm.reload_doc();
                        }
                    });
                }
            );
        }, __('Webhook'));

        frm.add_custom_button(__('Unregister Webhook'), function () {
            frappe.confirm(
                __('This will remove the Razorpay webhook registered for boutique {0}. Continue?', [frm.doc.boutique]),
                function () {
                    frappe.call({
                        method: 'aetas_customization.aetas_customization.api.webhook_registration.unregister_webhook_manually',
                        args: { razorpay_settings: frm.doc.name },
                        freeze: true,
                        freeze_message: __('Unregistering webhook...'),
                        callback: function () {
                            frm.reload_doc();
                        }
                    });
                }
            );
        }, __('Webhook'));
    }
});
