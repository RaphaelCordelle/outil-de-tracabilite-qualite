# Présentation CV et entretien

## Formulation CV

**Quality Traceability Tool — Python** : développement d’un prototype personnel de traçabilité qualité inspiré d’un environnement de production électronique, avec gestion de lots fictifs, contrôles qualité, règles configurables, détection d’anomalies, audit, reporting Markdown et tests reliés aux exigences.

## Points à défendre en entretien

- choix d’un stockage CSV proportionné au MVP et limites clairement documentées ;
- séparation interface/service/règles/validation/stockage ;
- conservation de l’historique par archivage ;
- validation d’une modification contre les contrôles déjà enregistrés ;
- distinction entre log technique et audit métier ;
- moyenne pondérée plutôt qu’une moyenne simple des pourcentages ;
- matrice reliant exigences, tests et preuves ;
- décision explicite de ne jamais utiliser de donnée réelle d’entreprise.

## Questions probables

**Pourquoi ne pas utiliser une base de données ?** Le cahier des charges impose un MVP standard Python. Le CSV rend les preuves inspectables et suffit au volume de démonstration. Une base deviendrait pertinente pour la concurrence, les transactions multi-utilisateurs et les volumes élevés.

**Comment passer à un système industriel ?** Introduire une base transactionnelle, une gestion des identités et rôles, des migrations de schéma, une API authentifiée, des sauvegardes administrées et des validations métier spécifiques au contexte réel.

**Comment garantissez-vous la cohérence ?** Validation avant écriture, revalidation des contrôles lors d’une modification, calcul centralisé des champs dérivés, écritures atomiques, sauvegardes et tests de non-régression.
