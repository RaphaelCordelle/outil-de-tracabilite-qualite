# Procès-verbal de vérification — version 1.1.0

Date : 2026-07-21  
Environnement : Python 3.12, Windows  
Nature : prototype personnel, données intégralement fictives

## Résultats

| Vérification | Résultat |
|---|---|
| Compilation de tous les modules | Réussie |
| Exigences T-001 à T-016 | 16/16 réussies |
| Tests de robustesse complémentaires | 6/6 réussis |
| Test de performance à 1 000 lots | Réussi |
| Total automatisé | **23/23 réussis** |
| Commande `check` sur les exemples | Fonctionnelle, 1 alerte attendue |
| Commande `demo` | Fonctionnelle |
| Génération du rapport | Fonctionnelle |
| Export CSV/JSON/SHA-256 | Fonctionnel |

L’alerte attendue concerne `LOT-20260704-004`, volontairement livré sans contrôle afin de démontrer la détection F-013.

## Commandes exécutées

```powershell
py -3 -m compileall -q .
py -3 -m unittest discover -s tests -v
py -3 main.py --version
py -3 main.py check
py -3 main.py demo
```

La recette visuelle interactive reste à effectuer dans le terminal cible, notamment pour vérifier la largeur d’affichage et le rendu des accents.
