<template>
	<div class="cd-builder-shell">
		<section class="cd-builder-hero">
			<div>
				<p class="cd-kicker">Prototype V1</p>
				<h1 class="cd-hero-title">
					{{ currentDashboard ? currentDashboard.title || __("Untitled Dashboard") : __("Dashboard Builder") }}
				</h1>
				<p class="cd-hero-subtitle">{{ dashboardSubtitle }}</p>
			</div>

			<div class="cd-hero-actions">
				<button class="btn btn-default" @click="createDashboard()">
					{{ __("New Dashboard") }}
				</button>
				<button class="btn btn-default" @click="reloadCurrent()">
					{{ __("Refresh") }}
				</button>
				<button
					class="btn btn-primary"
					:disabled="saving || !currentDashboard || !canEditCurrent"
					@click="saveDashboard()"
				>
					{{ saving ? __("Saving...") : __("Save Dashboard") }}
				</button>
			</div>
		</section>

		<div v-if="pageError" class="cd-alert cd-alert-error">
			{{ pageError }}
		</div>

		<div v-if="currentDashboard && !canEditCurrent" class="cd-alert">
			{{ __("This dashboard is shared and read-only for you. Use New Dashboard to create a personal copy.") }}
		</div>

		<div class="cd-grid">
			<aside class="cd-panel">
				<div class="cd-panel-header">
					<div>
						<h2>{{ __("Widget Library") }}</h2>
						<p>{{ __("Only widgets allowed by your roles are shown here.") }}</p>
					</div>
					<span class="cd-badge">{{ availableWidgets.length }}</span>
				</div>

				<div v-if="widgetsLoading" class="cd-panel-state">
					{{ __("Loading widgets...") }}
				</div>
				<div v-else-if="!availableWidgets.length" class="cd-panel-state">
					{{ __("No widgets are available for your account.") }}
				</div>
				<div v-else class="cd-library-list">
					<button
						v-for="widget in availableWidgets"
						:key="widget.name"
						class="cd-library-card"
						type="button"
						:disabled="!canEditCurrent"
						@click="addWidget(widget)"
					>
						<div class="cd-library-header">
							<strong>{{ widget.title }}</strong>
							<span class="cd-chip">{{ widget.widget_type }}</span>
						</div>
						<div class="cd-library-meta">
							{{ widget.category || __("General") }}
						</div>
						<div class="cd-library-foot">
							<span>{{ widget.data_source_type }}</span>
							<span>{{ __("Add") }}</span>
						</div>
					</button>
				</div>
			</aside>

			<main class="cd-panel cd-canvas">
				<div v-if="!currentDashboard" class="cd-panel-state">
					{{ __("Create a dashboard or open an existing one to start.") }}
				</div>

				<template v-else>
					<div class="cd-dashboard-form">
						<div class="cd-field">
							<label>{{ __("Dashboard Title") }}</label>
							<input
								v-model="currentDashboard.title"
								class="form-control"
								:disabled="!canEditCurrent"
								type="text"
							/>
						</div>

						<div class="cd-checkbox-row">
							<label class="cd-toggle">
								<input
									v-model="currentDashboard.is_default"
									:disabled="!canEditCurrent"
									type="checkbox"
								/>
								<span>{{ __("Default") }}</span>
							</label>

							<label class="cd-toggle">
								<input
									v-model="currentDashboard.is_shared"
									:disabled="!canEditCurrent"
									type="checkbox"
								/>
								<span>{{ __("Shared") }}</span>
							</label>
						</div>
					</div>

					<div v-if="loadingDashboard" class="cd-panel-state">
						{{ __("Loading dashboard...") }}
					</div>
					<div v-else-if="!currentDashboard.items.length" class="cd-empty-state">
						<p>{{ __("No widgets on this dashboard yet.") }}</p>
						<span>{{ __("Use the library on the left to add your first widget.") }}</span>
					</div>
					<div v-else class="cd-items">
						<article
							v-for="(item, index) in currentDashboard.items"
							:key="item.local_id"
							class="cd-item-card"
						>
							<header class="cd-item-header">
								<div class="cd-item-heading">
									<input
										v-model="item.display_title"
										class="form-control input-sm"
										:disabled="!canEditCurrent"
										type="text"
									/>
									<p class="cd-item-caption">
										{{ item.definition?.widget_type || item.widget }} - {{ layoutLabel(item) }}
									</p>
								</div>

								<div class="cd-item-actions">
									<button class="btn btn-default btn-sm" @click="refreshItem(item)">
										{{ __("Refresh") }}
									</button>
									<button
										class="btn btn-default btn-sm"
										:disabled="!canEditCurrent"
										@click="removeItem(index)"
									>
										{{ __("Remove") }}
									</button>
								</div>
							</header>

							<div v-if="item.definition?.allow_filters" class="cd-field">
								<label>{{ __("Filters JSON") }}</label>
								<textarea
									v-model="item.filters_json"
									class="form-control"
									:disabled="!canEditCurrent"
									rows="3"
								></textarea>
							</div>

							<div class="cd-preview">
								<div v-if="item.loading" class="cd-panel-state">
									{{ __("Loading widget...") }}
								</div>
								<div v-else-if="item.error" class="cd-preview-error">
									{{ item.error }}
								</div>
								<template v-else>
									<div v-if="itemType(item) === 'number_card'" class="cd-number-card">
										<strong class="cd-number-value">{{ formatNumberCardValue(item) }}</strong>
										<span class="cd-number-label">{{ numberCardLabel(item) }}</span>
									</div>

									<div v-else-if="itemType(item) === 'table'" class="table-responsive">
										<table class="table table-bordered cd-table-preview">
											<thead>
												<tr>
													<th v-for="column in getTableColumns(item)" :key="column">
														{{ column }}
													</th>
												</tr>
											</thead>
											<tbody>
												<tr v-for="(row, rowIndex) in getTableRows(item)" :key="rowIndex">
													<td v-for="(cell, cellIndex) in row" :key="`${rowIndex}-${cellIndex}`">
														{{ cell }}
													</td>
												</tr>
											</tbody>
										</table>
									</div>

									<div v-else-if="itemType(item) === 'chart'" class="cd-chart-preview">
										<div
											v-for="bar in getChartBars(item)"
											:key="bar.label"
											class="cd-chart-row"
										>
											<span class="cd-chart-label">{{ bar.label }}</span>
											<div class="cd-chart-track">
												<div class="cd-chart-fill" :style="{ width: `${bar.width}%` }"></div>
											</div>
											<strong class="cd-chart-value">{{ bar.value }}</strong>
										</div>
									</div>

									<div v-else class="cd-custom-preview">
										<p v-if="customSummary(item)" class="cd-custom-summary">
											{{ customSummary(item) }}
										</p>
										<pre>{{ formatJson(item.preview?.data) }}</pre>
									</div>
								</template>
							</div>
						</article>
					</div>
				</template>
			</main>

			<aside class="cd-panel">
				<div class="cd-panel-header">
					<div>
						<h2>{{ __("Dashboards") }}</h2>
						<p>{{ __("Your personal dashboards and shared dashboards.") }}</p>
					</div>
					<span class="cd-badge">{{ dashboards.length }}</span>
				</div>

				<div v-if="dashboardsLoading" class="cd-panel-state">
					{{ __("Loading dashboards...") }}
				</div>
				<div v-else-if="!dashboards.length" class="cd-panel-state">
					{{ __("No dashboards found yet.") }}
				</div>
				<div v-else class="cd-dashboard-list">
					<button
						v-for="dashboard in dashboards"
						:key="dashboard.name"
						class="cd-dashboard-row"
						:class="{ 'is-active': currentDashboard?.name === dashboard.name }"
						type="button"
						@click="openDashboard(dashboard.name)"
					>
						<div class="cd-dashboard-row-main">
							<strong>{{ dashboard.title }}</strong>
							<span>
								{{
									dashboard.user === currentUser
										? __("Mine")
										: __("Shared by {0}", [dashboard.user])
								}}
							</span>
						</div>
						<div class="cd-dashboard-row-flags">
							<span v-if="dashboard.is_default" class="cd-chip">{{ __("Default") }}</span>
							<span v-if="!dashboard.can_write" class="cd-chip">{{ __("Read only") }}</span>
						</div>
					</button>
				</div>
			</aside>
		</div>
	</div>
