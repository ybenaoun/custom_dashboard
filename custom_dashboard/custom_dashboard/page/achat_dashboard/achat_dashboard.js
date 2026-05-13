frappe.pages["achat-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Tableau de bord Achats"),
		single_column: true,
	});

	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_achat_dashboard(wrapper));
	}
};

frappe.pages["achat-dashboard"].on_page_show = function (wrapper) {
	load_achat_dashboard(wrapper);
};

function load_achat_dashboard(wrapper) {
	const $parent = $(wrapper).find(".layout-main-section");
	if (wrapper.achat_dashboard_app?.destroy) {
		wrapper.achat_dashboard_app.destroy();
	}

	$parent.empty();
	$parent.addClass("erp-compact-dashboard achat-dashboard");

	frappe.require("achat_dashboard.bundle.js").then(() => {
		wrapper.achat_dashboard_app = new custom_dashboard.ui.AchatDashboardApp({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
