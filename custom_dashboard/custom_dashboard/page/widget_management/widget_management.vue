<template>
	<div class="wm-shell">
		<header class="wm-header">
			<div>
				<h1>Gestion des widgets</h1>
				<p>
					Activez ou désactivez les widgets et gérez les permissions par rôle
					(« Voir » et « Utiliser »).
				</p>
			</div>
		</header>

		<div v-if="pageError" class="wm-banner is-error">{{ pageError }}</div>

		<div class="wm-toolbar">
			<div class="wm-filters">
				<button
					v-for="filter in categoryFilters"
					:key="filter.value"
					class="wm-pill"
					:class="{ 'is-active': activeCategory === filter.value }"
					type="button"
					@click="setCategory(filter.value)"
				>
					{{ filter.label }}
				</button>
			</div>
			<div class="wm-search">
				<input
					v-model.trim="searchTerm"
					class="form-control"
					type="search"
					placeholder="Rechercher un widget…"
				/>
			</div>
		</div>

		<div class="wm-layout">
			<aside class="wm-list-pane">
				<div v-if="loading" class="wm-state">Chargement des widgets…</div>
				<div v-else-if="!filteredWidgets.length" class="wm-state">
					Aucun widget trouvé.
				</div>
				<button
					v-for="widget in filteredWidgets"
					:key="widget.name"
					class="wm-card"
					:class="{
						'is-active': selectedWidget?.name === widget.name,
						'is-disabled': !widget.is_active,
					}"
					type="button"
					@click="selectWidget(widget.name)"
				>
					<div>
						<strong>{{ widget.title }}</strong>
						<p>{{ widget.description || "—" }}</p>
					</div>
					<div class="wm-card-meta">
						<span class="wm-chip" :class="categoryClass(widget.category_label)">
							{{ widget.category_label || "Général" }}
						</span>
						<span class="wm-chip" :class="widget.is_active ? 'is-on' : 'is-off'">
							{{ widget.is_active ? "Actif" : "Inactif" }}
						</span>
					</div>
				</button>
			</aside>

			<main class="wm-detail-pane">
				<div v-if="!selectedWidget" class="wm-state">
					Sélectionnez un widget pour gérer ses permissions.
				</div>
				<template v-else>
					<header class="wm-detail-head">
						<div>
							<h2>{{ selectedWidget.title }}</h2>
							<p>{{ selectedWidget.description || "Aucune description." }}</p>
							<div class="wm-detail-meta">
								<span class="wm-chip" :class="categoryClass(selectedWidget.category_label)">
									{{ selectedWidget.category_label || "Général" }}
								</span>
								<span class="wm-chip">{{ selectedWidget.widget_type }}</span>
							</div>
						</div>
						<label class="wm-switch">
							<input
								type="checkbox"
								:checked="Boolean(selectedWidget.is_active)"
								@change="toggleActive(selectedWidget)"
							/>
							<span>{{ selectedWidget.is_active ? "Activé" : "Désactivé" }}</span>
						</label>
					</header>

					<section class="wm-roles">
						<header class="wm-roles-head">
							<h3>Permissions par rôle</h3>
							<p>
								« Voir » autorise l'affichage du widget dans la bibliothèque.
								« Utiliser » autorise son ajout/exécution dans un tableau de bord.
							</p>
						</header>
						<div class="wm-roles-table">
							<div class="wm-roles-row wm-roles-head-row">
								<span>Rôle</span>
								<span>Voir</span>
								<span>Utiliser</span>
							</div>
							<div
								v-for="role in roleMatrix"
								:key="role.role"
								class="wm-roles-row"
							>
								<span>{{ role.role }}</span>
								<input type="checkbox" v-model="role.can_view" @change="syncCanView(role)" />
								<input type="checkbox" v-model="role.can_use" @change="syncCanUse(role)" />
							</div>
						</div>
						<footer class="wm-roles-foot">
							<button
								class="btn btn-primary"
								type="button"
								:disabled="savingPermissions"
								@click="savePermissions"
							>
								{{ savingPermissions ? "Enregistrement…" : "Enregistrer les permissions" }}
							</button>
						</footer>
					</section>
				</template>
			</main>
		</div>
	</div>
</template>

