<template>
	<div class="adx-root" :data-theme="theme">
		<!-- Hero -->
		<header class="adx-hero">
			<div class="adx-hero-bg" aria-hidden="true"></div>
			<div class="adx-hero-grid" aria-hidden="true"></div>
			<div class="adx-hero-glow" aria-hidden="true"></div>
			<div class="adx-hero-content">
				<div class="adx-hero-left">
					<div class="adx-hero-icon">
						<svg
							viewBox="0 0 24 24"
							width="24"
							height="24"
							fill="none"
							stroke="currentColor"
							stroke-width="1.7"
							stroke-linecap="round"
							stroke-linejoin="round"
						>
							<path d="M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6l8-4z" />
							<path d="M9 12l2 2 4-4" />
						</svg>
					</div>
					<div>
						<span class="adx-hero-tag">{{ __('Administration') }}</span>
						<h1 class="adx-hero-title">{{ __('Admin Dashboard') }}</h1>
						<p class="adx-hero-sub">
							{{ __("Vue d'ensemble santé système, sécurité et activité.") }}
						</p>
					</div>
				</div>
				<div class="adx-hero-right">
					<div class="adx-pill">
						<span class="adx-dot" :class="health.cls"></span>
						<span>{{ health.label }}</span>
					</div>
					<button class="adx-btn-glass" @click="reload" :disabled="loading">
						<svg
							viewBox="0 0 24 24"
							width="14"
							height="14"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							stroke-linecap="round"
							stroke-linejoin="round"
							:class="{ 'adx-spin': loading }"
						>
							<path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
							<path d="M21 3v5h-5" />
							<path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
							<path d="M3 21v-5h5" />
						</svg>
						{{ __('Actualiser') }}
					</button>
				</div>
			</div>
		</header>

		<!-- Loading skeleton -->
		<div v-if="loading && !data" class="adx-loading">
			<div class="adx-skeleton-grid">
				<div v-for="i in 5" :key="i" class="adx-skeleton-card"></div>
			</div>
		</div>

		<template v-else-if="data">
			<!-- KPI cards -->
			<section class="adx-section">
				<div class="adx-section-head">
					<h5>{{ __('Indicateurs clés') }}</h5>
					<span class="adx-section-line"></span>
				</div>
				<div class="adx-kpi-grid">
					<KpiCard
						v-for="kpi in kpiList"
						:key="kpi.id"
						:label="kpi.label"
						:value="kpi.value"
						:badge="kpi.badge"
						:badge-tone="kpi.badgeTone"
						:tone="kpi.tone"
						:icon="kpi.icon"
						:route="kpi.route"
					/>
				</div>
			</section>

			<!-- Charts: line + bar + donut -->
			<section class="adx-section">
				<div class="adx-section-head">
					<h5>{{ __('Analytique visuelle') }}</h5>
					<span class="adx-section-line"></span>
				</div>
				<div class="adx-chart-grid">
					<ChartCard
						class="adx-chart-wide"
						:title="__('Tendance des connexions (7j)')"
						subtitle="line"
						:data="loginChartData"
						type="line"
						:colors="['#1B84FF']"
						:height="240"
						:fill="true"
					/>
					<ChartCard
						:title="__('Répartition utilisateurs')"
						subtitle="donut"
						:data="userDonutData"
						type="donut"
						:colors="['#1B84FF', '#10B981', '#94A3B8']"
						:height="240"
					/>
					<ChartCard
						:title="__('Erreurs (14 jours)')"
						subtitle="line"
						:data="errorChartData"
						type="line"
						:colors="['#EF4444']"
						:height="240"
						:fill="true"
					/>
					<ChartCard
						:title="__('Activité emails')"
						subtitle="bar"
						:data="emailBarData"
						type="bar"
						:colors="['#1B84FF', '#10B981', '#6366F1', '#EF4444']"
						:height="240"
					/>
					<ChartCard
						:title="__('Stockage fichiers')"
						subtitle="donut"
						:data="fileDonutData"
						type="donut"
						:colors="['#6366F1', '#22C55E']"
						:height="240"
					/>
					<ChartCard
						class="adx-chart-wide"
						:title="__('Santé des modules')"
						subtitle="bar"
						:data="moduleBarData"
						type="bar"
						:colors="['#1B84FF']"
						:height="240"
					/>
				</div>
			</section>

			<!-- Module detail cards -->
			<section class="adx-section">
				<div class="adx-section-head">
					<h5>{{ __('Détails par module') }}</h5>
					<span class="adx-section-line"></span>
				</div>
				<div class="adx-module-grid">
					<ModuleCard
						v-for="m in modules"
						:key="m.id"
						:title="m.title"
						:icon="m.icon"
						:tone="m.tone"
						:items="m.items"
					/>
				</div>
			</section>

			<!-- Top Errors Table -->
			<section class="adx-section">
				<div class="adx-section-head">
					<h5>{{ __("Top erreurs aujourd'hui") }}</h5>
					<span class="adx-section-line"></span>
				</div>
				<div class="adx-table-card">
					<table class="adx-table">
						<thead>
							<tr>
								<th>{{ __('Méthode') }}</th>
								<th class="adx-right">{{ __('Occurrences') }}</th>
							</tr>
						</thead>
						<tbody>
							<tr v-if="!data.errors.top_errors || !data.errors.top_errors.length">
								<td colspan="2" class="adx-muted adx-center">
									{{ __("Aucune erreur aujourd'hui") }}
								</td>
							</tr>
							<tr v-for="(err, idx) in data.errors.top_errors" :key="idx">
								<td class="adx-truncate">{{ truncate(err.method || __('Inconnu'), 80) }}</td>
								<td class="adx-right">
									<span class="adx-pill-danger">{{ err.count }}</span>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>
		</template>
	</div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, computed } from "vue";
