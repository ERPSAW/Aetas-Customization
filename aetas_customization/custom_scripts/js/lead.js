frappe.ui.form.on('Lead', {
    before_save: function (frm) {
        // DORMANT: the old bidding flow is superseded by the Lead Pipeline workflow.
        // Unqualified / sales-person assignment now happen via workflow transitions
        // (see the LEAD PIPELINE block at the bottom of this file). Kept inert to
        // avoid the assign-sales-person dialog firing when native status flips to
        // "Qualified" during the new flow.
        return;

        // --- LOGIC 1: Unqualified Status (Prompt for Reason) ---
        if (frm.doc.status == "UnQualified" && !frm.doc.__unqualified_handled) {
            // 1. Stop immediate save
            frappe.validated = false;

            // 2. Call Promise
            prompt_unqualified_reason(frm).then(() => {
                frm.doc.__unqualified_handled = true;
                frm.save();
            }).catch(() => {
                // User cancelled the dialog, save remains stopped
                console.log("User cancelled the dialog, save remains stopped");
            });

            // Return here so we don't trigger the Qualified logic simultaneously
            return;
        }

        // --- LOGIC 2: Qualified Status (Assign Sales Person) ---
        let bids = frm.doc.custom_bids || [];
        let is_any_approved = bids.some(row => row.status == "Approved");

        if (frm.doc.status == "Qualified" && frm.doc.custom_sales_person && !frm.doc.__assignment_handled && !is_any_approved) {

            // 1. Stop immediate save
            frappe.validated = false;

            // 2. Call Promise
            validate_and_assign_sales_person(frm).then(() => {
                frm.doc.__assignment_handled = true;
                frm.save();
            }).catch(() => {
                // User cancelled or closed dialog
            });
        }
    },
    refresh: function (frm) {

        // DORMANT: bidding Approve/Unapprove buttons superseded by the Lead
        // Pipeline workflow. Helpers (show_approval_dialog / approve_sales_person /
        // unapprove_sales_person) are retained below but no longer wired to buttons.

        // --- Standard Custom Buttons ---
        if (!frm.doc.customer) {
            frm.add_custom_button(__('Search Customer'), function () {
                show_customer_search_dialog(frm);
            });
        }

        if (!frm.doc.custom_si_ref && (frm.doc.status == 'Qualified' || frm.doc.status == 'Converted')) {
            frm.add_custom_button(__('Create Sales Invoice'), function () {
                create_sales_invoice_from_lead(frm);
            });
        }

        setTimeout(() => {
            frm.remove_custom_button('Customer', 'Create');
        }, 10);

        // --- Styles & Hooks ---
        frm.trigger("inject_approved_button_css");
        frm.trigger("setup_grid_observer"); // <--- NEW: Setup the watcher
        frm.trigger("style_approved_buttons"); // Run once immediately
    },

    onload_post_render(frm) {
        frm.trigger("inject_approved_button_css");
        frm.trigger("style_approved_buttons");
    },

    inject_approved_button_css(frm) {
        if (document.getElementById("approved-btn-style")) return;
        const style = document.createElement("style");
        style.id = "approved-btn-style";
        style.innerHTML = `
            button[data-fieldname="approved"] {
                background-color: #28a745 !important;
                color: #fff !important;
                border: none !important;
                display: flex; justify-content: center; align-items: center; 
                height: 30px !important; width: auto; cursor: pointer;
            }
            button[data-fieldname="approved"]:hover {
                background-color: #218838 !important;
            }
        `;
        document.head.appendChild(style);
    },

    setup_grid_observer(frm) {
        // This watches the grid for ANY changes (like row clicks/renders)
        if (!frm.fields_dict.custom_bids) return;
        const grid = frm.fields_dict.custom_bids.grid;

        // Only attach once
        if (grid.wrapper.data('observer-attached')) return;

        const observer = new MutationObserver((mutations) => {
            // Re-apply styles whenever DOM changes
            frm.trigger("style_approved_buttons");
        });

        observer.observe(grid.wrapper[0], {
            childList: true, // Watch for added/removed rows
            subtree: true    // Watch deeper (like button text changes inside rows)
        });

        grid.wrapper.data('observer-attached', true);
    },

    style_approved_buttons(frm) {
        if (!frm.fields_dict.custom_bids) return;
        const grid = frm.fields_dict.custom_bids.grid;

        (grid.grid_rows || []).forEach(row => {
            const d = row.doc;
            const $btn = $(row.wrapper).find('button[data-fieldname="approved"]');

            if (!$btn.length) return;

            if (d.status === "Approved") {
                // If Approved: HIDE button
                // Check visibility first to avoid infinite MutationObserver loops
                if ($btn.is(":visible")) {
                    $btn.hide();
                    $btn.parent().hide();
                }
            } else {
                // If Not Approved: SHOW button and set text to "Approve"
                if (!$btn.is(":visible")) {
                    $btn.parent().show();
                    $btn.show();
                    $btn.css('display', 'flex');
                }

                // CRITICAL: Force text to "Approve" if it reverted to default
                if ($btn.text() !== "Approve") {
                    $btn.text("Approve");
                }

                if ($btn.prop("disabled")) {
                    $btn.prop("disabled", false);
                }
            }
        });
    }
});

