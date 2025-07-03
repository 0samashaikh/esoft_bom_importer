app_name = "esoft_bom_importer"
app_title = "Esoft Bom Importer"
app_publisher = "shaikhosama504"
app_description = "Bom Importer"
app_email = "shaikhosama504@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "esoft_bom_importer",
# 		"logo": "/assets/esoft_bom_importer/logo.png",
# 		"title": "Esoft Bom Importer",
# 		"route": "/esoft_bom_importer",
# 		"has_permission": "esoft_bom_importer.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/esoft_bom_importer/css/esoft_bom_importer.css"
# app_include_js = "/assets/esoft_bom_importer/js/esoft_bom_importer.js"

# include js, css files in header of web template
# web_include_css = "/assets/esoft_bom_importer/css/esoft_bom_importer.css"
# web_include_js = "/assets/esoft_bom_importer/js/esoft_bom_importer.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "esoft_bom_importer/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "esoft_bom_importer/public/icons.svg"

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
# 	"methods": "esoft_bom_importer.utils.jinja_methods",
# 	"filters": "esoft_bom_importer.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "esoft_bom_importer.install.before_install"
# after_install = "esoft_bom_importer.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "esoft_bom_importer.uninstall.before_uninstall"
# after_uninstall = "esoft_bom_importer.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "esoft_bom_importer.utils.before_app_install"
# after_app_install = "esoft_bom_importer.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "esoft_bom_importer.utils.before_app_uninstall"
# after_app_uninstall = "esoft_bom_importer.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "esoft_bom_importer.notifications.get_notification_config"

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

override_doctype_class = {
	"BOM Creator": "esoft_bom_importer.public.py.bom_creator.BomCreator"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"BOM Creator": {
		"before_save": "esoft_bom_importer.overrides.bom_creator.before_save",
        "before_submit": "esoft_bom_importer.overrides.bom_creator.before_submit",
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"esoft_bom_importer.tasks.all"
# 	],
# 	"daily": [
# 		"esoft_bom_importer.tasks.daily"
# 	],
# 	"hourly": [
# 		"esoft_bom_importer.tasks.hourly"
# 	],
# 	"weekly": [
# 		"esoft_bom_importer.tasks.weekly"
# 	],
# 	"monthly": [
# 		"esoft_bom_importer.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "esoft_bom_importer.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "esoft_bom_importer.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "esoft_bom_importer.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["esoft_bom_importer.utils.before_request"]
# after_request = ["esoft_bom_importer.utils.after_request"]

# Job Events
# ----------
# before_job = ["esoft_bom_importer.utils.before_job"]
# after_job = ["esoft_bom_importer.utils.after_job"]

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
# 	"esoft_bom_importer.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
