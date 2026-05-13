<template>
	<div class="sd-shell" :class="`sd-theme-${themeKey}`" :style="themeStyle">
		<header class="sd-hero">
			<div class="sd-hero-bg" aria-hidden="true"></div>
			<div class="sd-hero-glow" aria-hidden="true"></div>

			<div class="sd-hero-main">
				<div class="sd-hero-left">
					<div class="sd-hero-icon" v-html="theme.icon"></div>
					<div class="sd-hero-titles">
						<div class="sd-hero-eyebrow">
							<span class="sd-hero-tag">{{ resolvedModuleLabel }}</span>
							<span v-if="dashboard" class="sd-hero-dot">•</span>
							<span v-if="dashboard" class="sd-hero-meta">
								{{ orderedItems.length }} widget{{ orderedItems.length > 1 ? "s" : "" }}
							</span>
							<span v-if="lastRefreshLabel" class="sd-hero-dot">•</span>
							<span v-if="lastRefreshLabel" class="sd-hero-meta">
								MAJ {{ lastRefreshLabel }}
							</span>
						</div>
						<h1 class="sd-hero-title">
							{{ dashboard ? dashboard.title : resolvedPageTitle }}
						</h1>
						<p class="sd-hero-subtitle">{{ subtitle }}</p>
					</div>
				</div>

				<div class="sd-hero-actions">
					<button
						class="sd-btn sd-btn-ghost"
						type="button"
						:disabled="loading"
						@click="refresh"
						:title="loading ? 'Actualisation en cours' : 'Actualiser les donnees'"
					>
						<span class="sd-btn-icon" :class="{ 'is-spinning': loading }">↻</span>
						<span>{{ loading ? "Actualisation..." : "Actualiser" }}</span>
					</button>
					<a class="sd-btn sd-btn-ghost" :href="builderHref">
						<span class="sd-btn-icon">⚙</span>
						<span>Constructeur</span>
					</a>
					<a class="sd-btn sd-btn-solid" :href="workspaceHref">
						<span>Workspace ERPNext</span>
						<span class="sd-btn-icon">→</span>
					</a>
				</div>
			</div>

			<!--
				Le KPI strip a ete retire : les widgets numeriques sont desormais
				affiches en tete de la grille principale (tri par type), ce qui
				evite la duplication visuelle.
			-->
		</header>

		<!-- Barre de filtres globale (DashboardFilterBar) - construite via frappe.ui.form.make_control -->
		<div ref="filterBarHost" class="sd-filterbar-host"></div>

		<div v-if="pageError" class="sd-banner is-error" role="alert">
			<span class="sd-banner-icon">!</span>
			<span>{{ pageError }}</span>
		</div>

		<div v-if="dashboard && dashboard.disabled" class="sd-empty sd-empty-large sd-disabled">
			<div class="sd-empty-illustration">⛔</div>
			<h3>{{ dashboard.disabled_message || disabledMessage }}</h3>
			<p>
				Contactez un administrateur pour réactiver ce tableau depuis la page
				« Gestion des tableaux ».
			</p>
		</div>

		<div v-else-if="loading && !dashboard" class="sd-grid sd-grid-skeleton">
			<div v-for="n in 6" :key="`skel-${n}`" class="sd-skel-card">
				<div class="sd-skel-line short"></div>
				<div class="sd-skel-line tall"></div>
				<div class="sd-skel-line"></div>
			</div>
		</div>

		<div v-else-if="!dashboard && !pageError" class="sd-empty sd-empty-large">
			<div class="sd-empty-illustration" v-html="theme.icon"></div>
			<h3>Aucun tableau de bord publié pour {{ resolvedModuleLabel }}</h3>
			<p>Configurez les widgets et la mise en page depuis le constructeur.</p>
			<a class="sd-btn sd-btn-solid" :href="builderHref">
				<span>Créer un dashboard {{ resolvedModuleLabel }}</span>
				<span class="sd-btn-icon">→</span>
			</a>
		</div>

		<div v-else-if="!orderedItems.length" class="sd-empty sd-empty-large">
			<div class="sd-empty-illustration">∅</div>
			<h3>Aucun widget visible pour vos rôles</h3>
			<p>Demandez à un administrateur d'ajuster les permissions ou les widgets publiés.</p>
		</div>

		<div v-else class="sd-grid" :style="canvasStyle">
			<article
				v-for="(item, idx) in orderedItems"
				:key="item.name || item.local_id"
				class="sd-card"
				:class="[`is-type-${itemType(item)}`, { 'is-loading': item.loading }]"
				:style="[gridItemStyle(item), { animationDelay: `${Math.min(idx * 35, 300)}ms` }]"
			>
				<div class="sd-card-accent" aria-hidden="true"></div>

				<header class="sd-card-head">
					<div class="sd-card-head-titles">
						<h3>{{ item.display_title || item.definition?.title || item.widget }}</h3>
						<p class="sd-card-cat">
							<span class="sd-card-cat-dot"></span>
							{{ item.definition?.category || "Général" }}
							<span class="sd-card-cat-sep">·</span>
							{{ widgetTypeLabel(item) }}
						</p>
					</div>
					<span class="sd-card-glyph">{{ widgetGlyph(item) }}</span>
				</header>

				<div class="sd-card-body">
					<div v-if="item.loading" class="sd-skel-body">
						<div class="sd-skel-line short"></div>
						<div class="sd-skel-line tall"></div>
						<div class="sd-skel-line"></div>
					</div>
					<div v-else-if="item.error" class="sd-inline-error">
						<span class="sd-inline-error-icon">!</span>
						<span>{{ item.error }}</span>
					</div>
					<div v-else-if="item.definition && !item.definition.can_use" class="sd-empty">
						<p>Lecture autorisée mais exécution non permise pour vos rôles.</p>
					</div>
					<template v-else>
						<div v-if="itemType(item) === 'number_card'" class="sd-number-card">
							<strong class="sd-number-value">{{ formatNumberCardValue(item) }}</strong>
							<span class="sd-number-label">{{ numberCardLabel(item) }}</span>
							<span v-if="numberCardSecondary(item)" class="sd-number-secondary">
								<span class="sd-number-trend">▲</span>
								{{ numberCardSecondary(item) }}
							</span>
							<small v-if="itemPayload(item).context" class="sd-context">
								{{ itemPayload(item).context }}
							</small>
						</div>

						<div v-else-if="itemType(item) === 'table'" class="sd-table-wrap">
							<small v-if="itemPayload(item).context" class="sd-context">
								{{ itemPayload(item).context }}
							</small>
							<div class="table-responsive sd-table-scroll">
								<table class="table sd-table">
									<thead>
										<tr>
											<th
												v-for="column in getTableColumns(item)"
												:key="column.key"
												:class="{ 'is-numeric': isNumericColumn(column) }"
											>
												{{ column.label }}
											</th>
										</tr>
									</thead>
									<tbody>
										<tr v-for="(row, rowIndex) in getTableRows(item)" :key="rowIndex">
											<td
												v-for="column in getTableColumns(item)"
												:key="`${rowIndex}-${column.key}`"
												:class="{ 'is-numeric': isNumericColumn(column) }"
											>
												{{ formatTableCell(row, column) }}
											</td>
										</tr>
									</tbody>
								</table>
							</div>
						</div>

						<div v-else-if="itemType(item) === 'chart'" class="sd-chart">
							<div class="sd-chart-headline">
								<div>
									<strong>{{ chartSummaryLabel(item) }}</strong>
									<span>{{ chartSummaryValue(item) }}</span>
								</div>
								<small v-if="itemPayload(item).context">{{ itemPayload(item).context }}</small>
							</div>
							<div :ref="`chart_${item.local_id}`" class="sd-chart-host"></div>
						</div>

						<div v-else-if="itemType(item) === 'ai_insight'" class="sd-ai">
							<div v-if="aiPayload(item).error" class="sd-inline-error">
								{{ aiPayload(item).error }}
							</div>
							<template v-else>
								<p class="sd-ai-summary">
									{{ aiPayload(item).summary || "Aucune synthese generee. Cliquez sur Regenerer." }}
								</p>

								<section class="sd-ai-section">
									<h4>Anomalies détectées</h4>
									<div v-if="!(aiPayload(item).anomalies || []).length" class="sd-ai-empty">
										Aucune anomalie significative.
									</div>
									<ul v-else class="sd-ai-list">
										<li
											v-for="(anomaly, idx) in aiPayload(item).anomalies"
											:key="`a-${idx}`"
											:class="`sd-ai-item sev-${anomaly.severity || 'medium'}`"
										>
											<div class="sd-ai-item-head">
												<span class="sd-ai-badge">{{ severityLabel(anomaly.severity) }}</span>
												<strong>{{ anomaly.label }}</strong>
											</div>
											<p>{{ anomaly.evidence }}</p>
										</li>
									</ul>
								</section>

								<section class="sd-ai-section">
									<h4>Recommandations</h4>
									<div v-if="!(aiPayload(item).recommendations || []).length" class="sd-ai-empty">
										Aucune recommandation.
									</div>
									<ol v-else class="sd-ai-list">
										<li
											v-for="(rec, idx) in aiPayload(item).recommendations"
											:key="`r-${idx}`"
											:class="`sd-ai-item sev-${rec.priority || 'medium'}`"
										>
											<div class="sd-ai-item-head">
												<span class="sd-ai-badge">{{ severityLabel(rec.priority) }}</span>
												<strong>{{ rec.action }}</strong>
											</div>
											<p>{{ rec.rationale }}</p>
										</li>
									</ol>
								</section>
							</template>

							<footer class="sd-ai-footer">
								<button
									class="sd-btn sd-btn-ghost sd-btn-xs"
									type="button"
									:disabled="item.aiRegenerating"
									@click="regenerateAi(item)"
								>
									<span class="sd-btn-icon" :class="{ 'is-spinning': item.aiRegenerating }">↻</span>
									<span>{{ item.aiRegenerating ? "Regeneration..." : "Regenerer" }}</span>
								</button>
								<small v-if="aiPayload(item).model">
									{{ aiPayload(item).from_cache ? "Cache" : "Frais" }}
									· {{ aiPayload(item).model }}
									· {{ formatGeneratedAt(item) }}
								</small>
							</footer>
						</div>

						<div v-else class="sd-custom">
							<pre>{{ formatJson(item.preview?.data) }}</pre>
						</div>
					</template>
				</div>
			</article>
		</div>
	</div>
