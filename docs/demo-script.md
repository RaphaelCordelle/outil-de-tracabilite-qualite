# Scénario de démonstration — 5 minutes

## Démonstration rapide

Exécuter `py -3 main.py demo`. La commande affiche les indicateurs, liste les lots, effectue une recherche, détecte les anomalies, génère un rapport et crée un export vérifiable.

## Démonstration interactive

1. Lister les lots pour présenter les quatre statuts.
2. Consulter `LOT-20260702-002` et afficher son contrôle associé.
3. Créer un nouveau lot avec l’identifiant proposé.
4. Ajouter un contrôle de 100 pièces et 3 défauts : montrer le calcul à 3 % et le passage à `A_CONTROLER`.
5. Essayer de réduire sa quantité produite sous 100 : montrer le refus protégeant l’historique.
6. Afficher les anomalies, puis la synthèse.
7. Générer le rapport et montrer les règles actives.
8. Exporter les données et présenter le manifeste SHA-256.
9. Ouvrir le journal d’audit pour montrer la traçabilité des opérations.

## Explication technique courte

« La console appelle un service métier. Celui-ci valide les objets, applique les règles configurées, met à jour le statut, écrit les CSV de façon atomique et journalise l’événement. Les calculs sont séparés du stockage et testés à partir des exigences. »
