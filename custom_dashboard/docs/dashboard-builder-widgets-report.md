# Rapport complet des widgets du Dashboard Builder

## Contexte

- App analysee: `custom_dashboard`
- Site utilise pour les valeurs actuelles: `erpnext.localhost`
- Date d'analyse: `2026-04-24`
- Perimetre: tous les widgets actifs du `Dashboard Builder`
- Source des valeurs actuelles: execution reelle des widgets avec les filtres par defaut declares dans `services/widget_registry.py`
- Utilisateur d'execution: `Administrator`

## Sources techniques

- Definitions et formules: `services/widget_executor.py`
- Filtres par defaut et metadata: `services/widget_registry.py`
- Chargement des widgets dans le builder / dashboard: `services/dashboard_service.py`

## Hypotheses importantes

1. Les "valeurs actuelles" ci-dessous correspondent aux filtres par defaut du builder, pas aux filtres personnalises d'un dashboard deja enregistre.
2. Les widgets visibles dans un dashboard specifique peuvent donc afficher des valeurs differentes si des filtres custom ont ete sauvegardes.
3. Les widgets `chart` et `table` ont une "valeur actuelle" resumee sous forme de synthese metier.

## Vue d'ensemble

| Categorie | Widget | Type | Formule metier | Valeur actuelle | Recommandation metier |
| --- | --- | --- | --- | --- | --- |
| CRM | `AT_RISK_CUSTOMERS` | `number_card` | Nombre de clients ayant au moins une facture en retard; secondaire = encours en retard | `9` clients a risque, `99,146.00 TND` d'encours en retard | Lancer un plan de relance cible par client et prioriser les plus gros encours |
| CRM | `PIPELINE_HEALTH` | `chart` | Repartition des opportunites par statut sur 90 jours; resume = montant potentiel total | Aucun dossier sur la periode; potentiel `0 TND` | Verifier si le pipeline commercial est vide ou si le doctype `Opportunity` n'est pas alimente |
| Finance | `PAYMENT_DELAY` | `number_card` | Delai moyen = date paiement - date facture | `41.0` jours, `42` factures reglees | Si le credit client cible est inferieur, renforcer relances et conditions de paiement |
| Finance | `MONTHLY_REVENUE_CHART` | `chart` | CA facture et nombre de factures par mois sur 180 jours | CA cumule `344,261.38 TND`; pic en `Mars 2026` avec `121,605.89 TND` | Analyser la chute d'avril et identifier les leviers qui ont porte mars |
| Finance | `OVERDUE_INVOICES` | `number_card` | Somme des soldes ouverts des factures echees; secondaire = nombre de factures en retard | `99,146.00 TND`, `19` factures en retard | Suivre ce KPI en hebdo avec ageing detaille par client |
| Stock | `STOCK_AGE_PROFILE` | `chart` | Valeur de stock par tranche d'anciennete du dernier mouvement | `2,917,380.55 TND`, 100% en `0-30 j` | Verifier si les mouvements sont reels ou si des entrees recentes ecrasent toute anciennete |
| Stock | `INVENTORY_CONCENTRATION` | `chart` | Classement ABC par valeur de stock cumulee | Total `2,917,380.55 TND`; Classe A `2,281,840.16 TND` | Mettre les articles A sous suivi serre achat, stock mini et couverture |
| Stock | `MONTHLY_STOCK_FLOW` | `chart` | Quantites entrantes et sortantes par mois | `21,668` unites entrees, `0` sorties sur 180 jours | Verifier pourquoi aucune sortie n'est remontee dans le grand livre stock |
| Stock | `RESERVATION_PRESSURE` | `chart` | Taux de reservation = qty reservee / qty physique par entrepot | `Magasins - TUS` a `4.0%` | Surveiller les entrepots avec reservation croissante pour eviter les tensions |
| Stock | `WAREHOUSE_STOCKOUT_RISK` | `chart` | Projection de rupture via `projected_qty < 0` par entrepot | Aucun risque detecte | Si cela semble faux, auditer le calcul de `projected_qty` et les reservations |
| Stock | `STOCK_TURNOVER` | `number_card` | Rotation = valeur de sortie sur periode / valeur de stock actuelle | `0.00`, valeur sortie `0` | Verifier si les sorties stock sont absentes ou mal valorisees |
| Stock | `DORMANT_STOCK` | `number_card` | Valeur et nombre d'articles en stock sans mouvement sur la periode | `0.00 TND`, `0` article dormant | Recontroler sur une periode plus longue, ex. 180 jours |
| Ventes | `REVENUE_BY_CATEGORY` | `chart` | CA par groupe client sur 90 jours | `274,024.67 TND`, tout sur `All Customer Groups` | Enrichir les groupes clients pour segmenter reellement les ventes |
| Ventes | `SALES_THIS_MONTH` | `number_card` | Somme du CA facture du mois; secondaire = nombre de factures | `60,234.54 TND`, `12` factures | Suivre la trajectoire de fin de mois vs objectif commercial |
| Ventes | `PROFITABLE_PRODUCTS` | `table` | Marge estimee = revenu - cout valorise (`qty * incoming_rate`) | Produit leader: `Projecteur HD 3000 lm`, marge `23,137.93 TND` | Utiliser ce top pour booster mix produit et promotions a forte marge |
| Ventes | `TOP_CUSTOMERS` | `table` | Classement des clients par CA facture | Client leader: `Sfax Informatique Pro`, `44,051.07 TND` | Mettre en place un suivi key account sur les 5 premiers clients |

