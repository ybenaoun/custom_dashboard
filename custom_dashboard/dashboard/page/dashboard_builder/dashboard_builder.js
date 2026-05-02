frappe.pages["dashboard-builder"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Dashboard Builder"),
		single_column: true,
	});

	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_dashboard_builder(wrapper));
	}
};

frappe.pages["dashboard-builder"].on_page_show = function (wrapper) {
	load_dashboard_builder(wrapper);
};

function load_dashboard_builder(wrapper) {
	const $parent = $(wrapper).find(".layout-main-section");
	if (wrapper.dashboard_builder_app?.destroy) {
		wrapper.dashboard_builder_app.destroy();
	}

	$parent.empty();

	frappe.require("dashboard_builder.bundle.js").then(() => {
		wrapper.dashboard_builder_app = new custom_dashboard.ui.DashboardBuilderApp({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
