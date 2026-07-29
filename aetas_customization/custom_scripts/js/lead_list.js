// Lead list view — colour the indicator by pipeline stage (workflow_state),
// using the SAME colour map as the form (custom_scripts/js/lead.js). Keep the two
// maps in sync; the form is the source of truth.
frappe.listview_settings['Lead'] = {
    // Make sure workflow_state is loaded so get_indicator can read it.
    add_fields: ['workflow_state'],

    get_indicator: function (doc) {
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
        const state = doc.workflow_state || 'Open';
        return [__(state), STAGE_COLOR[state] || 'gray', 'workflow_state,=,' + state];
    },
};
