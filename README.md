# Quality Traceability Tool

> **Prototype personnel inspiré d’un environnement de production électronique.** Toutes les données, références, lignes, défauts, seuils et procédures sont fictifs. Le projet n’est rattaché à aucune entreprise ni à aucun système industriel réel.

Quality Traceability Tool est un MVP Python de suivi qualité local. Il relie des lots fictifs à leurs contrôles, applique des règles configurables, détecte les incohérences et produit des rapports vérifiables. Le projet montre une approche complète : modélisation métier, validation, traçabilité, persistance, reporting, tests et documentation.

## Ce que le projet démontre

- architecture Python modulaire et compréhensible ;
- règles métier isolées et testables ;
- intégrité des relations lot/contrôle ;
- gestion explicite des erreurs et fichiers corrompus ;
- taux de défaut et statuts calculés depuis une configuration JSON ;
- journal d’événements métier distinct du log technique ;
- exports horodatés avec manifeste SHA-256 ;
- tests reliés aux exigences fonctionnelles `T-001` à `T-016` ;
- fonctionnement fluide vérifié sur 1 000 lots fictifs.

## Fonctionnalités

- création, modification, archivage et réactivation des lots ;
- recherche par identifiant, produit, ligne ou statut ;
- consultation détaillée d’un lot et de tous ses contrôles ;
- ajout de contrôles avec validation des dates et quantités ;
- consolidation du pire résultat au niveau du lot ;
- protection de l’historique lors de la modification d’un lot contrôlé ;
- anomalies : lot sans contrôle, taux anormal, taux/résultat/statut incohérent ;
- correction explicite des seuls champs calculés ;
- synthèse globale et rapport Markdown par ligne fictive ;
- sauvegardes `.bak`, données de démonstration réinitialisables et journal d’audit.

## Installation

Prérequis : Python 3.10 ou plus récent. Aucune dépendance externe.

```powershell
cd C:\Dev\quality-traceability-tool
py -3 main.py
```

Si `python` est enregistré dans le PATH, `python main.py` fonctionne également.

## Commandes utiles

```powershell
# Interface interactive
py -3 main.py

# Démonstration complète sans saisie
py -3 main.py demo

# Contrôle de cohérence
py -3 main.py check

# Rapport ou export direct
py -3 main.py report
py -3 main.py export

# Restauration confirmée du jeu fictif
py -3 sample_data.py

# Tests
py -3 -m unittest discover -s tests -v
```

## Architecture

| Élément | Responsabilité |
|---|---|
| `main.py` | commandes et démarrage de l’application |
| `console_ui.py` | saisies et affichage console |
| `service.py` | orchestration des cas d’usage et transactions métier |
| `models.py` | structures Lot, Contrôle, Détail et Synthèse |
| `validation.py` | validation des données, configuration et anomalies |
| `quality_rules.py` | calcul des taux, décisions et consolidation |
| `storage.py` | CSV, sauvegardes, audit, JSON et exports |
| `report.py` | rapport qualité Markdown |

Le flux principal est : **saisie → validation → règle métier → persistance atomique → audit**. Les fichiers CSV restent inspectables à la main et sont adaptés au périmètre local mono-utilisateur du MVP.

## Démonstration en entretien

Le chemin le plus rapide est `py -3 main.py demo`. Pour une démonstration interactive de cinq minutes, suivre [le scénario préparé](docs/demo-script.md). La [présentation CV](docs/presentation-cv.md) propose une formulation concise et les choix techniques à expliquer.

## Tests et qualité

La suite contient 23 tests : exigences `T-001` à `T-016`, erreurs de stockage, archivage, audit, génération d’identifiants et test sur 1 000 lots. Voir le [plan de validation](docs/test-plan.md), la [matrice de traçabilité](docs/traceability-matrix.md) et le [procès-verbal de vérification](docs/verification.md).

## Limites assumées

Le stockage CSV est destiné à une démonstration locale mono-utilisateur. Il ne fournit ni concurrence d’écriture, ni authentification, ni synchronisation réseau. Il n’y a volontairement ni base de données, ni API web, ni cloud, ni Docker, conformément au périmètre du MVP.

Version actuelle : **1.1.0** — voir [CHANGELOG.md](CHANGELOG.md).