</template>

<script>
const GRID_COLUMNS = 12;
const GRID_ROW_HEIGHT = 56;
const GRID_GAP = 14;

let LOCAL_ID = 1;

/**
 * Palette UNIFIEE pour les 3 pages (stock / vente / achat).
 * On garde la meme charte visuelle pour cohesion. Seul l'icone et le
 * petit "moduleHint" de couleur varient pour distinguer la page sans
 * casser l'unite chromatique.
 */
const SHARED_THEME = {
	accent: "#4f46e5",        // indigo-600
	accentDark: "#3730a3",    // indigo-800
	accentSoft: "rgba(79, 70, 229, 0.10)",
	gradFrom: "#1e293b",      // slate-800
	gradTo: "#4f46e5",        // indigo-600
	surfaceTint: "rgba(79, 70, 229, 0.04)",
	chartPalette: ["#4f46e5", "#10b981", "#f59e0b", "#06b6d4", "#ec4899", "#8b5cf6"],
};

const MODULE_ICONS = {
	stock: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 12l9 4 9-4"/><path d="M3 17l9 4 9-4"/></svg>',
	vente: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l5-5 4 4 8-9"/><path d="M14 7h7v7"/></svg>',
	achat: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="20" r="1.5"/><circle cx="17" cy="20" r="1.5"/><path d="M3 4h2l2.5 11.5a2 2 0 0 0 2 1.5h7a2 2 0 0 0 2-1.5L21 8H6"/></svg>',
};

