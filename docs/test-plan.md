# Plan de validation

## Stratégie

Les tests utilisent des répertoires temporaires : aucun test ne modifie les données de démonstration. Chaque exigence fonctionnelle possède un test nommé `test_tXXX_...`, facilement repérable dans la sortie.

```powershell
py -3 -m unittest discover -s tests -v
py -3 -m compileall -q .
```

## Cas fonctionnels

| ID | Vérification automatisée | Résultat attendu |
|---|---|---|
| T-001 | création d’un lot valide | lot sauvegardé, statut sans contrôle |
| T-002 | identifiant de lot dupliqué | refus explicite, aucune duplication |
| T-003 | champs obligatoires et quantité | données invalides refusées |
| T-004 | modification et rechargement | persistance et historique préservé |
| T-005 | recherches ID/produit/ligne | résultats exacts |
| T-006 | contrôle de 100 pièces, 3 défauts | 3,00 %, à contrôler, relation conservée |
| T-007 | quantité contrôlée supérieure | refus explicite |
| T-008 | défauts supérieurs au contrôle | refus explicite |
| T-009 | modification des seuils JSON | nouvelle décision appliquée |
| T-010 | plusieurs résultats | pire résultat consolidé |
| T-011 | sans contrôle et taux anormal | deux alertes visibles |
| T-012 | statut incohérent | détection puis correction dérivée |
| T-013 | rapport Markdown | sections et avertissement présents |
| T-014 | export et rechargement | CSV/JSON/manifeste valides, persistance |
| T-015 | restauration des exemples | données restaurées, sauvegarde créée |
| T-016 | choix console invalide | message propre, aucune trace Python |

## Robustesse complémentaire

- en-tête CSV incorrect et valeur numérique invalide avec numéro de ligne ;
- configuration JSON mal formée ;
- interdiction d’un contrôle sur lot archivé ;
- réactivation et recalcul du statut ;
- journalisation des événements métier ;
- identifiants proposés sans collision ;
- chargement et recherche sur 1 000 lots en moins de deux secondes.

## Recette manuelle

Vérifier les alignements dans un terminal Windows et Linux, les accents UTF-8, l’interruption `Ctrl+C`, les confirmations d’archivage/restauration, puis suivre `docs/demo-script.md`.
