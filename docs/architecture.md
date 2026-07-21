# Architecture logicielle

## Principes

Le projet applique une architecture en couches volontairement légère. Chaque module possède une responsabilité identifiable et peut être présenté indépendamment.

```text
main / console_ui
        ↓
TraceabilityService
   ↓          ↓
validation   quality_rules
        ↓
CsvRepository
        ↓
CSV / JSON / audit / exports
```

`main.py` traite les commandes. `console_ui.py` ne calcule aucune règle métier. `TraceabilityService` garantit qu’une opération complète reste cohérente : validation, mise à jour des index, sauvegarde et audit. Les calculs purs sont regroupés dans `quality_rules.py`; ils peuvent être testés sans fichier.

## Cohérence et transactions locales

Une modification de lot est appliquée en mémoire, puis tous ses contrôles sont revalidés. Si la modification rend un contrôle impossible — quantité produite devenue inférieure à la quantité contrôlée, par exemple — le lot retrouve ses valeurs précédentes.

Lors d’un ajout de contrôle, le service met à jour le contrôle, le statut consolidé et les index. En cas d’échec d’écriture, ces changements sont annulés en mémoire. Chaque fichier existant conserve également une copie `.bak`.

## Index et performance

Trois index mémoire donnent un accès direct aux lots, contrôles et contrôles par lot. Le CSV reste la source persistante, mais les actions usuelles évitent de parcourir inutilement toutes les données. Un test de non-régression charge et recherche dans 1 000 lots.

## Audit

`data/audit_events.csv` retrace les événements métier : création, modification, contrôle, archivage, réactivation et correction. `logs/app.log` reste réservé aux informations techniques. Cette séparation évite de confondre preuve fonctionnelle et diagnostic logiciel.

## Décisions assumées

- CSV/JSON : transparents, portables et suffisants pour un MVP mono-utilisateur ;
- bibliothèque standard : installation immédiate et surface technique limitée ;
- archivage plutôt que suppression : préservation de l’historique ;
- SHA-256 dans les exports : vérification de l’intégrité des livrables, pas mécanisme de sécurité avancé ;
- aucune donnée réelle : démonstration de méthode, pas reproduction d’un système d’entreprise.
