<template>
	<div class="dm-shell">
		<header class="dm-header">
			<div>
				<h1>Gestion des tableaux de bord</h1>
				<p>
					Supervisez, désactivez et gérez les accès des tableaux de bord
					Stock, Vente et Achat.
				</p>
			</div>
		</header>

		<div v-if="pageError" class="dm-banner is-error">{{ pageError }}</div>

		<div class="dm-toolbar">
			<div class="dm-filters">
				<button
					v-for="filter in categoryFilters"
					:key="filter.value"
					class="dm-pill"
					:class="{ 'is-active': activeCategory === filter.value }"
					type="button"
					@click="setCategory(filter.value)"
				>
					{{ filter.label }}
				</button>
			</div>
			<div class="dm-search">
				<input
					v-model.trim="searchTerm"
					class="form-control"
					type="search"
					:placeholder="__('Rechercher un tableau…')"
				/>
			</div>
		</div>

		<div v-if="loading" class="dm-state">Chargement des tableaux…</div>
		<div v-else-if="!filteredDashboards.length" class="dm-state">
			Aucun tableau trouvé pour ce filtre.
		</div>
		<div v-else class="dm-table-wrap">
			<table class="table dm-table">
				<thead>
					<tr>
						<th>Nom</th>
						<th>Catégorie</th>
						<th>Statut</th>
						<th>Type d’accès</th>
						<th class="dm-col-actions">Actions</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="dashboard in filteredDashboards"
						:key="dashboard.name"
						:class="{ 'is-disabled': !dashboard.is_active }"
					>
						<td>
							<strong>{{ dashboard.title }}</strong>
							<div class="dm-subline">
								<a :href="builderHref(dashboard)" target="_blank">Ouvrir dans le constructeur</a>
								<span v-if="dashboard.user"> · Propriétaire {{ dashboard.user }}</span>
							</div>
						</td>
						<td>
							<span class="dm-chip" :class="categoryClass(dashboard.category)">
								{{ dashboard.category || "Personnel" }}
							</span>
						</td>
						<td>
							<label class="dm-switch">
								<input
									type="checkbox"
									:checked="Boolean(dashboard.is_active)"
									@change="toggleActive(dashboard)"
								/>
								<span>{{ dashboard.is_active ? "Activé" : "Désactivé" }}</span>
							</label>
						</td>
						<td>
							<span class="dm-access-label">
								{{ accessLabel(dashboard) }}
							</span>
						</td>
						<td class="dm-col-actions">
							<button
								class="btn btn-default btn-xs"
								type="button"
								@click="openEditModal(dashboard)"
							>
								Modifier
							</button>
							<button
								class="btn btn-default btn-xs"
								type="button"
								@click="openAccessModal(dashboard)"
							>
								Accès
							</button>
							<button
								class="btn btn-danger btn-xs"
								type="button"
								@click="deleteDashboard(dashboard)"
							>
								Supprimer
							</button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- Modal édition / création -->
		<div v-if="editModal.open" class="dm-modal" role="dialog" aria-modal="true">
			<div class="dm-modal-content">
				<header>
					<h2>Modifier le tableau</h2>
					<button class="btn btn-default btn-xs" type="button" @click="closeEditModal">×</button>
				</header>
				<form @submit.prevent="saveDashboard">
					<label>
						<span>Titre</span>
						<input v-model="editModal.dashboard.title" type="text" class="form-control" required />
					</label>
					<label>
						<span>Catégorie</span>
						<select v-model="editModal.dashboard.category" class="form-control">
							<option value="">Aucune (personnel)</option>
							<option v-for="opt in categories" :key="opt" :value="opt">{{ opt }}</option>
						</select>
					</label>
					<label>
						<span>Propriétaire</span>
						<select v-model="editModal.dashboard.user" class="form-control">
							<option v-for="opt in sharingOptions.users" :key="opt.value" :value="opt.value">
								{{ opt.label }}
							</option>
						</select>
					</label>
					<label class="dm-toggle">
						<input v-model="editModal.dashboard.is_active" type="checkbox" />
						<span>Tableau activé</span>
					</label>
					<footer>
						<button type="button" class="btn btn-default" @click="closeEditModal">
							Annuler
						</button>
						<button type="submit" class="btn btn-primary" :disabled="savingDashboard">
							{{ savingDashboard ? "Enregistrement…" : "Enregistrer" }}
						</button>
					</footer>
				</form>
			</div>
		</div>

		<!-- Modal accès -->
		<div v-if="accessModal.open" class="dm-modal" role="dialog" aria-modal="true">
			<div class="dm-modal-content dm-modal-content-large">
				<header>
					<h2>Qui peut voir ce tableau ?</h2>
					<button class="btn btn-default btn-xs" type="button" @click="closeAccessModal">×</button>
				</header>
				<div class="dm-access-body">
					<p class="dm-modal-help">
						Choisissez les utilisateurs ou rôles autorisés à consulter
						<strong>{{ accessModal.dashboard.title }}</strong>. Si aucun accès n'est défini,
						le tableau ne sera pas visible des utilisateurs normaux.
					</p>
					<label class="dm-toggle">
						<input v-model="accessModal.dashboard.is_shared" type="checkbox" />
						<span>Accès global (tous les utilisateurs autorisés)</span>
					</label>

					<div class="dm-share-list">
						<div
							v-for="(share, index) in accessModal.dashboard.shares"
							:key="index"
							class="dm-share-row"
						>
							<select v-model="share.share_type" class="form-control">
								<option value="User">Utilisateur</option>
								<option value="Role">Rôle</option>
							</select>
							<select
								v-if="share.share_type === 'User'"
								v-model="share.user"
								class="form-control"
							>
								<option value="">Choisir un utilisateur</option>
								<option v-for="opt in sharingOptions.users" :key="opt.value" :value="opt.value">
									{{ opt.label }}
								</option>
							</select>
							<select v-else v-model="share.role" class="form-control">
								<option value="">Choisir un rôle</option>
								<option v-for="opt in sharingOptions.roles" :key="opt.value" :value="opt.value">
									{{ opt.label }}
								</option>
							</select>
							<label class="dm-toggle">
								<input v-model="share.can_edit" type="checkbox" />
								<span>Peut modifier</span>
							</label>
							<button
								type="button"
								class="btn btn-default btn-xs"
								@click="removeShareRow(index)"
							>
								Retirer
							</button>
						</div>
					</div>
					<div class="dm-share-actions">
						<button type="button" class="btn btn-default btn-xs" @click="addShareRow('User')">
							+ Ajouter un utilisateur
						</button>
						<button type="button" class="btn btn-default btn-xs" @click="addShareRow('Role')">
							+ Ajouter un rôle
						</button>
					</div>
				</div>
				<footer>
					<button type="button" class="btn btn-default" @click="closeAccessModal">
						Annuler
					</button>
					<button
						type="button"
						class="btn btn-primary"
						:disabled="savingAccess"
						@click="saveAccess"
					>
						{{ savingAccess ? "Enregistrement…" : "Enregistrer les accès" }}
					</button>
				</footer>
			</div>
		</div>
	</div>
