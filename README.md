# Quality Traceability Tool

> Prototype personnel inspiré d’un environnement de production électronique.
> Les données, les machines et les procédures présentées ici sont fictives.

J’ai développé cette application pour explorer un besoin concret de traçabilité :
suivre un lot depuis sa création, enregistrer ses contrôles, repérer les écarts et
garder une trace des décisions prises. Le projet comprend aussi un petit suivi
d’équipements, avec incidents, temps d’utilisation et fiches de prévention.

L’application fonctionne entièrement en local avec Python et Tkinter. Elle
n’utilise aucune dépendance externe.

![Tableau de bord](docs/images/gui-dashboard.png)

## Fonctions principales

- créer, rechercher, modifier, archiver et consulter des lots ;
- enregistrer et corriger des contrôles qualité ;
- calculer le taux de défaut et le statut d’un lot ;
- détecter les données incohérentes ;
- suivre une anomalie jusqu’à sa résolution ;
- gérer les équipements, incidents et utilisations ;
- produire un rapport Markdown et un export avec contrôle d’intégrité ;
- conserver un journal des opérations importantes.

Trois modes d'affichage sont disponibles dans **Configuration** :

- **Employé** : saisie des lots et contrôles en attente, incidents et utilisations ;
- **Inspecteur qualité** : validation des contrôles, anomalies et rapports ;
- **Manager** : vue complète, configuration, exports et historique des actions.

Le rôle se change directement en haut de la fenêtre. Ce choix adapte les pages
affichées, mais ne remplace pas un véritable système de comptes utilisateurs.

Les seuils qualité, les lignes de production et les types de défaut sont
modifiables depuis l’application. Ils sont enregistrés dans
`config/quality_rules.json`.

## Lancer le projet

Prérequis : Python 3.8 ou une version plus récente.

```powershell
cd C:\Dev\quality-traceability-tool
py -3 main.py
```

Dans EduPython, il suffit d’ouvrir `main.py` puis de l’exécuter. La commande
`python main.py` fonctionne aussi si Python est disponible dans le `PATH`.

Quelques commandes secondaires sont prévues :

```powershell
py -3 main.py console  # interface texte
py -3 main.py check    # contrôle de cohérence
py -3 main.py report   # rapport Markdown
py -3 main.py export   # copie des données et manifeste SHA-256
py -3 main.py restore  # restauration des données de démonstration
```

## Parcours de démonstration

Pour présenter le projet en quelques minutes :

1. ouvrir le tableau de bord et expliquer les indicateurs ;
2. consulter un lot et les contrôles qui lui sont rattachés ;
3. créer un lot, puis ajouter un contrôle ;
4. ouvrir la page des anomalies et prendre une anomalie en charge ;
5. signaler un incident sur un équipement ;
6. générer un rapport depuis la page **Rapports et exports**.

La donnée volontairement incomplète du jeu de démonstration permet de montrer
la détection d’un lot sans contrôle.

## Organisation du code

```text
main.py             démarrage et commandes
models.py           objets manipulés par l’application
quality_rules.py    calculs, validations et détection des anomalies
storage.py          lecture et écriture des CSV et du JSON
services.py         cas d’usage et règles de gestion
reporting.py        génération du rapport Markdown
console_ui.py       interface texte
gui*.py             interface Tkinter
tests/              tests automatisés
```

Le chemin suivi par une saisie est volontairement simple :

```text
interface → service → validation → stockage → journal d’audit
```

Cette séparation évite de placer les calculs métier dans les boutons de
l’interface. Elle permet aussi de tester le comportement sans ouvrir de
fenêtre.

## Tests

```powershell
py -3 -m unittest discover -s tests -v
```

La suite comprend 47 tests. Elle couvre les règles qualité, la persistance,
les anomalies, les équipements, les rapports, la compatibilité Python et une
recherche sur 1 000 lots. Elle vérifie aussi les profils d'affichage et la
présence permanente des boutons de validation dans les formulaires.

## Choix et limites

Le CSV a été choisi pour que les données restent faciles à lire et à montrer.
Les écritures utilisent un fichier temporaire et conservent une sauvegarde
`.bak` de la version précédente.

Ce stockage convient à une démonstration locale avec un seul utilisateur. Pour
un déploiement réel à plusieurs postes, il faudrait au minimum une base de
données, des comptes utilisateurs, une gestion des droits et des sauvegardes
centralisées.

Les détails sur les règles, le stockage et les tests se trouvent dans
[les notes techniques](docs/technical-notes.md).
