# Cahier des charges — synthèse publiable

Quality Traceability Tool est un prototype personnel inspiré d’un environnement de production électronique. Il gère des lots et contrôles fictifs, applique des seuils configurables, détecte les incohérences, persiste en CSV et génère un rapport Markdown.

Le MVP couvre les exigences F-001 à F-022 et les règles R-ERR-001 à R-ERR-010 définies dans le document de travail version 0.1.0. La version 1.1 ajoute, sans modifier ce périmètre, un journal d'audit local, des sauvegardes, l'archivage réversible, une démonstration automatisée, une consultation consolidée et une validation renforcée. Sont exclus : base de données, API web, cloud, Docker, comptes utilisateurs et temps réel.

Les seuils fictifs initiaux sont : conforme jusqu’à 2 %, à contrôler au-delà de 2 % et jusqu’à 5 %, rejeté au-delà de 5 %, anomalie au-delà de 20 %. Le statut lot reprend le pire contrôle. La moyenne rapportée est pondérée par les quantités contrôlées.

Toutes les données et procédures sont fictives. Aucune marque, donnée confidentielle ou information d’entreprise réelle ne doit être ajoutée au projet.
