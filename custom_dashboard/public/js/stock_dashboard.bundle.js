import { createApp } from "vue";
import StockDashboardComponent from "../../custom_dashboard/page/stock_dashboard/stock_dashboard.vue";

class StockDashboardApp {
	constructor({
		wrapper,
		page,
		moduleName = "Stock",
		moduleLabel = "Stock",
		pageTitle = "",
		workspaceHref = "/app/stock?cd_skip=1",
	}) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.moduleName = (moduleName || "Stock").trim() || "Stock";
		this.moduleLabel = (moduleLabel || this.moduleName).trim() || this.moduleName;
		this.pageTitle = (pageTitle || `Tableau de bord ${this.moduleLabel}`).trim();
		this.workspaceHref = workspaceHref || "/app/stock?cd_skip=1";

		this.page.clear_actions();
		this.page.clear_icons();
		this.page.clear_menu();
		this.page.clear_custom_actions();
		this.page.set_title(__(this.pageTitle));

		const app = createApp(StockDashboardComponent, {
			page,
			moduleName: this.moduleName,
			moduleLabel: this.moduleLabel,
			pageTitle: this.pageTitle,
			workspaceHref: this.workspaceHref,
			themePreset: "stock",
		});
		SetVueGlobals(app);

		this.app = app;
		this.vm = app.mount(this.$wrapper.get(0));
	}

	destroy() {
		if (this.app) {
			this.app.unmount();
			this.app = null;
		}
		this.$wrapper.empty();
	}
}

frappe.provide("custom_dashboard.ui");
custom_dashboard.ui.StockDashboardApp = StockDashboardApp;
custom_dashboard.ui.ModuleDashboardApp = StockDashboardApp;

export default StockDashboardApp;