const THEME_PRESETS = {
	stock: { key: "stock", ...SHARED_THEME, icon: MODULE_ICONS.stock },
	vente: { key: "vente", ...SHARED_THEME, icon: MODULE_ICONS.vente },
	achat: { key: "achat", ...SHARED_THEME, icon: MODULE_ICONS.achat },
};

// Priorite d'affichage des widgets dans la grille (KPI -> chart -> table -> reste).
const TYPE_ORDER = {
	number_card: 0,
	chart: 1,
	table: 2,
	ai_insight: 3,
	custom: 4,
};

function moduleNameToThemeKey(moduleName) {
	const value = String(moduleName || "").toLowerCase();
	if (value === "selling" || value === "ventes" || value === "vente") return "vente";
	if (value === "buying" || value === "achats" || value === "achat") return "achat";
	return "stock";
}

const TYPE_LABELS = {
	number_card: "Indicateur",
	chart: "Graphique",
	table: "Tableau",
	ai_insight: "Analyse IA",
	custom: "Bloc",
};

const TYPE_GLYPHS = {
	number_card: "Σ",
	chart: "▮▮▮",
	table: "▤",
	ai_insight: "✦",
	custom: "◇",
};

export default {
	name: "StockDashboardView",
	props: {
		page: { type: Object, default: null },
		moduleName: { type: String, default: "Stock" },
		moduleLabel: { type: String, default: "Stock" },
		pageTitle: { type: String, default: "" },
		workspaceHref: { type: String, default: "/app/stock?cd_skip=1" },
		themePreset: { type: [String, Object], default: "" },
	},
	data() {
		return {
			dashboard: null,
			loading: true,
			pageError: "",
			chartInstances: {},
			lastRefreshAt: null,
			activeFilters: {},
			filterBar: null,
		};
	},
	computed: {
		frappe() {
			return window.frappe;
		},
		resolvedModuleName() {
			return (this.moduleName || "Stock").trim() || "Stock";
		},
		resolvedModuleLabel() {
			return (this.moduleLabel || this.resolvedModuleName).trim() || this.resolvedModuleName;
		},
		resolvedPageTitle() {
			return (this.pageTitle || `Tableau de bord ${this.resolvedModuleLabel}`).trim();
		},
		disabledMessage() {
			return "Ce tableau de bord est actuellement désactivé par l'administrateur.";
		},
		themeKey() {
			const preset = this.themePreset;
			if (typeof preset === "string" && preset) return preset;
			if (preset && typeof preset === "object" && preset.key) return preset.key;
			return moduleNameToThemeKey(this.resolvedModuleName);
		},
		theme() {
			const preset = THEME_PRESETS[this.themeKey] || THEME_PRESETS.stock;
			if (this.themePreset && typeof this.themePreset === "object") {
				return { ...preset, ...this.themePreset };
			}
			return preset;
		},
		themeStyle() {
			const t = this.theme;
			return {
				"--sd-accent": t.accent,
				"--sd-accent-dark": t.accentDark,
				"--sd-accent-soft": t.accentSoft,
				"--sd-grad-from": t.gradFrom,
				"--sd-grad-to": t.gradTo,
				"--sd-surface-tint": t.surfaceTint,
			};
		},
		subtitle() {
			if (!this.dashboard) {
				return `Vue dédiée au module ${this.resolvedModuleLabel} — alimentée par custom_dashboard.`;
			}
			return `Tableau de bord publié par ${this.dashboard.user || "Administrator"}.`;
		},
		builderHref() {
			return "/app/dashboard-builder";
		},
		orderedItems() {
			if (!this.dashboard?.items) return [];
			// Tri principal : par type (KPI > chart > table > AI > custom).
			// Tri secondaire : par position d'origine du builder (y, x) pour stabilite.
			return [...this.dashboard.items].sort((a, b) => {
				const ta = TYPE_ORDER[this.itemType(a)] ?? 99;
				const tb = TYPE_ORDER[this.itemType(b)] ?? 99;
				if (ta !== tb) return ta - tb;
				if (a.y !== b.y) return a.y - b.y;
				return a.x - b.x;
			});
		},
		canvasRows() {
			const rows = this.orderedItems.map((item) => item.y + item.h);
			return Math.max(8, ...rows);
		},
		canvasStyle() {
			return {
				gridTemplateColumns: `repeat(${GRID_COLUMNS}, minmax(0, 1fr))`,
				gridAutoRows: `${GRID_ROW_HEIGHT}px`,
				gap: `${GRID_GAP}px`,
				minHeight: `${this.canvasRows * GRID_ROW_HEIGHT}px`,
			};
		},
		lastRefreshLabel() {
			if (!this.lastRefreshAt) return "";
			try {
				return new Date(this.lastRefreshAt).toLocaleTimeString("fr-FR", {
					hour: "2-digit",
					minute: "2-digit",
				});
			} catch {
				return "";
			}
		},
	},
	async mounted() {
		await this.setupFilterBar();
		await this.load();
	},
	beforeUnmount() {
		this.destroyCharts();
		if (this.filterBar?.destroy) this.filterBar.destroy();
		this.filterBar = null;
	},
	methods: {
		async setupFilterBar() {
			if (!this.$refs.filterBarHost) return;
			try {
				await this.frappe.require("dashboard_filters.bundle.js");
			} catch (error) {
				console.warn("[custom_dashboard] DashboardFilterBar bundle not loaded", error);
				return;
			}

			const FilterBar = window.custom_dashboard?.ui?.DashboardFilterBar;
			if (!FilterBar) return;

			if (this.filterBar?.destroy) this.filterBar.destroy();

			this.filterBar = new FilterBar({
				wrapper: this.$refs.filterBarHost,
				pageType: this.themeKey,
				onChange: (values) => {
					this.activeFilters = values || {};
				},
				onRefresh: async (values) => {
					this.activeFilters = values || {};
					await this.refreshAllItems();
					this.lastRefreshAt = Date.now();
				},
			});
			this.filterBar.render();
		},
		async load() {
			this.loading = true;
			this.pageError = "";
			try {
				const doc = await this.frappe.xcall(
					"custom_dashboard.api.dashboard.get_module_dashboard",
					{ module_name: this.resolvedModuleName }
				);
				this.dashboard = doc ? this.normalizeDashboard(doc) : null;
				if (this.dashboard && !this.dashboard.disabled) {
					await this.refreshAllItems();
				} else {
					this.destroyCharts();
				}
				this.lastRefreshAt = Date.now();
			} catch (error) {
				this.pageError = this.parseError(
					error,
					`Impossible de charger le tableau ${this.resolvedModuleLabel}.`
				);
			} finally {
				this.loading = false;
			}
		},
		async refresh() {
			await this.load();
		},
		normalizeDashboard(doc) {
			return {
				name: doc.name,
				title: doc.title,
				user: doc.user,
				module_name: doc.module_name,
				is_active: doc.is_active === undefined ? 1 : Number(doc.is_active),
				disabled: Boolean(doc.disabled),
				disabled_message: doc.disabled_message || "",
				items: (doc.items || []).map((item) => this.normalizeItem(item)),
			};
		},
		normalizeItem(item) {
			return {
				local_id: LOCAL_ID++,
				name: item.name,
				widget: item.widget,
				x: Number(item.x) || 0,
				y: Number(item.y) || 0,
				w: Number(item.w) || 6,
				h: Number(item.h) || 4,
				display_title: item.display_title || "",
				filters_json: item.filters_json || "",
				definition: item.widget_definition || null,
				preview: null,
				loading: false,
				error: "",
				aiRegenerating: false,
			};
		},
		async refreshAllItems() {
			if (!this.dashboard?.items?.length) {
				this.destroyCharts();
				return;
			}
			await Promise.all(this.dashboard.items.map((item) => this.refreshItem(item)));
			this.$nextTick(() => this.renderAllCharts());
		},
		async refreshItem(item) {
			item.loading = true;
			item.error = "";
			try {
				if (!item.definition) {
					item.definition = await this.frappe.xcall(
						"custom_dashboard.api.widget.get_widget_definition",
						{ widget_name: item.widget }
					);
				}
				if (!item.definition?.can_use) {
					item.preview = null;
					return;
				}
				// IMPORTANT : on n'envoie JAMAIS item.filters_json (configure dans le builder).
				// Les filtres actifs viennent UNIQUEMENT de la barre globale de la page finale.
				// Le serveur (normalize_filters) ne retient que les champs declares dans le
				// schema du widget = equivalent "supported_filters".
				item.preview = await this.frappe.xcall("custom_dashboard.api.widget.get_widget_data", {
					widget_name: item.widget,
					filters: JSON.stringify(this.activeFilters || {}),
				});
			} catch (error) {
				item.error = this.parseError(error, "Impossible de charger ce widget.");
			} finally {
				item.loading = false;
				this.$nextTick(() => this.renderAllCharts());
			}
		},
		gridItemStyle(item) {
			return {
				gridColumn: `${item.x + 1} / span ${item.w}`,
				gridRow: `${item.y + 1} / span ${item.h}`,
			};
		},
		itemType(item) {
			return item.preview?.type || item.definition?.widget_type || "custom";
		},
		itemPayload(item) {
			return item.preview?.data || {};
		},
		aiPayload(item) {
			return item.preview?.data || {};
		},
		widgetTypeLabel(item) {
			const type = this.itemType(item);
			return TYPE_LABELS[type] || type || "Bloc";
		},
		widgetGlyph(item) {
			const type = this.itemType(item);
			return TYPE_GLYPHS[type] || "◇";
		},
		isNumericColumn(column) {
			return ["Currency", "Int", "Float", "Percent"].includes(column.type);
		},
		severityLabel(value) {
			const v = String(value || "medium").toLowerCase();
			if (v === "high") return "Haute";
			if (v === "low") return "Faible";
			return "Moyenne";
		},
		formatGeneratedAt(item) {
			const ts = this.aiPayload(item).generated_at;
			if (!ts) return "";
			try {
				const d = new Date(ts);
				return d.toLocaleString("fr-FR", {
					hour: "2-digit",
					minute: "2-digit",
					day: "2-digit",
					month: "2-digit",
				});
			} catch {
				return ts;
			}
		},
		async regenerateAi(item) {
			if (item.aiRegenerating) return;
			item.aiRegenerating = true;
			item.error = "";
			try {
				// Filtres globaux uniquement (pas item.filters_json du builder).
				const filtersPayload = JSON.stringify({
					...(this.activeFilters || {}),
					force_refresh: 1,
				});
				item.preview = await this.frappe.xcall(
					"custom_dashboard.api.widget.get_widget_data",
					{ widget_name: item.widget, filters: filtersPayload }
				);
			} catch (error) {
				item.error = this.parseError(error, "Impossible de regenerer l'analyse.");
			} finally {
				item.aiRegenerating = false;
			}
		},
		formatNumberCardValue(item) {
			const payload = this.itemPayload(item);
			if (payload.currency) {
				return this.formatCurrency(payload.value, payload.currency);
			}
			return this.formatNumber(payload.value);
		},
		numberCardLabel(item) {
			const payload = this.itemPayload(item);
			return payload.label || item.display_title || item.definition?.title || item.widget;
		},
		numberCardSecondary(item) {
			const payload = this.itemPayload(item);
			if (payload.secondary_value === undefined || payload.secondary_value === null) {
				return "";
			}
			return `${this.formatNumber(payload.secondary_value)} ${payload.secondary_label || ""}`.trim();
		},
		getTableColumns(item) {
			const columns = this.itemPayload(item).columns || [];
			return columns.map((column, index) => {
				if (typeof column === "string") {
					return { key: column, label: column, type: "Data", index };
				}
				return {
					key: column.key || `col_${index}`,
					label: column.label || column.key || `Colonne ${index + 1}`,
					type: column.type || "Data",
					currency: column.currency || "",
					index,
				};
			});
		},
		getTableRows(item) {
			const rows = this.itemPayload(item).rows || [];
			const columns = this.getTableColumns(item);
			return rows.map((row) => {
				if (Array.isArray(row)) {
					const payload = {};
					for (const column of columns) {
						payload[column.key] = row[column.index];
					}
					return payload;
				}
				return row;
			});
		},
		formatTableCell(row, column) {
			const value = row[column.key];
			if (column.type === "Currency") {
				return this.formatCurrency(value, column.currency);
			}
			if (column.type === "Int") {
				return this.formatNumber(value);
			}
			return value ?? "";
		},
		chartSummaryLabel(item) {
			return this.itemPayload(item).summary?.label || "Aperçu du graphique";
		},
		chartSummaryValue(item) {
			const summary = this.itemPayload(item).summary || {};
			if (summary.currency) {
				return this.formatCurrency(summary.value, summary.currency);
			}
			return summary.value !== undefined ? this.formatNumber(summary.value) : "";
		},
		formatJson(value) {
			return JSON.stringify(value || {}, null, 2);
		},
		formatNumber(value) {
			return new Intl.NumberFormat("fr-FR", {
				maximumFractionDigits: 0,
			}).format(Number(value || 0));
		},
		formatCurrency(value, currency) {
			if (typeof window.format_currency === "function") {
				return window.format_currency(Number(value || 0), currency || "USD");
			}
			return new Intl.NumberFormat("fr-FR", {
				style: "currency",
				currency: currency || "USD",
				maximumFractionDigits: 0,
			}).format(Number(value || 0));
		},
		renderAllCharts() {
			for (const item of this.orderedItems) {
				if (this.itemType(item) === "chart") {
					this.renderChart(item);
				}
			}
		},
		renderChart(item) {
			const payload = this.itemPayload(item);
			const labels = Array.isArray(payload.labels) ? payload.labels : [];
			const datasets = Array.isArray(payload.datasets) ? payload.datasets : [];
			if (!labels.length || !datasets.length) {
				this.destroyChart(item.local_id);
				return;
			}
			const rawRef = this.$refs[`chart_${item.local_id}`];
			const element = Array.isArray(rawRef) ? rawRef[0] : rawRef;
			if (!element || !window.frappe?.Chart) return;
			this.destroyChart(item.local_id);
			element.innerHTML = "";
			const chartOptions = item.definition?.chart_options || {};
			const palette = payload.colors || chartOptions.colors || this.theme.chartPalette;
			this.chartInstances[item.local_id] = new window.frappe.Chart(element, {
				title: "",
				data: { labels, datasets },
				type: payload.chart_type || chartOptions.chart_type || "bar",
				height: chartOptions.height || 220,
				colors: palette,
				lineOptions: { regionFill: 1, spline: 1, hideDots: 0 },
				barOptions: { spaceRatio: 0.4, stacked: 0 },
				axisOptions: { xIsSeries: true, xAxisMode: "tick" },
				tooltipOptions: {
					formatTooltipX: (d) => d,
					formatTooltipY: (d) => this.formatNumber(d),
				},
			});
		},
		destroyChart(localId) {
			const chart = this.chartInstances[localId];
			if (chart?.destroy) chart.destroy();
			delete this.chartInstances[localId];
		},
		destroyCharts() {
			Object.keys(this.chartInstances).forEach((key) => this.destroyChart(Number(key)));
		},
		parseError(error, fallback) {
			if (error?._server_messages) {
				try {
					const messages = JSON.parse(error._server_messages);
					if (messages.length) {
						const first = JSON.parse(messages[0]);
						return first.message || fallback;
					}
				} catch {
					return fallback;
				}
			}
			return error?.message || fallback;
		},
	},
};
</script>

