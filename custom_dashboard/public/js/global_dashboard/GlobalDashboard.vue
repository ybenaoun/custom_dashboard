<template>
	<div class="gdx-root" :data-theme="theme">
		<!-- Hero with filters -->
		<header class="gdx-hero">
			<div class="gdx-hero-bg" aria-hidden="true"></div>
			<div class="gdx-hero-grid" aria-hidden="true"></div>
			<div class="gdx-hero-glow" aria-hidden="true"></div>

			<div class="gdx-hero-row">
				<div class="gdx-hero-left">
					<div class="gdx-hero-icon">
						<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
							<polyline points="3 17 9 11 13 15 21 7" />
							<polyline points="14 7 21 7 21 14" />
						</svg>
					</div>
					<div class="gdx-hero-text">
						<span class="gdx-hero-tag">{{ __("Vue d'ensemble") }}</span>
						<h1 class="gdx-hero-title">{{ __("Tableau de bord global") }}</h1>
						<p class="gdx-hero-sub">
							<span v-if="data && data.filters && data.filters.range_label">
								{{ data.filters.range_label }}
							</span>
							<span v-else>{{ __("Activité multi-modules en temps réel") }}</span>
							<span v-if="data && data.generated_at" class="gdx-hero-time">
								· {{ __("MAJ") }} {{ data.generated_at }}
							</span>
						</p>
					</div>
				</div>

				<div class="gdx-hero-actions">
					<div class="gdx-filter">
						<label>{{ __("Période") }}</label>
						<select v-model="filters.period" @change="reload">
							<option v-for="p in periods" :key="p" :value="p">{{ p }}</option>
						</select>
					</div>
					<div class="gdx-filter">
						<label>{{ __("Société") }}</label>
						<select v-model="filters.company" @change="reload">
							<option value="">{{ __("Toutes") }}</option>
							<option v-for="c in companies" :key="c" :value="c">{{ c }}</option>
						</select>
					</div>
					<button class="gdx-btn-glass" @click="reload" :disabled="loading">
						<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :class="{ 'gdx-spin': loading }">
							<path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
							<path d="M21 3v5h-5" />
							<path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
							<path d="M3 21v-5h5" />
						</svg>
						{{ __("Actualiser") }}
					</button>
					<button
						v-if="data && data.config && data.config.can_export"
						class="gdx-btn-primary"
						@click="openReport"
					>
						<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
							<polyline points="14 2 14 8 20 8" />
						</svg>
						{{ __("Rapport KPI") }}
					</button>
					<button
						class="gdx-btn-glass"
						:title="__('Ouvre le constructeur de tableaux de bord (Stock, Vente, Achat).')"
						@click="openDashboardBuilder"
					>
						<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<rect x="3" y="3" width="7" height="9" rx="1" />
							<rect x="14" y="3" width="7" height="5" rx="1" />
							<rect x="14" y="12" width="7" height="9" rx="1" />
							<rect x="3" y="16" width="7" height="5" rx="1" />
						</svg>
						{{ __("Personnaliser dans le constructeur") }}
					</button>
				</div>
			</div>
		</header>

		<!-- Loading skeleton -->
		<div v-if="loading && !data" class="gdx-loading">
			<div class="gdx-skeleton-strip">
				<div v-for="i in 5" :key="i" class="gdx-skel-card"></div>
			</div>
			<div class="gdx-skeleton-grid">
				<div v-for="i in 4" :key="i" class="gdx-skel-large"></div>
			</div>
		</div>

		<!-- Error state -->
		<div v-else-if="errorMessage" class="gdx-error-state">
			<svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
				<circle cx="12" cy="12" r="10" />
				<line x1="12" y1="8" x2="12" y2="12" />
				<line x1="12" y1="16" x2="12.01" y2="16" />
			</svg>
			<h4>{{ __("Impossible de charger le tableau de bord") }}</h4>
			<p>{{ errorMessage }}</p>
			<button class="gdx-btn-glass" @click="reload">{{ __("Réessayer") }}</button>
		</div>

		<template v-else-if="data">
			<!-- Summary cards strip -->
			<section class="gdx-section">
				<div class="gdx-section-head">
					<h5>{{ __("Synthèse multi-modules") }}</h5>
					<span class="gdx-section-line"></span>
				</div>
				<SummaryStrip :cards="data.summary_cards || []" />
			</section>

			<!-- Overview charts (donut + bar + line) -->
			<section v-if="hasOverview" class="gdx-section">
				<div class="gdx-section-head">
					<h5>{{ __("Analytique transversale") }}</h5>
					<span class="gdx-section-line"></span>
				</div>
				<div class="gdx-overview-grid">
					<div class="gdx-overview-card">
						<div class="gdx-overview-head">
							<h6>{{ __("Répartition activité") }}</h6>
							<span class="gdx-tag gdx-tag-donut">donut</span>
							<button class="gdx-ai-btn-sm" @click="runAi('donut')" :disabled="aiBusy.donut">
								<span v-if="aiBusy.donut" class="gdx-ai-spinner"></span>
								<span v-else>✦</span>
							</button>
						</div>
						<ChartBlock
							:data="donutData"
							type="donut"
							:colors="moduleColors"
							:height="240"
						/>
						<AiPanel
							:visible="!!aiResults.donut"
							:title="__('Répartition activité')"
							:result="aiResults.donut"
							@close="aiResults.donut = null"
						/>
					</div>

					<div class="gdx-overview-card">
						<div class="gdx-overview-head">
							<h6>{{ __("Activité cumulée par module") }}</h6>
							<span class="gdx-tag gdx-tag-bar">bar</span>
							<button class="gdx-ai-btn-sm" @click="runAi('bar')" :disabled="aiBusy.bar">
								<span v-if="aiBusy.bar" class="gdx-ai-spinner"></span>
								<span v-else>✦</span>
							</button>
						</div>
						<ChartBlock
							:data="barData"
							type="bar"
							:colors="moduleColors"
							:height="240"
						/>
						<AiPanel
							:visible="!!aiResults.bar"
							:title="__('Activité par module')"
							:result="aiResults.bar"
							@close="aiResults.bar = null"
						/>
					</div>

					<div class="gdx-overview-card gdx-overview-wide">
						<div class="gdx-overview-head">
							<h6>{{ __("Tendances croisées") }}</h6>
							<span class="gdx-tag gdx-tag-line">line</span>
							<button class="gdx-ai-btn-sm" @click="runAi('line')" :disabled="aiBusy.line">
								<span v-if="aiBusy.line" class="gdx-ai-spinner"></span>
								<span v-else>✦</span>
							</button>
						</div>
						<ChartBlock
							:data="lineData"
							type="axis-mixed"
							:colors="moduleColors"
							:height="260"
						/>
						<AiPanel
							:visible="!!aiResults.line"
							:title="__('Tendances croisées')"
							:result="aiResults.line"
							@close="aiResults.line = null"
						/>
					</div>
				</div>
			</section>

			<!-- Main revenue chart -->
			<section v-if="data.chart && data.chart.data" class="gdx-section">
				<div class="gdx-section-head">
					<h5>{{ __("Évolution sur 12 mois") }}</h5>
					<span class="gdx-section-line"></span>
				</div>
				<div class="gdx-overview-card">
					<div class="gdx-overview-head">
						<h6>{{ __("Chiffre d'affaires mensuel") }}</h6>
						<span class="gdx-tag gdx-tag-bar">{{ data.chart.type || "bar" }}</span>
						<button class="gdx-ai-btn-sm" @click="runAi('main')" :disabled="aiBusy.main">
							<span v-if="aiBusy.main" class="gdx-ai-spinner"></span>
							<span v-else>✦</span>
						</button>
					</div>
						<ChartBlock
							:data="data.chart.data"
							:type="data.chart.type || 'bar'"
							:colors="data.chart.colors || ['#1B84FF']"
							:height="data.chart.height || 220"
						/>
						<AiPanel
							:visible="!!aiResults.main"
							:title="__('Chiffre d\'affaires')"
							:result="aiResults.main"
							@close="aiResults.main = null"
						/>
				</div>
			</section>

			<!-- Module cards -->
			<section v-if="(data.modules || []).length" class="gdx-section">
				<div class="gdx-section-head">
					<h5>{{ __("Détail par module") }}</h5>
					<span class="gdx-section-line"></span>
				</div>
				<div class="gdx-modules-grid">
					<ModuleCard
						v-for="(mod, idx) in data.modules"
						:key="mod.label"
						:module="mod"
						:chart-type="trendTypes[idx % trendTypes.length]"
						:ai-visible="!!aiResults['module-' + idx]"
						:ai-loading="!!aiBusy['module-' + idx]"
						:ai-result="aiResults['module-' + idx]"
						@analyze="runAi('module-' + idx, idx)"
						@close-ai="aiResults['module-' + idx] = null"
					/>
				</div>
			</section>
		</template>
	</div>
