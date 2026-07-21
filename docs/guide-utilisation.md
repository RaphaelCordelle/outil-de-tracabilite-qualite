# Guide d’utilisation

## Formats attendus

- lot : `LOT-YYYYMMDD-XXX` ;
- contrôle : `QC-YYYYMMDD-XXX` ;
- date : `YYYY-MM-DD` ;
- produit : 2 à 40 caractères majuscules, chiffres, `_` ou `-` ;
- lignes et défauts : valeurs de `config/quality_rules.json`.

Les identifiants et la date du jour sont proposés automatiquement dans la console.

## Cycle d’un lot

Un lot commence au statut `SANS_CONTROLE`. Chaque contrôle obtient automatiquement un taux et un résultat. Le lot prend le pire résultat observé : `REJETE`, puis `A_CONTROLER`, puis `CONFORME`.

Un lot archivé reste consultable mais n’accepte plus de contrôle. Sa réactivation recalcule son statut depuis son historique. La quantité ou la date d’un lot contrôlé ne peut pas être modifiée si cela invalide un contrôle existant.

## Anomalies et correction

La détection ne modifie jamais les données. Elle signale les lots sans contrôle, taux anormaux et champs calculés incohérents. L’action de correction recalcule uniquement `taux_defaut`, `resultat` et `statut`; elle ne corrige pas silencieusement les données saisies.

## Fichiers générés

- `reports/quality_report_*.md` : synthèse lisible ;
- `exports/export_*/` : copies CSV, configuration, synthèse JSON et manifeste ;
- `data/*.csv.bak` : sauvegarde avant la dernière écriture ;
- `data/audit_events.csv` : événements métier ;
- `logs/app.log` : diagnostics techniques.

## Restauration

L’action 15 ou `py -3 sample_data.py` demande une confirmation explicite. Les fichiers courants sont copiés en `.bak` avant restauration.