function add_bid_row(frm, sales_person) {
    let row = frm.add_child("custom_bids");

    if (sales_person) {
        row.sales_person = sales_person;
    } else {
        // Logic for "Open for All" - maybe leave sales_person empty?
        row.sales_person = "";
    }

    row.status = (frm.doc.type == "Existing Customer") ? "Approved" : "Applied";
    row.applied_on = frappe.datetime.get_today();
    row.approved_by = frappe.session.user;

    frm.refresh_field("custom_bids");
}

// --- HELPER FUNCTION: Prompt for Unqualified Reason ---
function prompt_unqualified_reason(frm) {
    return new Promise((resolve, reject) => {
        let d = new frappe.ui.Dialog({
            title: __('Unqualified Reason'),
            fields: [
                {
                    label: __('Reason'),
                    fieldname: 'reason',
                    fieldtype: 'Small Text',
                    reqd: 1,
                    description: "Please specify why this lead is unqualified."
                }
            ],
            primary_action_label: __('Submit'),
            primary_action: function (values) {
                // Save reason to a custom field (Ensure 'custom_unqualified_reason' exists in DocType)
                frm.doc.custom_unqualified_reason = values.reason;
                d.hide();
                console.log("Unqualified Reason: ", values.reason);
                resolve(); // Proceed with Save
            },
        });
        d.show();
    });
}

function validate_and_assign_sales_person(frm) {
    return new Promise(function (resolve, reject) {

        // 1. Check for duplicate assignment
        let already_exists = (frm.doc.custom_bids || []).some(
            row => row.sales_person == frm.doc.custom_sales_person
        );

        if (already_exists) {
            resolve();
            return;
        }

        // 2. Custom Dialog
        let d = new frappe.ui.Dialog({
            title: __('Assign Sales Person'),
            fields: [
                {
                    fieldtype: 'HTML',
                    options: `<p>Do you want to assign <b>${frm.doc.custom_sales_person}</b> to this Lead or keep it Open for All?</p>`
                }
            ],
            // Button 1: Specific Sales Person
            primary_action_label: __('This Sales Person'),
            primary_action: function () {
                add_bid_row(frm, frm.doc.custom_sales_person); // Pass specific person
                d.hide();
                resolve();
            },
            // Button 2: Open For All
            secondary_action_label: __('Open for All'),
            secondary_action: function () {
                frm.doc.custom_sales_person = "";
                d.hide();
                resolve();
            }
        });

        d.show();
    });
}

frappe.ui.form.on('Sales Person Bids', {
    approved(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.status === "Approved") return;

        frappe.model.set_value(cdt, cdn, "status", "Approved");
        frappe.model.set_value(cdt, cdn, "approved_by", frappe.session.user);

        frm.save().then(() => {
            frappe.show_alert({ message: __("Bid Approved"), indicator: "green" });
            // Observer will automatically handle the hiding now
        });
    }
});

