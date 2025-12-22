frappe.ui.form.on('Lead', {
    refresh: function (frm) {
        if (!frm.doc.customer) {
            frm.add_custom_button(__('Search Customer'), function () {
                show_customer_search_dialog(frm);
            });
        }
    }
});

function show_customer_search_dialog(frm) {
    // --- State Management ---
    let current_page = 1;
    let total_pages = 0;
    const page_len = 20;
    let current_filters = {}; // Store filters here to persist them while paginating

    let d = new frappe.ui.Dialog({
        title: __('Search and Link Customer'),
        size: 'extra-large',
        fields: [
            // --- ROW START ---
            {
                fieldtype: 'Section Break',
                label: ''
            },

            // --- COLUMN 1 (LEFT 20%) ---
            {
                fieldtype: 'Column Break',
                fieldname: 'col_left',
            },
            {
                label: __('Name'),
                fieldname: 'search_name',
                fieldtype: 'Data',
            },
            {
                label: __('Email'),
                fieldname: 'search_email',
                fieldtype: 'Data'
            },
            {
                label: __('Mobile'),
                fieldname: 'search_mobile',
                fieldtype: 'Data'
            },
            {
                fieldtype: 'HTML',
                options: '<div style="height: 10px;"></div>'
            },
            {
                label: __('Search'),
                fieldname: 'search_btn',
                fieldtype: 'Button',
                click: function () {
                    // 1. Get Values
                    let data = d.get_values();

                    // 2. Validate
                    if (!data.search_name && !data.search_email && !data.search_mobile) {
                        frappe.msgprint(__('Please enter at least one search criterion.'));
                        return;
                    }

                    // 3. Save filters and Reset Page
                    current_filters = data;
                    current_page = 1;

                    // 4. Run Search
                    run_search();
                }
            },

            // --- COLUMN 2 (RIGHT 80%) ---
            {
                fieldtype: 'Column Break',
                fieldname: 'col_right',
            },
            {
                label: __('Search Results'),
                fieldname: 'results_table',
                fieldtype: 'Table',
                cannot_add_rows: true,
                in_place_edit: false,
                data: [],
                fields: [
                    {
                        label: 'ID',
                        fieldname: 'name',
                        fieldtype: 'Data',
                        in_list_view: 1,
                        columns: 2,
                        read_only: 1
                    },
                    {
                        label: 'Customer Name',
                        fieldname: 'customer_name',
                        fieldtype: 'Data',
                        in_list_view: 1,
                        columns: 2,
                        read_only: 1
                    },
                    {
                        label: 'Email',
                        fieldname: 'email_id',
                        fieldtype: 'Data',
                        in_list_view: 1,
                        columns: 2,
                        read_only: 1
                    },
                    {
                        label: 'Mobile',
                        fieldname: 'mobile_no',
                        fieldtype: 'Data',
                        in_list_view: 1,
                        columns: 2,
                        read_only: 1
                    },
                    {
                        label: 'Action',
                        fieldname: 'select_btn',
                        fieldtype: 'Button',
                        in_list_view: 1,
                        label: __('Use'),
                    }
                ]
            },
            // --- Pagination Controls ---
            {
                fieldtype: 'HTML',
                fieldname: 'pagination_html',
                options: `
                    <div class="row" style="margin-top: 10px; display: none;" id="pagination-controls">
                        <div class="col-xs-12 text-right">
                            <button class="btn btn-default btn-sm" id="btn-prev" disabled>
                                <span class="fa fa-chevron-left"></span> Previous
                            </button>
                            <span id="page-info" style="margin: 0 15px; font-weight: bold; vertical-align: middle;"></span>
                            <button class="btn btn-default btn-sm" id="btn-next" disabled>
                                Next <span class="fa fa-chevron-right"></span>
                            </button>
                        </div>
                    </div>
                `
            }
        ]
    });

    // --- Search Logic ---
    const run_search = () => {
        let grid_field = d.fields_dict.results_table;

        // Visual feedback
        if (grid_field && grid_field.grid) {
            grid_field.grid.wrapper.find('.grid-body').css('opacity', '0.5');
        }

        frappe.call({
            method: 'aetas_customization.api.search_customers',
            args: {
                name: current_filters.search_name,
                email: current_filters.search_email,
                mobile: current_filters.search_mobile,
                page: current_page,
                page_len: page_len
            },
            freeze: false, // Don't freeze whole screen, opacity change is enough
            callback: function (r) {
                // Restore opacity
                if (grid_field && grid_field.grid) {
                    grid_field.grid.wrapper.find('.grid-body').css('opacity', '1');
                }

                if (r.message) {
                    // Extract data from new API response structure
                    let results = r.message.data || [];
                    total_pages = r.message.total_pages || 0;
                    current_page = r.message.page || 1;

                    if (grid_field && grid_field.grid) {
                        grid_field.df.data = results;
                        grid_field.grid.refresh();
                    }

                    // Handle "No Results" specifically
                    if (results.length === 0 && current_page === 1) {
                        frappe.msgprint(__('No customers found.'));
                    }

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

            // Toggle Buttons
            d.$wrapper.find('#btn-prev').prop('disabled', current_page <= 1);
            d.$wrapper.find('#btn-next').prop('disabled', current_page >= total_pages);
        } else {
            $controls.hide();
        }
    };

    d.show();

    // --- Post-Render Setup (Events & CSS) ---
    setTimeout(() => {
        // 1. Layout Fixes
        d.$wrapper.find('.modal-dialog').css("max-width", "95%").css("width", "95%");

        // --- NEW: Fix Grid Height ---
        // Constrain the grid body height and enable scrolling
        if (d.fields_dict.results_table) {
            d.fields_dict.results_table.$wrapper.find('.grid-body').css({
                'max-height': '50vh', // Limit height to 50% of viewport
                'overflow-y': 'auto',
                'min-height': '200px'
            });
        }

        let $columns = d.$wrapper.find('.form-section .form-column');
        if ($columns.length >= 2) {
            // Left Column (20%)
            $columns.eq(0).css({ 'flex': '0 0 20%', 'max-width': '20%' });
            // Right Column (80%)
            $columns.eq(1).css({ 'flex': '0 0 80%', 'max-width': '80%' });
        }

        // 2. Pagination Events
        // Unbind first to prevent duplicate listeners if dialog re-renders
        d.$wrapper.find('#btn-prev').off('click').on('click', function () {
            if (current_page > 1) {
                current_page--;
                run_search();
            }
        });

        d.$wrapper.find('#btn-next').off('click').on('click', function () {
            if (current_page < total_pages) {
                current_page++;
                run_search();
            }
        });

        // 3. Grid Row Click Event
        let grid = d.fields_dict.results_table.grid;
        grid.wrapper.on('click', '.grid-row .btn', function (e) {
            let $row = $(this).closest('.grid-row');

            // Frappe stores row index as data-idx (1-based)
            let idx = cint($row.attr('data-idx'));

            if (!idx) return;

            // Grid data is zero-based
            let row = grid.df.data[idx - 1];

            if (!row) return;

            // Populate Form
            if (row.customer_name)
                frm.set_value('first_name', row.customer_name);
                frm.set_value('status','Open')
                frm.set_value('type','Existing Customer')

            if (row.email_id)
                frm.set_value('email_id', row.email_id);

            if (row.mobile_no)
                frm.set_value('mobile_no', row.mobile_no);

            if (row.custom_sales_person && frm.fields_dict.custom_sales_person) {
                frm.set_value('custom_sales_person', row.custom_sales_person);
            }

            frappe.show_alert({
                message: __('Customer Linked: ' + row.customer_name),
                indicator: 'green'
            });

            d.hide();
        });
    }, 200); // 200ms delay to ensure DOM is ready
}