</template>

<script>
import { ref, reactive, onMounted, onBeforeUnmount, computed } from "vue";
import SummaryStrip from "./SummaryStrip.vue";
import ChartBlock from "./ChartBlock.vue";
import ModuleCard from "./ModuleCard.vue";
import AiPanel from "./AiPanel.vue";

const PERIODS = ["Aujourd'hui", "Cette semaine", "Ce mois", "Ce trimestre", "Cette année"];
const TREND_TYPES = ["line", "bar", "line", "bar", "bar"];

export default {
	name: "GlobalDashboard",
	components: { SummaryStrip, ChartBlock, ModuleCard, AiPanel },
	setup() {
		const data = ref(null);
		const loading = ref(false);
		const errorMessage = ref("");
		const theme = ref(document.documentElement.getAttribute("data-theme") || "light");
		const filters = reactive({ period: "Ce mois", company: "" });
		const companies = ref([]);
		const aiBusy = reactive({});
		const aiResults = reactive({});

		async function fetchCompanies() {
			try {
				const r = await frappe.db.get_list("Company", { fields: ["name"], limit: 50 });
				companies.value = (r || []).map((c) => c.name);
			} catch (e) {
				companies.value = [];
			}
		}

		async function fetchData() {
			loading.value = true;
			errorMessage.value = "";
			try {
				const r = await frappe.xcall(
					"custom_dashboard.custom_dashboard.page.global_dashboard.global_dashboard.get_dashboard_data",
					{ period: filters.period, company: filters.company || null }
				);
				data.value = r;
				if (r && r.filters) {
					if (r.filters.period) filters.period = r.filters.period;
				}
			} catch (e) {
				console.error(e);
				errorMessage.value = extractErrorMsg(e);
				data.value = null;
			} finally {
				loading.value = false;
			}
		}

		function extractErrorMsg(error) {
			if (typeof error === "string") return error;
			if (error?.message) return error.message;
			if (error?._server_messages) {
				try {
					const msgs = JSON.parse(error._server_messages);
					if (msgs?.length) {
						try {
							return JSON.parse(msgs[0]).message || msgs[0];
						} catch (e2) {
							return msgs[0];
						}
					}
				} catch (e3) {
					return error._server_messages;
				}
			}
			return __("Erreur inconnue lors du chargement.");
		}

		onMounted(() => {
			fetchCompanies();
			fetchData();
		});

		const obs = new MutationObserver(() => {
			theme.value = document.documentElement.getAttribute("data-theme") || "light";
		});
		obs.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ["data-theme"],
		});
		onBeforeUnmount(() => obs.disconnect());

		const moduleColors = computed(() =>
			(data.value?.modules || []).map((m) => m.color || "#1B84FF")
		);

		const moduleTotals = computed(() =>
			(data.value?.modules || []).map((m) => {
				const values = (m.trend?.values || []);
				return values.reduce((s, v) => s + Number(v || 0), 0);
			})
		);

		const hasOverview = computed(() => moduleTotals.value.some((t) => t > 0));

		const donutData = computed(() => {
			const mods = data.value?.modules || [];
			const active = mods
				.map((m, i) => ({ label: m.label, total: moduleTotals.value[i] }))
				.filter((d) => d.total > 0);
			return {
				labels: active.map((d) => d.label),
				datasets: [{ values: active.map((d) => d.total) }],
			};
		});

		const barData = computed(() => {
			const mods = data.value?.modules || [];
			const active = mods
				.map((m, i) => ({ label: m.label, total: moduleTotals.value[i] }))
				.filter((d) => d.total > 0);
			return {
				labels: active.map((d) => d.label),
				datasets: [{ name: __("Total"), values: active.map((d) => d.total) }],
			};
		});

		const lineData = computed(() => {
			const mods = data.value?.modules || [];
			const seen = new Set();
			const allLabels = [];
			mods.forEach((m) => {
				(m.trend?.labels || []).forEach((l) => {
					if (!seen.has(l)) {
						seen.add(l);
						allLabels.push(l);
					}
				});
			});
			const datasets = mods.map((m) => {
				const map = {};
				(m.trend?.labels || []).forEach((l, i) => {
					map[l] = (m.trend?.values || [])[i] || 0;
				});
				return {
					name: m.label,
					values: allLabels.map((l) => map[l] || 0),
					chartType: "line",
				};
			});
			return { labels: allLabels, datasets };
		});

		async function runAi(key, moduleIndex) {
			aiBusy[key] = true;
			try {
				let chartMeta;
				if (key === "donut") {
					chartMeta = {
						title: __("Répartition activité par module"),
						type: "donut",
						labels: donutData.value.labels,
						datasets: donutData.value.datasets,
					};
				} else if (key === "bar") {
					chartMeta = {
						title: __("Activité cumulée par module"),
						type: "bar",
						labels: barData.value.labels,
						datasets: barData.value.datasets,
					};
				} else if (key === "line") {
					chartMeta = {
						title: __("Tendances croisées des modules"),
						type: "line",
						labels: lineData.value.labels,
						datasets: lineData.value.datasets,
					};
					} else if (key === "main" && data.value?.chart) {
						chartMeta = {
							title: __("Chiffre d'affaires 12 mois"),
							type: data.value.chart.type || "bar",
							labels: data.value.chart.data?.labels || [],
							datasets: data.value.chart.data?.datasets || [],
						};
					} else if (key.startsWith("module-")) {
						const m = data.value?.modules?.[moduleIndex];
						if (!m) return;
						chartMeta = {
							title: `${m.label} — ${__("Tendance")}`,
							type: TREND_TYPES[moduleIndex % TREND_TYPES.length],
							labels: m.trend?.labels || [],
							datasets: [{ name: m.label, values: m.trend?.values || [] }],
						};
					}
				if (!chartMeta) return;

				const filtersInfo = data.value?.filters || {};
				const result = await frappe.xcall(
					"custom_dashboard.custom_dashboard.page.global_dashboard.global_dashboard.analyze_with_ai",
					{
						chart_title: chartMeta.title,
						chart_type: chartMeta.type,
						labels: JSON.stringify(chartMeta.labels),
						datasets: JSON.stringify(chartMeta.datasets),
						filters: JSON.stringify(filtersInfo),
						period: filtersInfo.range_label || "",
					}
				);
				aiResults[key] = result;
			} catch (e) {
				frappe.msgprint({
					title: __("Erreur IA"),
					message: extractErrorMsg(e),
					indicator: "red",
				});
			} finally {
				aiBusy[key] = false;
			}
		}

		function reload() {
			fetchData();
		}

		function openReport() {
			const r = data.value?.report_route;
			if (!r || !r.path) return;
			if (r.route_options) frappe.route_options = r.route_options;
			frappe.set_route(r.path);
		}

		function openDashboardBuilder() {
			// Le constructeur ne prend en charge que Stock / Vente / Achat.
			// On passe la source à la fois via `frappe.route_options` (router Frappe)
			// et via la query string pour fiabilité.
			try {
				if (window.frappe) {
					frappe.route_options = Object.assign({}, frappe.route_options || {}, {
						source: "global",
					});
				}
				if (window.frappe?.set_route) {
					frappe.set_route("dashboard-builder");
					return;
				}
			} catch (e) {
				// fallback ci-dessous
			}
			window.location.href = "/app/dashboard-builder?source=global";
		}

		return {
			data,
			loading,
			errorMessage,
			theme,
			filters,
			companies,
			periods: PERIODS,
			trendTypes: TREND_TYPES,
			moduleColors,
			hasOverview,
			donutData,
			barData,
			lineData,
			aiBusy,
			aiResults,
			reload,
			openReport,
			openDashboardBuilder,
			runAi,
		};
	},
};
</script>
