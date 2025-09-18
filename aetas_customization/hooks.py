from . import __version__ as app_version

app_name = "aetas_customization"
app_title = "Aetas Customization"
app_publisher = "Akhilam Inc"
app_description = "Customization for Aetas"
app_email = "tailorraj111@gmail.com"
app_license = "MIT"


fixtures = [
    {"dt": "Custom Field", "filters": [
        [
            "name", "in", [
                "Purchase Invoice Item-margin_custom","Serial No-mrp","Sales Invoice-custom_source",
                "Payment Reconciliation Invoice-custom_bill_no","Stock Entry-custom_delivery_note","Stock Entry Detail-custom_mrp",
                "Payment Entry-custom_advance_payment_receipt","Cost Center-custom_letter_head",
                "Item Group-custom_unique_code","Item Group-custom_attribute_2","Item-custom_enable_dynamic_sn_naming",
                "Item-custom_attribute_3","Warehouse-custom_store_code",
                "Sales Invoice-custom_aetas_coupon_code"
            ]
        ]
    ]},
     {"dt": "Property Setter", "filters": [
        [
            "name", "in", [
                "Customer-mobile_no-in_standard_filter"
                "Purchase Invoice Item-margin_custom","Serial No-mrp",
                "Payment Reconciliation Invoice-custom_bill_no"
            ]
        ]
    ]}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/aetas_customization/css/aetas_customization.css"
# app_include_js = "/assets/aetas_customization/js/aetas_customization.js"

# include js, css files in header of web template
# web_include_css = "/assets/aetas_customization/css/aetas_customization.css"
# web_include_js = "/assets/aetas_customization/js/aetas_customization.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "aetas_customization/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_js = {
    "Purchase Invoice" : "custom_scripts/js/purchase_invoice.js",
    "Payment Reconciliation" : "custom_scripts/js/payment_reconciliation.js",
    "Payment Entry":"custom_scripts/js/payment_entry.js",
    "Sales Invoice":"custom_scripts/js/sales_invoice.js",
    "Purchase Order":"custom_scripts/js/purchase_order.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#	"methods": "aetas_customization.utils.jinja_methods",
#	"filters": "aetas_customization.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "aetas_customization.install.before_install"
# after_install = "aetas_customization.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "aetas_customization.uninstall.before_uninstall"
# after_uninstall = "aetas_customization.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "aetas_customization.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Payment Reconciliation": "aetas_customization.overrides.payment_reconciliation.CustomPaymentReconciliation"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Purchase Invoice": {
		"on_submit": "aetas_customization.aetas_customization.overrides.purchase_invoice.on_submit",
	},
    "Sales Invoice": {
		"validate": "aetas_customization.aetas_customization.overrides.sales_invoice.validate",
		"on_submit": "aetas_customization.aetas_customization.overrides.sales_invoice.on_submit",
		"on_cancel": "aetas_customization.aetas_customization.overrides.sales_invoice.on_cancel",
	},
    "Payment Entry": {
		"on_submit": "aetas_customization.aetas_customization.overrides.payment_entry.on_submit",
	},
    "Purchase Invoice":{
        "before_validate":"aetas_customization.aetas_customization.overrides.purchase_invoice.before_validate",
    },
    "Stock Entry":{
        "before_validate":"aetas_customization.aetas_customization.overrides.stock_entry.before_validate",
    },
    "Item":{
        "validate": "aetas_customization.aetas_customization.overrides.item.validate",
    },
    "Item Group":{
        "validate": "aetas_customization.aetas_customization.overrides.item_group.validate",
    },
    "Warehouse":{
        "validate": "aetas_customization.aetas_customization.overrides.warehouse.validate",
    }
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
#	"all": [
#		"aetas_customization.tasks.all"
#	],
#	"daily": [
#		"aetas_customization.tasks.daily"
#	],
#	"hourly": [
#		"aetas_customization.tasks.hourly"
#	],
#	"weekly": [
#		"aetas_customization.tasks.weekly"
#	],
#	"monthly": [
#		"aetas_customization.tasks.monthly"
#	],
# }

# Testing
# -------

# before_tests = "aetas_customization.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "aetas_customization.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "aetas_customization.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]


# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"aetas_customization.auth.validate"
# ]
