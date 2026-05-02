<template>
	<div class="cd-v2-shell" :class="{ 'is-fullscreen-preview': isFullscreenPreview }">
		<header class="cd-topbar">
			<div class="cd-topbar-left">
				<div class="cd-app-icon" aria-hidden="true" v-html="iconSvg('layout')"></div>
				<div class="cd-topbar-copy">
					<h1 class="cd-title">Constructeur de tableaux de bord</h1>
					<div class="cd-topbar-meta">
						<label class="sr-only" for="cd-dashboard-selector">Tableau de bord actif</label>
						<select
							id="cd-dashboard-selector"
							v-model="selectedDashboardName"
							class="cd-dashboard-selector"
							@change="handleDashboardSelect"
						>
							<option value="">{{ dashboardTitle }}</option>
							<option
								v-for="dashboard in dashboards"
								:key="dashboard.name"
								:value="dashboard.name"
							>
								{{ dashboard.title || "Mon tableau de bord" }}
							</option>
						</select>
						<span class="cd-version-badge">V2 reliée à ERPNext</span>
					</div>
				</div>
			</div>

			<div class="cd-topbar-actions">
				<span class="cd-save-status" :class="{ 'is-dirty': hasUnsavedChanges, 'is-saved': !hasUnsavedChanges && currentDashboard }">
					<span class="cd-status-dot"></span>
					{{ saveStatusLabel }}
				</span>
				<button class="btn btn-default" type="button" :disabled="loadingDashboard" @click="previewDashboard">
					Aperçu
				</button>
				<button
					class="btn btn-default"
					type="button"
					:disabled="!currentDashboard"
					@click="createDashboard(true)"
				>
					Dupliquer
				</button>
				<button
					v-if="isFullscreenPreview"
					class="btn btn-default"
					type="button"
					@click="exitFullscreenPreview"
				>
					Quitter
				</button>
				<button
					v-else
					class="btn btn-default"
					type="button"
					:disabled="!currentDashboard || !orderedDashboardItems.length"
					@click="enterFullscreenPreview"
				>
					Plein écran
				</button>
				<button
					class="btn btn-primary cd-save-button"
					type="button"
					:disabled="saving || !currentDashboard || !canEditCurrent"
					@click="saveDashboard"
				>
					{{ saving ? "Enregistrement…" : "Enregistrer" }}
				</button>
			</div>
		</header>

		<div v-if="pageError" class="cd-banner is-error">
			{{ pageError }}
		</div>

		<div v-if="currentDashboard && !canEditCurrent" class="cd-banner">
			Vous consultez un tableau partagé en lecture seule.
		</div>

		<div v-if="cameFromGlobalDashboard" class="cd-banner is-info">
			<strong>Modules personnalisables disponibles :</strong> Stock, Ventes, Achats.
			<span class="cd-banner-sub">
				Les modules RH et Comptabilité sont disponibles en consultation dans le
				tableau de bord global et pourront être intégrés au constructeur dans une
				évolution future.
			</span>
		</div>

			<div class="cd-layout" :class="{ 'is-library-collapsed': isLibraryCollapsed }">
				<aside class="cd-panel cd-library-panel" aria-label="Bibliothèque de widgets">
					<div class="cd-panel-head cd-library-head">
						<div>
							<h2>Bibliothèque de widgets</h2>
							<p>{{ filteredWidgets.length }} widget(s) disponible(s)</p>
						</div>
						<button
							class="cd-icon-button"
							type="button"
							:title="isLibraryCollapsed ? 'Déplier la bibliothèque' : 'Replier la bibliothèque'"
							@click="isLibraryCollapsed = !isLibraryCollapsed"
						>
							<span aria-hidden="true" v-html="iconSvg(isLibraryCollapsed ? 'panel-open' : 'panel-close')"></span>
							<span class="sr-only">{{ isLibraryCollapsed ? "Déplier la bibliothèque" : "Replier la bibliothèque" }}</span>
						</button>
					</div>

					<div v-if="!isLibraryCollapsed" class="cd-library-content">
						<div class="cd-library-tools">
							<span class="cd-search-icon" aria-hidden="true" v-html="iconSvg('search')"></span>
							<input
								v-model.trim="librarySearch"
								class="form-control"
								type="search"
								placeholder="Rechercher un widget…"
							/>
						</div>

						<div class="cd-filter-pills" role="list" aria-label="Filtres de widgets">
							<button
								v-for="filter in libraryFilterOptions"
								:key="filter.key"
								class="cd-filter-pill"
								:class="{ 'is-active': activeLibraryFilter === filter.key }"
								type="button"
								@click="activeLibraryFilter = filter.key"
							>
								{{ filter.label }}
							</button>
						</div>

						<div v-if="widgetsLoading" class="cd-state">Chargement des widgets…</div>
						<div v-else-if="!filteredWidgets.length" class="cd-state">
							Aucun widget disponible pour ce filtre.
						</div>
						<div v-else class="cd-library-list">
							<article
								v-for="widget in filteredWidgets"
								:key="widget.name"
								class="cd-library-card"
								:class="{ 'is-disabled': !widget.can_use || !canEditCurrent }"
								draggable="true"
								@dragstart="onLibraryDragStart($event, widget)"
								@dragend="clearDragState"
							>
								<div class="cd-widget-library-icon" :class="widgetToneClass(widget)" aria-hidden="true" v-html="iconSvg(widgetIconName(widget))"></div>
								<div class="cd-library-card-main">
									<h3>{{ widgetDisplayTitle(widget) }}</h3>
									<p>{{ widgetMetaLabel(widget) }}</p>
								</div>
								<button
									class="btn btn-default btn-sm cd-add-widget-button"
									type="button"
									:disabled="!widget.can_use || !canEditCurrent"
									@click="addWidget(widget)"
								>
									+ Ajouter
								</button>
							</article>
						</div>
					</div>
				</aside>

			<main class="cd-panel cd-workspace">
				<div v-if="!currentDashboard" class="cd-empty">
					<p>Créez un tableau de bord pour commencer.</p>
				</div>

				<template v-else>
						<section class="cd-dashboard-overview">
							<div>
								<h2>{{ dashboardTitle }}</h2>
								<div class="cd-canvas-metadata">
									<span>12 colonnes</span>
									<span>Déplacement libre</span>
									<span>{{ orderedDashboardItems.length }} widget(s)</span>
								</div>
							</div>
							<button class="cd-icon-button" type="button" title="Plus d’options" @click="activeInspectorTab = 'properties'">
								<span aria-hidden="true" v-html="iconSvg('more')"></span>
								<span class="sr-only">Plus d’options</span>
							</button>
						</section>

						<section class="cd-dashboard-form">
							<div class="cd-config-title">
								<h3>Configuration du tableau de bord</h3>
								<p>{{ currentDashboard.name ? "Tableau relié aux données ERPNext." : "Brouillon prêt à enregistrer." }}</p>
							</div>
							<div class="cd-field">
								<label>Titre</label>
								<input
									v-model="currentDashboard.title"
									class="form-control"
									type="text"
									:disabled="!canEditCurrent"
								/>
							</div>

							<div class="cd-field">
								<label>Module de destination</label>
								<select
									v-model="currentDashboard.module_name"
									class="form-control"
									:disabled="!userIsAdmin || !canEditCurrent"
									@change="syncModuleFlags"
								>
									<option value="">Aucun module</option>
									<option
										v-for="moduleOption in moduleOptions"
										:key="moduleOption.value"
										:value="moduleOption.value"
									>
										{{ moduleOption.label }}
									</option>
								</select>
							</div>

							<div class="cd-toggle-row">
								<label class="cd-toggle">
									<input
										v-model="currentDashboard.is_default"
										type="checkbox"
										:disabled="!currentDashboard.can_manage_sharing || Boolean(currentDashboard.module_name)"
									/>
									<span>Défaut</span>
								</label>

								<label class="cd-toggle">
									<input
										v-model="currentDashboard.is_shared"
										type="checkbox"
										:disabled="!currentDashboard.can_manage_sharing || Boolean(currentDashboard.module_name)"
									/>
									<span>Partage global</span>
								</label>
							</div>
						</section>

						<section class="cd-grid-stage">
							<div class="cd-grid-stage-head">
								<div>
									<h2>Canvas</h2>
									<p>Grille 12 colonnes avec aperçu des widgets connectés.</p>
								</div>
								<span class="cd-pill">{{ orderedDashboardItems.length ? `${orderedDashboardItems.length} widget(s)` : "Aucun widget ajouté" }}</span>
							</div>

							<div v-if="loadingDashboard" class="cd-state">Chargement du constructeur…</div>
							<div v-else class="cd-grid-scroll">
								<div
									ref="gridCanvas"
									class="cd-grid-canvas"
									:class="{ 'is-empty': !currentDashboard.items.length }"
									:style="canvasStyle"
									@dragover.prevent="onGridDragOver"
									@drop.prevent="onGridDrop"
									@dragleave="onGridDragLeave"
								>
									<div class="cd-column-labels" aria-hidden="true">
										<span v-for="column in gridColumns" :key="column">{{ column }}</span>
									</div>

									<div v-if="!currentDashboard.items.length" class="cd-empty-canvas-state">
										<div class="cd-empty-icon" aria-hidden="true" v-html="iconSvg('spark-layout')"></div>
										<h3>Déposez vos widgets ici</h3>
										<p>Glissez un widget depuis la bibliothèque ou cliquez sur “Ajouter” pour commencer.</p>
										<div class="cd-empty-placeholders" aria-hidden="true">
											<div class="cd-placeholder-donut"></div>
											<div class="cd-placeholder-kpi">
												<span></span>
												<strong></strong>
											</div>
											<div class="cd-placeholder-bars">
												<span></span>
												<span></span>
												<span></span>
											</div>
										</div>
									</div>

									<div
										v-if="dragState.over"
										class="cd-drop-preview"
									:style="gridItemStyle(dragState.over)"
								></div>

								<article
									v-for="item in orderedDashboardItems"
									:key="item.local_id"
									class="cd-widget-card"
									:style="gridItemStyle(item)"
									:class="{
										'is-locked': !item.definition?.can_use,
										'is-compact': isCompactWidget(item),
									}"
									:draggable="canEditCurrent && Boolean(item.definition?.can_use)"
									@dragstart="onItemDragStart($event, item)"
									@dragend="clearDragState"
								>
								<header class="cd-widget-head">
									<div class="cd-widget-head-main">
										<span class="cd-drag-handle">Déplacer</span>
										<input
											v-model="item.display_title"
											class="form-control input-sm"
											type="text"
											:disabled="!canEditCurrent"
										/>
										<p class="cd-widget-meta">
											{{ item.definition?.category || "Général" }} · {{ item.definition?.widget_type || item.widget }}
										</p>
									</div>

									<div class="cd-widget-head-actions">
										<span class="cd-chip">{{ item.w }}x{{ item.h }}</span>
										<span v-if="!item.definition?.can_use" class="cd-chip is-warning">
											Lecture seule
										</span>
									</div>
								</header>

								<div
									v-if="item.definition?.allow_filters && visibleFilterFields(item).length"
									class="cd-filter-box"
									:class="{ 'is-collapsed': item.filtersCollapsed }"
								>
									<div class="cd-filter-toolbar">
										<button
											class="btn btn-default btn-xs cd-filter-toggle"
											type="button"
											@click="toggleItemFilters(item)"
										>
											{{ item.filtersCollapsed ? "Afficher les filtres" : "Masquer les filtres" }}
										</button>
										<span v-if="item.filtersCollapsed" class="cd-filter-summary">
											{{ itemFilterSummary(item) }}
										</span>
									</div>

									<template v-if="!item.filtersCollapsed">
										<div class="cd-filter-grid">
											<div
												v-for="field in visibleFilterFields(item)"
												:key="field.fieldname"
												class="cd-field"
											>
												<label>{{ field.label }}</label>

												<select
													v-if="field.fieldtype === 'Select'"
													v-model="item.filters[field.fieldname]"
													class="form-control"
													:disabled="!canEditCurrent || !item.definition?.can_use"
												>
													<option
														v-for="option in field.options || []"
														:key="option.value"
														:value="option.value"
													>
														{{ option.label }}
													</option>
												</select>

												<input
													v-else-if="field.fieldtype === 'Date'"
													v-model="item.filters[field.fieldname]"
													class="form-control"
													type="date"
													:disabled="!canEditCurrent || !item.definition?.can_use"
												/>

												<input
													v-else-if="field.fieldtype === 'Int'"
													v-model.number="item.filters[field.fieldname]"
													class="form-control"
													type="number"
													:min="field.min || 0"
													:max="field.max || 9999"
													:disabled="!canEditCurrent || !item.definition?.can_use"
												/>

												<label v-else-if="field.fieldtype === 'Check'" class="cd-toggle">
													<input
														v-model="item.filters[field.fieldname]"
														type="checkbox"
														:disabled="!canEditCurrent || !item.definition?.can_use"
													/>
													<span>{{ field.label }}</span>
												</label>

												<input
													v-else
													v-model="item.filters[field.fieldname]"
													class="form-control"
													type="text"
													:disabled="!canEditCurrent || !item.definition?.can_use"
												/>
											</div>
										</div>

										<div class="cd-filter-actions">
											<button
												class="btn btn-default btn-sm"
												type="button"
												:disabled="!item.definition?.can_use"
												@click="applyItemFilters(item)"
											>
												Appliquer
											</button>
											<button
												class="btn btn-default btn-sm"
												type="button"
												:disabled="!canEditCurrent"
												@click="resetItemFilters(item)"
											>
												Réinitialiser
											</button>
										</div>
									</template>
								</div>

								<div class="cd-widget-body">
										<div v-if="item.loading" class="cd-state">Chargement du widget…</div>
									<div v-else-if="item.error" class="cd-inline-error">{{ item.error }}</div>
									<div v-else-if="item.definition && !item.definition.can_use" class="cd-empty">
										<p>Vous pouvez voir ce widget, mais pas l’exécuter.</p>
									</div>
									<template v-else>
										<div v-if="itemType(item) === 'number_card'" class="cd-number-card">
											<strong class="cd-number-card-value">{{ formatNumberCardValue(item) }}</strong>
											<span class="cd-number-card-label">{{ numberCardLabel(item) }}</span>
											<span v-if="numberCardSecondary(item)" class="cd-number-card-secondary">
												{{ numberCardSecondary(item) }}
											</span>
											<small v-if="itemPayload(item).context" class="cd-widget-context">
												{{ itemPayload(item).context }}
											</small>
										</div>

										<div v-else-if="itemType(item) === 'table'" class="cd-table-wrap">
											<small v-if="itemPayload(item).context" class="cd-widget-context">
												{{ itemPayload(item).context }}
											</small>
											<div class="table-responsive">
												<table class="table table-bordered cd-table-preview">
													<thead>
														<tr>
															<th v-for="column in getTableColumns(item)" :key="column.key">
																{{ column.label }}
															</th>
														</tr>
													</thead>
													<tbody>
														<tr v-for="(row, rowIndex) in getTableRows(item)" :key="rowIndex">
															<td
																v-for="column in getTableColumns(item)"
																:key="`${rowIndex}-${column.key}`"
															>
																{{ formatTableCell(row, column) }}
															</td>
														</tr>
													</tbody>
												</table>
											</div>
										</div>

										<div v-else-if="itemType(item) === 'chart'" class="cd-chart-card">
											<div class="cd-chart-headline">
												<div>
													<strong>{{ chartSummaryLabel(item) }}</strong>
													<span>{{ chartSummaryValue(item) }}</span>
												</div>
												<small v-if="itemPayload(item).context">{{ itemPayload(item).context }}</small>
											</div>
											<div :ref="`chart_${item.local_id}`" class="cd-chart-host"></div>
										</div>

										<div v-else-if="itemType(item) === 'ai_insight'" class="cd-ai-card">
											<div v-if="aiPayload(item).error" class="cd-inline-error">
												{{ aiPayload(item).error }}
											</div>
											<template v-else>
												<p class="cd-ai-summary">
													{{ aiPayload(item).summary || "Aucune synthèse générée. Cliquez sur Régénérer." }}
												</p>

												<section class="cd-ai-section">
													<h4>Anomalies détectées</h4>
													<div v-if="!(aiPayload(item).anomalies || []).length" class="cd-ai-empty">
														Aucune anomalie significative.
													</div>
													<ul v-else class="cd-ai-list">
														<li
															v-for="(anomaly, idx) in aiPayload(item).anomalies"
															:key="`a-${idx}`"
															:class="`cd-ai-item sev-${anomaly.severity || 'medium'}`"
														>
															<div class="cd-ai-item-head">
																<span class="cd-ai-badge">{{ severityLabel(anomaly.severity) }}</span>
																<strong>{{ anomaly.label }}</strong>
															</div>
															<p>{{ anomaly.evidence }}</p>
														</li>
													</ul>
												</section>

												<section class="cd-ai-section">
													<h4>Recommandations</h4>
													<div v-if="!(aiPayload(item).recommendations || []).length" class="cd-ai-empty">
														Aucune recommandation.
													</div>
													<ol v-else class="cd-ai-list">
														<li
															v-for="(rec, idx) in aiPayload(item).recommendations"
															:key="`r-${idx}`"
															:class="`cd-ai-item sev-${rec.priority || 'medium'}`"
														>
															<div class="cd-ai-item-head">
																<span class="cd-ai-badge">{{ severityLabel(rec.priority) }}</span>
																<strong>{{ rec.action }}</strong>
															</div>
															<p>{{ rec.rationale }}</p>
														</li>
													</ol>
												</section>
											</template>

											<footer class="cd-ai-footer">
												<button
													class="btn btn-default btn-sm"
													type="button"
													:disabled="item.aiRegenerating"
													@click="regenerateAi(item)"
												>
													{{ item.aiRegenerating ? "Régénération…" : "Régénérer l’analyse" }}
												</button>
												<small v-if="aiPayload(item).model">
													{{ aiPayload(item).from_cache ? "Cache" : "Frais" }}
													· {{ aiPayload(item).model }}
													· {{ formatGeneratedAt(item) }}
												</small>
											</footer>
										</div>

										<div v-else class="cd-custom-card">
											<pre>{{ formatJson(item.preview?.data) }}</pre>
										</div>
									</template>
								</div>

								<footer class="cd-widget-foot">
									<div class="cd-resize-group">
										<div class="cd-resize-control">
											<span>Largeur</span>
											<button
												class="btn btn-default btn-xs"
												type="button"
												:disabled="!canEditCurrent"
												@click="changeItemSize(item, 'w', -1)"
											>
												-
											</button>
											<button
												class="btn btn-default btn-xs"
												type="button"
												:disabled="!canEditCurrent"
												@click="changeItemSize(item, 'w', 1)"
											>
												+
											</button>
										</div>

										<div class="cd-resize-control">
											<span>Hauteur</span>
											<button
												class="btn btn-default btn-xs"
												type="button"
												:disabled="!canEditCurrent"
												@click="changeItemSize(item, 'h', -1)"
											>
												-
											</button>
											<button
												class="btn btn-default btn-xs"
												type="button"
												:disabled="!canEditCurrent"
												@click="changeItemSize(item, 'h', 1)"
											>
												+
											</button>
										</div>
									</div>

									<div class="cd-widget-actions">
										<button
											class="btn btn-default btn-sm"
											type="button"
											:disabled="!item.definition?.can_use"
											@click="refreshItem(item)"
										>
											Actualiser
										</button>
										<button
											class="btn btn-default btn-sm"
											type="button"
											:disabled="!canEditCurrent"
											@click="removeItem(item.local_id)"
										>
											Supprimer
										</button>
									</div>
								</footer>
								</article>
							</div>
						</div>
					</section>
				</template>
			</main>

				<aside class="cd-panel cd-side-panel">
					<div class="cd-inspector-head">
						<div>
							<h2>Inspecteur</h2>
							<p>{{ canEditCurrent ? "Réglages du tableau actif" : "Lecture seule" }}</p>
						</div>
						<span class="cd-pill">{{ selectedModuleLabel || "Personnel" }}</span>
					</div>

					<div class="cd-side-tabs">
						<button
							class="cd-tab"
							:class="{ 'is-active': activeInspectorTab === 'properties' }"
							type="button"
							@click="activeInspectorTab = 'properties'"
						>
							Propriétés
						</button>
						<button
							class="cd-tab"
							:class="{ 'is-active': activeInspectorTab === 'dashboards' }"
							type="button"
							@click="activeInspectorTab = 'dashboards'"
						>
							Tableaux
						</button>
						<button
							class="cd-tab"
							:class="{ 'is-active': activeInspectorTab === 'history' }"
							type="button"
							@click="activeInspectorTab = 'history'"
						>
							Historique
						</button>
					</div>

					<section v-if="activeInspectorTab === 'properties'" class="cd-side-section">
						<div v-if="!currentDashboard" class="cd-state">
							Créez un tableau de bord pour afficher ses propriétés.
						</div>
						<template v-else>
							<div class="cd-property-list">
								<label class="cd-property-field">
									<span>Titre</span>
									<input
										v-model="currentDashboard.title"
										class="form-control"
										type="text"
										:disabled="!canEditCurrent"
									/>
								</label>

								<label class="cd-property-field">
									<span>Module</span>
									<select
										v-model="currentDashboard.module_name"
										class="form-control"
										:disabled="!userIsAdmin || !canEditCurrent"
										@change="syncModuleFlags"
									>
										<option value="">Aucun module</option>
										<option
											v-for="moduleOption in moduleOptions"
											:key="moduleOption.value"
											:value="moduleOption.value"
										>
											{{ moduleOption.label }}
										</option>
									</select>
								</label>

								<div class="cd-readonly-field">
									<span>Disposition</span>
									<strong>12 colonnes · Déplacement libre</strong>
								</div>

								<div class="cd-readonly-field">
									<span>Partage</span>
									<strong>{{ sharingSummary }}</strong>
								</div>
							</div>

							<label class="cd-toggle cd-toggle-card">
								<input
									v-model="currentDashboard.is_default"
									type="checkbox"
									:disabled="!currentDashboard.can_manage_sharing || Boolean(currentDashboard.module_name)"
								/>
								<span>
									<strong>Défaut</strong>
									<small>Définir comme tableau de bord par défaut</small>
								</span>
							</label>

							<section class="cd-side-block">
								<h3>Actions</h3>
								<div class="cd-inspector-actions">
									<button
										class="btn btn-default"
										type="button"
										:disabled="!currentDashboard || !canEditCurrent || !orderedDashboardItems.length"
										@click="resetDashboardLayout"
									>
										Réinitialiser
									</button>
									<button
										class="btn btn-default cd-danger-button"
										type="button"
										disabled
										title="La suppression sera reliée au serveur ultérieurement."
									>
										Supprimer
									</button>
								</div>
							</section>

							<section class="cd-side-block">
								<h3>Tableaux existants</h3>
								<div v-if="dashboardsLoading" class="cd-state">Chargement des tableaux…</div>
								<div v-else-if="!dashboards.length" class="cd-state">Aucun tableau trouvé.</div>
								<div v-else class="cd-dashboard-list is-compact">
									<button
										v-for="dashboard in dashboardPreviewRows"
										:key="dashboard.name"
										class="cd-dashboard-row"
										:class="{ 'is-active': currentDashboard?.name === dashboard.name }"
										type="button"
										@click="openDashboard(dashboard.name)"
									>
										<div>
											<strong>{{ dashboard.title }}</strong>
											<p>{{ relativeModifiedLabel(dashboard.modified) }}</p>
										</div>
										<span class="cd-chip">{{ moduleDisplayLabel(dashboard.module_name) || "Personnel" }}</span>
									</button>
								</div>
								<button class="cd-link-button" type="button" @click="activeInspectorTab = 'dashboards'">
									Voir tous les tableaux de bord
								</button>
							</section>
						</template>
					</section>

					<section v-else-if="activeInspectorTab === 'dashboards'" class="cd-side-section">
						<div class="cd-panel-head">
							<div>
								<h2>Tableaux existants</h2>
								<p>Vos tableaux personnels, partagés et éditables.</p>
							</div>
							<span class="cd-pill">{{ dashboards.length }}</span>
						</div>

						<div v-if="dashboardsLoading" class="cd-state">Chargement des tableaux…</div>
						<div v-else-if="!dashboards.length" class="cd-state">Aucun tableau trouvé.</div>
						<div v-else class="cd-dashboard-list">
							<button
								v-for="dashboard in dashboards"
								:key="dashboard.name"
								class="cd-dashboard-row"
								:class="{ 'is-active': currentDashboard?.name === dashboard.name }"
								type="button"
								@click="openDashboard(dashboard.name)"
							>
								<div>
									<strong>{{ dashboard.title }}</strong>
									<p>
										{{ dashboard.user === currentUser ? "Moi" : `Propriétaire : ${dashboard.user}` }}
									</p>
								</div>
								<div class="cd-dashboard-flags">
									<span v-if="dashboard.is_default" class="cd-chip">Défaut</span>
									<span v-if="dashboard.is_shared" class="cd-chip">Partagé</span>
									<span v-if="dashboard.module_name" class="cd-chip">
										{{ moduleDisplayLabel(dashboard.module_name) }}
									</span>
									<span v-if="dashboard.can_write && !dashboard.is_owner" class="cd-chip">
										Modifiable
									</span>
								</div>
							</button>
						</div>

						<section class="cd-side-block cd-share-admin">
							<h3>Partage avancé</h3>
							<div v-if="!currentDashboard" class="cd-state">
								Ouvrez ou créez un tableau de bord pour gérer son partage.
							</div>
							<div v-else-if="currentDashboard.module_name" class="cd-state">
								Le tableau de bord du module {{ selectedModuleLabel }} est partagé automatiquement.
							</div>
							<div v-else-if="!currentDashboard.can_manage_sharing" class="cd-state">
								Seul le propriétaire ou un administrateur peut modifier le partage.
							</div>
							<div v-else class="cd-share-box">
								<label class="cd-toggle">
									<input v-model="currentDashboard.is_shared" type="checkbox" />
									<span>Visible pour tous les rôles autorisés</span>
								</label>

								<div class="cd-share-list">
									<div
										v-for="(share, index) in currentDashboard.shares"
										:key="share.local_id"
										class="cd-share-row"
									>
										<select v-model="share.share_type" class="form-control">
											<option value="User">Utilisateur</option>
											<option value="Role">Rôle</option>
										</select>

										<select
											v-if="share.share_type === 'User'"
											v-model="share.user"
											class="form-control"
										>
											<option value="">Choisir un utilisateur</option>
											<option
												v-for="option in sharingOptions.users"
												:key="option.value"
												:value="option.value"
											>
												{{ option.label }}
											</option>
										</select>

										<select
											v-else
											v-model="share.role"
											class="form-control"
										>
											<option value="">Choisir un rôle</option>
											<option
												v-for="option in sharingOptions.roles"
												:key="option.value"
												:value="option.value"
											>
												{{ option.label }}
											</option>
										</select>

										<label class="cd-toggle">
											<input v-model="share.can_edit" type="checkbox" />
											<span>Peut modifier</span>
										</label>

										<button
											class="btn btn-default btn-sm"
											type="button"
											@click="removeShareRow(index)"
										>
											Retirer
										</button>
									</div>
								</div>

								<div class="cd-inline-actions">
									<button class="btn btn-default btn-sm" type="button" @click="addShareRow('User')">
										Ajouter un utilisateur
									</button>
									<button class="btn btn-default btn-sm" type="button" @click="addShareRow('Role')">
										Ajouter un rôle
									</button>
								</div>
							</div>
						</section>
					</section>

					<section v-else class="cd-side-section">
						<div class="cd-panel-head">
							<div>
								<h2>Historique</h2>
								<p>Suivi sobre des états du constructeur.</p>
							</div>
						</div>

						<div class="cd-history-list">
							<div class="cd-history-row">
								<span class="cd-status-dot" :class="{ 'is-dirty': hasUnsavedChanges }"></span>
								<div>
									<strong>{{ saveStatusLabel }}</strong>
									<p>{{ currentDashboard?.name ? "Tableau déjà enregistré dans ERPNext." : "Brouillon local non enregistré." }}</p>
								</div>
							</div>
							<div class="cd-history-row">
								<span class="cd-status-dot is-saved"></span>
								<div>
									<strong>{{ orderedDashboardItems.length }} widget(s)</strong>
									<p>{{ orderedDashboardItems.length ? "Canvas prêt pour l’aperçu." : "Aucun widget ajouté." }}</p>
								</div>
							</div>
						</div>

						<section v-if="userIsAdmin" class="cd-side-block cd-admin-access">
							<div class="cd-panel-head">
								<div>
									<h2>Administration des accès</h2>
									<p>Activez les widgets et gérez leurs droits par rôle.</p>
								</div>
							</div>

						<div v-if="adminWidgetsLoading" class="cd-state">Chargement des widgets d’administration…</div>
						<div v-else class="cd-admin-shell">
							<div class="cd-admin-list">
								<button
									v-for="widget in adminWidgets"
								:key="widget.name"
								class="cd-admin-widget-row"
								:class="{ 'is-active': selectedAdminWidgetName === widget.name }"
								type="button"
								@click="selectAdminWidget(widget.name)"
							>
								<div>
									<strong>{{ widget.title }}</strong>
									<p>{{ widget.category || "Général" }}</p>
								</div>
								<span class="cd-chip" :class="{ 'is-warning': !widget.is_active }">
									{{ widget.is_active ? "Actif" : "Inactif" }}
									</span>
								</button>
							</div>

							<div v-if="adminForm" class="cd-admin-form">
								<label class="cd-toggle">
									<input v-model="adminForm.is_active" type="checkbox" />
									<span>Widget actif dans la bibliothèque</span>
								</label>

							<div class="cd-admin-description">
								<strong>{{ adminForm.title }}</strong>
								<p>{{ adminForm.description }}</p>
							</div>

							<div class="cd-admin-matrix">
								<div class="cd-admin-matrix-head">
									<span>Rôle</span>
									<span>Voir</span>
									<span>Utiliser</span>
								</div>
								<div
									v-for="roleRow in adminForm.roles"
									:key="roleRow.role"
									class="cd-admin-matrix-row"
								>
									<span>{{ roleRow.role }}</span>
									<input v-model="roleRow.can_view" type="checkbox" />
									<input v-model="roleRow.can_use" type="checkbox" />
								</div>
							</div>

							<button
								class="btn btn-primary"
								type="button"
								:disabled="adminSaving"
								@click="saveAdminWidget"
							>
									{{ adminSaving ? "Enregistrement…" : "Enregistrer les accès" }}
								</button>
							</div>
							<div v-else class="cd-state">Sélectionnez un widget pour éditer ses accès.</div>
						</div>
						</section>
						<div v-else class="cd-state">Aucun historique détaillé disponible pour le moment.</div>
					</section>
			</aside>
		</div>
	</div>
