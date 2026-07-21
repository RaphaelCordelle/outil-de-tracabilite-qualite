# Limites et feuille de route

## Limites connues et assumées

- usage local mono-utilisateur ;
- CSV sans verrou distribué ni transaction entre plusieurs processus ;
- audit local modifiable par un utilisateur ayant accès aux fichiers ;
- référentiels simples chargés au démarrage ;
- aucun compte, rôle, signature électronique ou approbation qualité ;
- absence de liaison avec un équipement ou un système d’entreprise ;
- rapport Markdown, sans génération PDF native.

Ces limites sont cohérentes avec un prototype personnel et ne sont pas masquées dans la démonstration.

## Étape suivante raisonnable

Avant toute extension technique, réaliser une recette avec plusieurs utilisateurs et relever les erreurs de compréhension. La première évolution pourrait ensuite être une interface Tkinter locale utilisant le même service métier.

## Extensions séparées du MVP

1. interface Tkinter et graphiques locaux ;
2. import de résultats PASS/FAIL fictifs avec aperçu avant validation ;
3. export HTML/PDF ;
4. liaison série vers un banc pédagogique ;
5. remplacement du dépôt CSV par une interface de stockage compatible SQLite.

Une API, le cloud, Docker et une authentification complète ne sont justifiés que dans un autre périmètre.
