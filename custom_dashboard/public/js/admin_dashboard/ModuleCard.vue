<template>
	<div class="adx-module" :class="'adx-tone-' + tone">
		<div class="adx-module-head">
			<div class="adx-module-icon">
				<svg
					viewBox="0 0 24 24"
					width="16"
					height="16"
					fill="none"
					stroke="currentColor"
					stroke-width="1.8"
					stroke-linecap="round"
					stroke-linejoin="round"
					v-html="iconPath"
				></svg>
			</div>
			<h6>{{ title }}</h6>
		</div>
		<div class="adx-module-body">
			<div
				v-for="(it, i) in items"
				:key="i"
				class="adx-stat"
				:class="{ 'adx-danger': it.danger }"
			>
				<span class="adx-stat-label">{{ it.label }}</span>
				<span class="adx-stat-value">{{ formatVal(it.value) }}</span>
			</div>
		</div>
	</div>
</template>

<script>
import { computed } from "vue";

const ICONS = {
	users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>',
	email: '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>',
	globe: '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
	folder: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
	branch: '<line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>',
	gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09a1.65 1.65 0 0 0 1.51-1z"/>',
};

export default {
	name: "ModuleCard",
	props: {
		title: String,
		icon: String,
		tone: { type: String, default: "primary" },
		items: { type: Array, default: () => [] },
	},
	setup(props) {
		const iconPath = computed(() => ICONS[props.icon] || ICONS.users);
		const formatVal = (v) => {
			if (v === undefined || v === null) return "—";
			if (typeof v === "string") return v;
			return Number(v).toLocaleString();
		};
		return { iconPath, formatVal };
	},
};
</script>
