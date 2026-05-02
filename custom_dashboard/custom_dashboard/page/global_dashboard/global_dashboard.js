frappe.pages["global-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Tableau de bord global"),
		single_column: true,
	});

	frappe.breadcrumbs.add("Desk");

	const bootstrap_html = `
		<div id="global-dashboard-app" class="gdx-mount">
			<div class="gdx-bootstrap">
				<div class="gdx-bootstrap-pulse"></div>
				<p>${__("Chargement du tableau de bord global…")}</p>
			</div>
		</div>
	`;
	$(bootstrap_html).appendTo(page.body);

	page.set_secondary_action(__("Actualiser"), () => {
		if (window.__globalDashboardInstance && window.__globalDashboardInstance.instance) {
			window.__globalDashboardInstance.instance.reload();
		} else {
			load_bundle();
		}
	}, "refresh");

	function showError(msg) {
		const target = page.body.get(0).querySelector("#global-dashboard-app");
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
		frappe.require("global_dashboard.bundle.js")
			.then(() => {
				if (
					!frappe.ui ||
					!frappe.ui.global_dashboard ||
					typeof frappe.ui.global_dashboard.mount !== "function"
				) {
					console.error(
						"global_dashboard: bundle chargé mais frappe.ui.global_dashboard.mount manquant. Lancez `bench build --app custom_dashboard`."
					);
					showError(__("Le bundle Vue n'est pas trouvé. Lancez la commande ci-dessous."));
					return;
				}
				const target = page.body.get(0).querySelector("#global-dashboard-app");
				if (!target) {
					console.error("global_dashboard: mount point introuvable");
					return;
				}
				if (window.__globalDashboardInstance && window.__globalDashboardInstance.app) {
					window.__globalDashboardInstance.app.unmount();
				}
				window.__globalDashboardInstance = frappe.ui.global_dashboard.mount(target);
			})
			.catch((e) => {
				console.error("global_dashboard: échec du chargement du bundle", e);
				showError(__("Échec du chargement du bundle. Voir la console."));
			});
	}

	load_bundle();
};
