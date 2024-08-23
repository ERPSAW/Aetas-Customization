// Copyright (c) 2024, Akhilam Inc and contributors
// For license information, please see license.txt

frappe.ui.form.on('Aetas Delivery Challan', {
	refresh: function(frm) {
		frm.set_query('supplier_address', () => {
			return {
				filters: {
					'link_doctype':'Supplier',
					'link_name': frm.doc.supplier
				}
			}
		})

		frm.set_query('warehouse', 'items', () => {
			return {
				filters: {
					is_group: 0,
					custom_is_reserved:0
				}
			}
		})
		if(frm.doc.docstatus === 1){
			frm.add_custom_button(__("Generate"),() => 
				show_generate_e_waybill_dialog(frm),
			"e-Waybill");
		}
		
	},
	supplier_address:function(frm){
		if(frm.doc.supplier_address){
			return frm.call({
			method: "frappe.contacts.doctype.address.address.get_address_display",
			args: {
			   "address_dict": frm.doc.supplier_address
			},
			callback: function(r) {
			  if(r.message)
				  frm.set_value("supplier_address_display", r.message);
				}
		   });
		  }
		  else{
			  frm.set_value("supplier_address_display", "");
		  }
	}
});

function show_generate_e_waybill_dialog(frm) {
    const generate_action = values => {
        frappe.call({
            method: "india_compliance.gst_india.utils.e_waybill.generate_e_waybill",
            args: {
                doctype: frm.doctype,
                docname: frm.doc.name,
                values: values,
                force: true,
            },
            callback: () => {
                return frm.refresh();
            },
        });
    };

    const json_action = async values => {
        const ewb_data = await frappe.xcall(
            "india_compliance.gst_india.utils.e_waybill.generate_e_waybill_json",
            {
                doctype: frm.doctype,
                docnames: frm.doc.name,
                values,
            }
        );

        frm.refresh();
        india_compliance.trigger_file_download(
            ewb_data,
            get_e_waybill_file_name(frm.doc.name)
        );
    };

    const api_enabled = india_compliance.is_api_enabled();

    const d = get_generate_e_waybill_dialog(
        {
            title: __("Generate e-Waybill"),
            primary_action_label: get_primary_action_label_for_generation(frm.doc),
            primary_action(values) {
                d.hide();
                if (api_enabled) {
                    generate_action(values);
                } else {
                    json_action(values);
                }
            },
            secondary_action_label:
                api_enabled && frm.doc.doctype ? __("Download JSON") : null,
            secondary_action: api_enabled
                ? () => {
                    d.hide();
                    json_action(d.get_values());
                }
                : null,
        },
        frm
    );

    d.show();
    set_gst_transporter_id_status(d);

    //Alert if E-waybill cannot be generated using api
    if (!is_e_waybill_generatable(frm)) {
        const address = frm.doc.customer_address || frm.doc.supplier_address;
        const reason = !address
            ? "<strong>party address</strong> is missing."
            : "party <strong>GSTIN is same</strong> as company GSTIN.";
        $(`
            <div class="alert alert-warning" role="alert">
                e-Waybill cannot be generated as ${reason}
            </div>
        `).prependTo(d.wrapper);
        d.disable_primary_action();
    }

    // Alert if e-Invoice hasn't been generated
    if (
        frm.doctype === "Sales Invoice" &&
        is_e_invoice_applicable(frm) &&
        !frm.doc.irn
    ) {
        $(`
            <div class="alert alert-warning" role="alert">
                e-Invoice hasn't been generated for this Sales Invoice.
                <a
                    href="https://docs.erpnext.com/docs/v14/user/manual/en/regional/india/generating_e_invoice#what-if-we-generate-e-waybill-before-the-e-invoice"
                    class="alert-link"
                    target="_blank"
                >
                    Learn more
                </a>
            </div>
        `).prependTo(d.wrapper);
    }
}

function set_gst_transporter_id_status(dialog) {
    const gst_transporter_id_field = dialog.get_field("gst_transporter_id");

    india_compliance.set_gstin_status(gst_transporter_id_field);
}

