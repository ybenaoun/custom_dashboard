import { createApp } from "vue";
import DashboardBuilderComponent from "../../custom_dashboard/page/dashboard_builder/dashboard_builder.vue";

class DashboardBuilderApp {
	constructor({ wrapper, page }) {
		this.$wrapper = $(wrapper);
		this.page = page;

		this.page.clear_actions();
		this.page.clear_icons();
		this.page.clear_menu();
		this.page.clear_custom_actions();
		this.page.set_title(__("Constructeur de tableaux de bord"));

		const app = createApp(DashboardBuilderComponent, { page });
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
custom_dashboard.ui.DashboardBuilderApp = DashboardBuilderApp;

export default DashboardBuilderApp;