## Predicats communs

### Bloc ventes / finance sur periode

Utilise par `SALES_THIS_MONTH`, `MONTHLY_REVENUE_CHART`, `TOP_CUSTOMERS`, `REVENUE_BY_CATEGORY`, `PROFITABLE_PRODUCTS`.

```sql
docstatus = 1
and ifnull(is_return, 0) = 0
and posting_date between :from_date and :to_date
-- filtres optionnels
and company = :company
and customer_group = :customer_group
and territory = :territory
```

### Bloc ventes / finance en retard

Utilise par `OVERDUE_INVOICES` et `AT_RISK_CUSTOMERS`.

```sql
docstatus = 1
and ifnull(is_return, 0) = 0
and outstanding_amount > 0
and due_date < :today
-- filtres optionnels
and company = :company
and customer_group = :customer_group
and territory = :territory
```

### Bloc stock scope

Utilise par les widgets stock.

```sql
-- filtre optionnel societe via warehouse.company
and ifnull(warehouse.company, '') = :company
-- filtre optionnel entrepot
and <alias_stock>.warehouse = :warehouse
-- filtre optionnel groupe d'articles
and ifnull(item.item_group, '') = :item_group
```

## Fiches detaillees

### 1. `AT_RISK_CUSTOMERS`

- Categorie: `CRM`
- Type: `number_card`
- Methode: `custom_dashboard.services.widget_executor.at_risk_customers_widget`
- Formule metier: `COUNT(DISTINCT customer)` sur les factures clients echees et encore ouvertes; la metrique secondaire est `SUM(outstanding_amount)`.
- Tables SQL: `tabSales Invoice`
- Filtres par defaut: `{"company": "", "customer_group": "", "territory": ""}`
- Valeur actuelle: `9` clients a risque; `99,146.00 TND` d'encours en retard; contexte `Arrete au 2026-04-24`
- Recommandation metier: croiser ce widget avec l'aging client, sortir un top 10 des clients a relancer et fixer des actions de recouvrement.

```sql
select
    count(distinct customer) as customer_count,
    count(*) as invoice_count,
    ifnull(sum(outstanding_amount), 0) as outstanding
from `tabSales Invoice`
where docstatus = 1
  and ifnull(is_return, 0) = 0
  and outstanding_amount > 0
  and due_date < :today
  -- optionnel
  and company = :company
  and customer_group = :customer_group
  and territory = :territory
```

### 2. `PIPELINE_HEALTH`

- Categorie: `CRM`
- Type: `chart`
- Methode: `custom_dashboard.services.widget_executor.pipeline_health_widget`
- Formule metier: nombre d'opportunites et montant potentiel agreges par `status` sur la periode.
- Tables SQL: `tabOpportunity`
- Filtres par defaut: `{"period": "last_90_days", "company": "", "status_scope": "all"}`
- Valeur actuelle: aucun statut remonte; montant potentiel `0 TND`; contexte `Du 2026-01-25 au 2026-04-24`
- Recommandation metier: si le pipeline devrait etre non vide, verifier l'usage du doctype `Opportunity` ou la qualite des dates `transaction_date`.

