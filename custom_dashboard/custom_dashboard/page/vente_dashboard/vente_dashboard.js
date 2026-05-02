frappe.pages["vente-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Tableau de bord Ventes"),
		single_column: true,
	});

	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_vente_dashboard(wrapper));
	}
};

frappe.pages["vente-dashboard"].on_page_show = function (wrapper) {
	load_vente_dashboard(wrapper);
};

function load_vente_dashboard(wrapper) {
	const $parent = $(wrapper).find(".layout-main-section");
	if (wrapper.vente_dashboard_app?.destroy) {
		wrapper.vente_dashboard_app.destroy();
	}

	$parent.empty();

	frappe.require("vente_dashboard.bundle.js").then(() => {
		wrapper.vente_dashboard_app = new custom_dashboard.ui.VenteDashboardApp({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
