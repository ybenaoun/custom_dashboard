import { createApp } from "vue";
import GlobalDashboard from "./GlobalDashboard.vue";

frappe.provide("frappe.ui.global_dashboard");

frappe.ui.global_dashboard.mount = function (selector, options = {}) {
	const target = typeof selector === "string" ? document.querySelector(selector) : selector;
	if (!target) {
		console.warn("global_dashboard: mount target not found", selector);
		return null;
	}
	const app = createApp(GlobalDashboard, options);
	app.config.globalProperties.__ = window.__ || ((s) => s);
	app.config.globalProperties.$t = window.__ || ((s) => s);
	const instance = app.mount(target);
	return { app, instance };
};
