# Historique des versions

## 1.1.1 — 2026-07-29

- compatibilité étendue à Python 3.8 et 3.9, notamment EduPython ;
- retrait de l'option `dataclass(slots=True)` introduite seulement en Python 3.10 ;
- annotations différées pour conserver les types modernes sans erreur au démarrage.

## 1.1.0 — 2026-07-21

- ajout de la consultation consolidée des lots et contrôles ;
- archivage réversible et protection des lots contrôlés ;
- validation renforcée des dates, références et seuils ;
- détection des taux et résultats stockés incohérents ;
- journal d’audit métier et rotation du log technique ;
- écritures atomiques, sauvegardes `.bak` et erreurs CSV détaillées ;
- exports horodatés avec synthèse JSON et manifeste SHA-256 ;
- commandes `demo`, `check`, `report` et `export` ;
- rapport enrichi avec couverture et indicateurs par ligne ;
- 23 tests automatisés, dont T-001 à T-016 et 1 000 lots.

## 1.0.0 — 2026-07-11

- première version fonctionnelle du MVP ;
- lots, contrôles, règles configurables, anomalies, CSV et rapport Markdown.
