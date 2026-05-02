<template>
	<div class="adx-chart">
		<div class="adx-chart-head">
			<h6>{{ title }}</h6>
			<span class="adx-chart-tag" :class="'adx-tag-' + subtitle">{{ subtitle }}</span>
		</div>
		<div class="adx-chart-body" :style="{ minHeight: height + 'px' }">
			<div v-if="isEmpty" class="adx-empty">
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
				<span>{{ emptyText }}</span>
			</div>
			<div v-show="!isEmpty" ref="containerRef" class="adx-chart-canvas"></div>
		</div>
	</div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from "vue";

export default {
	name: "ChartCard",
	props: {
		title: String,
		subtitle: String,
		data: { type: Object, required: true },
		type: { type: String, default: "line" },
		colors: { type: Array, default: () => ["#1B84FF"] },
		height: { type: Number, default: 220 },
		fill: { type: Boolean, default: false },
	},
	setup(props) {
		const containerRef = ref(null);
		let chart = null;

		const emptyText = computed(() => __("Aucune donnée disponible"));

		const isEmpty = computed(() => {
			if (!props.data || !props.data.labels || !props.data.labels.length) return true;
			const datasets = props.data.datasets || [];
			if (!datasets.length) return true;
			const total = datasets.reduce(
				(acc, ds) => acc + (ds.values || []).reduce((s, v) => s + Number(v || 0), 0),
				0
			);
			return total === 0;
		});

		function destroy() {
			if (containerRef.value) containerRef.value.innerHTML = "";
			chart = null;
		}

		function render() {
			if (!containerRef.value) return;
			destroy();
			if (isEmpty.value) return;

			const opts = {
				data: props.data,
				type: props.type,
				height: props.height,
				colors: props.colors,
				truncateLegends: 1,
				animate: 1,
			};
			if (props.type === "line") {
				opts.lineOptions = {
					regionFill: props.fill ? 1 : 0,
					hideDots: 0,
					heatline: 0,
					spline: 1,
				};
				opts.axisOptions = { xIsSeries: true, xAxisMode: "tick" };
			}
			if (props.type === "bar") {
				opts.barOptions = { spaceRatio: 0.4, stacked: 0 };
				opts.axisOptions = { xAxisMode: "tick" };
			}
			if (props.type === "donut") {
				opts.maxSlices = 6;
			}
			try {
				chart = new frappe.Chart(containerRef.value, opts);
			} catch (e) {
				console.error("ChartCard render error", e);
			}
		}

		onMounted(() => nextTick(render));
		onBeforeUnmount(destroy);
		watch(() => props.data, () => nextTick(render), { deep: true });
		watch(() => props.type, () => nextTick(render));

		return { containerRef, isEmpty, emptyText };
	},
};
</script>
