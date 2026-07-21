# Dictionnaire de données

## Lot

| Champ | Type | Règle |
|---|---|---|
| `id_lot` | texte | unique, `LOT-YYYYMMDD-XXX` |
| `date_creation` | date ISO | non future |
| `produit` | texte | référence fictive normalisée |
| `quantite_produite` | entier | strictement positive |
| `ligne_production` | texte | référentiel JSON |
| `statut` | texte | calculé ou `ARCHIVE` |
| `commentaire` | texte | optionnel, 250 caractères par défaut |

## Contrôle qualité

| Champ | Type | Règle |
|---|---|---|
| `id_controle` | texte | unique, `QC-YYYYMMDD-XXX` |
| `id_lot` | texte | lot existant et actif |
| `date_controle` | date ISO | entre création du lot et date actuelle |
| `quantite_controlee` | entier | entre 1 et quantité produite |
| `nombre_defauts` | entier | entre 0 et quantité contrôlée |
| `type_defaut` | texte | référentiel JSON ou `AUTRE` |
| `taux_defaut` | décimal | calculé à deux décimales |
| `resultat` | texte | calculé depuis les seuils |
| `commentaire` | texte | optionnel |

## Événement d’audit

Un événement contient un horodatage local ISO, un nom d’événement, un type et identifiant d’entité, puis un détail court. Il ne contient aucune donnée sensible.
