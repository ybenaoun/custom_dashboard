frappe.pages["admin-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Admin Dashboard"),
		single_column: true,
	});

	frappe.breadcrumbs.add("Setup");

	const bootstrap_html = `
		<div id="admin-dashboard-app" class="adx-mount">
			<div class="adx-bootstrap">
				<div class="adx-bootstrap-pulse"></div>
				<p>${__("Chargement du tableau de bord…")}</p>
			</div>
		</div>
	`;
	$(bootstrap_html).appendTo(page.body.addClass("no-border"));

	function showError(msg) {
		const target = page.body.get(0).querySelector("#admin-dashboard-app");
		if (!target) return;
		target.innerHTML = `
			<div style="padding:40px;text-align:center;color:#6b7280;font-family:'DM Sans',Inter,sans-serif;">
				<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="#EF4444" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom:14px;">
					<circle cx="12" cy="12" r="10"/>
					<line x1="12" y1="8" x2="12" y2="12"/>
					<line x1="12" y1="16" x2="12.01" y2="16"/>
				</svg>
				<h4 style="margin:0 0 8px;color:#0b1320;">${__("Tableau de bord indisponible")}</h4>
				<p style="margin:0 0 16px;font-size:13px;">${msg}</p>
				<pre style="display:inline-block;text-align:left;padding:12px 16px;background:#0b1320;color:#a5f3fc;border-radius:8px;font-size:12px;">cd /home/youss/frappe/my-bench
bench build --app custom_dashboard
bench restart</pre>
			</div>
		`;
	}

	function load_bundle() {
		if (typeof frappe.require !== "function") {
			showError("frappe.require n'est pas disponible");
			return;
		}
		frappe.require("admin_dashboard.bundle.js")
			.then(() => {
				if (!frappe.ui || !frappe.ui.admin_dashboard || typeof frappe.ui.admin_dashboard.mount !== "function") {
					console.error("admin_dashboard: bundle chargé mais frappe.ui.admin_dashboard.mount manquant. Lancez `bench build --app custom_dashboard`.");
					showError(__("Le bundle Vue n'est pas trouvé. Lancez la commande ci-dessous puis rafraîchissez."));
					return;
				}
				const target = page.body.get(0).querySelector("#admin-dashboard-app");
				if (!target) {
					console.error("admin_dashboard: mount point introuvable");
					return;
				}
				if (window.__adminDashboardInstance && window.__adminDashboardInstance.app) {
					window.__adminDashboardInstance.app.unmount();
				}
				window.__adminDashboardInstance = frappe.ui.admin_dashboard.mount(target);
			})
			.catch((e) => {
				console.error("admin_dashboard: échec du chargement du bundle", e);
				showError(__("Échec du chargement du bundle. Voir la console."));
			});
	}

	load_bundle();
};