function get_generate_e_waybill_dialog(opts, frm) {
    if (!frm) frm = { doc: {} };
    const fields = [
        {
            label: "Part A",
            fieldname: "section_part_a",
            fieldtype: "Section Break",
        },
        {
            label: "Transporter",
            fieldname: "transporter",
            fieldtype: "Link",
            options: "Supplier",
            default: frm.doc.transporter,
            get_query: () => {
                return {
                    filters: {
                        is_transporter: 1,
                    },
                };
            },
            onchange: () => update_gst_tranporter_id(d),
        },
        {
            label: "Distance (in km)",
            fieldname: "distance",
            fieldtype: "Float",
            default: frm.doc.distance || 0,
            description:
                "Set as zero to update distance as per the e-Waybill portal (if available)",
        },
        {
            fieldtype: "Column Break",
        },
        {
            label: "GST Transporter ID",
            fieldname: "gst_transporter_id",
            fieldtype: "Data",
            default:
                frm.doc.gst_transporter_id?.length == 15
                    ? frm.doc.gst_transporter_id
                    : "",
            onchange: () => set_gst_transporter_id_status(d),

        },
        // Sub Supply Type will be visible here for Delivery Note
        {
            label: "Part B",
            fieldname: "section_part_b",
            fieldtype: "Section Break",
        },

        {
            label: "Vehicle No",
            fieldname: "vehicle_no",
            fieldtype: "Data",
            default: frm.doc.vehicle_no,
            onchange: () => update_generation_dialog(d, frm.doc),
        },
        {
            label: "Transport Receipt No",
            fieldname: "lr_no",
            fieldtype: "Data",
            default: frm.doc.lr_no,
            onchange: () => update_generation_dialog(d, frm.doc),
        },
        {
            label: "Transport Receipt Date",
            fieldname: "lr_date",
            fieldtype: "Date",
            default: frm.doc.lr_date || "Today",
            mandatory_depends_on: "eval:doc.lr_no",
        },
        {
            fieldtype: "Column Break",
        },

        {
            label: "Mode Of Transport",
            fieldname: "mode_of_transport",
            fieldtype: "Select",
            options: `\nRoad\nAir\nRail\nShip`,
            default: frm.doc.mode_of_transport || "Road",
            onchange: () => {
                update_generation_dialog(d, frm.doc);
                update_vehicle_type(d);
            },
        },
        {
            label: "GST Vehicle Type",
            fieldname: "gst_vehicle_type",
            fieldtype: "Select",
            options: `Regular\nOver Dimensional Cargo (ODC)`,
            depends_on: 'eval:["Road", "Ship"].includes(doc.mode_of_transport)',
            read_only_depends_on: "eval: doc.mode_of_transport == 'Ship'",
            default: frm.doc.gst_vehicle_type || "Regular",
        },
    ];

    if (frm.doctype === "Delivery Note") {
        const same_gstin = frm.doc.billing_address_gstin == frm.doc.company_gstin;
        let options;

        if (frm.doc.is_return) {
            if (same_gstin) {
                options = ["For Own Use", "Exhibition or Fairs"];
            } else {
                options = ["Job Work Returns", "SKD/CKD"];
            }
        } else {
            if (same_gstin) {
                options = [
                    "For Own Use",
                    "Exhibition or Fairs",
                    "Line Sales",
                    "Recipient Not Known",
                ];
            } else {
                options = ["Job Work", "SKD/CKD"];
            }
        }

        // Inserted at the end of Part A section
        fields.splice(5, 0, {
            label: "Sub Supply Type",
            fieldname: "sub_supply_type",
            fieldtype: "Select",
            options: options.join("\n"),
            default: options[0],
            reqd: 1,
        });
    }

    const is_foreign_transaction =
        frm.doc.gst_category === "Overseas" &&
        frm.doc.place_of_supply === "96-Other Countries";

    if (frm.doctype === "Sales Invoice" && is_foreign_transaction) {
        fields.splice(5, 0, {
            label: "Origin Port / Border Checkpost Address",
            fieldname: "port_address",
            fieldtype: "Link",
            options: "Address",
            default: frm.doc.port_address,
            reqd: frm.doc?.__onload?.shipping_address_in_india != true,
            get_query: () => {
                return {
                    filters: {
                        country: "India",
                    },
                };
            },
        });
    }

    opts.fields = fields;

    // HACK!
    // To prevent triggering of change event on input twice
    frappe.ui.form.ControlData.trigger_change_on_input_event = false;
    const d = new frappe.ui.Dialog(opts);
    frappe.ui.form.ControlData.trigger_change_on_input_event = true;

    return d;
}

function schedule_e_waybill_extension(frm, dialog, scheduled_time) {
    const values = dialog.get_values();
    if (values) {
        frappe.call({
            method: "india_compliance.gst_india.utils.e_waybill.schedule_ewaybill_for_extension",
            args: {
                doctype: frm.doctype,
                docname: frm.docname,
                values,
                scheduled_time,
            },
            callback: () => {
                if (frm.doc.__onload?.e_waybill_info) {
                    frm.doc.__onload.e_waybill_info.extension_scheduled = 1;
                }
            },
        });
    }
    dialog.hide();
}