<script>
export default {
	name: "WidgetManagement",
	data() {
		return {
			loading: false,
			savingPermissions: false,
			pageError: "",
			widgets: [],
			selectedWidget: null,
			roleMatrix: [],
			activeCategory: "",
			searchTerm: "",
			categoryFilters: [
				{ label: "Tous", value: "" },
				{ label: "Stock", value: "Stock" },
				{ label: "Vente", value: "Vente" },
				{ label: "Achat", value: "Achat" },
			],
		};
	},
	computed: {
		filteredWidgets() {
			const search = (this.searchTerm || "").toLowerCase();
			return this.widgets.filter((widget) => {
				if (!search) return true;
				const haystack = [widget.title, widget.description, widget.category, widget.category_label]
					.filter(Boolean)
					.join(" ")
					.toLowerCase();
				return haystack.includes(search);
			});
		},
	},
	mounted() {
		this.loadWidgets();
	},
	methods: {
		categoryClass(label) {
			if (!label) return "is-general";
			return `is-${label.toLowerCase()}`;
		},
		setCategory(value) {
			this.activeCategory = value;
			this.loadWidgets();
		},
		async loadWidgets() {
			this.loading = true;
			this.pageError = "";
			try {
				this.widgets =
					(await this.frappe.xcall("custom_dashboard.api.widget.list_admin_widgets", {
						category: this.activeCategory || null,
					})) || [];
				if (this.widgets.length) {
					const targetName = this.selectedWidget?.name;
					if (targetName && this.widgets.find((w) => w.name === targetName)) {
						await this.selectWidget(targetName);
					} else {
						await this.selectWidget(this.widgets[0].name);
					}
				} else {
					this.selectedWidget = null;
					this.roleMatrix = [];
				}
			} catch (error) {
				this.pageError = this.parseError(error, "Impossible de charger les widgets.");
			} finally {
				this.loading = false;
			}
		},
		async selectWidget(name) {
			try {
				const detail = await this.frappe.xcall(
					"custom_dashboard.api.widget.get_widget_admin_definition",
					{ widget_name: name }
				);
				this.selectedWidget = detail;
				this.roleMatrix = (detail.roles || []).map((row) => ({
					role: row.role,
					can_view: Boolean(row.can_view),
					can_use: Boolean(row.can_use),
				}));
			} catch (error) {
				this.pageError = this.parseError(error, "Impossible de charger le widget.");
			}
		},
		async toggleActive(widget) {
			try {
				const updated = await this.frappe.xcall(
					"custom_dashboard.api.widget.admin_toggle_widget_active",
					{ widget_name: widget.name, is_active: widget.is_active ? 0 : 1 }
				);
				const idx = this.widgets.findIndex((w) => w.name === widget.name);
				if (idx >= 0) {
					this.widgets[idx] = {
						...this.widgets[idx],
						is_active: updated.is_active ? 1 : 0,
					};
				}
				this.selectedWidget = { ...this.selectedWidget, is_active: updated.is_active ? 1 : 0 };
				this.frappe.show_alert({
					message: updated.is_active ? "Widget activé." : "Widget désactivé.",
					indicator: updated.is_active ? "green" : "orange",
				});
			} catch (error) {
				this.pageError = this.parseError(error, "Impossible de changer le statut du widget.");
			}
		},
		syncCanUse(role) {
			if (role.can_use && !role.can_view) {
				role.can_view = true;
			}
		},
		syncCanView(role) {
			if (!role.can_view) {
				role.can_use = false;
			}
		},
		async savePermissions() {
			if (!this.selectedWidget) return;
			this.savingPermissions = true;
			this.pageError = "";
			try {
				const payload = {
					name: this.selectedWidget.name,
					is_active: this.selectedWidget.is_active ? 1 : 0,
					description: this.selectedWidget.description,
					roles: this.roleMatrix.map((row) => ({
						role: row.role,
						can_view: row.can_view ? 1 : 0,
						can_use: row.can_use ? 1 : 0,
					})),
				};
				await this.frappe.xcall("custom_dashboard.api.widget.save_widget_access", {
					doc: payload,
				});
				this.frappe.show_alert({
					message: "Permissions mises à jour.",
					indicator: "green",
				});
				await this.loadWidgets();
			} catch (error) {
				this.pageError = this.parseError(error, "Impossible d'enregistrer les permissions.");
			} finally {
				this.savingPermissions = false;
			}
		},
		parseError(error, fallback) {
			if (!error) return fallback;
			if (typeof error === "string") return error;
			return (
				error._server_messages?.[0] ||
				error.message ||
				error.exc ||
				error.responseText ||
				fallback
			);
		},
	},
};
</script>