</template>

<script>
export default {
	name: "DashboardBuilder",
	props: {
		page: {
			type: Object,
			default: null,
		},
	},
	data() {
		return {
			availableWidgets: [],
			dashboards: [],
			currentDashboard: null,
			widgetsLoading: true,
			dashboardsLoading: true,
			loadingDashboard: false,
			saving: false,
			pageError: "",
			localId: 1,
		};
	},
	computed: {
		currentUser() {
			return this.frappe.session.user;
		},
		userIsAdmin() {
			return (this.frappe.user_roles || []).some((role) =>
				["System Manager", "Dashboard Admin"].includes(role)
			);
		},
		canEditCurrent() {
			if (!this.currentDashboard) {
				return true;
			}

			return Boolean(this.currentDashboard.can_write);
		},
		dashboardSubtitle() {
			if (!this.currentDashboard) {
				return this.__("Build a personal dashboard from the widgets you are allowed to use.");
			}

			if (this.currentDashboard.user === this.currentUser) {
				return this.__("Personal dashboard owned by you.");
			}

			return this.__("Shared dashboard owned by {0}.", [this.currentDashboard.user]);
		},
	},
	async mounted() {
		await this.loadInitialState();
	},
	methods: {
		async loadInitialState() {
			this.pageError = "";

			try {
				await Promise.all([this.loadWidgets(), this.loadDashboards()]);

				if (this.dashboards.length) {
					const preferredDashboard =
						this.dashboards.find(
							(dashboard) => dashboard.is_default && dashboard.user === this.currentUser
						) || this.dashboards[0];

					await this.openDashboard(preferredDashboard.name);
					return;
				}

				this.createDashboard(false);
			} catch (error) {
				this.pageError = this.parseError(
					error,
					this.__("Unable to initialize the dashboard builder.")
				);
			}
		},
		async loadWidgets() {
			this.widgetsLoading = true;

			try {
				this.availableWidgets =
					(await this.frappe.xcall("custom_dashboard.api.widget.list_available_widgets")) || [];
			} finally {
				this.widgetsLoading = false;
			}
		},
		async loadDashboards() {
			this.dashboardsLoading = true;

			try {
				this.dashboards =
					(await this.frappe.xcall("custom_dashboard.api.dashboard.list_user_dashboards")) || [];
			} finally {
				this.dashboardsLoading = false;
			}
		},
		normalizeDashboard(doc) {
			return {
				doctype: "User Dashboard",
				name: doc.name || null,
				title: doc.title || this.__("Untitled Dashboard"),
				user: doc.user || this.currentUser,
				is_default: Boolean(doc.is_default),
				is_shared: Boolean(doc.is_shared),
				can_write: doc.can_write !== false && doc.can_write !== 0,
				items: (doc.items || []).map((item) => this.normalizeItem(item)),
			};
		},
		normalizeItem(item) {
			const widgetDefinition = item.widget_definition || this.getWidgetDefinition(item.widget);

			return {
				local_id: this.localId++,
				name: item.name || null,
				widget: item.widget,
				x: Number(item.x || 0),
				y: Number(item.y || 0),
				w: Number(item.w || 6),
				h: Number(item.h || this.defaultHeight(widgetDefinition?.widget_type)),
				display_title: item.display_title || widgetDefinition?.title || item.widget,
				filters_json: item.filters_json || "",
				definition: widgetDefinition || null,
				preview: null,
				loading: false,
				error: "",
			};
		},
		getWidgetDefinition(widgetName) {
			return this.availableWidgets.find((widget) => widget.name === widgetName) || null;
		},
		defaultHeight(widgetType) {
			return widgetType === "table" ? 6 : 4;
		},
		copyItems(items = []) {
			return items.map((item) =>
				this.normalizeItem({
					widget: item.widget,
					x: item.x,
					y: item.y,
					w: item.w,
					h: item.h,
					display_title: item.display_title,
					filters_json: item.filters_json,
					widget_definition: item.definition || item.widget_definition,
				})
			);
		},
		createDashboard(copyCurrent = true) {
			const hasPersonalDashboards = this.dashboards.some(
				(dashboard) => dashboard.user === this.currentUser
			);
			const sourceTitle = this.currentDashboard?.title || this.__("My Dashboard");
			const copiedItems =
				copyCurrent && this.currentDashboard?.items?.length
					? this.copyItems(this.currentDashboard.items)
					: [];

			this.currentDashboard = {
				doctype: "User Dashboard",
				name: null,
				title: copyCurrent ? this.__("{0} Copy", [sourceTitle]) : this.__("My Dashboard"),
				user: this.currentUser,
				is_default: !hasPersonalDashboards,
				is_shared: false,
				can_write: true,
				items: copiedItems,
			};

			this.pageError = "";
			this.refreshAllItems();
		},
		addWidget(widget) {
			if (!this.currentDashboard) {
				this.createDashboard(false);
			}

			if (!this.canEditCurrent) {
				this.notifyReadonly();
				return;
			}

			const nextY = this.currentDashboard.items.reduce(
				(maxY, item) => Math.max(maxY, Number(item.y) + Number(item.h)),
				0
			);

			const dashboardItem = this.normalizeItem({
				widget: widget.name,
				x: 0,
				y: nextY,
				w: 6,
				h: this.defaultHeight(widget.widget_type),
				display_title: widget.title,
				filters_json: "",
				widget_definition: widget,
			});

			this.currentDashboard.items.push(dashboardItem);
			this.refreshItem(dashboardItem);
		},
		removeItem(index) {
			if (!this.canEditCurrent) {
				this.notifyReadonly();
				return;
			}

			this.currentDashboard.items.splice(index, 1);
		},
		async openDashboard(name) {
			this.loadingDashboard = true;
			this.pageError = "";

			try {
				const doc = await this.frappe.xcall("custom_dashboard.api.dashboard.get_dashboard", {
					name,
				});
				this.currentDashboard = this.normalizeDashboard(doc);
				await this.refreshAllItems();
			} catch (error) {
				this.pageError = this.parseError(
					error,
					this.__("Unable to load the selected dashboard.")
				);
			} finally {
				this.loadingDashboard = false;
			}
		},
		async saveDashboard() {
			if (!this.currentDashboard) {
				return;
			}

			if (!this.canEditCurrent) {
				this.notifyReadonly();
				return;
			}

			if (!this.currentDashboard.title?.trim()) {
				this.frappe.throw(this.__("Dashboard title is required."));
			}

			this.saving = true;
			this.pageError = "";

			try {
				const payload = {
					doctype: "User Dashboard",
					name: this.currentDashboard.name,
					title: this.currentDashboard.title,
					user: this.currentDashboard.user,
					is_default: this.currentDashboard.is_default ? 1 : 0,
					is_shared: this.currentDashboard.is_shared ? 1 : 0,
					items: this.currentDashboard.items.map((item) => ({
						widget: item.widget,
						x: item.x,
						y: item.y,
						w: item.w,
						h: item.h,
						display_title: item.display_title,
						filters_json: item.filters_json,
					})),
				};

				const savedDashboard = await this.frappe.xcall(
					"custom_dashboard.api.dashboard.save_user_dashboard",
					{ doc: payload }
				);

				this.currentDashboard = this.normalizeDashboard(savedDashboard);
				await Promise.all([this.refreshAllItems(), this.loadDashboards()]);
				this.notify(this.__("Dashboard saved successfully."), "green");
			} catch (error) {
				this.pageError = this.parseError(error, this.__("Unable to save the dashboard."));
			} finally {
				this.saving = false;
			}
		},
		async reloadCurrent() {
			if (!this.currentDashboard) {
				await this.loadInitialState();
				return;
			}

			if (this.currentDashboard.name) {
				await this.openDashboard(this.currentDashboard.name);
				return;
			}

			await this.refreshAllItems();
		},
		async refreshAllItems() {
			if (!this.currentDashboard?.items?.length) {
				return;
			}

			await Promise.all(this.currentDashboard.items.map((item) => this.refreshItem(item)));
		},
		async refreshItem(item) {
			item.loading = true;
			item.error = "";

			try {
				if (!item.definition) {
					item.definition =
						(await this.frappe.xcall("custom_dashboard.api.widget.get_widget_definition", {
							widget_name: item.widget,
						})) || null;
				}

				item.preview = await this.frappe.xcall("custom_dashboard.api.widget.get_widget_data", {
					widget_name: item.widget,
					filters: item.filters_json || null,
				});
			} catch (error) {
				item.error = this.parseError(error, this.__("Unable to load this widget."));
			} finally {
				item.loading = false;
			}
		},
		itemType(item) {
			return item.preview?.type || item.definition?.widget_type || "custom";
		},
		itemPayload(item) {
			return item.preview?.data || {};
		},
		formatNumberCardValue(item) {
			const payload = this.itemPayload(item);

			if (payload && typeof payload === "object" && "value" in payload) {
				return `${payload.value}${payload.suffix || ""}`;
			}

			return payload ?? "0";
		},
		numberCardLabel(item) {
			const payload = this.itemPayload(item);
			return payload?.label || item.display_title || item.definition?.title || item.widget;
		},
		getTableColumns(item) {
			const payload = this.itemPayload(item);
			if (Array.isArray(payload.columns) && payload.columns.length) {
				return payload.columns;
			}

			const rows = payload.rows || [];
			if (Array.isArray(rows[0]) && rows[0].length) {
				return rows[0].map((_, index) => this.__("Column {0}", [index + 1]));
			}

			if (rows.length && typeof rows[0] === "object") {
				return Object.keys(rows[0]);
			}

			return [];
		},
		getTableRows(item) {
			const payload = this.itemPayload(item);
			const rows = payload.rows || [];
			if (!Array.isArray(rows)) {
				return [];
			}

			if (rows.length && typeof rows[0] === "object" && !Array.isArray(rows[0])) {
				const columns = this.getTableColumns(item);
				return rows.map((row) => columns.map((column) => row[column]));
			}

			return rows;
		},
		getChartBars(item) {
			const payload = this.itemPayload(item);
			const labels = Array.isArray(payload.labels) ? payload.labels : [];
			const values =
				Array.isArray(payload.datasets) && payload.datasets.length
					? payload.datasets[0].values || []
					: [];
			const maxValue = Math.max(...values, 1);

			return labels.map((label, index) => {
				const value = Number(values[index] || 0);
				return {
					label,
					value,
					width: Math.max((value / maxValue) * 100, value ? 8 : 0),
				};
			});
		},
		customSummary(item) {
			const payload = this.itemPayload(item);
			return payload?.summary || "";
		},
		formatJson(value) {
			return JSON.stringify(value || {}, null, 2);
		},
		layoutLabel(item) {
			return `x:${item.x} y:${item.y} w:${item.w} h:${item.h}`;
		},
		notify(message, indicator = "blue") {
			this.frappe.show_alert({ message, indicator });
		},
		notifyReadonly() {
			this.notify(
				this.__("This dashboard is read-only. Create a personal copy to edit it."),
				"orange"
			);
		},
		parseError(error, fallbackMessage) {
			if (error?._server_messages) {
				try {
					const messages = JSON.parse(error._server_messages);
					if (messages.length) {
						const firstMessage = JSON.parse(messages[0]);
						return firstMessage.message || fallbackMessage;
					}
				} catch {
					return fallbackMessage;
				}
			}

			return error?.message || fallbackMessage;
		},
	},
};
</script>