</template>

<script>
const GRID_COLUMNS = 12;
const GRID_ROW_HEIGHT = 72;
const MODULE_OPTIONS = [
	{ value: "Stock", label: "Stock" },
	{ value: "Selling", label: "Ventes" },
	{ value: "Buying", label: "Achats" },
];

const LIBRARY_FILTERS = [
	{ key: "all", label: "Tous" },
	{ key: "stock", label: "Stock", module: "Stock" },
	{ key: "selling", label: "Ventes", module: "Selling" },
	{ key: "buying", label: "Achats", module: "Buying" },
	{ key: "support", label: "Support", category: "Support" },
];

const WIDGET_DISPLAY_OVERRIDES = {
	STOCK_AGE_PROFILE: { title: "Âge du stock", priority: 1 },
	WAREHOUSE_STOCKOUT_RISK: { title: "Stock critique", priority: 2 },
	MONTHLY_REVENUE_CHART: { title: "Analyse des ventes", priority: 3 },
	SELLING_REVENUE_TREND: { title: "Analyse des ventes", priority: 3 },
	BUYING_OPEN_PURCHASE_ORDERS: { title: "Commandes en attente", priority: 4 },
	PROFITABLE_PRODUCTS: { title: "Top produits", priority: 5 },
	OVERDUE_INVOICES: { title: "Factures en retard", priority: 6 },
	SELLING_OVERDUE_INVOICES: { title: "Factures en retard", priority: 6 },
	BUYING_MONTHLY_SPEND: { title: "Répartition des achats", priority: 7 },
};