</template>

<script>
const CATEGORIES = ["Stock", "Vente", "Achat"];

export default {
	name: "DashboardManagement",
	data() {
		return {
			loading: false,
			savingDashboard: false,
			savingAccess: false,
			pageError: "",
			dashboards: [],
			activeCategory: "",
			searchTerm: "",
			sharingOptions: { users: [], roles: [] },
			categories: CATEGORIES,
			categoryFilters: [
				{ label: "Tous", value: "" },
				{ label: "Stock", value: "Stock" },
				{ label: "Vente", value: "Vente" },
				{ label: "Achat", value: "Achat" },
			],
			editModal: {
				open: false,
				dashboard: this.emptyDashboard(),
			},
			accessModal: {
				open: false,
				dashboard: { name: null, title: "", is_shared: 0, shares: [] },
			},
		};
	},
	computed: {
		filteredDashboards() {
			const search = (this.searchTerm || "").toLowerCase();
			return this.dashboards.filter((dashboard) => {
				if (search) {
					const haystack = [dashboard.title, dashboard.user, dashboard.category]
						.filter(Boolean)
						.join(" ")
						.toLowerCase();
					if (!haystack.includes(search)) return false;
				}
				return true;
			});
		},
	},
	mounted() {
		this.loadDashboards();
		this.loadSharingOptions();
	},
	methods: {
		__(value) {
			return this.frappe?._?.(value) ?? value;
		},
		emptyDashboard() {
			return {
				name: null,
				title: "",
				user: this.frappe?.session?.user || "Administrator",
				category: "",
				is_active: 1,
			};
		},
		categoryClass(category) {
			if (!category) return "is-personal";
			return `is-${category.toLowerCase()}`;
		},
		accessLabel(dashboard) {
			if (dashboard.is_shared) return "Accès global";
			switch (dashboard.access_label) {
				case "user":
					return `${dashboard.share_count} utilisateur(s)`;
				case "role":
					return `${dashboard.share_count} rôle(s)`;
				case "global":
					return "Accès global";
				default:
					return "Aucun accès défini";
			}
		},
		builderHref(dashboard) {
			const moduleParam = dashboard.module_name
				? `?dashboard=${encodeURIComponent(dashboard.name)}`
				: "";
			return `/app/dashboard-builder${moduleParam}`;
		},
		setCategory(value) {
			this.activeCategory = value;
			this.loadDashboards();
		},
		async loadDashboards() {
			this.loading = true;
			this.pageError = "";
			try {
				this.dashboards =
					(await this.frappe.xcall(
						"custom_dashboard.api.dashboard.list_admin_dashboards",
						{ category: this.activeCategory || null }
					)) || [];
			} catch (error) {
				this.pageError = this.parseError(error, "Impossible de charger les tableaux.");
			} finally {
				this.loading = false;
			}
		},
		async loadSharingOptions() {
			try {
				this.sharingOptions =
					(await this.frappe.xcall("custom_dashboard.api.dashboard.get_sharing_options")) || {
						users: [],
						roles: [],
					};
			} catch (error) {
				/* silencieux */
			}
		},
		openEditModal(dashboard) {
			this.editModal.dashboard = {
				name: dashboard.name,
				title: dashboard.title,
				user: dashboard.user,
				category: dashboard.category || "",
				is_active: Boolean(dashboard.is_active),
			};
			this.editModal.open = true;
		},
		closeEditModal() {
			this.editModal.open = false;
		},
		async saveDashboard() {
			this.savingDashboard = true;
			try {
				const payload = {
					name: this.editModal.dashboard.name,
					title: this.editModal.dashboard.title,
					user: this.editModal.dashboard.user,
					category: this.editModal.dashboard.category,
					is_active: this.editModal.dashboard.is_active ? 1 : 0,
				};
				await this.frappe.xcall("custom_dashboard.api.dashboard.admin_save_dashboard", {
					doc: payload,
				});
				this.frappe.show_alert({ message: "Tableau enregistré.", indicator: "green" });
				this.closeEditModal();
				await this.loadDashboards();
			} catch (error) {
				this.pageError = this.parseError(error, "Impossible d'enregistrer le tableau.");
			} finally {
				this.savingDashboard = false;
			}
		},
		async toggleActive(dashboard) {
			try {
				await this.frappe.xcall(
					"custom_dashboard.api.dashboard.admin_toggle_dashboard_active",
					{ name: dashboard.name, is_active: dashboard.is_active ? 0 : 1 }
				);
				dashboard.is_active = dashboard.is_active ? 0 : 1;
				this.frappe.show_alert({
					message: dashboard.is_active ? "Tableau activé." : "Tableau désactivé.",
					indicator: dashboard.is_active ? "green" : "orange",
				});
			} catch (error) {
				this.pageError = this.parseError(error, "Impossible de modifier le statut.");
			}
		},
		async deleteDashboard(dashboard) {
			const confirm = () =>
				new Promise((resolve) => {
					if (this.frappe.confirm) {
						this.frappe.confirm(
							`Supprimer définitivement « ${dashboard.title} » ?`,
							() => resolve(true),
							() => resolve(false)
						);
					} else {
						resolve(window.confirm(`Supprimer définitivement « ${dashboard.title} » ?`));
					}
				});
			if (!(await confirm())) return;

			try {
				await this.frappe.xcall(
					"custom_dashboard.api.dashboard.admin_delete_dashboard",
					{ name: dashboard.name }
				);
				this.frappe.show_alert({ message: "Tableau supprimé.", indicator: "red" });
				await this.loadDashboards();
			} catch (error) {
				this.pageError = this.parseError(error, "Impossible de supprimer le tableau.");
			}
		},
		async openAccessModal(dashboard) {
			try {
				const detail = await this.frappe.xcall(
					"custom_dashboard.api.dashboard.get_admin_dashboard",
					{ name: dashboard.name }
				);
				this.accessModal.dashboard = {
					name: detail.name,
					title: detail.title,
					user: detail.user,
					category: detail.category,
					is_active: Boolean(detail.is_active),
					is_shared: Boolean(detail.is_shared),
					module_name: detail.module_name || "",
					shares: (detail.shares || []).map((s) => ({
						share_type: s.share_type || "User",
						user: s.user || "",
						role: s.role || "",
						can_edit: Boolean(s.can_edit),
					})),
				};
				this.accessModal.open = true;
			} catch (error) {
				this.pageError = this.parseError(error, "Impossible de charger les accès.");
			}
		},
		closeAccessModal() {
			this.accessModal.open = false;
		},
		addShareRow(type = "User") {
			this.accessModal.dashboard.shares.push({
				share_type: type,
				user: "",
				role: "",
				can_edit: false,
			});
		},
		removeShareRow(index) {
			this.accessModal.dashboard.shares.splice(index, 1);
		},
		async saveAccess() {
			this.savingAccess = true;
			try {
				const payload = {
					name: this.accessModal.dashboard.name,
					title: this.accessModal.dashboard.title,
					user: this.accessModal.dashboard.user,
					category: this.accessModal.dashboard.category,
					is_active: this.accessModal.dashboard.is_active ? 1 : 0,
					is_shared: this.accessModal.dashboard.is_shared ? 1 : 0,
					shares: this.accessModal.dashboard.shares
						.filter((s) => (s.share_type === "User" ? s.user : s.role))
						.map((s) => ({
							share_type: s.share_type,
							user: s.share_type === "User" ? s.user : "",
							role: s.share_type === "Role" ? s.role : "",
							can_edit: s.can_edit ? 1 : 0,
						})),
				};
				await this.frappe.xcall("custom_dashboard.api.dashboard.admin_save_dashboard", {
					doc: payload,
				});
				this.frappe.show_alert({ message: "Accès mis à jour.", indicator: "green" });
				this.closeAccessModal();
				await this.loadDashboards();
			} catch (error) {
				this.pageError = this.parseError(error, "Impossible de sauvegarder les accès.");
			} finally {
				this.savingAccess = false;
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
.dm-shell {
	display: flex;
	flex-direction: column;
	gap: 18px;
	padding: 18px;
	font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
}
.dm-header {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 24px;
}
.dm-header h1 { margin: 0; font-size: 26px; }
.dm-header p { margin: 6px 0 0; color: #6b7280; max-width: 700px; }
.dm-toolbar {
	display: flex;
	flex-wrap: wrap;
	gap: 12px;
	justify-content: space-between;
}
.dm-filters { display: flex; gap: 8px; flex-wrap: wrap; }
.dm-pill {
	border: 1px solid #e5e7eb;
	background: #fff;
	border-radius: 999px;
	padding: 6px 14px;
	font-weight: 600;
	font-size: 12.5px;
	cursor: pointer;
}
.dm-pill.is-active {
	background: #0f766e;
	color: white;
	border-color: #0f766e;
}
.dm-search input { width: 240px; }
.dm-table-wrap {
	background: #fff;
	border: 1px solid #e5e7eb;
	border-radius: 16px;
	overflow: hidden;
}
.dm-table { margin: 0; }
.dm-table th { background: #f9fafb; font-weight: 600; }
.dm-table tr.is-disabled { opacity: 0.6; }
.dm-subline { color: #6b7280; font-size: 12px; margin-top: 2px; }
.dm-subline a { color: #0f766e; text-decoration: none; margin-right: 8px; }
.dm-chip {
	display: inline-flex;
	padding: 4px 10px;
	border-radius: 999px;
	background: rgba(15, 118, 110, 0.1);
	color: #0f766e;
	font-weight: 600;
	font-size: 12px;
}
.dm-chip.is-stock { background: rgba(37, 99, 235, 0.12); color: #2563eb; }
.dm-chip.is-vente { background: rgba(15, 118, 110, 0.12); color: #0f766e; }
.dm-chip.is-achat { background: rgba(217, 119, 6, 0.12); color: #d97706; }
.dm-chip.is-personal { background: rgba(107, 114, 128, 0.15); color: #4b5563; }
.dm-switch { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
.dm-switch input { transform: scale(1.1); }
.dm-access-label { color: #4b5563; font-size: 13px; }
.dm-col-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.dm-state {
	background: #fff;
	padding: 24px;
	text-align: center;
	color: #6b7280;
	border: 1px dashed #e5e7eb;
	border-radius: 16px;
}
.dm-banner.is-error {
	background: #fef2f2;
	color: #b91c1c;
	border: 1px solid #fecaca;
	padding: 12px 16px;
	border-radius: 12px;
}

.dm-modal {
	position: fixed;
	inset: 0;
	background: rgba(15, 23, 42, 0.55);
	display: flex;
	justify-content: center;
	align-items: flex-start;
	padding: 60px 20px;
	z-index: 1500;
}
.dm-modal-content {
	background: #fff;
	border-radius: 16px;
	padding: 22px;
	width: 100%;
	max-width: 480px;
	box-shadow: 0 18px 42px rgba(15, 23, 42, 0.18);
	display: flex;
	flex-direction: column;
	gap: 14px;
}
.dm-modal-content-large { max-width: 640px; }
.dm-modal-content header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 12px;
}
.dm-modal-content header h2 { margin: 0; font-size: 18px; }
.dm-modal-content form,
.dm-access-body {
	display: flex;
	flex-direction: column;
	gap: 12px;
}
.dm-modal-content label { display: flex; flex-direction: column; gap: 4px; font-weight: 500; }
.dm-modal-content footer {
	display: flex;
	justify-content: flex-end;
	gap: 10px;
}
.dm-modal-help { margin: 0; color: #4b5563; }
.dm-toggle { display: inline-flex; align-items: center; gap: 8px; font-weight: 500; flex-direction: row !important; }
.dm-toggle input { transform: scale(1.05); }
.dm-share-list { display: flex; flex-direction: column; gap: 8px; }
.dm-share-row {
	display: grid;
	grid-template-columns: 110px 1fr auto auto;
	gap: 8px;
	align-items: center;
}
.dm-share-actions { display: flex; gap: 8px; }
</style>
