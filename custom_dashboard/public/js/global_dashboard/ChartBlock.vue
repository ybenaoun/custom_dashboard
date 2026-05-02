<template>
	<div class="gdx-chart-block">
		<div v-if="isEmpty" class="gdx-chart-empty" :style="{ minHeight: height + 'px' }">
			<svg
				viewBox="0 0 24 24"
				width="28"
				height="28"
				fill="none"
				stroke="currentColor"
				stroke-width="1.5"
				stroke-linecap="round"
				stroke-linejoin="round"
			>
				<path d="M3 3v18h18" />
				<path d="M7 14l4-4 4 4 5-5" />
			</svg>
			<span>{{ emptyText || __("Aucune donnée") }}</span>
		</div>
		<div v-show="!isEmpty" ref="containerRef" class="gdx-chart-canvas"></div>
	</div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from "vue";

export default {
	name: "ChartBlock",
	props: {
		data: { type: Object, required: true },
		type: { type: String, default: "line" },
		colors: { type: Array, default: () => ["#1B84FF"] },
		height: { type: Number, default: 220 },
		fill: { type: Boolean, default: false },
		emptyText: String,
		// Mode sparkline : axes/légende/grille masqués pour mini-courbes.
		mini: { type: Boolean, default: false },
	},
	setup(props) {
		const containerRef = ref(null);
		let chart = null;

		const isEmpty = computed(() => {
			if (!props.data || !props.data.labels || !props.data.labels.length) return true;
			const datasets = props.data.datasets || [];
			if (!datasets.length) return true;
			const total = datasets.reduce(
				(acc, ds) =>
					acc + (ds.values || []).reduce((s, v) => s + Number(v || 0), 0),
				0
			);
			return total === 0;
		});

		function destroy() {
			if (containerRef.value) containerRef.value.innerHTML = "";
			chart = null;
		}

		function render() {
			if (!containerRef.value || isEmpty.value) {
				destroy();
				return;
			}
			destroy();

			const opts = {
				data: props.data,
				type: props.type,
				height: props.height,
				colors: props.colors,
				truncateLegends: 1,
				animate: 1,
				tooltipOptions: {
					formatTooltipY: (d) => (d != null ? String(d) : ""),
				},
			};
			if (props.type === "line" || props.type === "axis-mixed") {
				opts.lineOptions = {
					regionFill: props.fill ? 1 : 0,
					hideDots: props.mini || (props.data.labels || []).length > 12 ? 1 : 0,
					tension: 0.4,
					spline: 1,
				};
				opts.axisOptions = { xIsSeries: true, xAxisMode: "tick" };
			}
			if (props.type === "bar") {
				opts.barOptions = { spaceRatio: 0.4, stacked: 0 };
				opts.axisOptions = { xAxisMode: "tick" };
			}
			if (props.type === "donut" || props.type === "pie") {
				opts.maxSlices = 8;
			}
			// Mode sparkline : pas de Y-axis ticks, pas d'animation parasite,
			// pas de region pour les bars. Les masques visuels restants sont CSS.
			if (props.mini) {
				opts.animate = 0;
				opts.axisOptions = Object.assign({}, opts.axisOptions, {
					yAxisMode: "",
					xAxisMode: "tick",
				});
				if (opts.lineOptions) {
					opts.lineOptions.dotSize = 0;
				}
				if (opts.barOptions) {
					opts.barOptions.spaceRatio = 0.2;
				}
			}
			try {
				chart = new frappe.Chart(containerRef.value, opts);
			} catch (e) {
				console.error("ChartBlock render error", e);
			}
		}

		onMounted(() => nextTick(render));
		onBeforeUnmount(destroy);
		watch(() => props.data, () => nextTick(render), { deep: true });
		watch(() => [props.type, props.height, props.fill], () => nextTick(render));
		watch(() => props.colors, () => nextTick(render), { deep: true });

		return { containerRef, isEmpty };
	},
};
</script>
