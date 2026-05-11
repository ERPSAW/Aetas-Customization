frappe.pages['aot-dashboard'].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: '',
		single_column: true
	});
};

frappe.pages['aot-dashboard'].on_page_show = function (wrapper) {
	load_aot_dashboard(wrapper);
};

function load_aot_dashboard(wrapper) {
	let $parent = $(wrapper).find('.layout-main-section');
	$parent.empty();

	// Make parent a fixed-height container so only our inner content div scrolls
	$parent.css({ height: 'calc(100vh - 120px)', overflow: 'hidden', padding: '0' });

	frappe.require('aot_dashboard.bundle.js').then(() => {
		new aot.dashboard.AotDashboardUI({
			wrapper: $parent.get(0),
			page: wrapper.page,
		});
	});
}
