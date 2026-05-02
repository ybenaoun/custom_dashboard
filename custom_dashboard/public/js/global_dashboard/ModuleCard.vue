<template>
	<article class="gdx-module gdx-module-compact" :style="{ '--mod-color': module.color || '#1B84FF' }">
		<div class="gdx-module-bar"></div>

		<header class="gdx-module-head">
			<div class="gdx-module-titles">
				<div class="gdx-module-tag-row">
					<span class="gdx-module-tag">
						<span class="gdx-module-dot"></span>
						{{ module.label }}
					</span>
					<span class="gdx-module-pill" :class="isCustomizable ? 'is-custom' : 'is-readonly'">
						{{ isCustomizable ? __("Personnalisable") : __("Consultation") }}
					</span>
				</div>
				<div class="gdx-module-value">{{ primaryMetric.formatted_value || "0" }}</div>
			</div>
			<div class="gdx-module-actions">
				<button
					class="gdx-ai-btn-sm gdx-module-ai"
					:disabled="aiLoading"
					:title="__('Analyse IA')"
					@click="$emit('analyze')"
				>
					<span v-if="aiLoading" class="gdx-ai-spinner"></span>
					<span v-else>✦</span>
				</button>
				<button
					v-if="primaryMetric.route"
					class="gdx-route-btn"
					@click="open(primaryMetric.route)"
				>
					{{ __("Détail") }}
					<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<line x1="5" y1="12" x2="19" y2="12" />
						<polyline points="12 5 19 12 12 19" />
					</svg>
				</button>
			</div>
		</header>

		<!-- Mini-courbes uniquement (max 4) -->
		<div v-if="miniCharts.length" class="gdx-mini-charts">
			<div
				v-for="chart in miniCharts"
				:key="chart.key"
				class="gdx-mini-chart"
			>
				<div class="gdx-mini-chart-head">
					<span class="gdx-mini-chart-label">{{ chart.label }}</span>
				</div>
				<MiniSparkline
					:values="chart.values"
					:type="chart.type"
					:color="module.color || '#1B84FF'"
					:height="56"
				/>
			</div>
		</div>
		<div v-else class="gdx-mini-charts-empty">
			{{ __("Aucune tendance disponible pour cette période.") }}
		</div>

		<AiPanel
			:visible="aiVisible"
			:title="module.label"
			:result="aiResult"
			@close="$emit('close-ai')"
		/>
	</article>
</template>

<script>
import MiniSparkline from "./MiniSparkline.vue";
import AiPanel from "./AiPanel.vue";

const MAX_CHARTS = 4;
const MAX_POINTS = 16;

// Downsampling uniforme : conserve premier/dernier, ramène à au plus MAX_POINTS.
function downsample(values) {
	const n = values?.length || 0;
	if (n <= MAX_POINTS) return values || [];
	const step = (n - 1) / (MAX_POINTS - 1);
	const out = [];
	for (let i = 0; i < MAX_POINTS; i++) {
		out.push(values[Math.round(i * step)]);
	}
	return out;
}

export default {
	name: "ModuleCard",
	components: { MiniSparkline, AiPanel },
	props: {
		module: { type: Object, required: true },
		chartType: { type: String, default: "line" },
		aiVisible: Boolean,
		aiLoading: Boolean,
		aiResult: Object,
	},
	emits: ["analyze", "close-ai"],
	computed: {
		primaryMetric() {
			return this.module.primary_metric || {};
		},
		isCustomizable() {
			return Boolean(this.module.is_customizable);
		},
		miniCharts() {
			const trends = this.module.trends;
			const out = [];
			const buildEntry = (key, series, fallbackType) => {
				const values = series?.values || [];
				if (!values.length) return null;
				const total = values.reduce((s, v) => s + Number(v || 0), 0);
				if (total === 0) return null;
				return {
					key,
					label: series?.label || key,
					type: series?.type || fallbackType || this.chartType,
					values: downsample(values),
				};
			};
			if (trends && typeof trends === "object") {
				for (const [key, series] of Object.entries(trends)) {
					const entry = buildEntry(key, series);
					if (entry) out.push(entry);
					if (out.length >= MAX_CHARTS) break;
				}
			}
			if (!out.length) {
				const entry = buildEntry("default", this.module.trend, this.chartType);
				if (entry) out.push(entry);
			}
			return out;
		},
	},
	methods: {
		open(route) {
			if (!route || !route.path) return;
			if (route.route_options) frappe.route_options = route.route_options;
			frappe.set_route(route.path);
		},
	},
};
</script>