```sql
select
    coalesce(nullif(status, ''), 'Sans statut') as status,
    count(*) as opportunity_count,
    ifnull(sum(opportunity_amount), 0) as amount
from `tabOpportunity`
where transaction_date between :from_date and :to_date
  -- optionnel
  and company = :company
  -- si status_scope = 'open'
  and status not in ('Lost', 'Won', 'Closed')
group by status
order by opportunity_count desc, status asc
```

### 3. `PAYMENT_DELAY`

- Categorie: `Finance`
- Type: `number_card`
- Methode: `custom_dashboard.services.widget_executor.payment_delay_widget`
- Formule metier: delai moyen de paiement en jours entre `Sales Invoice.posting_date` et `Payment Entry.posting_date`.
- Tables SQL: `tabPayment Entry Reference`, `tabPayment Entry`, `tabSales Invoice`
- Filtres par defaut: `{"period": "last_90_days", "company": "", "customer_group": "", "territory": ""}`
- Valeur actuelle: `41.0` jours; `42` factures reglees; contexte `Du 2026-01-25 au 2026-04-24`
- Recommandation metier: comparer ce delai au credit client cible; si trop haut, resserrer echeanciers, acomptes et relances.

```sql
select
    ifnull(avg(datediff(pe.posting_date, si.posting_date)), 0) as avg_days,
    count(distinct si.name) as invoice_count
from `tabPayment Entry Reference` per
inner join `tabPayment Entry` pe on pe.name = per.parent
inner join `tabSales Invoice` si on si.name = per.reference_name
where per.reference_doctype = 'Sales Invoice'
  and pe.docstatus = 1
  and si.docstatus = 1
  and si.posting_date between :from_date and :to_date
```

### 4. `MONTHLY_REVENUE_CHART`

- Categorie: `Finance`
- Type: `chart`
- Methode: `custom_dashboard.services.widget_executor.monthly_revenue_chart_widget`
- Formule metier: somme du `base_grand_total` et nombre de factures par mois sur une fenetre de 180 jours.
- Tables SQL: `tabSales Invoice`
- Filtres par defaut: `{"period": "last_180_days", "company": "", "customer_group": "", "territory": ""}`
- Valeur actuelle: CA cumule `344,261.38 TND`; facturation visible surtout de janvier a avril 2026; pic de CA en `Mars 2026` avec `121,605.89 TND`
- Recommandation metier: analyser le mix clients / produits des mois forts et comparer avril a mars pour comprendre le ralentissement.

```sql
select
    date_format(posting_date, '%Y-%m') as month_key,
    ifnull(sum(base_grand_total), 0) as amount,
    count(*) as invoice_count
from `tabSales Invoice`
where docstatus = 1
  and ifnull(is_return, 0) = 0
  and posting_date between :from_date and :to_date
  -- optionnel
  and company = :company
  and customer_group = :customer_group
  and territory = :territory
group by date_format(posting_date, '%Y-%m')
order by month_key asc
```

### 5. `OVERDUE_INVOICES`

- Categorie: `Finance`
- Type: `number_card`
- Methode: `custom_dashboard.services.widget_executor.overdue_invoices_widget`
- Formule metier: somme des `outstanding_amount` pour les factures echees et encore ouvertes; secondaire = nombre de factures.
- Tables SQL: `tabSales Invoice`
- Filtres par defaut: `{"company": "", "customer_group": "", "territory": ""}`
- Valeur actuelle: `99,146.00 TND` en retard; `19` factures; contexte `Arrete au 2026-04-24`
- Recommandation metier: mettre une cible de reduction de l'encours echu et la suivre avec un ageing 0-30 / 31-60 / 60+ jours.

```sql
select
    ifnull(sum(outstanding_amount), 0) as amount_due,
    count(*) as invoice_count
from `tabSales Invoice`
where docstatus = 1
  and ifnull(is_return, 0) = 0
  and outstanding_amount > 0
  and due_date < :today
  -- optionnel
  and company = :company
  and customer_group = :customer_group
  and territory = :territory
```

### 6. `STOCK_AGE_PROFILE`

