import { createApp } from "vue";
import WidgetManagementComponent from "../../custom_dashboard/page/widget_management/widget_management.vue";

class WidgetManagementApp {
	constructor({ wrapper, page }) {
		this.$wrapper = $(wrapper);
		this.page = page;

		this.page.clear_actions();
		this.page.clear_icons();
		this.page.clear_menu();
		this.page.clear_custom_actions();
		this.page.set_title(__("Gestion des widgets"));

		const app = createApp(WidgetManagementComponent, { page });
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
custom_dashboard.ui.WidgetManagementApp = WidgetManagementApp;

export default WidgetManagementApp;
