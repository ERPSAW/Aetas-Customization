frappe.ui.form.on('Lead', {
    before_save: function (frm) {
        let bids = frm.doc.custom_bids || [];
        let is_any_approved = bids.some(row => row.status == "Approved");
        // Check conditions and ensure we haven't already handled this to avoid loops
        if (frm.doc.status == "Qualified" && frm.doc.custom_sales_person && !frm.doc.__assignment_handled && !is_any_approved) {

            // 1. Stop the immediate save
            frappe.validated = false;

            // 2. Call the Promise function
            validate_and_assign_sales_person(frm).then(() => {
                // Success: Set flag and re-save
                frm.doc.__assignment_handled = true;
                frm.save();
            }).catch(() => {
                // Failure: Do nothing (save stays stopped)
            });
        }
    },
    refresh: function (frm) {

        let approved_row = (frm.doc.custom_bids || []).find(d => d.status === 'Approved');

        if (approved_row) {
            // CASE: Already Approved -> Show "Unapprove" Button
            frm.add_custom_button(__('Unapprove Sales Person'), function () {
                unapprove_sales_person(frm, approved_row);
            }).addClass('btn-danger'); // Optional: Make it red
        } else {
            // CASE: Not Approved -> Show "Approve" Button
            // Only show if there are actually people to approve
            if (frm.doc.custom_bids && frm.doc.custom_bids.length > 0) {
                frm.add_custom_button(__('Approve Sales Person'), function () {
                    show_approval_dialog(frm);
                }).addClass('btn-primary');
            }
        }

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

function validate_and_assign_sales_person(frm) {
    return new Promise(function (resolve, reject) {

        // 1. Check for duplicate assignment
        let already_exists = (frm.doc.custom_bids || []).some(
            row => row.sales_person == frm.doc.custom_sales_person
        );

        if (already_exists) {
            // If already exists, just proceed without asking
            resolve();
            return;
        }

        // 2. Ask for Confirmation
        frappe.confirm(
            __("Do you want to assign Sales Person <b>{0}</b> to this Lead or Open for all?", [frm.doc.custom_sales_person]),

            // YES: Add row and Resolve
            function () {
                let row = frm.add_child("custom_bids");
                row.sales_person = frm.doc.custom_sales_person;
                row.status = (frm.doc.type == "Existing Customer") ? "Approved" : "Applied";
                row.applied_on = frappe.datetime.get_today();
                row.approved_by = frappe.session.user;

                frm.refresh_field("custom_bids");

                resolve();
            },

            // NO: Reject (Cancel Save)
            function () {
                resolve();
            }
        );
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
                frm.set_value('custom_contact', data.mobile_no);
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