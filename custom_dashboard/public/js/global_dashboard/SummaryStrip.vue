<template>
	<div v-if="cards.length" class="gdx-summary">
		<div
			v-for="(card, idx) in cards"
			:key="idx"
			class="gdx-summary-card"
			:class="{ 'gdx-clickable': card.route }"
			:style="{ '--card-color': palette[idx % palette.length] }"
			@click="open(card.route)"
		>
			<div class="gdx-summary-bar"></div>
			<div class="gdx-summary-meta">
				<span class="gdx-summary-module">{{ card.module_label }}</span>
				<span class="gdx-summary-label">{{ card.label }}</span>
			</div>
			<div class="gdx-summary-value">{{ card.formatted_value }}</div>
			<div v-if="card.description" class="gdx-summary-desc">
				{{ card.description }}
			</div>
		</div>
	</div>
	<div v-else class="gdx-empty-state">
		{{ __("Aucun KPI visible pour les modules autorisés.") }}
	</div>
</template>

<script>
const PALETTE = ["#1B84FF", "#10B981", "#F59E0B", "#7C3AED", "#EF4444", "#0EA5E9"];

export default {
	name: "SummaryStrip",
	props: {
		cards: { type: Array, default: () => [] },
	},
	data() {
		return { palette: PALETTE };
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