<style scoped>
.cd-builder-shell {
	--cd-bg: linear-gradient(135deg, #f7f3eb 0%, #eef6f4 100%);
	--cd-panel: rgba(255, 255, 255, 0.88);
	--cd-border: rgba(31, 74, 66, 0.12);
	--cd-text: #173d38;
	--cd-muted: #62807a;
	--cd-accent: #0d9488;
	--cd-accent-soft: rgba(13, 148, 136, 0.12);
	--cd-danger: #b42318;
	background: var(--cd-bg);
	border-radius: 22px;
	padding: 20px;
	color: var(--cd-text);
}

.cd-builder-hero {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 16px;
	background: linear-gradient(135deg, rgba(255, 255, 255, 0.94), rgba(255, 250, 243, 0.88));
	border: 1px solid var(--cd-border);
	border-radius: 20px;
	padding: 20px 22px;
	box-shadow: 0 16px 34px rgba(23, 61, 56, 0.08);
}

.cd-kicker {
	margin: 0 0 6px;
	text-transform: uppercase;
	letter-spacing: 0.14em;
	font-size: 11px;
	font-weight: 700;
	color: var(--cd-accent);
}

.cd-hero-title {
	margin: 0;
	font-size: 28px;
	font-weight: 700;
}

.cd-hero-subtitle {
	margin: 8px 0 0;
	color: var(--cd-muted);
}

.cd-hero-actions {
	display: flex;
	gap: 10px;
	flex-wrap: wrap;
}

.cd-alert {
	margin-top: 16px;
	padding: 12px 14px;
	border-radius: 14px;
	background: rgba(255, 255, 255, 0.76);
	border: 1px solid var(--cd-border);
	color: var(--cd-text);
}

.cd-alert-error {
	border-color: rgba(180, 35, 24, 0.2);
	color: var(--cd-danger);
}

.cd-grid {
	display: grid;
	grid-template-columns: minmax(240px, 280px) minmax(0, 1fr) minmax(240px, 280px);
	gap: 16px;
	margin-top: 16px;
}

.cd-panel {
	background: var(--cd-panel);
	border: 1px solid var(--cd-border);
	border-radius: 20px;
	padding: 16px;
	box-shadow: 0 12px 28px rgba(23, 61, 56, 0.07);
	backdrop-filter: blur(8px);
}

.cd-panel-header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 12px;
	margin-bottom: 14px;
}