- Categorie: `Stock`
- Type: `chart`
- Methode: `custom_dashboard.services.widget_executor.stock_age_profile_widget`
- Formule metier: somme de `bin.stock_value` par tranche d'anciennete calculee sur la derniere date de mouvement stock (`0-30`, `31-90`, `91-180`, `180+` jours).
- Tables SQL: `tabBin`, `tabItem`, `tabWarehouse`, `tabStock Ledger Entry`
- Filtres par defaut: `{"company": "", "warehouse": "", "item_group": ""}`
- Valeur actuelle: `2,917,380.55 TND`; buckets `0-30 j = 2,917,380.55`, autres buckets = `0`
- Recommandation metier: un profil 100% recent est atypique; verifier si les entrees recentes, ajustements ou repostings rendent l'anciennete trop optimiste.

```sql
select
    case
        when datediff(:as_of_date, coalesce(last_move.last_posting_date, :as_of_date)) <= 30 then '0-30 j'
        when datediff(:as_of_date, coalesce(last_move.last_posting_date, :as_of_date)) <= 90 then '31-90 j'
        when datediff(:as_of_date, coalesce(last_move.last_posting_date, :as_of_date)) <= 180 then '91-180 j'
        else '180+ j'
    end as age_bucket,
    ifnull(sum(bin.stock_value), 0) as stock_value
from `tabBin` bin
left join `tabItem` item on item.name = bin.item_code
left join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
left join (
    select
        item_code,
        warehouse,
        max(posting_date) as last_posting_date
    from `tabStock Ledger Entry`
    where is_cancelled = 0
    group by item_code, warehouse
) last_move
  on last_move.item_code = bin.item_code
 and last_move.warehouse = bin.warehouse
where bin.actual_qty > 0
  and ifnull(item.disabled, 0) = 0
  -- optionnel
  and ifnull(warehouse.company, '') = :company
  and bin.warehouse = :warehouse
  and ifnull(item.item_group, '') = :item_group
group by age_bucket
```

### 7. `INVENTORY_CONCENTRATION`

- Categorie: `Stock`
- Type: `chart`
- Methode: `custom_dashboard.services.widget_executor.inventory_concentration_widget`
- Formule metier: agreger la valeur de stock par article, trier desc, puis classer en `Classe A` jusqu'a 80% du cumul, `Classe B` jusqu'a 95%, `Classe C` au-dela.
- Tables SQL: `tabBin`, `tabItem`, `tabWarehouse`
- Filtres par defaut: `{"company": "", "warehouse": "", "item_group": ""}`
- Valeur actuelle: total `2,917,380.55 TND`; Classe A `2,281,840.16`, Classe B `487,920.09`, Classe C `147,620.30`; contexte `11 articles portent 78.2% de la valeur.`
- Recommandation metier: traiter les articles A comme prioritaires en planification, inventaire tournant et gestion fournisseur.

```sql
select
    bin.item_code,
    ifnull(sum(bin.stock_value), 0) as stock_value
from `tabBin` bin
left join `tabItem` item on item.name = bin.item_code
left join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
where bin.actual_qty > 0
  and ifnull(item.disabled, 0) = 0
  -- optionnel
  and ifnull(warehouse.company, '') = :company
  and bin.warehouse = :warehouse
  and ifnull(item.item_group, '') = :item_group
group by bin.item_code
having ifnull(sum(bin.stock_value), 0) > 0
order by stock_value desc, bin.item_code asc
```

### 8. `MONTHLY_STOCK_FLOW`

- Categorie: `Stock`
- Type: `chart`
- Methode: `custom_dashboard.services.widget_executor.monthly_stock_flow_widget`
- Formule metier: somme mensuelle des quantites d'entree (`actual_qty > 0`) et des sorties (`abs(actual_qty < 0)`).
- Tables SQL: `tabStock Ledger Entry`, `tabItem`, `tabWarehouse`
- Filtres par defaut: `{"period": "last_180_days", "company": "", "warehouse": "", "item_group": ""}`
- Valeur actuelle: entrees totales `21,668` unites, sorties totales `0`; activite visible en janvier, fevrier, mars et surtout avril 2026
- Recommandation metier: si le site consomme du stock, l'absence totale de sorties doit etre verifiee en priorite.

