app_name = "service_app"
app_title = "Service Tracking"
app_publisher = "Nickson "
app_description = "Service Management"
app_email = "njohn@sfgroup.co.tz"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "service_app",
# 		"logo": "/assets/service_app/logo.png",
# 		"title": "Service Tracking",
# 		"route": "/service_app",
# 		"has_permission": "service_app.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/service_app/css/service_app.css"
# app_include_js = "/assets/service_app/js/service_app.js"

# include js, css files in header of web template
# web_include_css = "/assets/service_app/css/service_app.css"
# web_include_js = "/assets/service_app/js/service_app.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "service_app/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Purchase Order": "public/js/purchase_order.js",
	"Item": "public/js/item.js",
	"Vehicle": "public/js/vehicle.js",
	"Item Price": "public/js/item_price.js",
	"Supplier Quotation": "public/js/supplier_quotation.js"
}

STANDARD_CUSTOMIZED_DOCTYPES = [
	"Address",
	"Communication",
	"Contact",
	"Customer",
	"Delivery Note",
	"Delivery Note Item",
	"Email Account",
	"Employee",
	"Item",
	"Item Barcode",
	"Item Price",
	"Job Card",
	"Material Request",
	"POS Invoice",
	"POS Invoice Item",
	"Packed Item",
	"Pick List",
	"Print Settings",
	"Purchase Invoice",
	"Purchase Invoice Item",
	"Purchase Order",
	"Purchase Order Item",
	"Purchase Receipt",
	"Purchase Receipt Item",
	"Quotation",
	"Sales Invoice",
	"Sales Invoice Item",
	"Sales Order",
	"Stock Entry",
	"Stock Entry Detail",
	"Stock Reconciliation",
	"Stock Reconciliation Item",
	"Supplier",
	"Supplier Quotation",
	"Supplier Quotation Item",
]

# Export standard ERPNext doctype customizations so they deploy to new sites.
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			["dt", "in", STANDARD_CUSTOMIZED_DOCTYPES]
		]
	},
	{
		"dt": "Property Setter",
		"filters": [
			["doc_type", "in", STANDARD_CUSTOMIZED_DOCTYPES]
		]
	},
]
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "service_app/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "service_app.utils.jinja_methods",
# 	"filters": "service_app.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "service_app.install.before_install"
after_install = "service_app.service_tracking.workspace.bootstrap_service_tracking_dashboards"
after_migrate = [
	"service_app.service_tracking.workspace.bootstrap_service_tracking_dashboards"
]

# Uninstallation
# ------------

# before_uninstall = "service_app.uninstall.before_uninstall"
# after_uninstall = "service_app.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "service_app.utils.before_app_install"
# after_app_install = "service_app.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "service_app.utils.before_app_uninstall"
# after_app_uninstall = "service_app.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "service_app.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Item": {
		"validate": "service_app.service_tracking.item.validate_spare_part_part_category"
	},
	"Vehicle": {
		"validate": "service_app.service_tracking.vehicle_make_controls.validate_doc_make_enabled"
	},
	"Item Price": {
		"validate": "service_app.service_tracking.vehicle_make_controls.validate_doc_make_enabled"
	},
	"Service Tempelate": {
		"validate": "service_app.service_tracking.vehicle_make_controls.validate_doc_make_enabled"
	},
	"Maintenance Postion": {
		"validate": "service_app.service_tracking.vehicle_make_controls.validate_doc_make_enabled"
	},
	"Supplier Quotation": {
		"validate": "service_app.service_tracking.supplier_quotation.validate_supplier_quotation_duplicate_item_prices",
		"on_submit": "service_app.service_tracking.supplier_quotation.sync_item_prices_from_supplier_quotation",
		"on_update": "service_app.service_tracking.supplier_quotation.sync_item_prices_from_supplier_quotation"
	},
	"Purchase Order": {
		"validate": "service_app.service_tracking.purchase_order.validate_purchase_order_source_integrity",
		"after_insert": "service_app.service_tracking.purchase_order.sync_job_card_purchase_order_link",
		"on_submit": "service_app.service_tracking.purchase_order.sync_job_card_purchase_order_link",
		"on_cancel": "service_app.service_tracking.purchase_order.clear_job_card_purchase_order_link"
	},
	"Sales Order": {
		"validate": "service_app.service_tracking.sales_order.validate_sales_order_trip_revenue_allocations"
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"service_app.tasks.all"
# 	],
# 	"daily": [
# 		"service_app.tasks.daily"
# 	],
# 	"hourly": [
# 		"service_app.tasks.hourly"
# 	],
# 	"weekly": [
# 		"service_app.tasks.weekly"
# 	],
# 	"monthly": [
# 		"service_app.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "service_app.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "service_app.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "service_app.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["service_app.utils.before_request"]
# after_request = ["service_app.utils.after_request"]

# Job Events
# ----------
# before_job = ["service_app.utils.before_job"]
# after_job = ["service_app.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"service_app.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