.cd-panel-header h2 {
	margin: 0;
	font-size: 17px;
	font-weight: 700;
}

.cd-panel-header p {
	margin: 4px 0 0;
	color: var(--cd-muted);
	font-size: 13px;
}

.cd-badge {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	min-width: 28px;
	height: 28px;
	border-radius: 999px;
	background: var(--cd-accent-soft);
	color: var(--cd-accent);
	font-size: 12px;
	font-weight: 700;
	padding: 0 10px;
}

.cd-library-list,
.cd-dashboard-list,
.cd-items {
	display: flex;
	flex-direction: column;
	gap: 12px;
}

.cd-library-card,
.cd-dashboard-row {
	width: 100%;
	border: 1px solid var(--cd-border);
	border-radius: 16px;
	background: rgba(255, 255, 255, 0.75);
	padding: 14px;
	text-align: left;
	transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}

.cd-library-card:hover,
.cd-dashboard-row:hover,
.cd-dashboard-row.is-active {
	transform: translateY(-1px);
	border-color: rgba(13, 148, 136, 0.28);
	box-shadow: 0 8px 18px rgba(13, 148, 136, 0.08);
}

.cd-library-header,
.cd-library-foot,
.cd-dashboard-row-main,
.cd-dashboard-row-flags,
.cd-item-header,
.cd-item-actions,
.cd-checkbox-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
}