<style scoped>
.sd-shell {
	--sd-bg: #f3f5f7;
	--sd-panel: #ffffff;
	--sd-border: #e3e8ee;
	--sd-border-strong: #cdd5df;
	--sd-text: #0f172a;
	--sd-muted: #64748b;
	--sd-accent: #0f766e;
	--sd-accent-dark: #115e59;
	--sd-accent-soft: rgba(15, 118, 110, 0.10);
	--sd-grad-from: #0f766e;
	--sd-grad-to: #0ea5a4;
	--sd-surface-tint: rgba(15, 118, 110, 0.04);
	--sd-danger: #b42318;
	--sd-success: #15803d;
	color: var(--sd-text);
	background: var(--sd-bg);
	border-radius: 12px;
	padding: 14px 16px 22px;
	font-size: 13px;
}

/* ========== HERO HEADER ========== */
.sd-hero {
	position: relative;
	border-radius: 14px;
	padding: 18px 22px 16px;
	margin-bottom: 16px;
	color: #ffffff;
	overflow: hidden;
	isolation: isolate;
}
.sd-hero-bg {
	position: absolute;
	inset: 0;
	background: linear-gradient(135deg, var(--sd-grad-from), var(--sd-grad-to));
	z-index: -2;
}
.sd-hero-glow {
	position: absolute;
	right: -120px;
	top: -120px;
	width: 360px;
	height: 360px;
	background: radial-gradient(closest-side, rgba(255, 255, 255, 0.35), transparent 70%);
	z-index: -1;
	pointer-events: none;
}
.sd-hero::after {
	content: "";
	position: absolute;
	inset: 0;
	background-image:
		radial-gradient(rgba(255, 255, 255, 0.07) 1px, transparent 1px);
	background-size: 18px 18px;
	z-index: -1;
	opacity: 0.6;
	pointer-events: none;
}
.sd-hero-main {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 16px;
	flex-wrap: wrap;
}
.sd-hero-left {
	display: flex;
	gap: 14px;
	align-items: center;
	min-width: 0;
}
.sd-hero-icon {
	width: 44px;
	height: 44px;
	border-radius: 10px;
	background: rgba(255, 255, 255, 0.18);
	border: 1px solid rgba(255, 255, 255, 0.28);
	display: flex;
	align-items: center;
	justify-content: center;
	color: #fff;
	backdrop-filter: blur(4px);
	flex-shrink: 0;
}
.sd-hero-icon :deep(svg) { display: block; }
.sd-hero-titles { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.sd-hero-eyebrow {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 10.5px;
	color: rgba(255, 255, 255, 0.85);
	flex-wrap: wrap;
}
.sd-hero-tag {
	font-size: 10px;
	font-weight: 700;
	letter-spacing: 0.10em;
	text-transform: uppercase;
	padding: 2px 7px;
	border-radius: 4px;
	background: rgba(255, 255, 255, 0.18);
	border: 1px solid rgba(255, 255, 255, 0.25);
	color: #fff;
}
.sd-hero-dot { opacity: 0.5; }
.sd-hero-meta {
	font-weight: 500;
	letter-spacing: 0.02em;
}
.sd-hero-title {
	margin: 0;
	font-size: 20px;
	font-weight: 700;
	line-height: 1.2;
	letter-spacing: -0.01em;
	color: #fff;
}
.sd-hero-subtitle {
	margin: 0;
	color: rgba(255, 255, 255, 0.82);
	font-size: 12px;
	line-height: 1.4;
}

.sd-hero-actions { display: flex; gap: 6px; flex-wrap: wrap; flex-shrink: 0; }

.sd-btn {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	padding: 6px 12px;
	border-radius: 6px;
	font-size: 11.5px;
	font-weight: 500;
	line-height: 1.4;
	cursor: pointer;
	transition: transform 120ms ease, background 150ms ease, border-color 150ms ease, opacity 150ms ease;
	border: 1px solid transparent;
	text-decoration: none;
	white-space: nowrap;
}
.sd-btn:hover { transform: translateY(-1px); }
.sd-btn:disabled { opacity: 0.55; cursor: not-allowed; transform: none; }

.sd-btn-ghost {
	color: #fff;
	background: rgba(255, 255, 255, 0.10);
	border-color: rgba(255, 255, 255, 0.30);
}
.sd-btn-ghost:hover {
	background: rgba(255, 255, 255, 0.18);
	color: #fff;
	text-decoration: none;
}
.sd-btn-solid {
	color: var(--sd-accent-dark);
	background: #ffffff;
	border-color: rgba(255, 255, 255, 0.6);
	font-weight: 600;
	box-shadow: 0 4px 12px rgba(15, 23, 42, 0.10);
}
.sd-btn-solid:hover {
	background: #fff;
	color: var(--sd-accent-dark);
	text-decoration: none;
	box-shadow: 0 6px 16px rgba(15, 23, 42, 0.14);
}
.sd-btn-xs {
	padding: 3px 9px;
	font-size: 11px;
}
.sd-btn-icon {
	display: inline-block;
	font-size: 12px;
	line-height: 1;
}
.sd-btn-icon.is-spinning {
	animation: sd-spin 900ms linear infinite;
}
@keyframes sd-spin { to { transform: rotate(360deg); } }

/* ========== KPI STRIP ========== */
.sd-kpis {
	margin-top: 14px;
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
	gap: 10px;
}
.sd-kpi {
	background: rgba(255, 255, 255, 0.16);
	border: 1px solid rgba(255, 255, 255, 0.25);
	backdrop-filter: blur(6px);
	border-radius: 10px;
	padding: 10px 12px;
	display: flex;
	gap: 10px;
	align-items: center;
	color: #fff;
	animation: sd-rise 360ms ease both;
}
.sd-kpi-icon {
	width: 32px;
	height: 32px;
	border-radius: 8px;
	background: rgba(255, 255, 255, 0.20);
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 14px;
	flex-shrink: 0;
}
.sd-kpi-body { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.sd-kpi-label {
	font-size: 10px;
	font-weight: 600;
	letter-spacing: 0.05em;
	text-transform: uppercase;
	color: rgba(255, 255, 255, 0.85);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}
.sd-kpi-value {
	font-size: 18px;
	font-weight: 700;
	color: #fff;
	line-height: 1.1;
	letter-spacing: -0.01em;
}
.sd-kpi-secondary {
	font-size: 10.5px;
	color: rgba(255, 255, 255, 0.85);
	margin-top: 2px;
}

@keyframes sd-rise {
	from { opacity: 0; transform: translateY(6px); }
	to { opacity: 1; transform: translateY(0); }
}

/* ========== FILTER BAR HOST (le contenu est rendu par DashboardFilterBar) ========== */
.sd-filterbar-host {
	margin-bottom: 12px;
}
.sd-filterbar-host:empty {
	display: none;
}

/* ========== BANNER ========== */
.sd-banner {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 10px 14px;
	border-radius: 8px;
	margin-bottom: 12px;
	font-size: 12px;
	background: var(--sd-accent-soft);
	border: 1px solid var(--sd-border);
}
.sd-banner-icon {
	display: inline-flex;
	width: 20px;
	height: 20px;
	border-radius: 50%;
	background: rgba(180, 35, 24, 0.15);
	color: var(--sd-danger);
	font-weight: 700;
	align-items: center;
	justify-content: center;
	font-size: 11px;
	flex-shrink: 0;
}
.sd-banner.is-error {
	background: rgba(180, 35, 24, 0.06);
	border-color: rgba(180, 35, 24, 0.25);
	color: var(--sd-danger);
}

/* ========== EMPTY STATES ========== */
.sd-empty,
.sd-state {
	background: var(--sd-panel);
	border: 1px dashed var(--sd-border-strong);
	border-radius: 8px;
	padding: 18px;
	text-align: center;
	color: var(--sd-muted);
	font-size: 12px;
}
.sd-empty .btn,
.sd-empty .sd-btn { margin-top: 10px; }

.sd-empty-large {
	padding: 36px 24px;
}
.sd-empty-large h3 {
	margin: 12px 0 4px;
	font-size: 16px;
	font-weight: 600;
	color: var(--sd-text);
}
.sd-empty-large p {
	margin: 0 0 14px;
	color: var(--sd-muted);
	font-size: 13px;
}
.sd-empty-illustration {
	display: inline-flex;
	width: 56px;
	height: 56px;
	border-radius: 14px;
	background: var(--sd-accent-soft);
	color: var(--sd-accent);
	align-items: center;
	justify-content: center;
	font-size: 24px;
}
.sd-empty-large .sd-btn-solid {
	color: #fff;
	background: var(--sd-accent);
	border-color: var(--sd-accent);
}
.sd-empty-large .sd-btn-solid:hover {
	background: var(--sd-accent-dark);
	border-color: var(--sd-accent-dark);
	color: #fff;
}

/* ========== GRID ========== */
.sd-grid { display: grid; }
.sd-grid-skeleton {
	grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
	gap: 12px;
}

/* ========== CARDS ========== */
.sd-card {
	position: relative;
	background: var(--sd-panel);
	border: 1px solid var(--sd-border);
	border-radius: 10px;
	padding: 12px 14px;
	display: flex;
	flex-direction: column;
	overflow: hidden;
	box-shadow: 0 1px 0 rgba(15, 23, 42, 0.02), 0 4px 14px rgba(15, 23, 42, 0.04);
	transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
	animation: sd-rise 320ms ease both;
}
.sd-card:hover {
	transform: translateY(-1px);
	border-color: var(--sd-border-strong);
	box-shadow: 0 1px 0 rgba(15, 23, 42, 0.02), 0 10px 24px rgba(15, 23, 42, 0.08);
}
.sd-card-accent {
	position: absolute;
	top: 0;
	left: 0;
	right: 0;
	height: 3px;
	background: linear-gradient(90deg, var(--sd-grad-from), var(--sd-grad-to));
	opacity: 0.85;
	border-radius: 10px 10px 0 0;
}
.sd-card.is-loading { opacity: 0.85; }

.sd-card-head {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 8px;
	margin-bottom: 8px;
	padding: 4px 0 8px;
	border-bottom: 1px solid var(--sd-border);
}
.sd-card-head-titles { min-width: 0; flex: 1; }
.sd-card-head h3 {
	margin: 0 0 3px;
	font-size: 12.5px;
	font-weight: 600;
	color: var(--sd-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
	letter-spacing: -0.005em;
}
.sd-card-cat {
	margin: 0;
	display: flex;
	align-items: center;
	gap: 5px;
	font-size: 10.5px;
	color: var(--sd-muted);
}
.sd-card-cat-dot {
	display: inline-block;
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background: var(--sd-accent);
	opacity: 0.7;
}
.sd-card-cat-sep { opacity: 0.5; }
.sd-card-glyph {
	display: inline-flex;
	width: 24px;
	height: 24px;
	border-radius: 6px;
	background: var(--sd-accent-soft);
	color: var(--sd-accent);
	align-items: center;
	justify-content: center;
	font-size: 11px;
	font-weight: 700;
	flex-shrink: 0;
}

.sd-card-body {
	flex: 1;
	min-height: 0;
	overflow: auto;
}

/* ========== NUMBER CARD ========== */
.sd-number-card {
	display: flex;
	flex-direction: column;
	gap: 3px;
	height: 100%;
	justify-content: center;
	padding: 4px 0;
}
.sd-number-value {
	font-size: 26px;
	font-weight: 700;
	line-height: 1.05;
	color: var(--sd-text);
	letter-spacing: -0.02em;
	background: linear-gradient(135deg, var(--sd-text), var(--sd-accent-dark));
	-webkit-background-clip: text;
	background-clip: text;
	-webkit-text-fill-color: transparent;
}
.sd-number-label {
	color: var(--sd-muted);
	font-size: 11px;
	line-height: 1.3;
	margin-top: 2px;
}
.sd-number-secondary {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	color: var(--sd-success);
	font-size: 11px;
	font-weight: 600;
	margin-top: 4px;
	padding: 2px 7px;
	background: rgba(21, 128, 61, 0.10);
	border-radius: 12px;
	align-self: flex-start;
}
.sd-number-trend { font-size: 9px; }

.sd-context {
	display: block;
	color: var(--sd-muted);
	margin-bottom: 4px;
	font-size: 10px;
	font-style: italic;
}

/* ========== TABLE ========== */
.sd-table-wrap { display: flex; flex-direction: column; height: 100%; }
.sd-table-scroll { overflow: auto; flex: 1; }
.sd-table {
	font-size: 11.5px;
	margin-bottom: 0;
	border-collapse: separate;
	border-spacing: 0;
	width: 100%;
}
.sd-table th {
	background: linear-gradient(180deg, #f8fafc, #f1f5f9);
	color: var(--sd-muted);
	font-weight: 600;
	font-size: 10px;
	text-transform: uppercase;
	letter-spacing: 0.05em;
	padding: 7px 9px;
	position: sticky;
	top: 0;
	border-bottom: 1px solid var(--sd-border);
	z-index: 1;
}
.sd-table td {
	padding: 6px 9px;
	border-bottom: 1px solid var(--sd-border);
	color: var(--sd-text);
}
.sd-table tbody tr:nth-child(even) td {
	background: var(--sd-surface-tint);
}
.sd-table tbody tr:hover td {
	background: var(--sd-accent-soft);
}
.sd-table tbody tr:last-child td { border-bottom: 0; }
.sd-table th.is-numeric,
.sd-table td.is-numeric {
	text-align: right;
	font-variant-numeric: tabular-nums;
}

/* ========== CHART ========== */
.sd-chart { display: flex; flex-direction: column; height: 100%; gap: 4px; }
.sd-chart-headline {
	display: flex;
	justify-content: space-between;
	align-items: baseline;
	margin-bottom: 6px;
	gap: 8px;
	padding-bottom: 6px;
	border-bottom: 1px dashed var(--sd-border);
}
.sd-chart-headline strong {
	display: block;
	font-size: 10px;
	color: var(--sd-muted);
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.05em;
}
.sd-chart-headline span {
	color: var(--sd-text);
	font-size: 16px;
	font-weight: 700;
	letter-spacing: -0.01em;
}
.sd-chart-host {
	width: 100%;
	flex: 1;
	min-height: 120px;
}
.sd-chart-host :deep(.frappe-chart) { width: 100% !important; }
.sd-chart-host :deep(.chart-container) { width: 100% !important; }

/* ========== INLINE ERROR ========== */
.sd-inline-error {
	display: flex;
	align-items: center;
	gap: 6px;
	color: var(--sd-danger);
	font-size: 11.5px;
	background: rgba(180, 35, 24, 0.06);
	border: 1px solid rgba(180, 35, 24, 0.18);
	padding: 8px 10px;
	border-radius: 6px;
}
.sd-inline-error-icon {
	display: inline-flex;
	width: 18px;
	height: 18px;
	border-radius: 50%;
	background: rgba(180, 35, 24, 0.15);
	color: var(--sd-danger);
	font-weight: 700;
	align-items: center;
	justify-content: center;
	font-size: 10px;
	flex-shrink: 0;
}

.sd-custom pre {
	margin: 0;
	font-size: 10px;
	white-space: pre-wrap;
	word-break: break-word;
	background: #f8fafc;
	border: 1px solid var(--sd-border);
	border-radius: 4px;
	padding: 8px;
}

/* ========== AI INSIGHT ========== */
.sd-ai {
	display: flex;
	flex-direction: column;
	gap: 8px;
	height: 100%;
}
.sd-ai-summary {
	margin: 0;
	background: var(--sd-accent-soft);
	border: 1px solid var(--sd-border);
	border-left: 3px solid var(--sd-accent);
	padding: 10px 12px;
	border-radius: 6px;
	font-size: 12.5px;
	line-height: 1.5;
	color: var(--sd-text);
}
.sd-ai-section h4 {
	margin: 0 0 4px;
	font-size: 10px;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 0.06em;
	color: var(--sd-muted);
}
.sd-ai-empty {
	font-size: 11px;
	color: var(--sd-muted);
	font-style: italic;
}
.sd-ai-list {
	margin: 0;
	padding: 0;
	list-style: none;
	display: flex;
	flex-direction: column;
	gap: 4px;
}
.sd-ai-item {
	background: #fbfcfd;
	border: 1px solid var(--sd-border);
	border-radius: 6px;
	padding: 7px 10px;
	border-left-width: 3px;
	transition: background 150ms ease;
}
.sd-ai-item:hover { background: #f8fafc; }
.sd-ai-item.sev-high { border-left-color: var(--sd-danger); }
.sd-ai-item.sev-medium { border-left-color: #d97706; }
.sd-ai-item.sev-low { border-left-color: var(--sd-accent); }
.sd-ai-item-head {
	display: flex;
	align-items: center;
	gap: 6px;
	margin-bottom: 2px;
}
.sd-ai-item-head strong { font-size: 12px; font-weight: 600; }
.sd-ai-item p {
	margin: 0;
	font-size: 11px;
	color: var(--sd-muted);
	line-height: 1.4;
}
.sd-ai-badge {
	font-size: 9px;
	font-weight: 700;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	padding: 2px 6px;
	border-radius: 3px;
	background: var(--sd-accent-soft);
	color: var(--sd-accent);
}
.sd-ai-item.sev-high .sd-ai-badge { background: rgba(180, 35, 24, 0.12); color: var(--sd-danger); }
.sd-ai-item.sev-medium .sd-ai-badge { background: rgba(217, 119, 6, 0.12); color: #b45309; }
.sd-ai-footer {
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 6px;
	margin-top: auto;
	padding-top: 8px;
	border-top: 1px dashed var(--sd-border);
}
.sd-ai-footer .sd-btn-ghost {
	color: var(--sd-accent);
	background: var(--sd-accent-soft);
	border-color: transparent;
}
.sd-ai-footer .sd-btn-ghost:hover {
	background: var(--sd-accent);
	color: #fff;
}
.sd-ai-footer small {
	color: var(--sd-muted);
	font-size: 10px;
}

/* ========== SKELETONS ========== */
.sd-skel-card {
	background: var(--sd-panel);
	border: 1px solid var(--sd-border);
	border-radius: 10px;
	padding: 14px;
	min-height: 140px;
	display: flex;
	flex-direction: column;
	gap: 8px;
}
.sd-skel-body {
	display: flex;
	flex-direction: column;
	gap: 8px;
	padding: 4px 0;
}
.sd-skel-line {
	height: 12px;
	width: 100%;
	border-radius: 4px;
	background: linear-gradient(90deg, #eef1f5 0%, #f8fafc 50%, #eef1f5 100%);
	background-size: 200% 100%;
	animation: sd-shimmer 1400ms ease-in-out infinite;
}
.sd-skel-line.short { width: 40%; }
.sd-skel-line.tall { height: 32px; }
@keyframes sd-shimmer {
	0% { background-position: 200% 0; }
	100% { background-position: -200% 0; }
}

/* ========== RESPONSIVE ========== */
@media (max-width: 720px) {
	.sd-hero { padding: 14px; }
	.sd-hero-main { flex-direction: column; }
	.sd-hero-actions { width: 100%; }
	.sd-hero-title { font-size: 17px; }
	.sd-kpis { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 480px) {
	.sd-kpis { grid-template-columns: 1fr; }
}
</style>
