frappe.pages["stock-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Tableau de bord Stock"),
		single_column: true,
	});

	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_stock_dashboard(wrapper));
	}
};

frappe.pages["stock-dashboard"].on_page_show = function (wrapper) {
	load_stock_dashboard(wrapper);
};

function load_stock_dashboard(wrapper) {
	const $parent = $(wrapper).find(".layout-main-section");
	if (wrapper.stock_dashboard_app?.destroy) {
		wrapper.stock_dashboard_app.destroy();
	}

	$parent.empty();

	frappe.require("stock_dashboard.bundle.js").then(() => {
		wrapper.stock_dashboard_app = new custom_dashboard.ui.StockDashboardApp({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