```sql
select
    date_format(sle.posting_date, '%Y-%m') as month_key,
    ifnull(sum(case when sle.actual_qty > 0 then sle.actual_qty else 0 end), 0) as inbound_qty,
    abs(ifnull(sum(case when sle.actual_qty < 0 then sle.actual_qty else 0 end), 0)) as outbound_qty
from `tabStock Ledger Entry` sle
left join `tabItem` item on item.name = sle.item_code
left join `tabWarehouse` warehouse on warehouse.name = sle.warehouse
where sle.is_cancelled = 0
  and sle.posting_date between :from_date and :to_date
  and sle.actual_qty <> 0
  and ifnull(item.disabled, 0) = 0
  -- optionnel
  and ifnull(warehouse.company, '') = :company
  and sle.warehouse = :warehouse
  and ifnull(item.item_group, '') = :item_group
group by month_key
order by month_key asc
```

### 9. `RESERVATION_PRESSURE`

- Categorie: `Stock`
- Type: `chart`
- Methode: `custom_dashboard.services.widget_executor.reservation_pressure_widget`
- Formule metier: taux de reservation par entrepot = `SUM(reserved_qty) / SUM(actual_qty) * 100`.
- Tables SQL: `tabBin`, `tabItem`, `tabWarehouse`
- Filtres par defaut: `{"company": "", "warehouse": "", "item_group": "", "limit": 6}`
- Valeur actuelle: `Magasins - TUS` a `4.0%` de reservation moyenne; resume `4.0`
- Recommandation metier: suivre l'evolution de ce ratio; au-dela d'un seuil interne, renforcer reappro et arbitrage commandes.

```sql
select
    bin.warehouse,
    ifnull(sum(bin.actual_qty), 0) as actual_qty,
    ifnull(sum(bin.reserved_qty), 0) as reserved_qty
from `tabBin` bin
left join `tabItem` item on item.name = bin.item_code
left join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
where bin.actual_qty > 0
  and ifnull(item.disabled, 0) = 0
  -- optionnel
  and ifnull(warehouse.company, '') = :company
  and bin.warehouse = :warehouse
  and ifnull(item.item_group, '') = :item_group
group by bin.warehouse
having ifnull(sum(bin.reserved_qty), 0) > 0
order by
    (ifnull(sum(bin.reserved_qty), 0) / nullif(ifnull(sum(bin.actual_qty), 0), 0)) desc,
    ifnull(sum(bin.reserved_qty), 0) desc,
    bin.warehouse asc
limit :limit
```

### 10. `WAREHOUSE_STOCKOUT_RISK`

- Categorie: `Stock`
- Type: `chart`
- Methode: `custom_dashboard.services.widget_executor.warehouse_stockout_risk_widget`
- Formule metier: quantifier les entrepots en rupture projetee via `projected_qty < 0`; secondaire = nombre de SKU exposes.
- Tables SQL: `tabBin`, `tabItem`, `tabWarehouse`
- Filtres par defaut: `{"company": "", "warehouse": "", "item_group": "", "limit": 6}`
- Valeur actuelle: aucun entrepot remonte; quantite totale en deficit `0`
- Recommandation metier: si les equipes signalent des ruptures mais que le widget est vide, controler `projected_qty`, reservations et ordres ouverts.

```sql
select
    bin.warehouse,
    count(*) as sku_count,
    ifnull(sum(abs(bin.projected_qty)), 0) as shortage_qty
from `tabBin` bin
left join `tabItem` item on item.name = bin.item_code
left join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
where bin.projected_qty < 0
  and ifnull(item.disabled, 0) = 0
  -- optionnel
  and ifnull(warehouse.company, '') = :company
  and bin.warehouse = :warehouse
  and ifnull(item.item_group, '') = :item_group
group by bin.warehouse
order by shortage_qty desc, sku_count desc, bin.warehouse asc
limit :limit
```

### 11. `STOCK_TURNOVER`

- Categorie: `Stock`
- Type: `number_card`
- Methode: `custom_dashboard.services.widget_executor.stock_turnover_widget`
- Formule metier: `rotation = valeur_sortie_periode / valeur_stock_courante`.
- Tables SQL: `tabStock Ledger Entry`, `tabBin`, `tabItem`, `tabWarehouse`
- Filtres par defaut: `{"period": "last_90_days", "company": "", "warehouse": "", "item_group": ""}`
- Valeur actuelle: rotation `0.00`; valeur de sortie `0.0`; contexte `Du 2026-01-25 au 2026-04-24`
- Recommandation metier: ce KPI est aujourd'hui inutilisable pour piloter la rotation; il faut d'abord comprendre l'absence de sorties valorisees.