.cd-library-meta,
.cd-dashboard-row-main span,
.cd-item-caption,
.cd-number-label,
.cd-custom-summary {
	color: var(--cd-muted);
	font-size: 13px;
}

.cd-chip {
	display: inline-flex;
	align-items: center;
	padding: 4px 8px;
	border-radius: 999px;
	background: rgba(23, 61, 56, 0.08);
	font-size: 11px;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 0.06em;
}

.cd-canvas {
	min-height: 540px;
}

.cd-dashboard-form {
	display: flex;
	align-items: flex-end;
	justify-content: space-between;
	gap: 16px;
	padding-bottom: 16px;
	margin-bottom: 16px;
	border-bottom: 1px solid var(--cd-border);
}

.cd-field {
	flex: 1;
}

.cd-field label {
	display: block;
	margin-bottom: 6px;
	font-size: 12px;
	font-weight: 600;
	color: var(--cd-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
}

.cd-toggle {
	display: inline-flex;
	align-items: center;
	gap: 8px;
	padding: 10px 12px;
	border-radius: 14px;
	background: rgba(255, 255, 255, 0.72);
	border: 1px solid var(--cd-border);
}

.cd-item-card {
	border: 1px solid var(--cd-border);
	border-radius: 18px;
	padding: 16px;
	background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(248, 252, 251, 0.9));
}

