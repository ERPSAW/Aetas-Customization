frappe.pages['boutique-day-registe'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Boutique Day Register',
		single_column: true
	});
}

frappe.pages["boutique-day-registe"].on_page_show = function (wrapper) {
	load_day_entry_ui(wrapper);
};

function load_day_entry_ui(wrapper) {
	let $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	// Add full width class to page
	$(wrapper).find(".page-content").addClass("dayentry-full-width");

	frappe.require("dayentry.bundle.js").then(() => {
		new dayentry.ui.DayEntryUI({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}