```sql
-- valeur des sorties sur la periode
select
    abs(ifnull(sum(case when sle.stock_value_difference < 0 then sle.stock_value_difference else 0 end), 0)) as outflow_value
from `tabStock Ledger Entry` sle
left join `tabItem` item on item.name = sle.item_code
left join `tabWarehouse` warehouse on warehouse.name = sle.warehouse
where sle.is_cancelled = 0
  and sle.posting_date between :from_date and :to_date
  and sle.actual_qty < 0
  and ifnull(item.disabled, 0) = 0
  -- optionnel
  and ifnull(warehouse.company, '') = :company
  and sle.warehouse = :warehouse
  and ifnull(item.item_group, '') = :item_group;

-- valeur de stock instantanee
select
    ifnull(sum(bin.stock_value), 0) as stock_value
from `tabBin` bin
left join `tabItem` item on item.name = bin.item_code
left join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
where bin.actual_qty > 0
  and ifnull(item.disabled, 0) = 0
  -- optionnel
  and ifnull(warehouse.company, '') = :company
  and bin.warehouse = :warehouse
  and ifnull(item.item_group, '') = :item_group
```

### 12. `DORMANT_STOCK`

- Categorie: `Stock`
- Type: `number_card`
- Methode: `custom_dashboard.services.widget_executor.dormant_stock_widget`
- Formule metier: valeur des bins avec stock positif et sans aucun mouvement sur la periode selectionnee.
- Tables SQL: `tabBin`, `tabItem`, `tabWarehouse`, `tabStock Ledger Entry`
- Filtres par defaut: `{"period": "last_90_days", "company": "", "warehouse": "", "item_group": ""}`
- Valeur actuelle: `0.00 TND`; `0` article sans mouvement; contexte `Du 2026-01-25 au 2026-04-24`
- Recommandation metier: tester aussi `last_180_days` pour mieux detecter les surstocks lents ou obsoletes.

```sql
select
    ifnull(sum(bin.stock_value), 0) as dormant_value,
    count(distinct bin.item_code) as dormant_items
from `tabBin` bin
left join `tabItem` item on item.name = bin.item_code
left join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
where bin.actual_qty > 0
  and ifnull(item.disabled, 0) = 0
  -- optionnel
  and ifnull(warehouse.company, '') = :company
  and bin.warehouse = :warehouse
  and ifnull(item.item_group, '') = :item_group
  and not exists (
      select 1
      from `tabStock Ledger Entry` sle
      where sle.item_code = bin.item_code
        and sle.warehouse = bin.warehouse
        and sle.is_cancelled = 0
        and sle.posting_date between :from_date and :to_date
        and abs(sle.actual_qty) > 0
  )
```

### 13. `REVENUE_BY_CATEGORY`

- Categorie: `Ventes`
- Type: `chart`
- Methode: `custom_dashboard.services.widget_executor.revenue_by_category_widget`
- Formule metier: somme du CA facture par `customer_group`.
- Tables SQL: `tabSales Invoice`
- Filtres par defaut: `{"period": "last_90_days", "company": "", "customer_group": "", "territory": "", "limit": 6}`
- Valeur actuelle: `274,024.67 TND` entierement porte par `All Customer Groups`
- Recommandation metier: normaliser les `Customer Group` pour transformer ce widget en vrai levier de segmentation commerciale.

```sql
select
    coalesce(nullif(customer_group, ''), 'Non classifie') as category,
    ifnull(sum(base_grand_total), 0) as amount
from `tabSales Invoice`
where docstatus = 1
  and ifnull(is_return, 0) = 0
  and posting_date between :from_date and :to_date
  -- optionnel
  and company = :company
  and customer_group = :customer_group
  and territory = :territory
group by category
order by amount desc
limit :limit
```

### 14. `SALES_THIS_MONTH`

- Categorie: `Ventes`
- Type: `number_card`
- Methode: `custom_dashboard.services.widget_executor.sales_this_month_widget`
- Formule metier: somme du `base_grand_total` des factures soumises sur la periode; secondaire = nombre de factures.
- Tables SQL: `tabSales Invoice`
- Filtres par defaut: `{"period": "this_month", "company": "", "customer_group": "", "territory": ""}`
- Valeur actuelle: `60,234.54 TND`; `12` factures; contexte `Du 2026-04-01 au 2026-04-30`
- Recommandation metier: rapprocher ce KPI de l'objectif mensuel et du pipe restant pour piloter la fin de mois.