import KpiCard from "./KpiCard.vue";
import ChartCard from "./ChartCard.vue";
import ModuleCard from "./ModuleCard.vue";

export default {
	name: "AdminDashboard",
	components: { KpiCard, ChartCard, ModuleCard },
	setup() {
		const data = ref(null);
		const errorTrend = ref([]);
		const loading = ref(false);
		const theme = ref(document.documentElement.getAttribute("data-theme") || "light");

		async function fetchAll() {
			loading.value = true;
			try {
				const [main, errors] = await Promise.all([
					frappe.call({
						method: "custom_dashboard.custom_dashboard.page.admin_dashboard.admin_dashboard.get_dashboard_data",
					}),
					frappe.call({
						method: "custom_dashboard.custom_dashboard.page.admin_dashboard.admin_dashboard.get_error_trend",
					}),
				]);
				data.value = main.message || null;
				errorTrend.value = errors.message || [];
			} catch (e) {
				frappe.msgprint({
					title: __("Erreur"),
					message: String(e),
					indicator: "red",
				});
			} finally {
				loading.value = false;
			}
		}

		onMounted(fetchAll);

		const obs = new MutationObserver(() => {
			theme.value = document.documentElement.getAttribute("data-theme") || "light";
		});
		obs.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ["data-theme"],
		});
		onBeforeUnmount(() => obs.disconnect());

		const kpiList = computed(() => {
			if (!data.value) return [];
			const d = data.value;
			return [
				{
					id: "users",
					label: __("Utilisateurs système"),
					value: d.users.total_system,
					badge: d.users.new_this_week
						? `+${d.users.new_this_week} ${__("cette semaine")}`
						: "",
					badgeTone: "info",
					tone: "primary",
					icon: "users",
					route: "List/User/User Type/is/System User",
				},
				{
					id: "errors",
					label: __("Erreurs aujourd'hui"),
					value: d.errors.total_today,
					badge: d.errors.unseen ? `${d.errors.unseen} ${__("non vues")}` : "",
					badgeTone: "danger",
					tone: "danger",
					icon: "errors",
					route: "List/Error Log",
				},
				{
					id: "email",
					label: __("File d'attente email"),
					value: d.emails.queue_count,
					badge: d.emails.sent_today
						? `${d.emails.sent_today} ${__("envoyés")}`
						: "",
					badgeTone: "success",
					tone: "info",
					icon: "email",
					route: "List/Email Queue/status/is/Not Sent",
				},
				{
					id: "logins",
					label: __("Connexions aujourd'hui"),
					value: d.activity.logins_today,
					badge: d.activity.failed_logins_week
						? `${d.activity.failed_logins_week} ${__("échouées")}`
						: "",
					badgeTone: "warning",
					tone: "success",
					icon: "logins",
				},
				{
					id: "todos",
					label: __("Tâches ouvertes"),
					value: d.todos.open,
					badge: d.todos.overdue ? `${d.todos.overdue} ${__("en retard")}` : "",
					badgeTone: "danger",
					tone: "warning",
					icon: "todos",
					route: "List/ToDo/status/is/Open",
				},
			];
		});

		const loginChartData = computed(() => {
			const trend = data.value?.activity?.login_trend || [];
			return {
				labels: trend.map((t) => formatDate(t.date)),
				datasets: [{ name: __("Connexions"), values: trend.map((t) => t.count) }],
			};
		});

		const errorChartData = computed(() => {
			const trend = errorTrend.value || [];
			return {
				labels: trend.map((t) => formatDate(t.date)),
				datasets: [{ name: __("Erreurs"), values: trend.map((t) => t.count) }],
			};
		});

		const userDonutData = computed(() => {
			const dist = data.value?.distributions?.users || [];
			return {
				labels: dist.map((d) => d.label),
				datasets: [{ values: dist.map((d) => d.value) }],
			};
		});

		const fileDonutData = computed(() => {
			const dist = data.value?.distributions?.files || [];
			return {
				labels: dist.map((d) => d.label),
				datasets: [{ values: dist.map((d) => d.value) }],
			};
		});

		const emailBarData = computed(() => {
			const dist = data.value?.distributions?.emails || [];
			return {
				labels: dist.map((d) => d.label),
				datasets: [{ name: __("Emails"), values: dist.map((d) => d.value) }],
			};
		});

		const moduleBarData = computed(() => {
			const dist = data.value?.distributions?.modules || [];
			return {
				labels: dist.map((d) => d.label),
				datasets: [{ name: __("Actifs"), values: dist.map((d) => d.value) }],
			};
		});

		const modules = computed(() => {
			if (!data.value) return [];
			const d = data.value;
			return [
				{
					id: "users",
					title: __("Utilisateurs & Sécurité"),
					icon: "users",
					tone: "primary",
					items: [
						{ label: __("Système"), value: d.users.total_system },
						{ label: __("Site web"), value: d.users.total_website },
						{ label: __("Désactivés"), value: d.users.disabled },
						{ label: __("Actifs (7j)"), value: d.users.active_last_week },
						{
							label: __("Échecs login (semaine)"),
							value: d.activity.failed_logins_week,
							danger: true,
						},
					],
				},
				{
					id: "email",
					title: __("Email"),
					icon: "email",
					tone: "info",
					items: [
						{ label: __("En file"), value: d.emails.queue_count },
						{ label: __("Envoyés (jour)"), value: d.emails.sent_today },
						{ label: __("Envoyés (semaine)"), value: d.emails.sent_this_week },
						{ label: __("Erreurs"), value: d.emails.errors, danger: true },
					],
				},
				{
					id: "website",
					title: __("Site web"),
					icon: "globe",
					tone: "success",
					items: [
						{ label: __("Pages publiées"), value: d.website.published_pages },
						{ label: __("Formulaires publiés"), value: d.website.published_forms },
						{ label: __("Vues totales"), value: d.website.total_views },
					],
				},
				{
					id: "files",
					title: __("Fichiers & Stockage"),
					icon: "folder",
					tone: "warning",
					items: [
						{ label: __("Total"), value: d.files.total_files },
						{ label: __("Privés"), value: d.files.total_private },
						{ label: __("Publics"), value: d.files.total_public },
						{ label: __("Taille"), value: `${d.files.total_size_mb} MB` },
					],
				},
				{
					id: "workflow",
					title: __("Workflow"),
					icon: "branch",
					tone: "primary",
					items: [
						{ label: __("Workflows actifs"), value: d.workflows.total_active },
						{ label: __("Actions en attente"), value: d.workflows.pending_actions },
					],
				},
				{
					id: "automation",
					title: __("Automatisation"),
					icon: "gear",
					tone: "info",
					items: [
						{ label: __("Auto Repeat"), value: d.automation.auto_repeat },
						{ label: __("Règles d'attribution"), value: d.automation.assignment_rules },
						{ label: __("Notifications"), value: d.automation.notifications },
						{
							label: __("Jobs en échec (semaine)"),
							value: d.background_jobs.failed_this_week,
							danger: true,
						},
						{ label: __("Types planifiés"), value: d.background_jobs.total_job_types },
					],
				},
			];
		});

		const health = computed(() => {
			if (!data.value) return { label: __("Chargement"), cls: "adx-dot-info" };
			const d = data.value;
			const errors = d.errors.total_today || 0;
			const failedJobs = d.background_jobs.failed_this_week || 0;
			const failedLogins = d.activity.failed_logins_week || 0;
			if (errors > 50 || failedJobs > 20)
				return { label: __("Critique"), cls: "adx-dot-danger" };
			if (errors > 10 || failedJobs > 5 || failedLogins > 20)
				return { label: __("Attention"), cls: "adx-dot-warning" };
			return { label: __("Système OK"), cls: "adx-dot-success" };
		});

		function formatDate(d) {
			try {
				return frappe.format(d, { fieldtype: "Date" });
			} catch (e) {
				return String(d);
			}
		}

		function truncate(s, n) {
			if (!s) return "";
			return s.length > n ? s.slice(0, n) + "…" : s;
		}

		function reload() {
			fetchAll();
		}

		return {
			data,
			loading,
			theme,
			kpiList,
			loginChartData,
			errorChartData,
			userDonutData,
			fileDonutData,
			emailBarData,
			moduleBarData,
			modules,
			health,
			reload,
			truncate,
		};
	},
};
</script>
