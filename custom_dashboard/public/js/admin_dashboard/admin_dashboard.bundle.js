import { createApp } from "vue";
import AdminDashboard from "./AdminDashboard.vue";

frappe.provide("frappe.ui.admin_dashboard");

frappe.ui.admin_dashboard.mount = function (selector) {
	const target = typeof selector === "string" ? document.querySelector(selector) : selector;
	if (!target) {
		console.warn("admin_dashboard: mount target not found", selector);
		return null;
	}
	const app = createApp(AdminDashboard);
	// Expose Frappe's translation helper to all templates
	app.config.globalProperties.__ = window.__ || ((s) => s);
	app.config.globalProperties.$t = window.__ || ((s) => s);
	const instance = app.mount(target);
	return { app, instance };
};