const ICONS = {
	layout:
		'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="8" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="15" width="7" height="6" rx="1.5"/></svg>',
	search:
		'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
	"panel-close":
		'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/><rect x="3" y="4" width="18" height="16" rx="2"/></svg>',
	"panel-open":
		'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/><rect x="3" y="4" width="18" height="16" rx="2"/></svg>',
	more:
		'<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/></svg>',
	donut:
		'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-9-9"/><path d="M21 12A9 9 0 0 0 12 3"/><circle cx="12" cy="12" r="3"/></svg>',
	gauge:
		'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14a8 8 0 0 1 16 0"/><path d="M12 14l4-4"/><path d="M7 18h10"/></svg>',
	line:
		'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 18h16"/><path d="M5 15l4-4 4 3 6-8"/></svg>',
	list:
		'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/></svg>',
	bar:
		'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16"/><rect x="6" y="10" width="3" height="7" rx="1"/><rect x="11" y="6" width="3" height="11" rx="1"/><rect x="16" y="13" width="3" height="4" rx="1"/></svg>',
	document:
		'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M8 13h8"/><path d="M8 17h5"/></svg>',
	"spark-layout":
		'<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><rect x="10" y="12" width="16" height="16" rx="3"/><rect x="34" y="12" width="20" height="10" rx="3"/><rect x="34" y="30" width="20" height="22" rx="3"/><rect x="10" y="36" width="16" height="16" rx="3"/><path d="M28 20h4M28 44h4"/></svg>',
};