function show_customer_search_dialog(frm) {
    // --- State Management ---
    let current_page = 1;
    let total_pages = 0;
    const page_len = 20;
    let current_filters = {};

    // Define the custom HTML template for the table
    const get_table_html = (rows) => {
        if (!rows || rows.length === 0) {
            return `<div class="text-center text-muted" style="padding: 20px;">${__("No customers found.")}</div>`;
        }

        let rows_html = rows.map(row => {
            // Keep vertical-align: middle for neatness, but LEFT align text columns
            // Only CENTER align the last column (Action)
            return `
                <tr>
                    <td style="vertical-align: middle;">
                        <a href="/app/customer/${row.name}" target="_blank" style="font-weight: bold;">${row.name}</a>
                    </td>
                    <td style="vertical-align: middle;">${row.customer_name || ''}</td>
                    <td style="vertical-align: middle;">${row.email_id || ''}</td>
                    <td style="vertical-align: middle;">${row.mobile_no || ''}</td>
                    <td style="text-align: center; vertical-align: middle;">
                        <button class="btn btn-xs btn-primary btn-use-customer"
                            data-name="${row.name}"
                            data-customer-name="${row.customer_name || ''}"
                            data-email="${row.email_id || ''}"
                            data-mobile="${row.mobile_no || ''}"
                            data-sales-person="${row.custom_sales_person || ''}"
                        >
                            ${__("Use")}
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        return `
            <div class="table-responsive">
                <table class="table table-bordered table-hover table-condensed">
                    <thead>
                        <tr style="background-color: #f7fafc;">
                            <th style="width: 15%; vertical-align: middle;">${__("ID")}</th>
                            <th style="width: 30%; vertical-align: middle;">${__("Name")}</th>
                            <th style="width: 25%; vertical-align: middle;">${__("Email")}</th>
                            <th style="width: 20%; vertical-align: middle;">${__("Mobile")}</th>
                            <th style="width: 10%; text-align: center; vertical-align: middle;">${__("Action")}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows_html}
                    </tbody>
                </table>
            </div>
        `;
    };

    let d = new frappe.ui.Dialog({
        title: __('Search and Link Customer'),
        size: 'extra-large',
        fields: [
            // --- ROW START ---
            { fieldtype: 'Section Break', label: '' },

            // --- COLUMN 1 (LEFT 20%) ---
            { fieldtype: 'Column Break', fieldname: 'col_left' },
            { label: __('Name'), fieldname: 'search_name', fieldtype: 'Data' },
            { label: __('Email'), fieldname: 'search_email', fieldtype: 'Data' },
            { label: __('Mobile'), fieldname: 'search_mobile', fieldtype: 'Data' },
            { fieldtype: 'HTML', options: '<div style="height: 10px;"></div>' },
            {
                label: __('Search'),
                fieldname: 'search_btn',
                fieldtype: 'Button',
                click: function () {
                    let data = d.get_values();
                    if (!data.search_name && !data.search_email && !data.search_mobile) {
                        frappe.msgprint(__('Please enter at least one search criterion.'));
                        return;
                    }
                    current_filters = data;
                    current_page = 1;
                    run_search();
                }
            },

            // --- COLUMN 2 (RIGHT 80%) ---
            { fieldtype: 'Column Break', fieldname: 'col_right' },
            {
                label: __('Search Results'),
                fieldname: 'results_html',
                fieldtype: 'HTML',
                options: `<div class="text-muted text-center" style="padding: 40px; border: 1px dashed #d1d8dd; border-radius: 4px;">
                    ${__("Enter criteria and search to see results")}
                </div>`
            },

            // --- Pagination Controls ---
            {
                fieldtype: 'HTML',
                fieldname: 'pagination_html',
                options: `
                    <div class="row" style="margin-top: 10px; display: none;" id="pagination-controls">
                        <div class="col-xs-12 text-right">
                            <button class="btn btn-default btn-sm" id="btn-prev" disabled>
                                <span class="fa fa-chevron-left"></span> ${__("Previous")}
                            </button>
                            <span id="page-info" style="margin: 0 15px; font-weight: bold; vertical-align: middle;"></span>
                            <button class="btn btn-default btn-sm" id="btn-next" disabled>
                                ${__("Next")} <span class="fa fa-chevron-right"></span>
                            </button>
                        </div>
                    </div>
                `
            }
        ]
    });

    // --- Search Logic ---
    const run_search = () => {
        let $container = d.fields_dict.results_html.$wrapper;
        $container.css('opacity', '0.5');

        frappe.call({
            method: 'aetas_customization.api.search_customers',
            args: {
                name: current_filters.search_name,
                email: current_filters.search_email,
                mobile: current_filters.search_mobile,
                page: current_page,
                page_len: page_len
            },
            freeze: false,
            callback: function (r) {
                $container.css('opacity', '1');

                if (r.message) {
                    let results = r.message.data || [];
                    total_pages = r.message.total_pages || 0;
                    current_page = r.message.page || 1;

                    results.forEach(row => {
                        row.mobile_no = row.custom_contact || row.mobile_no;
                    });

                    $container.html(get_table_html(results));
                    update_pagination_ui();
                }
            }
        });
    };

    // --- UI Updates ---
    const update_pagination_ui = () => {
        let $controls = d.$wrapper.find('#pagination-controls');

        if (total_pages > 0) {
            $controls.show();
            d.$wrapper.find('#page-info').text(`Page ${current_page} of ${total_pages}`);
            d.$wrapper.find('#btn-prev').prop('disabled', current_page <= 1);
            d.$wrapper.find('#btn-next').prop('disabled', current_page >= total_pages);
        } else {
            $controls.hide();
        }
    };

    d.show();

    // --- Post-Render Setup ---
    setTimeout(() => {
        d.$wrapper.find('.modal-dialog').css("max-width", "95%").css("width", "95%");

        let $columns = d.$wrapper.find('.form-section .form-column');
        if ($columns.length >= 2) {
            $columns.eq(0).css({ 'flex': '0 0 20%', 'max-width': '20%' });
            $columns.eq(1).css({ 'flex': '0 0 80%', 'max-width': '80%' });
        }

        let $html_wrapper = d.fields_dict.results_html.$wrapper;
        $html_wrapper.css({
            'max-height': '55vh',
            'overflow-y': 'auto',
            'border': '1px solid #d1d8dd',
            'border-radius': '4px'
        });

        d.$wrapper.find('#btn-prev').off('click').on('click', function () {
            if (current_page > 1) { current_page--; run_search(); }
        });
        d.$wrapper.find('#btn-next').off('click').on('click', function () {
            if (current_page < total_pages) { current_page++; run_search(); }
        });

        $html_wrapper.off('click').on('click', '.btn-use-customer', function (e) {
            e.preventDefault();
            let $btn = $(this);

            let data = {
                name: $btn.attr('data-name'),
                customer_name: $btn.attr('data-customer-name'),
                email_id: $btn.attr('data-email'),
                mobile_no: $btn.attr('data-mobile'),
                custom_sales_person: $btn.attr('data-sales-person')
            };

            if (data.customer_name) frm.set_value('first_name', data.customer_name);
            frm.set_value('status', 'Open');
            frm.set_value('type', 'Existing Customer');
            frm.set_value('customer', data.name);

            if (data.email_id && data.email_id !== 'null') frm.set_value('email_id', data.email_id);
            if (data.mobile_no && data.mobile_no !== 'null') {
                frm.set_value('mobile_no', data.mobile_no);
            }
            if (data.custom_sales_person && data.custom_sales_person !== 'null' && frm.fields_dict.custom_sales_person) {
                frm.set_value('custom_sales_person', data.custom_sales_person);
            }

            frappe.show_alert({
                message: __('Customer Linked: ' + data.customer_name),
                indicator: 'green'
            });

            d.hide();
        });

    }, 200);
}


function create_sales_invoice_from_lead(frm) {
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Lead',
            name: frm.doc.name
        },
        callback: function (r) {
            if (r.message) {
                var lead = r.message;
                frappe.model.open_mapped_doc({
                    method: 'aetas_customization.overrides.lead.make_sales_invoice_from_lead',
                    frm: frm
                });
            }
        }
    });
}

function show_approval_dialog(frm) {
    // 1. Get list of Sales Persons from the child table who are 'Applied'
    let options = frm.doc.custom_bids
        .filter(d => d.status !== 'Approved') // Should be all of them, but safety first
        .map(d => ({ label: d.sales_person, value: d.sales_person }));

    if (options.length === 0) {
        frappe.msgprint(__('No Sales Persons available to approve.'));
        return;
    }

    // 2. Create Dialog
    let d = new frappe.ui.Dialog({
        title: __('Select Sales Person to Approve'),
        fields: [
            {
                label: 'Sales Person',
                fieldname: 'sales_person',
                fieldtype: 'Select',
                options: options,
                reqd: 1
            }
        ],
        primary_action_label: __('Approve'),
        primary_action: function (data) {
            approve_sales_person(frm, data.sales_person);
            d.hide();
        }
    });

    d.show();
}

function approve_sales_person(frm, sales_person_name) {
    frappe.dom.freeze(__('Approving...'));

    // 1. Find the specific row
    let row = (frm.doc.custom_bids || []).find(d => d.sales_person == sales_person_name);

    if (row) {
        // 2. Update Status
        frappe.model.set_value(row.doctype, row.name, 'status', 'Approved');
        frappe.model.set_value(row.doctype, row.name, 'approved_by', frappe.session.user);
        frm.set_value("custom_sales_person", sales_person_name);
        // 3. Save
        frm.save().then(() => {
            frappe.dom.unfreeze();
            frappe.show_alert({ message: __('Sales Person Approved'), indicator: 'green' });
            // Refresh will automatically toggle the buttons
        }).catch(() => {
            frappe.dom.unfreeze();
        });
    } else {
        frappe.dom.unfreeze();
        frappe.msgprint(__('Could not find row for selected Sales Person.'));
    }
}

function unapprove_sales_person(frm, row) {
    frappe.confirm(
        __('Are you sure you want to <b>Unapprove</b> {0}?', [row.sales_person]),
        function () {
            // YES
            frappe.dom.freeze(__('Unapproving...'));

            // 1. Revert Status
            frappe.model.set_value(row.doctype, row.name, 'status', 'Applied');
            frappe.model.set_value(row.doctype, row.name, 'approved_by', null); // Clear approver

            // 2. Save
            frm.save().then(() => {
                frappe.dom.unfreeze();
                frappe.show_alert({ message: __('Sales Person Unapproved'), indicator: 'orange' });
            }).catch(() => {
                frappe.dom.unfreeze();
            });
        }
    );
}


// =============================================================================
// LEAD PIPELINE (Frappe Workflow "Lead Pipeline")
// -----------------------------------------------------------------------------
// Stage-advance buttons are auto-generated by the workflow. This block only:
//   * shows the current probability as an indicator
//   * adds a "Log Attempt (Not Contacted)" button while the lead is Open
//   * intercepts the transitions that need extra input (Allocate / Close Lost /
//     Mark Unqualified) — collecting the value in a dialog, then applying the
//     transition server-side (see aetas_customization/lead/actions.py).
// This is a separate handler registration; the (dormant) bidding block above is
// left untouched.
// =============================================================================

const LEAD_PIPELINE = {
    // action name -> server method + the field it needs
    Allocate: 'aetas_customization.lead.actions.allocate_lead',
    'Close Lost': 'aetas_customization.lead.actions.close_lost',
    'Mark Unqualified': 'aetas_customization.lead.actions.mark_unqualified',
};

frappe.ui.form.on('Lead', {
    refresh(frm) {
        if (frm.is_new()) return;

        // Header chip: show the pipeline stage (workflow_state) with a per-stage colour,
        // so the title indicator reflects the pipeline rather than the (hidden) native status.
        const STAGE_COLOR = {
            'Open': 'yellow',
            'Follow Up': 'orange',
            'In Progress': 'blue',
            'Qualified': 'cyan',
            'Prospecting': 'cyan',
            'Visit Planned': 'purple',
            'Lead Allocation': 'orange',
            'Closed Won': 'green',
            'Closed Lost': 'red',
            'Unqualified': 'red',
        };
        if (frm.doc.workflow_state) {
            frm.page.set_indicator(
                frm.doc.workflow_state,
                STAGE_COLOR[frm.doc.workflow_state] || 'gray'
            );
        }

        const probability = frm.doc.custom_probability || 0;
        frm.dashboard.add_indicator(
            __('Probability: {0}%', [probability]),
            probability >= 80 ? 'green' : probability >= 20 ? 'blue' : 'gray'
        );

        if (frm.doc.workflow_state === 'Follow Up') {
            frm.add_custom_button(__('Log Attempt'), function () {
                log_contact_attempt(frm);
            }, __('Follow Up'));
        }

        render_customer_history(frm);
        render_won_invoice(frm);
    },

    // Journey table: auto-fill the read-only By User / To Customer on row add.
    custom_lead_journey_add(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, 'by_user', frappe.session.user);
        if (frm.doc.customer) {
            frappe.model.set_value(cdt, cdn, 'to_customer', frm.doc.customer);
        }
        if (!row.initiated_at) {
            frappe.model.set_value(cdt, cdn, 'initiated_at', frappe.datetime.now_datetime());
        }
    },

    before_workflow_action(frm) {
        const action = frm.selected_workflow_action;
        if (action === 'Close Won') {
            // Two person-based paths (see lead/actions.py::close_won_route).
            frappe.dom.unfreeze();
            handle_close_won(frm);
            return new Promise(() => { });
        }
        if (!(action in LEAD_PIPELINE)) {
            // Simple transition — resolve normally so the engine applies it.
            return;
        }
        // Intercepted transition (needs a dialog). The core froze the screen just
        // before calling us and only unfreezes inside its success chain (no catch),
        // so we must (1) unfreeze here, (2) run our own dialog + server apply, and
        // (3) return a promise that never settles so the engine's default
        // apply_workflow is skipped.
        frappe.dom.unfreeze();
        handle_intercepted_action(frm, action);
        return new Promise(() => { });
    },
});

function handle_intercepted_action(frm, action) {
    if (action === 'Allocate') return allocate_dialog(frm);
    if (action === 'Close Lost') return reason_dialog(frm, {
        title: __('Close as Lost'),
        label: __('Lost Reason'),
        options: frm.fields_dict.custom_lost_reason.df.options,
        method: LEAD_PIPELINE['Close Lost'],
        arg: 'lost_reason',
    });
    if (action === 'Mark Unqualified') return reason_dialog(frm, {
        title: __('Mark Unqualified'),
        label: __('Unqualified Reason'),
        options: frm.fields_dict.custom_unqualified_reason.df.options,
        method: LEAD_PIPELINE['Mark Unqualified'],
        arg: 'reason',
    });
    return Promise.reject();
}

function allocate_dialog(frm) {
    return new Promise((resolve, reject) => {
        const d = new frappe.ui.Dialog({
            title: __('Allocate Lead'),
            fields: [
                {
                    label: __('Store'), fieldname: 'store', fieldtype: 'Link',
                    options: 'Boutique', reqd: 1,
                    onchange() {
                        // Re-filter the salesperson list to the chosen store.
                        d.set_value('salesperson', '');
                        const store = d.get_value('store');
                        const sp_field = d.get_field('salesperson');
                        if (!store) { sp_field.df.options = []; sp_field.refresh(); return; }
                        frappe.call({
                            method: 'aetas_customization.lead.assignment.get_salespersons_for_store',
                            args: { store },
                            callback(r) {
                                sp_field.df.options = (r.message || []).join('\n');
                                sp_field.refresh();
                            },
                        });
                    },
                },
                {
                    label: __('Sales Person'), fieldname: 'salesperson',
                    fieldtype: 'Select', options: [], reqd: 1,
                },
            ],
            primary_action_label: __('Allocate'),
            primary_action(values) {
                frappe.call({
                    method: LEAD_PIPELINE.Allocate,
                    args: { lead: frm.doc.name, store: values.store, salesperson: values.salesperson },
                    freeze: true,
                    callback() {
                        d.hide();
                        frm.reload_doc();
                        frappe.show_alert({ message: __('Lead allocated'), indicator: 'green' });
                        resolve();
                    },
                });
            },
        });
        d.onhide = () => reject();
        d.show();
    });
}

function reason_dialog(frm, opts) {
    return new Promise((resolve, reject) => {
        const d = new frappe.ui.Dialog({
            title: opts.title,
            fields: [
                {
                    label: opts.label, fieldname: 'reason', fieldtype: 'Select',
                    options: opts.options, reqd: 1
                },
            ],
            primary_action_label: __('Confirm'),
            primary_action(values) {
                const args = { lead: frm.doc.name };
                args[opts.arg] = values.reason;
                frappe.call({
                    method: opts.method,
                    args,
                    freeze: true,
                    callback() {
                        d.hide();
                        frm.reload_doc();
                        resolve();
                    },
                });
            },
        });
        d.onhide = () => reject();
        d.show();
    });
}

function log_contact_attempt(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Log Attempt (Not Contacted)'),
        fields: [
            {
                label: __('Type'), fieldname: 'contact_type', fieldtype: 'Select',
                options: 'Call\nWhatsapp', default: 'Call', reqd: 1
            },
        ],
        primary_action_label: __('Log Attempt'),
        primary_action(values) {
            frappe.call({
                method: 'aetas_customization.lead.followup.log_attempt',
                args: { lead: frm.doc.name, contact_type: values.contact_type },
                freeze: true,
                callback(r) {
                    d.hide();
                    frm.reload_doc();
                    if (r.message) {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: r.message.status === 'unqualified' ? 'red' : 'blue',
                        });
                    }
                },
            });
        },
    });
    d.show();
}

// ---- Closed Won: two person-based paths -------------------------------------
function handle_close_won(frm) {
    frappe.call({
        method: 'aetas_customization.lead.actions.close_won_route',
        args: { lead: frm.doc.name },
        callback(r) {
            const route = r.message;
            if (route === 'store') return open_store_invoice(frm);
            if (route === 'owner') return owner_invoice_dialog(frm);
            return close_won_choose_dialog(frm);
        },
    });
}

function open_store_invoice(frm) {
    // Store path: redirect to a new Sales Invoice (customer + custom_lead_ref
    // prefilled). The lead auto-moves to Closed Won when that invoice is submitted
    // (see lead/sales_invoice_hooks.py).
    frappe.model.open_mapped_doc({
        method: 'aetas_customization.overrides.lead.make_sales_invoice_from_lead',
        frm: frm,
    });
}

function owner_invoice_dialog(frm) {
    // Owner path: record an existing submitted invoice, then Close Won.
    const d = new frappe.ui.Dialog({
        title: __('Close Won — Enter Invoice'),
        fields: [
            {
                label: __('Invoice Number'), fieldname: 'invoice', fieldtype: 'Link',
                options: 'Sales Invoice', reqd: 1,
                get_query() {
                    const filters = { docstatus: 1 };
                    if (frm.doc.customer) filters.customer = frm.doc.customer;
                    return { filters };
                },
            },
        ],
        primary_action_label: __('Close Won'),
        primary_action(values) {
            frappe.call({
                method: 'aetas_customization.lead.actions.close_won_with_invoice',
                args: { lead: frm.doc.name, invoice: values.invoice },
                freeze: true,
                callback() {
                    d.hide();
                    frm.reload_doc();
                    frappe.show_alert({ message: __('Closed Won'), indicator: 'green' });
                },
            });
        },
    });
    d.show();
}

function close_won_choose_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Close Won'),
        fields: [
            { fieldtype: 'HTML', options: `<p>${__('How do you want to record this sale?')}</p>` },
        ],
        primary_action_label: __('Enter Invoice Number'),
        primary_action() { d.hide(); owner_invoice_dialog(frm); },
        secondary_action_label: __('Create Invoice'),
        secondary_action() { d.hide(); open_store_invoice(frm); },
    });
    d.show();
}

// ---- HTML injections --------------------------------------------------------
function render_won_invoice(frm) {
    const f = frm.fields_dict.custom_won_invoice_html;
    if (!f) return;
    if (!frm.doc.custom_si_ref) { f.$wrapper.empty(); return; }
    frappe.call({
        method: 'aetas_customization.lead.history.get_invoice_lines_html',
        args: { invoice: frm.doc.custom_si_ref },
        callback(r) { f.$wrapper.html(r.message || ''); },
    });
}

function render_customer_history(frm) {
    const ph = frm.fields_dict.custom_purchase_history_html;
    const lh = frm.fields_dict.custom_lead_history_html;
    if (!frm.doc.customer) {
        const msg = `<div class="text-muted" style="padding:8px 0;">${__('No customer linked.')}</div>`;
        if (ph) ph.$wrapper.html(msg);
        if (lh) lh.$wrapper.html(msg);
        return;
    }
    if (ph) {
        frappe.call({
            method: 'aetas_customization.lead.history.get_customer_purchase_history',
            args: { customer: frm.doc.customer },
            callback(r) { ph.$wrapper.html(r.message || ''); },
        });
    }
    if (lh) {
        frappe.call({
            method: 'aetas_customization.lead.history.get_customer_lead_history',
            args: { customer: frm.doc.customer, exclude_lead: frm.doc.name },
            callback(r) { lh.$wrapper.html(r.message || ''); },
        });
    }
}