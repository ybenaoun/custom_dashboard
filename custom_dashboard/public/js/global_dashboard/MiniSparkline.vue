<template>
	<div class="gdx-spark" :style="{ height: height + 'px' }">
		<svg
			v-if="hasData"
			:viewBox="`0 0 ${width} ${height}`"
			preserveAspectRatio="none"
			class="gdx-spark-svg"
		>
			<!-- Aire de remplissage pour les courbes "line" -->
			<path
				v-if="type === 'line' && areaPath"
				:d="areaPath"
				:fill="color"
				fill-opacity="0.12"
			/>
			<!-- Tracé principal -->
			<path
				v-if="type === 'line'"
				:d="linePath"
				fill="none"
				:stroke="color"
				stroke-width="1.6"
				stroke-linejoin="round"
				stroke-linecap="round"
			/>
			<!-- Barres -->
			<g v-else-if="type === 'bar'">
				<rect
					v-for="(b, i) in bars"
					:key="i"
					:x="b.x"
					:y="b.y"
					:width="b.w"
					:height="b.h"
					:fill="color"
					rx="1"
				/>
			</g>
		</svg>
		<div v-else class="gdx-spark-empty">{{ __("Aucune donnée") }}</div>
	</div>
</template>

<script>
const W = 200;

export default {
	name: "MiniSparkline",
	props: {
		values: { type: Array, default: () => [] },
		type: { type: String, default: "line" }, // "line" | "bar"
		color: { type: String, default: "#1B84FF" },
		height: { type: Number, default: 56 },
	},
	computed: {
		width() {
			return W;
		},
		hasData() {
			const arr = this.values || [];
			if (!arr.length) return false;
			return arr.some((v) => Number(v || 0) !== 0);
		},
		stats() {
			const arr = (this.values || []).map((v) => Number(v || 0));
			const min = Math.min(...arr, 0);
			const max = Math.max(...arr, 0);
			const range = max - min || 1;
			return { min, max, range, n: arr.length, arr };
		},
		linePath() {
			if (!this.hasData) return "";
			const { arr, min, range, n } = this.stats;
			if (n < 2) {
				const y = this.height / 2;
				return `M 0 ${y} L ${W} ${y}`;
			}
			const stepX = W / (n - 1);
			const innerH = this.height - 4;
			const pts = arr.map((v, i) => {
				const x = i * stepX;
				const y = 2 + innerH - ((v - min) / range) * innerH;
				return [x, y];
			});
			return pts
				.map((p, i) => (i === 0 ? `M ${p[0]} ${p[1]}` : `L ${p[0]} ${p[1]}`))
				.join(" ");
		},
		areaPath() {
			if (!this.hasData) return "";
			const path = this.linePath;
			if (!path) return "";
			return `${path} L ${W} ${this.height} L 0 ${this.height} Z`;
		},
		bars() {
			if (!this.hasData) return [];
			const { arr, min, range, n } = this.stats;
			if (!n) return [];
			const slot = W / n;
			const gap = Math.min(slot * 0.25, 2);
			const w = Math.max(slot - gap, 1);
			const innerH = this.height - 4;
			return arr.map((v, i) => {
				const value = Number(v || 0);
				const h = Math.max(((value - min) / range) * innerH, 0);
				return {
					x: i * slot + gap / 2,
					y: 2 + innerH - h,
					w,
					h,
				};
			});
		},
	},
};
</script>

<style>
.gdx-spark {
	position: relative;
	width: 100%;
	display: flex;
	align-items: stretch;
}

.gdx-spark-svg {
	width: 100%;
	height: 100%;
	display: block;
}

.gdx-spark-empty {
	flex: 1;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 10px;
	color: var(--gdx-muted, #6b7280);
	border: 1px dashed var(--gdx-border, #e6e9f0);
	border-radius: 6px;
}
</style>