export default {
	name: "DashboardBuilder",
	props: {
		page: {
			type: Object,
			default: null,
		},
	},
	data() {
		return {
			availableWidgets: [],
			dashboards: [],
			currentDashboard: null,
			widgetsLoading: true,
			dashboardsLoading: true,
			loadingDashboard: false,
			saving: false,
			pageError: "",
				localId: 1,
				librarySearch: "",
				activeTab: "dashboards",
				activeInspectorTab: "properties",
				activeLibraryFilter: "all",
				baselineSignature: "",
				saveSucceeded: false,
				selectedDashboardName: "",
				isLibraryCollapsed: false,
				dragState: {
				source: "",
				widgetName: "",
				itemId: null,
				width: 0,
				height: 0,
				over: null,
			},
			sharingOptions: {
				users: [],
				roles: [],
			},
			adminWidgets: [],
			adminWidgetsLoading: false,
			adminSaving: false,
			adminForm: null,
			selectedAdminWidgetName: "",
			chartInstances: {},
			isFullscreenPreview: false,
			moduleOptions: MODULE_OPTIONS,
			cameFromGlobalDashboard: false,
		};
		},
		computed: {
			libraryFilterOptions() {
				return LIBRARY_FILTERS;
			},
			gridColumns() {
				return Array.from({ length: GRID_COLUMNS }, (_, index) => index + 1);
			},
			currentUser() {
				return this.frappe.session.user;
			},
		userIsAdmin() {
			return (this.frappe.user_roles || []).some((role) =>
				["System Manager", "Dashboard Admin"].includes(role)
			);
		},
		canEditCurrent() {
			if (!this.currentDashboard) {
				return true;
				}
				return Boolean(this.currentDashboard.can_write);
			},
			dashboardTitle() {
				return this.currentDashboard?.title?.trim() || "Mon tableau de bord";
			},
			hasUnsavedChanges() {
				if (!this.currentDashboard) {
					return false;
				}
				if (!this.currentDashboard.name) {
					return true;
				}
				return this.dashboardSignature() !== this.baselineSignature;
			},
			saveStatusLabel() {
				if (this.saving) {
					return "Enregistrement en cours";
				}
				if (!this.currentDashboard) {
					return "Chargement du constructeur…";
				}
				if (this.hasUnsavedChanges) {
					return "Modifications non enregistrées";
				}
				return this.saveSucceeded ? "Enregistré" : "Enregistré";
			},
			sharingSummary() {
				if (!this.currentDashboard) {
					return "Moi uniquement";
				}
				if (this.currentDashboard.module_name) {
					return `Module ${this.selectedModuleLabel}`;
				}
				if (this.currentDashboard.is_shared) {
					return "Partage global";
				}
				if ((this.currentDashboard.shares || []).length) {
					return `${this.currentDashboard.shares.length} partage(s) ciblé(s)`;
				}
				return "Moi uniquement";
			},
			dashboardPreviewRows() {
				return this.dashboards.slice(0, 3);
			},
			dashboardSubtitle() {
				if (!this.currentDashboard) {
					return "Composez un tableau modulaire avec de vrais KPI ERPNext.";
				}
				if (this.currentDashboard.module_name) {
					return `Tableau de bord publié pour le module ${this.selectedModuleLabel}.`;
				}
				if (this.currentDashboard.user === this.currentUser) {
					return "Tableau personnel modifiable par vous.";
			}
			if (this.currentDashboard.can_write) {
				return `Tableau partagé par ${this.currentDashboard.user}, avec délégation d'édition.`;
			}
			return `Tableau partagé par ${this.currentDashboard.user}.`;
		},
		selectedModuleLabel() {
			const selected = MODULE_OPTIONS.find(
				(option) => option.value === this.currentDashboard?.module_name
			);
			return selected?.label || this.currentDashboard?.module_name || "";
		},
			filteredWidgets() {
				const search = (this.librarySearch || "").toLowerCase();
				const selectedModule = this.currentDashboard?.module_name || "";
				const selectedFilter = LIBRARY_FILTERS.find((filter) => filter.key === this.activeLibraryFilter);
				const seen = new Set();
				return this.availableWidgets.filter((widget) => {
					if (selectedModule && widget.module_name !== selectedModule) {
						return false;
					}
					if (selectedFilter && selectedFilter.key !== "all" && !this.matchesLibraryFilter(widget, selectedFilter)) {
						return false;
					}
					const uniqueKey = `${widget.module_name || "general"}:${widget.canonical_name || widget.name}`;
					if (seen.has(uniqueKey)) {
						return false;
				}
				seen.add(uniqueKey);
				if (!search) {
					return true;
				}
					return [widget.title, widget.description, widget.category, widget.name, widget.module_label]
						.filter(Boolean)
						.some((value) => String(value).toLowerCase().includes(search));
				}).sort((a, b) => this.widgetPriority(a) - this.widgetPriority(b) || this.widgetDisplayTitle(a).localeCompare(this.widgetDisplayTitle(b)));
			},
		groupedWidgets() {
			const groups = new Map();
			for (const widget of this.filteredWidgets) {
				const key = widget.module_name || "general";
				if (!groups.has(key)) {
					groups.set(key, {
						key,
						label: this.moduleLabel(key === "general" ? "" : key),
						order: this.moduleOrder(key === "general" ? "" : key),
						widgets: [],
					});
				}
				groups.get(key).widgets.push(widget);
			}
			return [...groups.values()].sort((a, b) => a.order - b.order || a.label.localeCompare(b.label));
		},
		orderedDashboardItems() {
			if (!this.currentDashboard?.items) {
				return [];
			}
			return [...this.currentDashboard.items].sort((a, b) => a.y - b.y || a.x - b.x);
		},
			canvasRows() {
				const itemRows = this.orderedDashboardItems.map((item) => item.y + item.h);
				const dragRows = this.dragState.over ? [this.dragState.over.y + this.dragState.over.h] : [];
				return Math.max(10, ...itemRows, ...dragRows);
			},
		canvasStyle() {
			return {
				gridTemplateColumns: `repeat(${GRID_COLUMNS}, minmax(0, 1fr))`,
				gridAutoRows: `${GRID_ROW_HEIGHT}px`,
				minHeight: `${this.canvasRows * GRID_ROW_HEIGHT}px`,
			};
		},
	},
	async mounted() {
		this.detectGlobalDashboardSource();
		await this.loadInitialState();
		window.addEventListener("keydown", this.onFullscreenKeydown);
	},
	beforeUnmount() {
		this.destroyCharts();
		window.removeEventListener("keydown", this.onFullscreenKeydown);
		if (this.isFullscreenPreview) {
			document.body.classList.remove("cd-fullscreen-open");
		}
		},
		methods: {
			iconSvg(name) {
				return ICONS[name] || ICONS.layout;
			},
			matchesLibraryFilter(widget, filter) {
				if (filter.module) {
					return widget.module_name === filter.module;
				}
				const haystack = [widget.category, widget.module_label, widget.title, widget.description]
					.filter(Boolean)
					.join(" ")
					.toLowerCase();
				return haystack.includes((filter.category || "").toLowerCase());
			},
			widgetDisplayTitle(widget) {
				return WIDGET_DISPLAY_OVERRIDES[widget.name]?.title || widget.title || "Widget";
			},
			widgetPriority(widget) {
				return WIDGET_DISPLAY_OVERRIDES[widget.name]?.priority || 99;
			},
			widgetTypeLabel(widget) {
				const chartType = widget.chart_options?.chart_type;
				if (chartType === "donut") {
					return "Donut";
				}
				if (chartType === "line") {
					return "Courbe";
				}
				if (chartType === "bar") {
					return "Barres";
				}
				if (widget.widget_type === "number_card") {
					return "KPI";
				}
				if (widget.widget_type === "table") {
					return "Liste";
				}
				if (widget.widget_type === "ai_insight") {
					return "IA";
				}
				if (widget.widget_type === "chart") {
					return "Graphique";
				}
				return "Widget";
			},
			widgetMetaLabel(widget) {
				return `${this.widgetTypeLabel(widget)} · ${widget.default_w || 3} × ${widget.default_h || 2}`;
			},
			widgetIconName(widget) {
				const type = this.widgetTypeLabel(widget);
				if (type === "Donut") return "donut";
				if (type === "KPI") return "gauge";
				if (type === "Courbe") return "line";
				if (type === "Liste") return "list";
				if (type === "Barres") return "bar";
				if ((widget.icon || "").includes("file") || this.widgetDisplayTitle(widget).toLowerCase().includes("facture")) {
					return "document";
				}
				return "bar";
			},
			widgetToneClass(widget) {
				const moduleName = widget.module_name || "";
				if (moduleName === "Stock") return "is-stock";
				if (moduleName === "Selling") return "is-selling";
				if (moduleName === "Buying") return "is-buying";
				return "is-general";
			},
			dashboardSignature() {
				if (!this.currentDashboard) {
					return "";
				}
				const payload = {
					title: this.currentDashboard.title || "",
					module_name: this.currentDashboard.module_name || "",
					is_default: Boolean(this.currentDashboard.is_default),
					is_shared: Boolean(this.currentDashboard.is_shared),
					shares: (this.currentDashboard.shares || []).map((share) => ({
						share_type: share.share_type,
						user: share.user || "",
						role: share.role || "",
						can_edit: Boolean(share.can_edit),
					})),
					items: (this.currentDashboard.items || []).map((item) => ({
						widget: item.widget,
						x: item.x,
						y: item.y,
						w: item.w,
						h: item.h,
						display_title: item.display_title,
						filters: this.serializeItemFilters(item),
					})),
				};
				return JSON.stringify(payload);
			},
			rememberDashboardState() {
				this.baselineSignature = this.dashboardSignature();
				this.saveSucceeded = false;
			},
			relativeModifiedLabel(value) {
				if (!value) {
					return "Modification récente";
				}
				const modified = new Date(value);
				if (Number.isNaN(modified.getTime())) {
					return "Modification récente";
				}
				const diffMs = Date.now() - modified.getTime();
				const diffDays = Math.max(0, Math.floor(diffMs / 86400000));
				if (diffDays === 0) {
					return "Modifié aujourd’hui";
				}
				if (diffDays === 1) {
					return "Modifié hier";
				}
				return `Modifié il y a ${diffDays} jours`;
			},
			handleDashboardSelect() {
				if (!this.selectedDashboardName) {
					return;
				}
				this.openDashboard(this.selectedDashboardName);
			},
			moduleDisplayLabel(moduleName) {
				const option = MODULE_OPTIONS.find((o) => o.value === moduleName);
				return option ? option.label : moduleName;
		},
		detectGlobalDashboardSource() {
			// Lit le paramètre `source` de l'URL pour adapter l'affichage quand
			// l'utilisateur arrive depuis le tableau de bord global.
			try {
				const search = window.location.search || "";
				const params = new URLSearchParams(search);
				if (params.get("source") === "global") {
					this.cameFromGlobalDashboard = true;
				}
				// Frappe peut aussi pousser des options de route via frappe.route_options
				const routeOptions = window.frappe?.route_options || {};
				if (routeOptions && routeOptions.source === "global") {
					this.cameFromGlobalDashboard = true;
				}
			} catch (e) {
				this.cameFromGlobalDashboard = false;
			}
		},
		async loadInitialState() {
			this.pageError = "";
			try {
				await Promise.all([
					this.loadWidgets(),
					this.loadDashboards(),
					this.loadSharingOptions(),
					this.userIsAdmin ? this.loadAdminWidgets() : Promise.resolve(),
				]);
				if (this.dashboards.length) {
					const preferredDashboard =
						this.dashboards.find(
							(dashboard) => dashboard.is_default && dashboard.user === this.currentUser
						) || this.dashboards[0];
					await this.openDashboard(preferredDashboard.name);
				} else {
					this.createDashboard(false);
				}
			} catch (error) {
					this.pageError = this.parseError(
						error,
						"Impossible de charger le tableau de bord."
					);
			}
		},
		async loadWidgets() {
			this.widgetsLoading = true;
			try {
				this.availableWidgets =
					(await this.frappe.xcall("custom_dashboard.api.widget.list_available_widgets")) || [];
			} finally {
				this.widgetsLoading = false;
			}
		},
		async loadDashboards() {
			this.dashboardsLoading = true;
			try {
				this.dashboards =
					(await this.frappe.xcall("custom_dashboard.api.dashboard.list_user_dashboards")) || [];
			} finally {
				this.dashboardsLoading = false;
			}
		},
		async loadSharingOptions() {
			this.sharingOptions =
				(await this.frappe.xcall("custom_dashboard.api.dashboard.get_sharing_options")) || {
					users: [],
					roles: [],
				};
		},
		async loadAdminWidgets() {
			this.adminWidgetsLoading = true;
			try {
				this.adminWidgets =
					(await this.frappe.xcall("custom_dashboard.api.widget.list_admin_widgets")) || [];
				if (!this.selectedAdminWidgetName && this.adminWidgets.length) {
					await this.selectAdminWidget(this.adminWidgets[0].name);
				}
			} finally {
				this.adminWidgetsLoading = false;
			}
		},
		async selectAdminWidget(name) {
			this.selectedAdminWidgetName = name;
			this.adminForm = await this.frappe.xcall(
				"custom_dashboard.api.widget.get_widget_admin_definition",
				{ widget_name: name }
			);
			this.adminForm.is_active = Boolean(this.adminForm.is_active);
			this.adminForm.roles = (this.adminForm.roles || []).map((row) => ({
				role: row.role,
				can_view: Boolean(row.can_view),
				can_use: Boolean(row.can_use),
			}));
		},
		async saveAdminWidget() {
			if (!this.adminForm) {
				return;
			}
			this.adminSaving = true;
			try {
				this.adminForm = await this.frappe.xcall("custom_dashboard.api.widget.save_widget_access", {
					doc: {
						name: this.adminForm.name,
						is_active: this.adminForm.is_active ? 1 : 0,
						description: this.adminForm.description,
						roles: this.adminForm.roles.map((row) => ({
							role: row.role,
							can_view: row.can_view ? 1 : 0,
							can_use: row.can_use ? 1 : 0,
						})),
					},
				});
				this.adminForm.is_active = Boolean(this.adminForm.is_active);
				this.adminForm.roles = (this.adminForm.roles || []).map((row) => ({
					role: row.role,
					can_view: Boolean(row.can_view),
					can_use: Boolean(row.can_use),
				}));
				await Promise.all([this.loadAdminWidgets(), this.loadWidgets()]);
				if (this.currentDashboard?.name) {
					await this.openDashboard(this.currentDashboard.name);
				}
				this.notify("Les accès du widget ont été enregistrés.", "green");
			} catch (error) {
				this.pageError = this.parseError(
					error,
					"Impossible d'enregistrer les accès du widget."
				);
			} finally {
				this.adminSaving = false;
			}
		},
		normalizeDashboard(doc) {
			return {
				doctype: "User Dashboard",
				name: doc.name || null,
				title: doc.title || "Nouveau tableau de bord",
				user: doc.user || this.currentUser,
				module_name: doc.module_name || "",
				is_default: Boolean(doc.is_default),
				is_shared: Boolean(doc.is_shared),
				can_write: doc.can_write !== false && doc.can_write !== 0,
				can_manage_sharing:
					doc.can_manage_sharing !== false && doc.can_manage_sharing !== 0,
				is_owner: Boolean(doc.is_owner),
				items: (doc.items || []).map((item) => this.normalizeItem(item)),
				shares: (doc.shares || []).map((share) => this.normalizeShareRow(share)),
			};
		},
		syncModuleFlags() {
			if (!this.currentDashboard?.module_name) {
				return;
			}
			this.currentDashboard.is_default = true;
			this.currentDashboard.is_shared = true;
		},
		moduleLabel(moduleName) {
			const selected = MODULE_OPTIONS.find((option) => option.value === moduleName);
			return selected?.label || moduleName || "Général";
		},
		moduleOrder(moduleName) {
			if (!moduleName) {
				return 99;
			}
			const index = MODULE_OPTIONS.findIndex((option) => option.value === moduleName);
			return index >= 0 ? index : 98;
		},
		itemModuleName(item) {
			if (item.definition?.module_name !== undefined) {
				return item.definition.module_name || "";
			}
			const widget = this.availableWidgets.find((entry) => entry.name === item.widget);
			return widget?.module_name || "";
		},
		validateModuleItems() {
			const moduleName = this.currentDashboard?.module_name || "";
			if (!moduleName) {
				return;
			}
			const invalidItems = (this.currentDashboard.items || []).filter(
				(item) => this.itemModuleName(item) !== moduleName
			);
			if (!invalidItems.length) {
				return;
			}
			const labels = invalidItems
				.map((item) => item.display_title || item.definition?.title || item.widget)
				.join(", ");
			this.frappe.throw(
				`Ces widgets ne sont pas disponibles pour le module ${this.selectedModuleLabel}: ${labels}.`
			);
		},
		normalizeShareRow(row = {}) {
			return {
				local_id: this.localId++,
				name: row.name || null,
				share_type: row.share_type || "User",
				user: row.user || "",
				role: row.role || "",
				can_edit: Boolean(row.can_edit),
			};
		},
		parseFilters(value, definition) {
			let parsed = {};
			if (value) {
				try {
					parsed = typeof value === "string" ? JSON.parse(value) : value || {};
				} catch {
					parsed = {};
				}
			}
			return {
				...(definition?.default_filters || {}),
				...(parsed || {}),
			};
		},
		normalizeItem(item) {
			const widgetDefinition =
				item.widget_definition || this.availableWidgets.find((widget) => widget.name === item.widget);
			const minimumSize = this.getMinimumWidgetSize(widgetDefinition);
			return {
				local_id: this.localId++,
				name: item.name || null,
				widget: item.widget,
				x: Number(item.x || 0),
				y: Number(item.y || 0),
				w: Math.max(Number(item.w || widgetDefinition?.default_w || 6), minimumSize.w),
				h: Math.max(Number(item.h || widgetDefinition?.default_h || 4), minimumSize.h),
				display_title: item.display_title || widgetDefinition?.title || item.widget,
				definition: widgetDefinition || null,
				filters_json: item.filters_json || "",
				filters: this.parseFilters(item.filters_json, widgetDefinition),
				filtersCollapsed: false,
				preview: null,
				loading: false,
				error: "",
				aiRegenerating: false,
			};
		},
		getMinimumWidgetSize(definition) {
			const widgetType = definition?.widget_type || "custom";
			const allowFilters = Boolean(definition?.allow_filters);

			if (widgetType === "table") {
				return { w: 5, h: allowFilters ? 5 : 4 };
			}

			if (widgetType === "chart") {
				return { w: allowFilters ? 5 : 4, h: allowFilters ? 4 : 3 };
			}

			if (widgetType === "number_card") {
				return { w: allowFilters ? 3 : 2, h: allowFilters ? 3 : 2 };
			}

			if (widgetType === "ai_insight") {
				return { w: 6, h: allowFilters ? 7 : 6 };
			}

			return { w: allowFilters ? 4 : 3, h: allowFilters ? 3 : 2 };
		},
		getSuggestedWidgetSize(definition) {
			const minimumSize = this.getMinimumWidgetSize(definition);
			const widgetType = definition?.widget_type || "custom";
			const suggestedCap = {
				table: { w: 6, h: 5 },
				chart: { w: 5, h: 4 },
				number_card: { w: 3, h: 3 },
				ai_insight: { w: 8, h: 7 },
				custom: { w: 4, h: 3 },
			};
			const cap = suggestedCap[widgetType] || suggestedCap.custom;
			const defaultW = Number(definition?.default_w || 0) || cap.w;
			const defaultH = Number(definition?.default_h || 0) || cap.h;
			return {
				w: Math.max(minimumSize.w, Math.min(defaultW, cap.w)),
				h: Math.max(minimumSize.h, Math.min(defaultH, cap.h)),
			};
		},
		isCompactWidget(item) {
			return item.w <= 4 || item.h <= 3;
		},
		createDashboard(copyCurrent = true) {
			const sourceTitle = this.currentDashboard?.title || "Mon tableau";
			const hasPersonalDashboards = this.dashboards.some(
				(dashboard) => dashboard.user === this.currentUser
			);
			const moduleName = this.userIsAdmin
				? copyCurrent
					? this.currentDashboard?.module_name || ""
					: ""
				: copyCurrent
					? this.currentDashboard?.module_name || ""
					: "";
			const items =
				copyCurrent && this.currentDashboard?.items?.length
					? this.currentDashboard.items.map((item) =>
							this.normalizeItem({
								widget: item.widget,
								x: item.x,
								y: item.y,
								w: item.w,
								h: item.h,
								display_title: item.display_title,
								filters_json: this.serializeItemFilters(item),
								widget_definition: item.definition,
							})
					  )
					: [];
				this.currentDashboard = {
					doctype: "User Dashboard",
					name: null,
				title: copyCurrent ? `${sourceTitle} - copie` : "Mon tableau de bord",
				user: this.currentUser,
				module_name: moduleName,
				is_default: moduleName ? false : !hasPersonalDashboards,
				is_shared: Boolean(moduleName),
				can_write: true,
				can_manage_sharing: true,
				is_owner: true,
				items,
					shares: [],
				};
				this.selectedDashboardName = "";
				this.baselineSignature = this.dashboardSignature();
				this.saveSucceeded = false;
				this.clearDragState();
				this.$nextTick(() => this.renderAllCharts());
			},
		addShareRow(shareType = "User") {
			if (!this.currentDashboard) {
				return;
			}
			this.currentDashboard.shares.push(
				this.normalizeShareRow({
					share_type: shareType,
				})
			);
		},
		removeShareRow(index) {
			this.currentDashboard.shares.splice(index, 1);
		},
		addWidget(widget) {
			const nextY = this.nextAvailableRow();
			const suggestedSize = this.getSuggestedWidgetSize(widget);
			this.addWidgetAt(widget, { x: 0, y: nextY, w: suggestedSize.w, h: suggestedSize.h });
		},
		addWidgetAt(widget, target = {}) {
			if (!widget?.can_use) {
				this.notify("Ce widget est visible mais non utilisable pour votre rôle.", "orange");
				return;
			}
			if (!this.currentDashboard) {
				this.createDashboard(false);
			}
			if (!this.canEditCurrent) {
				this.notifyReadonly();
				return;
			}
			const dashboardItem = this.normalizeItem({
				widget: widget.name,
				x: Number(target.x || 0),
				y: Number(target.y || this.nextAvailableRow()),
				w: Number(target.w || widget.default_w || 6),
				h: Number(target.h || widget.default_h || 4),
				display_title: widget.title,
				widget_definition: widget,
				filters_json: JSON.stringify(widget.default_filters || {}),
			});
			this.currentDashboard.items.push(dashboardItem);
			this.reflowLayout(dashboardItem.local_id);
			this.refreshItem(dashboardItem);
		},
		removeItem(localId) {
			if (!this.canEditCurrent) {
				this.notifyReadonly();
				return;
			}
			const index = this.currentDashboard.items.findIndex((item) => item.local_id === localId);
			if (index >= 0) {
				const [removed] = this.currentDashboard.items.splice(index, 1);
				this.destroyChart(removed.local_id);
				this.reflowLayout();
			}
		},
		async openDashboard(name) {
			this.loadingDashboard = true;
			this.pageError = "";
			try {
				const doc = await this.frappe.xcall("custom_dashboard.api.dashboard.get_dashboard", {
					name,
					});
				this.currentDashboard = this.normalizeDashboard(doc);
				await this.refreshAllItems();
				this.selectedDashboardName = name;
				this.activeInspectorTab = "properties";
				this.rememberDashboardState();
			} catch (error) {
				this.pageError = this.parseError(error, "Impossible de charger le tableau sélectionné.");
			} finally {
				this.loadingDashboard = false;
			}
		},
		async saveDashboard() {
			if (!this.currentDashboard) {
				return;
			}
			this.syncModuleFlags();
			if (!this.canEditCurrent) {
				this.notifyReadonly();
				return;
			}
			if (!this.currentDashboard.title?.trim()) {
				this.frappe.throw("Le titre du tableau de bord est obligatoire.");
			}
			this.validateModuleItems();
			this.saving = true;
			this.pageError = "";
			try {
				const payload = {
					doctype: "User Dashboard",
					name: this.currentDashboard.name,
					title: this.currentDashboard.title,
					user: this.currentDashboard.user,
					module_name: this.currentDashboard.module_name || "",
					is_default:
						this.currentDashboard.module_name ? 1 : this.currentDashboard.is_default ? 1 : 0,
					is_shared:
						this.currentDashboard.module_name ? 1 : this.currentDashboard.is_shared ? 1 : 0,
					shares: (this.currentDashboard.shares || []).map((share) => ({
						share_type: share.share_type,
						user: share.user,
						role: share.role,
						can_edit: share.can_edit ? 1 : 0,
					})),
					items: this.currentDashboard.items.map((item) => ({
						widget: item.widget,
						x: item.x,
						y: item.y,
						w: item.w,
						h: item.h,
						display_title: item.display_title,
						filters_json: this.serializeItemFilters(item),
					})),
				};
				const savedDashboard = await this.frappe.xcall(
					"custom_dashboard.api.dashboard.save_user_dashboard",
					{ doc: payload }
				);
					this.currentDashboard = this.normalizeDashboard(savedDashboard);
					this.markModuleDashboardAvailable(savedDashboard.module_name);
					await Promise.all([this.refreshAllItems(), this.loadDashboards()]);
					this.selectedDashboardName = this.currentDashboard.name || "";
					this.baselineSignature = this.dashboardSignature();
					this.saveSucceeded = true;
					this.notify("Le tableau de bord a été enregistré.", "green");
			} catch (error) {
				this.pageError = this.parseError(error, "Impossible d'enregistrer le tableau.");
			} finally {
				this.saving = false;
			}
		},
		markModuleDashboardAvailable(moduleName) {
			if (!moduleName) {
				return;
			}
			this.frappe.boot.custom_dashboard_modules =
				this.frappe.boot.custom_dashboard_modules || {};
			this.frappe.boot.custom_dashboard_modules[moduleName] = true;
			document.dispatchEvent(
				new CustomEvent("custom_dashboard:module-dashboard-saved", {
					detail: { module_name: moduleName },
				})
			);
		},
			async reloadCurrent() {
				if (!this.currentDashboard) {
					await this.loadInitialState();
					return;
			}
			if (this.currentDashboard.name) {
				await this.openDashboard(this.currentDashboard.name);
				return;
				}
				await this.refreshAllItems();
			},
			async previewDashboard() {
				if (!this.currentDashboard) {
					this.notify("Action impossible : aucun tableau de bord ouvert.", "orange");
					return;
				}
				if (!this.orderedDashboardItems.length) {
					this.notify("Aucun widget ajouté.", "orange");
					return;
				}
				await this.refreshAllItems();
				this.notify("Aperçu actualisé.", "blue");
			},
			resetDashboardLayout() {
				if (!this.currentDashboard || !this.canEditCurrent) {
					this.notifyReadonly();
					return;
				}
				if (!this.currentDashboard.items.length) {
					this.notify("Aucun widget ajouté.", "orange");
					return;
				}
				const reset = () => {
					this.destroyCharts();
					this.currentDashboard.items = [];
					this.saveSucceeded = false;
					this.notify("Tableau de bord réinitialisé.", "orange");
				};
				if (this.frappe.confirm) {
					this.frappe.confirm("Réinitialiser les widgets de ce tableau de bord ?", reset);
				} else {
					reset();
				}
			},
			async refreshAllItems() {
				if (!this.currentDashboard?.items?.length) {
					this.destroyCharts();
				return;
			}
			await Promise.all(this.currentDashboard.items.map((item) => this.refreshItem(item)));
			this.$nextTick(() => this.renderAllCharts());
		},
		async refreshItem(item) {
			item.loading = true;
			item.error = "";
			try {
				if (!item.definition) {
					item.definition = await this.frappe.xcall(
						"custom_dashboard.api.widget.get_widget_definition",
						{ widget_name: item.widget }
					);
				}
				if (!item.definition?.can_use) {
					item.preview = null;
					return;
				}
				item.preview = await this.frappe.xcall("custom_dashboard.api.widget.get_widget_data", {
					widget_name: item.widget,
					filters: this.serializeItemFilters(item),
				});
			} catch (error) {
				item.error = this.parseError(error, "Impossible de charger ce widget.");
			} finally {
				item.loading = false;
				this.$nextTick(() => this.renderAllCharts());
			}
		},
		resetItemFilters(item) {
			item.filters = { ...(item.definition?.default_filters || {}) };
			this.refreshItem(item);
		},
		applyItemFilters(item) {
			item.filtersCollapsed = true;
			this.refreshItem(item);
		},
		toggleItemFilters(item) {
			item.filtersCollapsed = !item.filtersCollapsed;
			if (!item.filtersCollapsed) {
				this.$nextTick(() => this.renderAllCharts());
			}
		},
		itemFilterSummary(item) {
			const fields = this.visibleFilterFields(item);
			const entries = [];
			for (const field of fields) {
				const raw = item.filters?.[field.fieldname];
				if (raw === "" || raw === null || raw === undefined) {
					continue;
				}
				let label = raw;
				if (field.fieldtype === "Select" && Array.isArray(field.options)) {
					const match = field.options.find((opt) => opt.value === raw);
					if (match) {
						label = match.label;
					}
				}
				if (field.fieldtype === "Check") {
					label = raw ? "Oui" : "Non";
				}
				entries.push(`${field.label}: ${label}`);
			}
			if (!entries.length) {
				return "Filtres par défaut";
			}
			return entries.slice(0, 3).join(" · ") + (entries.length > 3 ? " …" : "");
		},
		serializeItemFilters(item) {
			const result = {};
			for (const field of item.definition?.filters_schema || []) {
				const value = item.filters[field.fieldname];
				if (value === "" || value === null || value === undefined) {
					continue;
				}
				result[field.fieldname] = field.fieldtype === "Check" ? (value ? 1 : 0) : value;
			}
			return Object.keys(result).length ? JSON.stringify(result) : "";
		},
		visibleFilterFields(item) {
			return (item.definition?.filters_schema || []).filter((field) =>
				this.isFieldVisible(field, item.filters)
			);
		},
		isFieldVisible(field, filters) {
			if (!field.visible_when) {
				return true;
			}
			return Object.entries(field.visible_when).every(([fieldname, expected]) => {
				if (Array.isArray(expected)) {
					return expected.includes(filters[fieldname]);
				}
				return filters[fieldname] === expected;
			});
		},
		gridItemStyle(item) {
			return {
				gridColumn: `${item.x + 1} / span ${item.w}`,
				gridRow: `${item.y + 1} / span ${item.h}`,
			};
		},
		nextAvailableRow() {
			if (!this.currentDashboard?.items?.length) {
				return 0;
			}
			return this.currentDashboard.items.reduce(
				(maxY, item) => Math.max(maxY, Number(item.y) + Number(item.h)),
				0
			);
		},
		onLibraryDragStart(event, widget) {
			if (!widget.can_use || !this.canEditCurrent) {
				event.preventDefault();
				return;
			}
			const suggestedSize = this.getSuggestedWidgetSize(widget);
			this.dragState = {
				source: "library",
				widgetName: widget.name,
				itemId: null,
				width: suggestedSize.w,
				height: suggestedSize.h,
				over: null,
			};
			event.dataTransfer.effectAllowed = "copy";
			event.dataTransfer.setData("text/plain", widget.name);
		},
		onItemDragStart(event, item) {
			if (!this.canEditCurrent || !item.definition?.can_use) {
				event.preventDefault();
				return;
			}
			this.dragState = {
				source: "canvas",
				widgetName: item.widget,
				itemId: item.local_id,
				width: item.w,
				height: item.h,
				over: { x: item.x, y: item.y, w: item.w, h: item.h },
			};
			event.dataTransfer.effectAllowed = "move";
			event.dataTransfer.setData("text/plain", item.widget);
		},
		onGridDragOver(event) {
			if (!this.dragState.source) {
				return;
			}
			this.dragState.over = this.computeDropTarget(
				event,
				this.dragState.width || 6,
				this.dragState.height || 4
			);
		},
		onGridDragLeave(event) {
			if (event.currentTarget?.contains(event.relatedTarget)) {
				return;
			}
			if (this.dragState.source) {
				this.dragState.over = null;
			}
		},
		onGridDrop(event) {
			if (!this.dragState.source) {
				return;
			}
			const target =
				this.dragState.over ||
				this.computeDropTarget(
					event,
					this.dragState.width || 6,
					this.dragState.height || 4
				);
			if (this.dragState.source === "library") {
				const widget = this.availableWidgets.find(
					(entry) => entry.name === this.dragState.widgetName
				);
				if (widget) {
					this.addWidgetAt(widget, target);
				}
			} else if (this.dragState.source === "canvas") {
				this.moveItemTo(this.dragState.itemId, target);
			}
			this.clearDragState();
		},
		clearDragState() {
			this.dragState = {
				source: "",
				widgetName: "",
				itemId: null,
				width: 0,
				height: 0,
				over: null,
			};
		},
		computeDropTarget(event, width, height) {
			const canvas = this.$refs.gridCanvas;
			if (!canvas) {
				return { x: 0, y: this.nextAvailableRow(), w: width, h: height };
			}
			const rect = canvas.getBoundingClientRect();
			const colWidth = rect.width / GRID_COLUMNS || 1;
			const x = Math.max(
				0,
				Math.min(GRID_COLUMNS - width, Math.floor((event.clientX - rect.left) / colWidth))
			);
			const y = Math.max(0, Math.floor((event.clientY - rect.top) / GRID_ROW_HEIGHT));
			return { x, y, w: width, h: height };
		},
		moveItemTo(localId, target) {
			const item = this.currentDashboard?.items?.find((entry) => entry.local_id === localId);
			if (!item) {
				return;
			}
			item.x = target.x;
			item.y = target.y;
			this.reflowLayout(localId);
			this.$nextTick(() => this.renderAllCharts());
		},
		changeItemSize(item, axis, delta) {
			if (!this.canEditCurrent) {
				this.notifyReadonly();
				return;
			}
			const minimumSize = this.getMinimumWidgetSize(item.definition);
			if (axis === "w") {
				item.w = Math.max(minimumSize.w, Math.min(GRID_COLUMNS, item.w + delta));
				item.x = Math.min(item.x, GRID_COLUMNS - item.w);
			} else {
				item.h = Math.max(minimumSize.h, item.h + delta);
			}
			this.reflowLayout(item.local_id);
			this.$nextTick(() => this.renderAllCharts());
		},
		reflowLayout(priorityId = null) {
			if (!this.currentDashboard?.items?.length) {
				return;
			}
			const items = [...this.currentDashboard.items];
			const ordered = [
				...items
					.filter((item) => item.local_id === priorityId)
					.sort((a, b) => a.y - b.y || a.x - b.x),
				...items
					.filter((item) => item.local_id !== priorityId)
					.sort((a, b) => a.y - b.y || a.x - b.x),
			];
			const placed = [];
			for (const item of ordered) {
				const minimumSize = this.getMinimumWidgetSize(item.definition);
				item.w = Math.max(minimumSize.w, Math.min(GRID_COLUMNS, item.w || 6));
				item.h = Math.max(minimumSize.h, item.h || 4);
				item.x = Math.max(0, Math.min(GRID_COLUMNS - item.w, item.x || 0));
				item.y = Math.max(0, item.y || 0);
				while (placed.some((other) => this.itemsOverlap(item, other))) {
					item.y += 1;
				}
				placed.push(item);
			}
			const compacted = [...placed].sort((a, b) => a.y - b.y || a.x - b.x);
			for (const item of compacted) {
				const minimumSize = this.getMinimumWidgetSize(item.definition);
				item.w = Math.max(item.w, minimumSize.w);
				item.h = Math.max(item.h, minimumSize.h);
				while (item.y > 0) {
					const candidate = { ...item, y: item.y - 1 };
					if (
						compacted.some(
							(other) => other.local_id !== item.local_id && this.itemsOverlap(candidate, other)
						)
					) {
						break;
					}
					item.y -= 1;
				}
			}
		},
		itemsOverlap(a, b) {
			return !(
				a.x + a.w <= b.x ||
				b.x + b.w <= a.x ||
				a.y + a.h <= b.y ||
				b.y + b.h <= a.y
			);
		},
		itemType(item) {
			return item.preview?.type || item.definition?.widget_type || "custom";
		},
		itemPayload(item) {
			return item.preview?.data || {};
		},
		formatNumberCardValue(item) {
			const payload = this.itemPayload(item);
			if (payload.currency) {
				return this.formatCurrency(payload.value, payload.currency);
			}
			return this.formatNumber(payload.value);
		},
		numberCardLabel(item) {
			const payload = this.itemPayload(item);
			return payload.label || item.display_title || item.definition?.title || item.widget;
		},
		numberCardSecondary(item) {
			const payload = this.itemPayload(item);
			if (payload.secondary_value === undefined || payload.secondary_value === null) {
				return "";
			}
			return `${this.formatNumber(payload.secondary_value)} ${payload.secondary_label || ""}`.trim();
		},
		getTableColumns(item) {
			const columns = this.itemPayload(item).columns || [];
			return columns.map((column, index) => {
				if (typeof column === "string") {
					return { key: column, label: column, type: "Data", index };
				}
				return {
					key: column.key || `col_${index}`,
					label: column.label || column.key || `Colonne ${index + 1}`,
					type: column.type || "Data",
					currency: column.currency || "",
					index,
				};
			});
		},
		getTableRows(item) {
			const rows = this.itemPayload(item).rows || [];
			const columns = this.getTableColumns(item);
			return rows.map((row) => {
				if (Array.isArray(row)) {
					const payload = {};
					for (const column of columns) {
						payload[column.key] = row[column.index];
					}
					return payload;
				}
				return row;
			});
		},
		formatTableCell(row, column) {
			const value = row[column.key];
			if (column.type === "Currency") {
				return this.formatCurrency(value, column.currency);
			}
			if (column.type === "Int") {
				return this.formatNumber(value);
			}
			return value ?? "";
		},
		chartSummaryLabel(item) {
			return itemPayloadSafe(item).summary?.label || "Aperçu du graphique";
		},
		chartSummaryValue(item) {
			const summary = itemPayloadSafe(item).summary || {};
			if (summary.currency) {
				return this.formatCurrency(summary.value, summary.currency);
			}
			return summary.value !== undefined ? this.formatNumber(summary.value) : "";
		},
		formatJson(value) {
			return JSON.stringify(value || {}, null, 2);
		},
		aiPayload(item) {
			return item.preview?.data || {};
		},
		severityLabel(value) {
			const v = String(value || "medium").toLowerCase();
			if (v === "high") return "Haute";
			if (v === "low") return "Faible";
			return "Moyenne";
		},
		formatGeneratedAt(item) {
			const ts = this.aiPayload(item).generated_at;
			if (!ts) return "";
			try {
				const d = new Date(ts);
				return d.toLocaleString("fr-FR", {
					hour: "2-digit",
					minute: "2-digit",
					day: "2-digit",
					month: "2-digit",
				});
			} catch {
				return ts;
			}
		},
		async regenerateAi(item) {
			if (item.aiRegenerating) return;
			item.aiRegenerating = true;
			item.error = "";
			try {
				const baseFilters = { ...(item.filters || {}) };
				const filtersPayload = JSON.stringify({ ...baseFilters, force_refresh: 1 });
				item.preview = await this.frappe.xcall(
					"custom_dashboard.api.widget.get_widget_data",
					{ widget_name: item.widget, filters: filtersPayload }
				);
			} catch (error) {
					item.error = this.parseError(error, "Impossible de régénérer l’analyse.");
			} finally {
				item.aiRegenerating = false;
			}
		},
		formatNumber(value) {
			return new Intl.NumberFormat("fr-FR", {
				maximumFractionDigits: 0,
			}).format(Number(value || 0));
		},
		formatCurrency(value, currency) {
			if (typeof window.format_currency === "function") {
				return window.format_currency(Number(value || 0), currency || "USD");
			}
			return new Intl.NumberFormat("fr-FR", {
				style: "currency",
				currency: currency || "USD",
				maximumFractionDigits: 0,
			}).format(Number(value || 0));
		},
		renderAllCharts() {
			for (const item of this.orderedDashboardItems) {
				if (this.itemType(item) === "chart") {
					this.renderChart(item);
				}
			}
		},
		renderChart(item) {
			const payload = this.itemPayload(item);
			const labels = Array.isArray(payload.labels) ? payload.labels : [];
			const datasets = Array.isArray(payload.datasets) ? payload.datasets : [];
			if (!labels.length || !datasets.length) {
				this.destroyChart(item.local_id);
				return;
			}
			const rawRef = this.$refs[`chart_${item.local_id}`];
			const element = Array.isArray(rawRef) ? rawRef[0] : rawRef;
			if (!element || !window.frappe?.Chart) {
				return;
			}
			this.destroyChart(item.local_id);
			element.innerHTML = "";
			const chartOptions = item.definition?.chart_options || {};
			this.chartInstances[item.local_id] = new window.frappe.Chart(element, {
				title: "",
				data: {
					labels,
					datasets,
				},
				type: payload.chart_type || chartOptions.chart_type || "bar",
				height: chartOptions.height || 200,
				colors: payload.colors || chartOptions.colors || undefined,
				lineOptions: { regionFill: 1, spline: 0 },
				axisOptions: { xIsSeries: true },
			});
		},
		destroyChart(localId) {
			const chart = this.chartInstances[localId];
			if (chart?.destroy) {
				chart.destroy();
			}
			delete this.chartInstances[localId];
		},
		destroyCharts() {
			Object.keys(this.chartInstances).forEach((key) => this.destroyChart(Number(key)));
		},
		enterFullscreenPreview() {
			if (!this.currentDashboard || !this.orderedDashboardItems.length) {
				return;
			}
			this.isFullscreenPreview = true;
			document.body.classList.add("cd-fullscreen-open");
			this.$nextTick(() => this.renderAllCharts());
		},
		exitFullscreenPreview() {
			if (!this.isFullscreenPreview) {
				return;
			}
			this.isFullscreenPreview = false;
			document.body.classList.remove("cd-fullscreen-open");
			this.$nextTick(() => this.renderAllCharts());
		},
		onFullscreenKeydown(event) {
			if (event.key === "Escape" && this.isFullscreenPreview) {
				this.exitFullscreenPreview();
			}
		},
		notify(message, indicator = "blue") {
			this.frappe.show_alert({ message, indicator });
		},
		notifyReadonly() {
			this.notify(
				"Ce tableau est en lecture seule pour vous. Dupliquez-le pour le modifier.",
				"orange"
			);
		},
		parseError(error, fallbackMessage) {
			if (error?._server_messages) {
				try {
					const messages = JSON.parse(error._server_messages);
					if (messages.length) {
						const firstMessage = JSON.parse(messages[0]);
						return firstMessage.message || fallbackMessage;
					}
				} catch {
					return fallbackMessage;
				}
			}
			return error?.message || fallbackMessage;
		},
	},
};

