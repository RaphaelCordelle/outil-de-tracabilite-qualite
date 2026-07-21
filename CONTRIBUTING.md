# Contribution

Ce projet est un prototype personnel. Toute contribution doit conserver un code simple, la bibliothèque standard Python et le caractère entièrement fictif des données.

Avant une proposition de modification :

1. ajouter ou adapter un test lié au comportement ;
2. exécuter `py -3 -m unittest discover -s tests -v` ;
3. vérifier `py -3 -m compileall -q .` ;
4. mettre à jour la documentation si une règle métier change.

Convention de commits recommandée : `feat:`, `fix:`, `test:`, `docs:` ou `refactor:`.
