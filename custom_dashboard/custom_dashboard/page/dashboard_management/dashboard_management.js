frappe.pages["dashboard-management"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Gestion des tableaux"),
		single_column: true,
	});

	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_dashboard_management(wrapper));
	}
};

frappe.pages["dashboard-management"].on_page_show = function (wrapper) {
	load_dashboard_management(wrapper);
};

function load_dashboard_management(wrapper) {
	const $parent = $(wrapper).find(".layout-main-section");
	if (wrapper.dashboard_management_app?.destroy) {
		wrapper.dashboard_management_app.destroy();
	}

	$parent.empty();

	const adminRoles = ["System Manager", "Dashboard Admin"];
	const userRoles = frappe.user_roles || [];
	const isAdmin = userRoles.some((role) => adminRoles.includes(role)) || frappe.session.user === "Administrator";
	if (!isAdmin) {
		$parent.html(
			`<div class="alert alert-danger" style="margin:24px;">${__(
				"Accès réservé à l'administrateur ou au rôle System Manager."
			)}</div>`
		);
		return;
	}

	frappe.require("dashboard_management.bundle.js").then(() => {
		wrapper.dashboard_management_app = new custom_dashboard.ui.DashboardManagementApp({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