function itemPayloadSafe(item) {
	return item?.preview?.data || {};
}
</script>

<style scoped>
.cd-v2-shell {
	--cd-bg: linear-gradient(145deg, #eef7f4 0%, #fff8ec 55%, #f4efe8 100%);
	--cd-panel: rgba(255, 255, 255, 0.88);
	--cd-border: rgba(17, 94, 89, 0.12);
	--cd-text: #17342f;
	--cd-muted: #60736e;
	--cd-accent: #0f766e;
	--cd-accent-strong: #115e59;
	--cd-gold: #d97706;
	--cd-danger: #b42318;
	--cd-grid: rgba(15, 118, 110, 0.08);
	color: var(--cd-text);
	background: var(--cd-bg);
	border-radius: 24px;
	padding: 20px;
}

.cd-topbar {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 16px;
	padding: 20px 22px;
	border-radius: 22px;
	background: linear-gradient(135deg, rgba(255, 255, 255, 0.94), rgba(255, 248, 236, 0.82));
	border: 1px solid var(--cd-border);
	box-shadow: 0 22px 46px rgba(23, 52, 47, 0.08);
}

.cd-eyebrow {
	margin: 0 0 6px;
	font-size: 11px;
	font-weight: 700;
	letter-spacing: 0.16em;
	text-transform: uppercase;
	color: var(--cd-accent);
}

.cd-title {
	margin: 0;
	font-size: 30px;
	font-weight: 800;
}

.cd-subtitle {
	margin: 8px 0 0;
	color: var(--cd-muted);
	max-width: 720px;
}

.cd-topbar-actions {
	display: flex;
	flex-wrap: wrap;
	gap: 10px;
}

.cd-banner {
	margin-top: 16px;
	padding: 12px 14px;
	border-radius: 14px;
	background: rgba(255, 255, 255, 0.82);
	border: 1px solid var(--cd-border);
}

.cd-banner.is-error {
	border-color: rgba(180, 35, 24, 0.2);
	color: var(--cd-danger);
}

.cd-banner.is-info {
	border-color: rgba(27, 132, 255, 0.25);
	background: rgba(27, 132, 255, 0.06);
	color: var(--cd-text, #0b1320);
	display: flex;
	flex-direction: column;
	gap: 4px;
	font-size: 12.5px;
}

.cd-banner.is-info strong {
	color: #0f5ed7;
}

.cd-banner-sub {
	color: var(--cd-muted, #6b7280);
	font-size: 11.5px;
	line-height: 1.45;
}

.cd-layout {
	display: grid;
	grid-template-columns: minmax(220px, 236px) minmax(0, 1fr) minmax(252px, 284px);
	grid-template-areas: "library workspace sidebar";
	gap: 18px;
	margin-top: 18px;
	align-items: start;
}

.cd-panel {
	background: var(--cd-panel);
	border: 1px solid var(--cd-border);
	border-radius: 22px;
	box-shadow: 0 18px 42px rgba(23, 52, 47, 0.06);
	backdrop-filter: blur(10px);
}

.cd-library-panel,
.cd-side-panel {
	padding: 18px;
	position: sticky;
	top: 12px;
	max-height: calc(100vh - 150px);
	overflow: auto;
}

.cd-library-panel {
	grid-area: library;
}

.cd-workspace {
	grid-area: workspace;
	padding: 20px;
	min-width: 0;
	overflow: hidden;
}

.cd-side-panel {
	grid-area: sidebar;
}

.cd-panel-head {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 12px;
	margin-bottom: 14px;
}

.cd-panel-head h2,
.cd-grid-stage-head h2 {
	margin: 0;
	font-size: 19px;
	font-weight: 700;
}

.cd-panel-head p,
.cd-grid-stage-head p {
	margin: 6px 0 0;
	color: var(--cd-muted);
	font-size: 13px;
}

.cd-pill,
.cd-chip {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	padding: 6px 10px;
	border-radius: 999px;
	background: rgba(15, 118, 110, 0.08);
	color: var(--cd-accent-strong);
	font-size: 12px;
	font-weight: 700;
}

.cd-chip.is-warning {
	background: rgba(217, 119, 6, 0.12);
	color: var(--cd-gold);
}

.cd-library-tools {
	margin-bottom: 12px;
}

.cd-library-list,
.cd-dashboard-list,
.cd-admin-list,
.cd-share-list {
	display: grid;
	gap: 12px;
}

.cd-library-group {
	display: grid;
	gap: 10px;
}

.cd-library-group-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
	padding: 0 2px;
	color: var(--cd-muted);
	font-size: 12px;
}

.cd-library-group-head strong {
	color: var(--cd-text);
	font-size: 13px;
}

.cd-library-card,
.cd-dashboard-row,
.cd-admin-widget-row {
	width: 100%;
	border: 1px solid var(--cd-border);
	background: rgba(255, 255, 255, 0.82);
	border-radius: 18px;
	padding: 14px;
	text-align: left;
	transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.cd-library-card:hover,
.cd-dashboard-row:hover,
.cd-admin-widget-row:hover {
	transform: translateY(-1px);
	box-shadow: 0 14px 32px rgba(23, 52, 47, 0.08);
	border-color: rgba(15, 118, 110, 0.22);
}

.cd-library-card.is-disabled {
	opacity: 0.72;
}

.cd-library-card-top,
.cd-library-card-meta,
.cd-library-card-foot,
.cd-dashboard-row,
.cd-admin-widget-row,
.cd-grid-stage-head,
.cd-widget-head,
.cd-widget-foot,
.cd-share-row,
.cd-filter-actions,
.cd-inline-actions,
.cd-chart-headline,
.cd-dashboard-form,
.cd-toggle-row,
.cd-resize-group,
.cd-resize-control,
.cd-widget-actions,
.cd-side-tabs,
.cd-admin-matrix-head,
.cd-admin-matrix-row {
	display: flex;
	align-items: center;
	gap: 10px;
}

.cd-library-card-top,
.cd-library-card-foot,
.cd-dashboard-row,
.cd-admin-widget-row,
.cd-grid-stage-head,
.cd-widget-head,
.cd-widget-foot,
.cd-chart-headline {
	justify-content: space-between;
}

.cd-library-card h3,
.cd-admin-description strong {
	margin: 0;
	font-size: 16px;
}

.cd-library-card p,
.cd-dashboard-row p,
.cd-admin-widget-row p,
.cd-admin-description p {
	margin: 5px 0 0;
	color: var(--cd-muted);
	font-size: 12px;
}

.cd-workspace .cd-dashboard-form {
	display: grid;
	grid-template-columns: minmax(0, 1fr) auto;
	gap: 14px;
	padding: 16px;
	border-radius: 18px;
	background: rgba(255, 255, 255, 0.72);
	border: 1px solid var(--cd-border);
}

.cd-field {
	display: grid;
	gap: 6px;
}

.cd-field label {
	font-size: 12px;
	font-weight: 700;
	color: var(--cd-muted);
}

.cd-field-help {
	font-size: 12px;
	color: var(--cd-muted);
}

.cd-toggle-row,
.cd-inline-actions,
.cd-filter-actions,
.cd-widget-actions,
.cd-resize-group,
.cd-topbar-actions {
	flex-wrap: wrap;
}

.cd-toggle {
	display: inline-flex;
	align-items: center;
	gap: 8px;
	font-size: 13px;
}

.cd-grid-stage {
	margin-top: 16px;
}

.cd-grid-scroll {
	margin-top: 12px;
	overflow-x: auto;
	overflow-y: hidden;
	padding: 0 4px 10px;
}

.cd-grid-canvas {
	position: relative;
	display: grid;
	gap: 16px;
	padding: 18px;
	width: max(100%, 1320px);
	min-width: 1320px;
	border-radius: 26px;
	border: 1px dashed rgba(15, 118, 110, 0.24);
	background:
		linear-gradient(90deg, transparent calc(100% - 1px), var(--cd-grid) 0),
		linear-gradient(transparent calc(100% - 1px), var(--cd-grid) 0),
		linear-gradient(180deg, rgba(255, 255, 255, 0.85), rgba(249, 252, 251, 0.72));
	background-size: calc(100% / 12) 100%, 100% 72px, 100% 100%;
}

.cd-drop-preview {
	border-radius: 18px;
	border: 2px dashed rgba(15, 118, 110, 0.45);
	background: rgba(15, 118, 110, 0.08);
	z-index: 0;
}

.cd-widget-card {
	position: relative;
	display: flex;
	flex-direction: column;
	gap: 14px;
	padding: 16px;
	border-radius: 24px;
	background: rgba(255, 255, 255, 0.96);
	border: 1px solid rgba(15, 118, 110, 0.12);
	box-shadow: 0 18px 30px rgba(23, 52, 47, 0.07);
	z-index: 1;
	min-height: 100%;
	min-width: 0;
	overflow: hidden;
}

.cd-widget-card.is-locked {
	background: rgba(248, 247, 244, 0.94);
}

.cd-widget-head-main {
	display: grid;
	gap: 6px;
	flex: 1;
	min-width: 0;
}

.cd-drag-handle {
	display: inline-flex;
	align-items: center;
	width: fit-content;
	padding: 4px 8px;
	border-radius: 999px;
	background: rgba(15, 118, 110, 0.08);
	color: var(--cd-accent-strong);
	font-size: 11px;
	font-weight: 700;
	cursor: grab;
}

.cd-widget-meta,
.cd-widget-context {
	margin: 0;
	color: var(--cd-muted);
	font-size: 12px;
}

.cd-widget-body {
	flex: 1;
	display: flex;
	flex-direction: column;
	gap: 12px;
	min-height: 0;
	overflow: auto;
	padding-right: 4px;
}

.cd-filter-box {
	padding: 12px;
	border-radius: 16px;
	background: rgba(245, 251, 250, 0.92);
	border: 1px solid rgba(15, 118, 110, 0.08);
	display: grid;
	gap: 10px;
}

.cd-filter-box.is-collapsed {
	padding: 8px 12px;
	background: rgba(245, 251, 250, 0.65);
}

.cd-filter-toolbar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
	flex-wrap: wrap;
}

.cd-filter-toggle {
	flex-shrink: 0;
}

.cd-filter-summary {
	font-size: 12px;
	color: var(--cd-muted);
	text-align: right;
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.cd-filter-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(164px, 1fr));
	gap: 10px;
}

.cd-number-card {
	display: flex;
	flex-direction: column;
	justify-content: center;
	align-items: flex-start;
	gap: 6px;
	min-height: 100%;
	padding: 8px 0;
}

.cd-number-card-value {
	font-size: 34px;
	line-height: 1;
	font-weight: 800;
}

.cd-number-card-label {
	font-size: 14px;
	font-weight: 700;
}

.cd-number-card-secondary {
	color: var(--cd-muted);
	font-size: 13px;
}

.cd-table-wrap,
.cd-chart-card,
.cd-custom-card,
.cd-ai-card {
	display: grid;
	gap: 10px;
	height: 100%;
}

.cd-ai-card {
	display: flex;
	flex-direction: column;
	gap: 12px;
	overflow: auto;
}
.cd-ai-summary {
	margin: 0;
	background: rgba(15, 118, 110, 0.06);
	border: 1px solid var(--cd-border);
	border-left: 3px solid var(--cd-accent);
	padding: 10px 12px;
	border-radius: 8px;
	font-size: 13px;
}
.cd-ai-section h4 {
	margin: 0 0 6px;
	font-size: 12px;
	text-transform: uppercase;
	letter-spacing: 0.06em;
	color: var(--cd-muted);
}
.cd-ai-empty {
	font-size: 12px;
	color: var(--cd-muted);
	font-style: italic;
}
.cd-ai-list {
	margin: 0;
	padding: 0;
	list-style: none;
	display: flex;
	flex-direction: column;
	gap: 6px;
}
.cd-ai-item {
	background: var(--cd-panel);
	border: 1px solid var(--cd-border);
	border-radius: 8px;
	padding: 8px 10px;
	border-left-width: 3px;
}
.cd-ai-item.sev-high { border-left-color: var(--cd-danger); }
.cd-ai-item.sev-medium { border-left-color: var(--cd-gold); }
.cd-ai-item.sev-low { border-left-color: var(--cd-accent); }
.cd-ai-item-head {
	display: flex;
	align-items: center;
	gap: 8px;
	margin-bottom: 4px;
}
.cd-ai-item-head strong { font-size: 13px; }
.cd-ai-item p {
	margin: 0;
	font-size: 12px;
	color: var(--cd-muted);
}
.cd-ai-badge {
	font-size: 10px;
	font-weight: 700;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	padding: 2px 6px;
	border-radius: 999px;
	background: rgba(15, 118, 110, 0.1);
	color: var(--cd-accent);
}
.cd-ai-item.sev-high .cd-ai-badge { background: rgba(180, 35, 24, 0.12); color: var(--cd-danger); }
.cd-ai-item.sev-medium .cd-ai-badge { background: rgba(217, 119, 6, 0.12); color: #b45309; }
.cd-ai-footer {
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 8px;
	margin-top: auto;
	padding-top: 8px;
	border-top: 1px dashed var(--cd-border);
}
.cd-ai-footer small {
	color: var(--cd-muted);
	font-size: 11px;
}

.cd-table-preview {
	margin-bottom: 0;
	background: rgba(255, 255, 255, 0.82);
}

.cd-chart-host {
	min-height: 180px;
}

.cd-chart-headline strong,
.cd-chart-headline span {
	display: block;
}

.cd-chart-headline span {
	font-size: 20px;
	font-weight: 700;
}

.cd-resize-control {
	gap: 6px;
}

.cd-resize-control span {
	font-size: 12px;
	color: var(--cd-muted);
}

.cd-side-tabs {
	margin-bottom: 16px;
	padding: 4px;
	border-radius: 999px;
	background: rgba(15, 118, 110, 0.06);
}

.cd-tab {
	flex: 1;
	border: 0;
	border-radius: 999px;
	background: transparent;
	padding: 10px 12px;
	font-size: 13px;
	font-weight: 700;
	color: var(--cd-muted);
}

.cd-tab.is-active {
	background: rgba(255, 255, 255, 0.92);
	color: var(--cd-accent-strong);
	box-shadow: 0 8px 20px rgba(23, 52, 47, 0.08);
}

.cd-side-section + .cd-side-section {
	margin-top: 18px;
}

.cd-share-box,
.cd-admin-form,
.cd-admin-shell {
	display: grid;
	gap: 14px;
}

.cd-share-row {
	align-items: center;
	padding: 10px;
	border-radius: 14px;
	background: rgba(255, 255, 255, 0.8);
	border: 1px solid var(--cd-border);
}

.cd-admin-matrix {
	display: grid;
	gap: 8px;
}

.cd-admin-matrix-head,
.cd-admin-matrix-row {
	grid-template-columns: minmax(0, 1fr) 56px 72px;
	display: grid;
	align-items: center;
	gap: 10px;
}

.cd-admin-matrix-head {
	font-size: 12px;
	font-weight: 700;
	color: var(--cd-muted);
}

.cd-admin-matrix-row {
	padding: 8px 10px;
	border-radius: 12px;
	background: rgba(255, 255, 255, 0.82);
	border: 1px solid var(--cd-border);
}

.cd-state,
.cd-empty {
	padding: 18px;
	border-radius: 16px;
	border: 1px dashed var(--cd-border);
	background: rgba(255, 255, 255, 0.74);
	color: var(--cd-muted);
}

.cd-inline-error {
	padding: 10px 12px;
	border-radius: 14px;
	background: rgba(180, 35, 24, 0.08);
	color: var(--cd-danger);
}

.cd-dashboard-row.is-active,
.cd-admin-widget-row.is-active {
	border-color: rgba(15, 118, 110, 0.28);
	background: rgba(242, 251, 249, 0.95);
}

.cd-dashboard-flags {
	display: grid;
	gap: 6px;
}

.cd-widget-head {
	flex-wrap: wrap;
	align-items: flex-start;
}

.cd-widget-head-actions {
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
	justify-content: flex-end;
}

.cd-widget-head-main,
.cd-filter-box,
.cd-table-wrap,
.cd-chart-card,
.cd-custom-card {
	min-width: 0;
}

.cd-widget-card .form-control,
.cd-widget-card .table-responsive,
.cd-widget-card pre {
	min-width: 0;
}

.cd-table-wrap .table-responsive {
	flex: 1;
	min-height: 0;
}

.cd-custom-card pre {
	margin: 0;
	white-space: pre-wrap;
	word-break: break-word;
}

.cd-widget-foot {
	flex-wrap: wrap;
	margin-top: auto;
}

.cd-widget-card.is-compact .cd-widget-head,
.cd-widget-card.is-compact .cd-widget-foot {
	flex-direction: column;
	align-items: stretch;
}

.cd-widget-card.is-compact .cd-widget-head-actions,
.cd-widget-card.is-compact .cd-widget-actions,
.cd-widget-card.is-compact .cd-resize-group {
	justify-content: space-between;
}

.cd-widget-card.is-compact .cd-filter-grid {
	grid-template-columns: 1fr;
}

.cd-widget-card.is-compact .cd-filter-actions {
	flex-direction: column;
	align-items: stretch;
}

.cd-widget-card.is-compact .cd-number-card-value {
	font-size: 26px;
}

.cd-table-preview th,
.cd-table-preview td {
	white-space: nowrap;
}

@media (max-width: 1600px) {
	.cd-layout {
		grid-template-columns: minmax(210px, 228px) minmax(0, 1fr);
		grid-template-areas:
			"library workspace"
			"sidebar workspace";
	}
}

@media (max-width: 1280px) {
	.cd-layout {
		grid-template-columns: 1fr;
		grid-template-areas:
			"library"
			"workspace"
			"sidebar";
	}

	.cd-library-panel,
	.cd-side-panel {
		position: static;
		max-height: none;
	}

	.cd-workspace .cd-dashboard-form {
		grid-template-columns: 1fr;
	}

	.cd-grid-canvas {
		min-width: 1120px;
		width: max(100%, 1120px);
	}
}

.cd-v2-shell.is-fullscreen-preview {
	position: fixed;
	inset: 0;
	z-index: 1050;
	margin: 0;
	border-radius: 0;
	padding: 16px 20px 24px;
	overflow: auto;
}

.cd-v2-shell.is-fullscreen-preview .cd-side-panel,
.cd-v2-shell.is-fullscreen-preview .cd-dashboard-form {
	display: none !important;
}

.cd-v2-shell.is-fullscreen-preview .cd-layout {
	grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
	grid-template-areas: "library workspace";
	gap: 16px;
}

.cd-v2-shell.is-fullscreen-preview .cd-library-panel {
	position: sticky;
	top: 12px;
	max-height: calc(100vh - 150px);
}

.cd-v2-shell.is-fullscreen-preview .cd-workspace {
	padding: 12px 14px 18px;
}

.cd-v2-shell.is-fullscreen-preview .cd-grid-stage {
	margin-top: 6px;
}

.cd-v2-shell.is-fullscreen-preview .cd-grid-canvas {
	min-width: 0;
	width: 100%;
}

.cd-v2-shell.is-fullscreen-preview .cd-widget-card {
	box-shadow: 0 12px 28px rgba(23, 52, 47, 0.1);
}
</style>

<style>
body.cd-fullscreen-open .navbar,
body.cd-fullscreen-open header.navbar,
body.cd-fullscreen-open .page-head,
body.cd-fullscreen-open .page-title,
body.cd-fullscreen-open .page-container > .page-head,
body.cd-fullscreen-open .layout-side-section,
body.cd-fullscreen-open .sidebar-wrapper,
body.cd-fullscreen-open .desk-sidebar,
body.cd-fullscreen-open #navbar-breadcrumbs,
body.cd-fullscreen-open .breadcrumb-container {
	display: none !important;
}

body.cd-fullscreen-open .main-section,
body.cd-fullscreen-open .container.page-body,
body.cd-fullscreen-open .page-body,
body.cd-fullscreen-open .layout-main,
body.cd-fullscreen-open .layout-main-section,
body.cd-fullscreen-open .layout-main-section-wrapper,
body.cd-fullscreen-open .page-wrapper,
body.cd-fullscreen-open .content.page-container {
	padding: 0 !important;
	margin: 0 !important;
	max-width: 100% !important;
	width: 100% !important;
}

body.cd-fullscreen-open {
	overflow: hidden;
}
</style>

<style scoped>
.cd-v2-shell {
	--cd-bg: #f6f8fb;
	--cd-panel: #ffffff;
	--cd-border: #e5eaf0;
	--cd-text: #0f172a;
	--cd-muted: #64748b;
	--cd-soft: #f8fafc;
	--cd-blue: #2563eb;
	--cd-blue-soft: #dbeafe;
	--cd-green: #16a34a;
	--cd-orange: #f59e0b;
	--cd-red: #dc2626;
	--cd-grid: rgba(148, 163, 184, 0.24);
	min-height: calc(100vh - 104px);
	padding: 14px;
	border-radius: 0;
	background: var(--cd-bg);
	color: var(--cd-text);
}

.cd-v2-shell :deep(.form-control) {
	border: 1px solid var(--cd-border);
	border-radius: 12px;
	box-shadow: none;
	color: var(--cd-text);
	min-height: 36px;
}

.cd-v2-shell :deep(.form-control:focus) {
	border-color: rgba(37, 99, 235, 0.42);
	box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.cd-v2-shell :deep(.btn) {
	border-radius: 12px;
	border-color: var(--cd-border);
	font-weight: 700;
	min-height: 36px;
	transition: background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.cd-v2-shell :deep(.btn:hover:not(:disabled)) {
	transform: translateY(-1px);
	box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
}

.cd-v2-shell :deep(.btn-primary),
.cd-save-button {
	background: var(--cd-blue) !important;
	border-color: var(--cd-blue) !important;
	color: #fff !important;
	box-shadow: 0 10px 22px rgba(37, 99, 235, 0.22);
}

.cd-v2-shell :deep(.btn:disabled) {
	opacity: 0.55;
	cursor: not-allowed;
	transform: none;
	box-shadow: none;
}

.sr-only {
	position: absolute;
	width: 1px;
	height: 1px;
	padding: 0;
	margin: -1px;
	overflow: hidden;
	clip: rect(0, 0, 0, 0);
	white-space: nowrap;
	border: 0;
}

.cd-topbar {
	position: sticky;
	top: 0;
	z-index: 20;
	align-items: center;
	padding: 12px 14px;
	border-radius: 18px;
	background: rgba(255, 255, 255, 0.96);
	border: 1px solid var(--cd-border);
	box-shadow: 0 14px 34px rgba(15, 23, 42, 0.07);
	backdrop-filter: blur(14px);
}

.cd-topbar-left,
.cd-topbar-meta,
.cd-topbar-actions,
.cd-canvas-metadata,
.cd-inspector-actions,
.cd-history-row {
	display: flex;
	align-items: center;
	gap: 10px;
}

.cd-topbar-left {
	min-width: 280px;
}

.cd-app-icon {
	width: 38px;
	height: 38px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	border-radius: 14px;
	background: var(--cd-blue-soft);
	color: var(--cd-blue);
	flex: 0 0 auto;
}

.cd-app-icon :deep(svg),
.cd-icon-button :deep(svg),
.cd-widget-library-icon :deep(svg),
.cd-empty-icon :deep(svg),
.cd-search-icon :deep(svg) {
	display: block;
	width: 18px;
	height: 18px;
}

.cd-app-icon :deep(svg) {
	width: 21px;
	height: 21px;
}

.cd-topbar-copy {
	display: grid;
	gap: 5px;
	min-width: 0;
}

.cd-title {
	font-size: 17px;
	line-height: 1.2;
	font-weight: 800;
	color: var(--cd-text);
}

.cd-dashboard-selector {
	width: min(260px, 34vw);
	min-height: 32px;
	border: 1px solid var(--cd-border);
	border-radius: 10px;
	background: #fff;
	color: var(--cd-text);
	font-weight: 700;
	padding: 0 32px 0 10px;
}

.cd-version-badge,
.cd-save-status,
.cd-pill,
.cd-chip {
	border-radius: 999px;
	font-size: 12px;
	font-weight: 800;
	white-space: nowrap;
}

.cd-version-badge {
	padding: 6px 10px;
	background: #eef2ff;
	color: #3730a3;
}

.cd-save-status {
	display: inline-flex;
	align-items: center;
	gap: 7px;
	padding: 7px 10px;
	background: var(--cd-soft);
	color: var(--cd-muted);
	border: 1px solid var(--cd-border);
}

.cd-status-dot {
	width: 8px;
	height: 8px;
	border-radius: 999px;
	background: var(--cd-muted);
	display: inline-block;
	flex: 0 0 auto;
}

.cd-save-status.is-dirty .cd-status-dot,
.cd-status-dot.is-dirty {
	background: var(--cd-orange);
}

.cd-save-status.is-saved .cd-status-dot,
.cd-status-dot.is-saved {
	background: var(--cd-green);
}

.cd-banner {
	margin-top: 12px;
	border-radius: 14px;
	border: 1px solid var(--cd-border);
	background: #fff;
	color: var(--cd-text);
	box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
}

.cd-banner.is-error {
	border-color: rgba(220, 38, 38, 0.24);
	background: #fef2f2;
	color: var(--cd-red);
}

.cd-banner.is-info {
	border-color: rgba(37, 99, 235, 0.18);
	background: #eff6ff;
}

.cd-layout {
	grid-template-columns: minmax(280px, 312px) minmax(560px, 1fr) minmax(300px, 336px);
	grid-template-areas: "library workspace sidebar";
	gap: 16px;
	margin-top: 14px;
	align-items: start;
}

.cd-layout.is-library-collapsed {
	grid-template-columns: 74px minmax(560px, 1fr) minmax(300px, 336px);
}

.cd-panel {
	background: var(--cd-panel);
	border: 1px solid var(--cd-border);
	border-radius: 18px;
	box-shadow: 0 12px 28px rgba(15, 23, 42, 0.045);
	backdrop-filter: none;
}

.cd-library-panel,
.cd-side-panel {
	top: 82px;
	max-height: calc(100vh - 108px);
	padding: 16px;
	overflow: auto;
	scrollbar-width: thin;
}

.cd-workspace {
	padding: 16px;
	border-radius: 18px;
	overflow: visible;
}

.cd-library-panel::-webkit-scrollbar,
.cd-side-panel::-webkit-scrollbar,
.cd-widget-body::-webkit-scrollbar {
	width: 6px;
	height: 6px;
}

.cd-library-panel::-webkit-scrollbar-thumb,
.cd-side-panel::-webkit-scrollbar-thumb,
.cd-widget-body::-webkit-scrollbar-thumb {
	background: rgba(100, 116, 139, 0.26);
	border-radius: 999px;
}

.cd-panel-head,
.cd-library-head,
.cd-inspector-head,
.cd-grid-stage-head,
.cd-dashboard-overview {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 12px;
}

.cd-panel-head h2,
.cd-inspector-head h2,
.cd-grid-stage-head h2,
.cd-dashboard-overview h2 {
	margin: 0;
	font-size: 16px;
	line-height: 1.25;
	font-weight: 800;
	color: var(--cd-text);
}

.cd-panel-head p,
.cd-inspector-head p,
.cd-grid-stage-head p,
.cd-library-head p,
.cd-config-title p {
	margin: 4px 0 0;
	color: var(--cd-muted);
	font-size: 12px;
}

.cd-icon-button {
	width: 34px;
	height: 34px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	border: 1px solid var(--cd-border);
	border-radius: 12px;
	background: #fff;
	color: var(--cd-muted);
	transition: color 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.cd-icon-button:hover {
	color: var(--cd-blue);
	border-color: rgba(37, 99, 235, 0.3);
	background: #eff6ff;
}

.cd-library-content {
	display: grid;
	gap: 12px;
}

.cd-library-tools {
	position: relative;
	margin: 0;
}

.cd-library-tools .form-control {
	padding-left: 36px;
}

.cd-search-icon {
	position: absolute;
	left: 12px;
	top: 50%;
	transform: translateY(-50%);
	color: var(--cd-muted);
	pointer-events: none;
}

.cd-filter-pills {
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
}

.cd-filter-pill {
	border: 1px solid var(--cd-border);
	background: #fff;
	color: var(--cd-muted);
	border-radius: 999px;
	padding: 7px 12px;
	font-size: 12px;
	font-weight: 800;
	transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
}

.cd-filter-pill:hover {
	border-color: rgba(37, 99, 235, 0.28);
	color: var(--cd-blue);
}

.cd-filter-pill.is-active {
	background: var(--cd-blue);
	border-color: var(--cd-blue);
	color: #fff;
}

.cd-library-list {
	gap: 10px;
}

.cd-library-card {
	display: grid;
	grid-template-columns: 42px minmax(0, 1fr) auto;
	align-items: center;
	gap: 10px;
	padding: 10px;
	border-radius: 14px;
	background: #fff;
	border: 1px solid var(--cd-border);
	box-shadow: none;
}

.cd-library-card:hover {
	transform: translateY(-1px);
	border-color: rgba(37, 99, 235, 0.24);
	box-shadow: 0 10px 22px rgba(15, 23, 42, 0.06);
}

.cd-widget-library-icon {
	width: 40px;
	height: 40px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	border-radius: 13px;
	background: #eef2ff;
	color: #4f46e5;
}

.cd-widget-library-icon.is-stock {
	background: #dcfce7;
	color: var(--cd-green);
}

.cd-widget-library-icon.is-selling {
	background: #dbeafe;
	color: var(--cd-blue);
}

.cd-widget-library-icon.is-buying {
	background: #fff7ed;
	color: #ea580c;
}

.cd-library-card-main {
	min-width: 0;
}

.cd-library-card h3 {
	margin: 0;
	color: var(--cd-text);
	font-size: 14px;
	font-weight: 800;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.cd-library-card p {
	margin: 3px 0 0;
	color: var(--cd-muted);
	font-size: 12px;
}

.cd-add-widget-button {
	padding-inline: 10px;
	white-space: nowrap;
}

.cd-layout.is-library-collapsed .cd-library-panel {
	padding: 12px;
}

.cd-layout.is-library-collapsed .cd-library-head {
	align-items: center;
	justify-content: center;
}

.cd-layout.is-library-collapsed .cd-library-head h2,
.cd-layout.is-library-collapsed .cd-library-head p {
	display: none;
}

.cd-dashboard-overview {
	align-items: center;
	margin-bottom: 12px;
}

.cd-dashboard-overview h2 {
	font-size: 20px;
}

.cd-canvas-metadata {
	margin-top: 6px;
	flex-wrap: wrap;
	color: var(--cd-muted);
	font-size: 12px;
	font-weight: 700;
}

.cd-canvas-metadata span {
	padding: 5px 9px;
	border-radius: 999px;
	background: var(--cd-soft);
	border: 1px solid var(--cd-border);
}

.cd-workspace .cd-dashboard-form {
	display: grid;
	grid-template-columns: minmax(180px, 1fr) minmax(180px, 1.1fr) minmax(180px, 1fr) auto;
	align-items: end;
	gap: 12px;
	padding: 14px;
	border-radius: 16px;
	background: #fff;
	border: 1px solid var(--cd-border);
}

.cd-config-title h3,
.cd-side-block h3 {
	margin: 0;
	font-size: 14px;
	font-weight: 800;
	color: var(--cd-text);
}

.cd-field label,
.cd-property-field > span,
.cd-readonly-field > span {
	color: var(--cd-muted);
	font-size: 12px;
	font-weight: 800;
}

.cd-toggle-row {
	justify-content: flex-end;
	gap: 12px;
	padding-bottom: 2px;
}

.cd-toggle {
	color: var(--cd-text);
	font-size: 13px;
	font-weight: 700;
}

.cd-toggle input {
	accent-color: var(--cd-blue);
}

.cd-grid-stage {
	margin-top: 14px;
}

.cd-grid-stage-head {
	align-items: center;
	margin-bottom: 10px;
}

.cd-pill,
.cd-chip {
	display: inline-flex;
	align-items: center;
	padding: 6px 10px;
	background: #eff6ff;
	color: var(--cd-blue);
}

.cd-chip.is-warning {
	background: #fff7ed;
	color: #c2410c;
}

.cd-grid-scroll {
	margin-top: 10px;
	padding: 0 0 8px;
	overflow-x: auto;
}

.cd-grid-canvas {
	position: relative;
	width: 100%;
	min-width: 900px;
	padding: 52px 16px 16px;
	gap: 12px;
	border-radius: 18px;
	border: 1px dashed rgba(148, 163, 184, 0.76);
	background:
		linear-gradient(90deg, transparent calc(100% - 1px), var(--cd-grid) 0),
		linear-gradient(#fff, #fff);
	background-size: calc(100% / 12) 100%, 100% 100%;
	box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.74);
}

.cd-grid-canvas.is-empty {
	min-height: 680px !important;
}

.cd-column-labels {
	position: absolute;
	top: 14px;
	left: 16px;
	right: 16px;
	display: grid;
	grid-template-columns: repeat(12, minmax(0, 1fr));
	gap: 12px;
	color: #94a3b8;
	font-size: 11px;
	font-weight: 800;
	text-align: center;
	pointer-events: none;
}

.cd-column-labels span {
	padding-bottom: 8px;
	border-bottom: 1px solid #eef2f7;
}

.cd-empty-canvas-state {
	position: absolute;
	inset: 78px 24px 24px;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	text-align: center;
	color: var(--cd-muted);
	pointer-events: none;
}

.cd-empty-icon {
	width: 76px;
	height: 76px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	border-radius: 24px;
	background: #eff6ff;
	color: var(--cd-blue);
	margin-bottom: 18px;
	opacity: 0.78;
}

.cd-empty-icon :deep(svg) {
	width: 52px;
	height: 52px;
}

.cd-empty-canvas-state h3 {
	margin: 0;
	font-size: 22px;
	color: var(--cd-text);
	font-weight: 800;
}

.cd-empty-canvas-state p {
	margin: 8px 0 0;
	max-width: 460px;
	font-size: 14px;
	line-height: 1.5;
}

.cd-empty-placeholders {
	display: flex;
	align-items: flex-end;
	gap: 12px;
	margin-top: 26px;
	opacity: 0.48;
}

.cd-placeholder-donut,
.cd-placeholder-kpi,
.cd-placeholder-bars {
	width: 76px;
	height: 54px;
	border-radius: 14px;
	border: 1px solid #e2e8f0;
	background: #f8fafc;
}

.cd-placeholder-donut {
	background:
		radial-gradient(circle at center, #f8fafc 0 36%, transparent 37%),
		conic-gradient(#bfdbfe 0 42%, #dbeafe 42% 72%, #e2e8f0 72%);
}

.cd-placeholder-kpi {
	display: grid;
	align-content: center;
	gap: 8px;
	padding: 10px;
}

.cd-placeholder-kpi span,
.cd-placeholder-kpi strong {
	display: block;
	height: 7px;
	border-radius: 999px;
	background: #dbeafe;
}

.cd-placeholder-kpi strong {
	width: 44px;
	height: 12px;
	background: #bfdbfe;
}

.cd-placeholder-bars {
	display: flex;
	align-items: end;
	gap: 7px;
	padding: 10px;
}

.cd-placeholder-bars span {
	flex: 1;
	border-radius: 999px 999px 4px 4px;
	background: #bfdbfe;
}

.cd-placeholder-bars span:nth-child(1) { height: 22px; }
.cd-placeholder-bars span:nth-child(2) { height: 34px; }
.cd-placeholder-bars span:nth-child(3) { height: 16px; }

.cd-drop-preview {
	border-radius: 14px;
	border: 2px dashed rgba(37, 99, 235, 0.46);
	background: rgba(37, 99, 235, 0.08);
	z-index: 2;
}

.cd-widget-card {
	gap: 12px;
	padding: 14px;
	border-radius: 16px;
	background: #fff;
	border: 1px solid var(--cd-border);
	box-shadow: 0 10px 22px rgba(15, 23, 42, 0.06);
	z-index: 3;
}

.cd-widget-card.is-locked {
	background: #f8fafc;
}

.cd-drag-handle {
	background: #eff6ff;
	color: var(--cd-blue);
}

.cd-filter-box {
	background: #f8fafc;
	border-color: var(--cd-border);
}

.cd-number-card-value {
	color: var(--cd-text);
}

.cd-inline-error {
	background: #fef2f2;
	color: var(--cd-red);
}

.cd-side-panel {
	padding: 16px;
}

.cd-inspector-head {
	margin-bottom: 12px;
}

.cd-side-tabs {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 4px;
	margin-bottom: 14px;
	padding: 4px;
	border-radius: 12px;
	background: #f1f5f9;
}

.cd-tab {
	padding: 9px 8px;
	border-radius: 10px;
	color: var(--cd-muted);
}

.cd-tab.is-active {
	background: #fff;
	color: var(--cd-blue);
	box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
}

.cd-side-section,
.cd-property-list,
.cd-side-block,
.cd-share-box,
.cd-admin-form,
.cd-admin-shell,
.cd-history-list {
	display: grid;
	gap: 12px;
}

.cd-property-field,
.cd-readonly-field {
	display: grid;
	gap: 6px;
}

.cd-readonly-field {
	padding: 10px 12px;
	border: 1px solid var(--cd-border);
	border-radius: 14px;
	background: var(--cd-soft);
}

.cd-readonly-field strong {
	font-size: 13px;
	color: var(--cd-text);
}

.cd-toggle-card {
	align-items: flex-start;
	padding: 12px;
	border: 1px solid var(--cd-border);
	border-radius: 14px;
	background: #fff;
}

.cd-toggle-card span {
	display: grid;
	gap: 3px;
}

.cd-toggle-card small {
	color: var(--cd-muted);
	font-size: 12px;
	font-weight: 600;
}

.cd-side-block {
	padding-top: 12px;
	border-top: 1px solid var(--cd-border);
}

.cd-inspector-actions {
	align-items: stretch;
}

.cd-inspector-actions .btn {
	flex: 1;
}

.cd-danger-button {
	color: var(--cd-red) !important;
	border-color: rgba(220, 38, 38, 0.2) !important;
	background: #fff !important;
}

.cd-dashboard-list {
	display: grid;
	gap: 10px;
}

.cd-dashboard-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
	padding: 11px;
	border-radius: 14px;
	border: 1px solid var(--cd-border);
	background: #fff;
}

.cd-dashboard-row:hover,
.cd-dashboard-row.is-active {
	transform: translateY(-1px);
	border-color: rgba(37, 99, 235, 0.28);
	background: #f8fbff;
	box-shadow: 0 10px 22px rgba(15, 23, 42, 0.06);
}

.cd-dashboard-row strong {
	display: block;
	font-size: 13px;
	color: var(--cd-text);
}

.cd-dashboard-row p {
	margin: 3px 0 0;
	color: var(--cd-muted);
	font-size: 12px;
}

.cd-dashboard-flags {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
	justify-content: flex-end;
}

.cd-link-button {
	width: fit-content;
	border: 0;
	background: transparent;
	color: var(--cd-blue);
	padding: 4px 0;
	font-size: 13px;
	font-weight: 800;
}

.cd-link-button:hover {
	text-decoration: underline;
}

.cd-share-row {
	display: grid;
	grid-template-columns: 100px minmax(0, 1fr);
	gap: 8px;
	align-items: center;
	padding: 10px;
	border-radius: 14px;
	background: #fff;
	border: 1px solid var(--cd-border);
}

.cd-share-row .cd-toggle,
.cd-share-row .btn {
	grid-column: span 2;
}

.cd-history-row {
	align-items: flex-start;
	padding: 12px;
	border: 1px solid var(--cd-border);
	border-radius: 14px;
	background: var(--cd-soft);
}

.cd-history-row strong {
	font-size: 13px;
	color: var(--cd-text);
}

.cd-history-row p {
	margin: 3px 0 0;
	color: var(--cd-muted);
	font-size: 12px;
}

.cd-admin-access {
	margin-top: 4px;
}

.cd-admin-widget-row {
	border-color: var(--cd-border);
	background: #fff;
	border-radius: 14px;
}

.cd-admin-widget-row.is-active {
	border-color: rgba(37, 99, 235, 0.3);
	background: #eff6ff;
}

.cd-state,
.cd-empty {
	padding: 14px;
	border-radius: 14px;
	border: 1px dashed var(--cd-border);
	background: var(--cd-soft);
	color: var(--cd-muted);
	font-size: 13px;
}

.cd-v2-shell.is-fullscreen-preview {
	padding: 14px;
	background: var(--cd-bg);
}

.cd-v2-shell.is-fullscreen-preview .cd-layout {
	grid-template-columns: minmax(0, 1fr);
	grid-template-areas: "workspace";
}

.cd-v2-shell.is-fullscreen-preview .cd-library-panel,
.cd-v2-shell.is-fullscreen-preview .cd-side-panel,
.cd-v2-shell.is-fullscreen-preview .cd-dashboard-form {
	display: none !important;
}

.cd-v2-shell.is-fullscreen-preview .cd-grid-canvas {
	min-width: 0;
}

@media (max-width: 1360px) {
	.cd-layout,
	.cd-layout.is-library-collapsed {
		grid-template-columns: minmax(260px, 300px) minmax(0, 1fr);
		grid-template-areas:
			"library workspace"
			"sidebar workspace";
	}

	.cd-side-panel {
		position: static;
		max-height: none;
	}

	.cd-workspace .cd-dashboard-form {
		grid-template-columns: 1fr 1fr;
	}
}

@media (max-width: 980px) {
	.cd-topbar {
		position: relative;
		align-items: stretch;
	}

	.cd-topbar,
	.cd-topbar-actions,
	.cd-topbar-left {
		flex-direction: column;
	}

	.cd-topbar-actions {
		align-items: stretch;
	}

	.cd-dashboard-selector {
		width: 100%;
	}

	.cd-layout,
	.cd-layout.is-library-collapsed {
		grid-template-columns: 1fr;
		grid-template-areas:
			"library"
			"workspace"
			"sidebar";
	}

	.cd-library-panel,
	.cd-side-panel {
		position: static;
		max-height: none;
	}

	.cd-workspace .cd-dashboard-form {
		grid-template-columns: 1fr;
	}

	.cd-grid-canvas {
		min-width: 760px;
	}
}
</style>
