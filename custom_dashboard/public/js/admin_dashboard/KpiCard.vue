<template>
	<div
		class="adx-kpi"
		:class="['adx-tone-' + tone, { 'adx-clickable': route }]"
		@click="open"
	>
		<div class="adx-kpi-glow"></div>
		<div class="adx-kpi-icon">
			<svg
				viewBox="0 0 24 24"
				width="20"
				height="20"
				fill="none"
				stroke="currentColor"
				stroke-width="1.8"
				stroke-linecap="round"
				stroke-linejoin="round"
				v-html="iconPath"
			></svg>
		</div>
		<div class="adx-kpi-body">
			<div class="adx-kpi-value">{{ formatted }}</div>
			<div class="adx-kpi-label">{{ label }}</div>
		</div>
		<div v-if="badge" class="adx-kpi-badge" :class="'adx-badge-' + badgeTone">
			{{ badge }}
		</div>
	</div>
</template>

<script>
import { computed } from "vue";

const ICONS = {
	users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>',
	errors: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
	email: '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>',
	logins: '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/>',
	todos: '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
};

export default {
	name: "KpiCard",
	props: {
		label: String,
		value: [Number, String],
		badge: String,
		badgeTone: { type: String, default: "info" },
		tone: { type: String, default: "primary" },
		icon: String,
		route: String,
	},
	setup(props) {
		const formatted = computed(() => {
			if (props.value === undefined || props.value === null) return "—";
			const n = Number(props.value);
			return isNaN(n) ? props.value : n.toLocaleString();
		});
		const iconPath = computed(() => ICONS[props.icon] || ICONS.users);
		const open = () => {
			if (props.route) frappe.set_route(props.route.split("/"));
		};
		return { formatted, iconPath, open };
	},
};
</script>