.cd-item-heading {
	flex: 1;
}

.cd-preview {
	margin-top: 14px;
	padding: 16px;
	border-radius: 16px;
	background: rgba(247, 250, 249, 0.95);
	border: 1px solid rgba(23, 61, 56, 0.08);
}

.cd-number-card {
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.cd-number-value {
	font-size: 34px;
	font-weight: 700;
	line-height: 1;
}

.cd-chart-preview {
	display: flex;
	flex-direction: column;
	gap: 12px;
}

.cd-chart-row {
	display: grid;
	grid-template-columns: 64px 1fr auto;
	align-items: center;
	gap: 10px;
}

.cd-chart-track {
	height: 10px;
	border-radius: 999px;
	background: rgba(13, 148, 136, 0.12);
	overflow: hidden;
}

.cd-chart-fill {
	height: 100%;
	border-radius: inherit;
	background: linear-gradient(90deg, #14b8a6, #0f766e);
}

.cd-chart-label,
.cd-chart-value {
	font-size: 12px;
}

.cd-table-preview {
	margin: 0;
	background: white;
}

.cd-table-preview th {
	background: rgba(13, 148, 136, 0.08);
}

.cd-custom-preview pre {
	margin: 0;
	padding: 12px;
	background: rgba(20, 24, 28, 0.94);
	color: #f3f6f4;
	border-radius: 14px;
	font-size: 12px;
	max-height: 240px;
	overflow: auto;
}

.cd-panel-state,
.cd-empty-state {
	display: grid;
	place-items: center;
	min-height: 160px;
	border: 1px dashed rgba(13, 148, 136, 0.25);
	border-radius: 16px;
	background: rgba(255, 255, 255, 0.56);
	text-align: center;
	color: var(--cd-muted);
	padding: 18px;
}

.cd-empty-state p {
	margin: 0 0 8px;
	font-weight: 600;
	color: var(--cd-text);
}

.cd-preview-error {
	color: var(--cd-danger);
}

@media (max-width: 1200px) {
	.cd-grid {
		grid-template-columns: 1fr;
	}
}

@media (max-width: 768px) {
	.cd-builder-shell {
		padding: 14px;
		border-radius: 18px;
	}

	.cd-builder-hero,
	.cd-dashboard-form,
	.cd-item-header {
		flex-direction: column;
		align-items: stretch;
	}

	.cd-hero-actions,
	.cd-item-actions,
	.cd-checkbox-row {
		width: 100%;
	}

	.cd-hero-actions .btn,
	.cd-item-actions .btn {
		flex: 1;
	}
}
</style>