```sql
select
    ifnull(sum(base_grand_total), 0) as amount,
    count(*) as invoice_count
from `tabSales Invoice`
where docstatus = 1
  and ifnull(is_return, 0) = 0
  and posting_date between :from_date and :to_date
  -- optionnel
  and company = :company
  and customer_group = :customer_group
  and territory = :territory
```

### 15. `PROFITABLE_PRODUCTS`

- Categorie: `Ventes`
- Type: `table`
- Methode: `custom_dashboard.services.widget_executor.profitable_products_widget`
- Formule metier: `marge = SUM(base_net_amount) - SUM(qty * incoming_rate)` par article; classement desc par marge.
- Tables SQL: `tabSales Invoice Item`, `tabSales Invoice`
- Filtres par defaut: `{"period": "last_90_days", "company": "", "customer_group": "", "territory": "", "limit": 5}`
- Valeur actuelle: top 5 produits par marge. Leader `Projecteur HD 3000 lm`: `56,031.61 TND` de CA, `23,137.93 TND` de marge, `41.3%` de marge.
- Recommandation metier: utiliser cette table pour orienter le mix produit, les bundles et les remises commerciales.

```sql
select
    sii.item_code,
    sii.item_name,
    ifnull(sum(sii.qty), 0) as qty_sold,
    ifnull(sum(sii.base_net_amount), 0) as revenue,
    ifnull(sum(sii.qty * ifnull(sii.incoming_rate, 0)), 0) as cost
from `tabSales Invoice Item` sii
where sii.parent in (
    select name
    from `tabSales Invoice`
    where docstatus = 1
      and ifnull(is_return, 0) = 0
      and posting_date between :from_date and :to_date
      -- optionnel
      and company = :company
      and customer_group = :customer_group
      and territory = :territory
)
group by sii.item_code, sii.item_name
order by (
    ifnull(sum(sii.base_net_amount), 0)
    - ifnull(sum(sii.qty * ifnull(sii.incoming_rate, 0)), 0)
) desc
limit :limit
```

### 16. `TOP_CUSTOMERS`

- Categorie: `Ventes`
- Type: `table`
- Methode: `custom_dashboard.services.widget_executor.top_customers_widget`
- Formule metier: classement des clients par `SUM(base_grand_total)`; secondaire = nombre de factures.
- Tables SQL: `tabSales Invoice`
- Filtres par defaut: `{"period": "last_90_days", "company": "", "customer_group": "", "territory": "", "limit": 5}`
- Valeur actuelle: top client `Sfax Informatique Pro` avec `44,051.07 TND`; les 5 premiers clients concentrent l'essentiel du CA de la periode.
- Recommandation metier: mettre en place un suivi `key account` et comparer CA, marge et encours pour chaque client majeur.

```sql
select
    customer,
    count(*) as invoice_count,
    ifnull(sum(base_grand_total), 0) as amount
from `tabSales Invoice`
where docstatus = 1
  and ifnull(is_return, 0) = 0
  and posting_date between :from_date and :to_date
  -- optionnel
  and company = :company
  and customer_group = :customer_group
  and territory = :territory
group by customer
order by amount desc
limit :limit
```

## Points d'attention transverses

1. Les widgets stock montrent actuellement des entrees mais aucune sortie. Cela impacte directement `STOCK_TURNOVER`, `MONTHLY_STOCK_FLOW` et potentiellement `DORMANT_STOCK`.
2. Les widgets commerciaux montrent une activite reelle en CA, mais le pipeline CRM est vide. Il y a probablement une rupture entre prospection et facturation.
3. `REVENUE_BY_CATEGORY` n'est pas encore exploitable tant que les `Customer Group` restent peu renseignes.
4. La concentration ABC montre une forte dependance a une petite partie du portefeuille article; ces articles doivent etre gouvernes plus finement.

## Priorites recommandees

1. Verifier le flux des sorties stock dans `tabStock Ledger Entry`.
2. Mettre sous controle l'encours client en retard (`OVERDUE_INVOICES`, `AT_RISK_CUSTOMERS`, `PAYMENT_DELAY`).
3. Structurer les dimensions analytiques manquantes (`Customer Group`, pipeline `Opportunity`).
4. Mettre en place un rituel hebdomadaire de lecture des widgets A/R, stock critique et top produits.