function display_extension_scheduled_message(dialog, scheduled_time) {
    const message = `<div>Already scheduled for ${scheduled_time}</div>`;
    $(message).prependTo(dialog.footer);
}

function prefill_data_from_e_waybill_log(frm, dialog) {
    frappe.db
        .get_value("e-Waybill Log", frm.doc.ewaybill, ["extension_data"])
        .then(response => {
            const values = response.message;
            const extension_data = JSON.parse(values.extension_data);

            dialog.set_values(extension_data);
        });
}

function is_e_waybill_valid(frm) {
    const e_waybill_info = frm.doc.__onload && frm.doc.__onload.e_waybill_info;
    return (
        e_waybill_info &&
        (!e_waybill_info.valid_upto ||
            frappe.datetime
                .convert_to_user_tz(e_waybill_info.valid_upto, false)
                .diff() > 0)
    );
}

function has_e_waybill_threshold_met(frm) {
    if (Math.abs(frm.doc.base_grand_total) >= gst_settings.e_waybill_threshold)
        return true;
}
function is_e_waybill_applicable(frm, show_message) {
    return new E_WAYBILL_CLASS[frm.doctype](frm).is_e_waybill_applicable(show_message);
}

function is_e_waybill_api_enabled(frm) {
    return new E_WAYBILL_CLASS[frm.doctype](frm).is_e_waybill_api_enabled();
}

function is_e_waybill_generatable(frm, show_message) {
    return new E_WAYBILL_CLASS[frm.doctype](frm).is_e_waybill_generatable(show_message);
}

function auto_generate_e_waybill(frm) {
    return new E_WAYBILL_CLASS[frm.doctype](frm).auto_generate_e_waybill();
}

function can_extend_e_waybill(frm) {
    if (
        frm.doc.gst_transporter_id &&
        frm.doc.gst_transporter_id != frm.doc.company_gstin
    )
        return false;

    return true;
}

function get_hours(date, hours, date_time_format = frappe.defaultDatetimeFormat) {
    return moment(date).add(hours, "hours").format(date_time_format);
}

function can_extend_e_waybill_now(valid_upto) {
    const extend_after = get_hours(valid_upto, -8);
    const extend_before = get_hours(valid_upto, 8);
    const now = frappe.datetime.now_datetime();

    if (extend_after < now && now < extend_before) return true;
    return false;
}

function has_extend_validity_expired(frm) {
    const valid_upto = frm.doc.__onload?.e_waybill_info?.valid_upto;
    const extend_before = get_hours(valid_upto, 8);
    const now = frappe.datetime.now_datetime();

    if (now > extend_before) return true;
    return false;
}

function is_e_waybill_cancellable(frm) {
    const e_waybill_info = frm.doc.__onload && frm.doc.__onload.e_waybill_info;
    return (
        e_waybill_info &&
        frappe.datetime
            .convert_to_user_tz(e_waybill_info.created_on, false)
            .add("days", 1)
            .diff() > 0
    );
}

async function update_gst_tranporter_id(dialog) {
    const transporter = dialog.get_value("transporter");
    const { message: response } = await frappe.db.get_value(
        "Supplier",
        transporter,
        "gst_transporter_id"
    );

    dialog.set_value("gst_transporter_id", response.gst_transporter_id);
}

function set_gst_transporter_id_status(dialog) {
    const gst_transporter_id_field = dialog.get_field("gst_transporter_id");

    india_compliance.set_gstin_status(gst_transporter_id_field);
}

function update_generation_dialog(dialog, doc) {
    const dialog_values = dialog.get_values(true);
    const primary_action_label = get_primary_action_label_for_generation(dialog_values);

    dialog.set_df_property(
        "gst_transporter_id",
        "reqd",
        primary_action_label.includes("Part A") ? 1 : 0
    );

    if (is_empty(doc)) return;

    set_primary_action_label(dialog, primary_action_label);
}

function get_primary_action_label_for_generation(doc) {
    const label = india_compliance.is_api_enabled()
        ? __("Generate")
        : __("Download JSON");

    if (are_transport_details_available(doc)) {
        return label;
    }

    return label + " (Part A)";
}

function is_empty(obj) {
    for (let prop in obj) {
        if (obj.hasOwnProperty(prop)) {
            return false;
        }
    }
    return true;
}
function are_transport_details_available(doc) {
    return (
        (doc.mode_of_transport == "Road" && doc.vehicle_no) ||
        (["Air", "Rail"].includes(doc.mode_of_transport) && doc.lr_no) ||
        (doc.mode_of_transport == "Ship" && doc.lr_no && doc.vehicle_no)
    );
}