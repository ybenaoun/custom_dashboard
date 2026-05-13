/**
 * DashboardFilterBar
 * ----------------------------------------------------------------------
 * Barre de filtres GLOBALE pour les pages finales :
 *   - stock-dashboard
 *   - vente-dashboard
 *   - achat-dashboard
 *
 * Le builder ne sert qu'a configurer la STRUCTURE des dashboards.
 * Les valeurs actives des filtres viennent UNIQUEMENT de cette barre.
 *
 * Usage :
 *   await frappe.require("dashboard_filters.bundle.js");
 *   const bar = new custom_dashboard.ui.DashboardFilterBar({
 *     wrapper: domElement,
 *     pageType: "stock", // "stock" | "vente" | "achat"
 *     onChange: (filters) => { ... },     // changement live (sans refetch)
 *     onRefresh: (filters) => { ... },    // bouton Actualiser ou Reset
 *   });
 *   bar.render();
 */

const PAGE_PRESETS = {
	stock: [
		{ fieldname: "company", fieldtype: "Link", options: "Company", label: "Société" },
		{ fieldname: "warehouse", fieldtype: "Link", options: "Warehouse", label: "Entrepôt" },
		{ fieldname: "item_group", fieldtype: "Link", options: "Item Group", label: "Groupe d'articles" },
		{ fieldname: "from_date", fieldtype: "Date", options: null, label: "Date début" },
		{ fieldname: "to_date", fieldtype: "Date", options: null, label: "Date fin" },
	],
	vente: [
		{ fieldname: "company", fieldtype: "Link", options: "Company", label: "Société" },
		{ fieldname: "customer", fieldtype: "Link", options: "Customer", label: "Client" },
		{ fieldname: "territory", fieldtype: "Link", options: "Territory", label: "Territoire" },
		{ fieldname: "item_group", fieldtype: "Link", options: "Item Group", label: "Groupe d'articles" },
		{ fieldname: "from_date", fieldtype: "Date", options: null, label: "Date début" },
		{ fieldname: "to_date", fieldtype: "Date", options: null, label: "Date fin" },
	],
	achat: [
		{ fieldname: "company", fieldtype: "Link", options: "Company", label: "Société" },
		{ fieldname: "supplier", fieldtype: "Link", options: "Supplier", label: "Fournisseur" },
		{ fieldname: "item_group", fieldtype: "Link", options: "Item Group", label: "Groupe d'articles" },
		{ fieldname: "warehouse", fieldtype: "Link", options: "Warehouse", label: "Entrepôt" },
		{ fieldname: "from_date", fieldtype: "Date", options: null, label: "Date début" },
		{ fieldname: "to_date", fieldtype: "Date", options: null, label: "Date fin" },
	],
};

class DashboardFilterBar {
	constructor({ wrapper, pageType, onChange, onRefresh }) {
		this.wrapper = wrapper instanceof HTMLElement ? wrapper : wrapper?.[0] || wrapper;
		this.pageType = String(pageType || "stock").toLowerCase();
		this.onChange = typeof onChange === "function" ? onChange : null;
		this.onRefresh = typeof onRefresh === "function" ? onRefresh : null;
		this.controls = {};
		this.fieldsWrapper = null;
	}

	render() {
		if (!this.wrapper) return;

		this.wrapper.innerHTML = `
			<div class="dashboard-filter-bar" role="region" aria-label="Filtres du tableau de bord">
				<div class="dashboard-filter-fields"></div>
				<div class="dashboard-filter-actions">
					<button class="btn btn-sm btn-primary dashboard-refresh-btn" type="button">
						<span class="dashboard-filter-btn-icon">↻</span>
						<span>Actualiser</span>
					</button>
					<button class="btn btn-sm btn-default dashboard-reset-btn" type="button">
						Réinitialiser
					</button>
				</div>
			</div>
		`;

		this.fieldsWrapper = this.wrapper.querySelector(".dashboard-filter-fields");
		const preset = PAGE_PRESETS[this.pageType] || PAGE_PRESETS.stock;
		preset.forEach((field) => this.addControl(field));

		this.wrapper
			.querySelector(".dashboard-refresh-btn")
			.addEventListener("click", () => {
				if (this.onRefresh) this.onRefresh(this.getValues());
			});

		this.wrapper
			.querySelector(".dashboard-reset-btn")
			.addEventListener("click", () => this.reset());
	}

	addControl({ fieldname, fieldtype, options, label }) {
		const fieldContainer = document.createElement("div");
		fieldContainer.className = "dashboard-filter-field";
		fieldContainer.dataset.fieldname = fieldname;
		this.fieldsWrapper.appendChild(fieldContainer);

		const control = frappe.ui.form.make_control({
			parent: fieldContainer,
			df: {
				fieldname,
				fieldtype,
				options: options || undefined,
				label,
				placeholder: label,
				change: () => {
					if (this.onChange) this.onChange(this.getValues());
				},
			},
			render_input: true,
		});

		control.refresh();
		this.controls[fieldname] = control;
	}

	/**
	 * Renvoie un dictionnaire {fieldname: value} en omettant les valeurs vides.
	 */
	getValues() {
		const values = {};
		Object.keys(this.controls).forEach((fieldname) => {
			const control = this.controls[fieldname];
			if (!control || typeof control.get_value !== "function") return;
			const value = control.get_value();
			if (value !== undefined && value !== null && value !== "") {
				values[fieldname] = value;
			}
		});
		return values;
	}

	/**
	 * Affecte plusieurs valeurs en une fois (sans declencher onRefresh).
	 */
	setValues(values = {}) {
		Object.keys(this.controls).forEach((fieldname) => {
			const control = this.controls[fieldname];
			if (!control || typeof control.set_value !== "function") return;
			const next = values[fieldname];
			control.set_value(next === undefined || next === null ? "" : next);
		});
	}

	/**
	 * Remet toutes les valeurs a vide puis declenche un refresh global.
	 */
	reset() {
		Object.values(this.controls).forEach((control) => {
			if (control && typeof control.set_value === "function") {
				control.set_value("");
			}
		});
		if (this.onRefresh) this.onRefresh({});
	}

	destroy() {
		Object.values(this.controls).forEach((control) => {
			if (control?.$wrapper) control.$wrapper.remove();
		});
		this.controls = {};
		if (this.wrapper) this.wrapper.innerHTML = "";
	}
}

frappe.provide("custom_dashboard.ui");
custom_dashboard.ui.DashboardFilterBar = DashboardFilterBar;

export default DashboardFilterBar;
