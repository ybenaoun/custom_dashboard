<template>
	<transition name="gdx-fade">
		<div v-if="visible" class="gdx-ai-panel">
			<div class="gdx-ai-header">
				<div class="gdx-ai-title">
					<span class="gdx-ai-spark">✦</span>
					{{ __("Analyse IA") }} — {{ title }}
				</div>
				<button class="gdx-ai-close" @click="$emit('close')" :title="__('Fermer')">
					<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<line x1="18" y1="6" x2="6" y2="18" />
						<line x1="6" y1="6" x2="18" y2="18" />
					</svg>
				</button>
			</div>
			<div class="gdx-ai-body">
				<div
					v-for="s in sections"
					:key="s.key"
					class="gdx-ai-section"
					:class="{ 'gdx-ai-highlight': s.highlight }"
				>
					<div class="gdx-ai-section-label">{{ s.label }}</div>
					<div class="gdx-ai-section-text">
						{{ (result || {})[s.key] || __("Non disponible") }}
					</div>
				</div>
			</div>
		</div>
	</transition>
</template>

<script>
export default {
	name: "AiPanel",
	props: {
		visible: Boolean,
		title: String,
		result: Object,
	},
	emits: ["close"],
	computed: {
		sections() {
			return [
				{ key: "resume", label: __("Résumé") },
				{ key: "tendance", label: __("Tendance principale") },
				{ key: "anomalies", label: __("Anomalies / Points d'attention") },
				{ key: "recommandation", label: __("Recommandation"), highlight: true },
			];
		},
	},
};
</script>