<style scoped>
.wm-shell {
	display: flex;
	flex-direction: column;
	gap: 18px;
	padding: 18px;
	font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
}
.wm-header h1 { margin: 0; font-size: 26px; }
.wm-header p { margin: 6px 0 0; color: #6b7280; max-width: 720px; }
.wm-toolbar {
	display: flex;
	flex-wrap: wrap;
	gap: 12px;
	justify-content: space-between;
}
.wm-filters { display: flex; gap: 8px; flex-wrap: wrap; }
.wm-pill {
	border: 1px solid #e5e7eb;
	background: #fff;
	border-radius: 999px;
	padding: 6px 14px;
	font-weight: 600;
	font-size: 12.5px;
	cursor: pointer;
}
.wm-pill.is-active {
	background: #0f766e;
	color: white;
	border-color: #0f766e;
}
.wm-search input { width: 240px; }
.wm-banner.is-error {
	background: #fef2f2;
	color: #b91c1c;
	border: 1px solid #fecaca;
	padding: 12px 16px;
	border-radius: 12px;
}
.wm-layout {
	display: grid;
	grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
	gap: 18px;
	align-items: start;
}
.wm-list-pane {
	display: flex;
	flex-direction: column;
	gap: 10px;
	max-height: calc(100vh - 240px);
	overflow: auto;
	padding-right: 4px;
}
.wm-card {
	display: flex;
	justify-content: space-between;
	gap: 12px;
	padding: 14px;
	background: #fff;
	border: 1px solid #e5e7eb;
	border-radius: 12px;
	cursor: pointer;
	text-align: left;
}
.wm-card.is-active {
	border-color: #0f766e;
	box-shadow: 0 0 0 2px rgba(15, 118, 110, 0.15);
}
.wm-card.is-disabled { opacity: 0.55; }
.wm-card strong { display: block; font-size: 14px; }
.wm-card p {
	margin: 4px 0 0;
	color: #6b7280;
	font-size: 12.5px;
	max-width: 240px;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
}
.wm-card-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.wm-chip {
	display: inline-flex;
	padding: 3px 10px;
	border-radius: 999px;
	background: rgba(107, 114, 128, 0.15);
	color: #4b5563;
	font-size: 11.5px;
	font-weight: 600;
}
.wm-chip.is-stock { background: rgba(37, 99, 235, 0.12); color: #2563eb; }
.wm-chip.is-vente { background: rgba(15, 118, 110, 0.12); color: #0f766e; }
.wm-chip.is-achat { background: rgba(217, 119, 6, 0.12); color: #d97706; }
.wm-chip.is-on { background: rgba(5, 150, 105, 0.15); color: #047857; }
.wm-chip.is-off { background: rgba(220, 38, 38, 0.12); color: #b91c1c; }
.wm-detail-pane {
	background: #fff;
	border: 1px solid #e5e7eb;
	border-radius: 16px;
	padding: 22px;
	display: flex;
	flex-direction: column;
	gap: 18px;
}
.wm-detail-head {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 16px;
}
.wm-detail-head h2 { margin: 0; font-size: 20px; }
.wm-detail-head p { margin: 6px 0 0; color: #6b7280; max-width: 540px; }
.wm-detail-meta { display: flex; gap: 6px; margin-top: 10px; }
.wm-switch { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; }
.wm-switch input { transform: scale(1.15); }
.wm-roles { display: flex; flex-direction: column; gap: 12px; }
.wm-roles-head h3 { margin: 0; font-size: 16px; }
.wm-roles-head p { margin: 4px 0 0; color: #6b7280; }
.wm-roles-table { display: flex; flex-direction: column; gap: 4px; }
.wm-roles-row {
	display: grid;
	grid-template-columns: 1fr 80px 100px;
	align-items: center;
	gap: 12px;
	padding: 8px 12px;
	border-radius: 8px;
	background: #f9fafb;
}
.wm-roles-head-row {
	background: transparent;
	font-weight: 600;
	color: #6b7280;
	text-transform: uppercase;
	font-size: 11.5px;
	letter-spacing: 0.04em;
}
.wm-state {
	background: #fff;
	padding: 24px;
	text-align: center;
	color: #6b7280;
	border: 1px dashed #e5e7eb;
	border-radius: 16px;
}
.wm-roles-foot { display: flex; justify-content: flex-end; }
</style>
