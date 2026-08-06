# Quality Traceability Tool

Quality Traceability Tool est un prototype développé en Python pour suivre des
lots de production, leurs contrôles qualité et les incidents liés aux
équipements.

Le projet est inspiré de situations que j’ai observées pendant mon stage
ouvrier dans l’industrie électronique. Toutes les données, machines et
procédures présentes dans l’application sont fictives.

![Tableau de bord de l'application](docs/images/gui-dashboard.png)

## Présentation du projet

Après mon stage ouvrier, je voulais créer un projet qui me permette de mieux
comprendre le fonctionnement d’un système de traçabilité industrielle.

L’objectif était de pouvoir répondre à plusieurs questions :

- quel est l’état actuel d’un lot ?
- quels contrôles ont conduit à cet état ?
- quels écarts ont été détectés ?
- quelles actions ont été réalisées pour les traiter ?
- un problème qualité peut-il être lié à un incident sur un équipement ?

J’ai d’abord développé le suivi des lots et des contrôles qualité. J’ai ensuite
ajouté la gestion des anomalies, des équipements et de leurs incidents afin de
relier les différentes informations entre elles.

## Fonctionnalités principales

L’application permet de :

- créer, rechercher et archiver des lots ;
- enregistrer des contrôles qualité ;
- valider ou refuser les contrôles en attente ;
- calculer un taux de défaut à partir de seuils configurables ;
- mettre à jour automatiquement l’état d’un lot ;
- détecter certaines incohérences dans les données ;
- suivre les équipements et leurs périodes d’utilisation ;
- déclarer et traiter des incidents ;
- générer un rapport au format Markdown ;
- exporter les données du projet.

## Profils d’affichage

L’application propose trois profils :

- **Employé** : consultation des lots et saisie des informations courantes ;
- **Inspecteur qualité** : validation des contrôles et traitement des anomalies ;
- **Manager** : vue plus globale sur les lots, les équipements et les rapports.

Ces profils adaptent les pages et les actions affichées dans l’interface.

Ils permettent de simuler plusieurs usages de l’application, mais ne constituent
pas un véritable système de comptes et d’autorisations. Une version utilisée
dans un environnement réel demanderait une authentification et une gestion
sécurisée des droits.

## Installation et lancement

Le projet utilise Python 3.8 ou une version plus récente. Il fonctionne
uniquement avec la bibliothèque standard de Python et ne nécessite donc aucune
dépendance externe.

Sous Windows :

```powershell
git clone https://github.com/RaphaelCordelle/quality-traceability-tool.git
cd quality-traceability-tool
py -3 main.py
```

Sous Linux ou macOS :

```bash
git clone https://github.com/RaphaelCordelle/quality-traceability-tool.git
cd quality-traceability-tool
python3 main.py
```

Au premier lancement, les données fictives présentes dans `samples/` sont
copiées dans `data/`. Les essais réalisés dans l’application ne modifient donc
pas les fichiers d’exemple publiés sur GitHub.

## Commandes disponibles

Certaines fonctions peuvent également être utilisées sans ouvrir l’interface
graphique :

```powershell
py -3 main.py console  # lancer l'interface texte
py -3 main.py check    # vérifier la cohérence des données
py -3 main.py report   # générer un rapport Markdown
py -3 main.py export   # exporter les données
py -3 main.py restore  # restaurer les données fictives
```

Sous Linux ou macOS, il suffit de remplacer `py -3` par `python3`.

## Parcours de démonstration

Pour découvrir rapidement les principales fonctionnalités :

1. ouvrir un lot depuis le tableau de bord ;
2. consulter les contrôles qui déterminent son statut ;
3. créer un nouveau lot ;
4. lui ajouter un contrôle en attente ;
5. passer sur le profil **Inspecteur qualité** ;
6. valider ou refuser le contrôle ;
7. ouvrir une anomalie ou déclarer un incident sur un équipement ;
8. générer un rapport depuis la page **Rapports et exports**.

Un lot du jeu de démonstration ne possède volontairement aucun contrôle. Il
permet de montrer comment l’application détecte puis traite une incohérence dans
les données.

## Organisation du projet

```text
main.py             point d’entrée et gestion des commandes
models.py           structures de données
quality_rules.py    règles de calcul et de validation
storage.py          lecture et écriture des fichiers CSV et JSON
services.py         opérations métier
reporting.py        génération des rapports Markdown
console_ui.py       interface en ligne de commande
gui*.py             interface graphique Tkinter
tests/              tests automatisés
samples/            données fictives d’origine
data/               données utilisées pendant l’exécution
```

Une action réalisée dans l’interface suit généralement ce parcours :

```text
interface → service → validation → stockage
```

Les boutons Tkinter ne modifient donc pas directement les fichiers. Ils
appellent les services, qui appliquent les règles métier avant d’enregistrer les
données.

Cette séparation permet notamment de tester les calculs et les changements
d’état sans avoir à ouvrir l’interface graphique.

## Tests automatisés

Les tests peuvent être lancés avec la commande suivante :

```powershell
py -3 -m unittest discover -s tests -v
```

Sous Linux ou macOS :

```bash
python3 -m unittest discover -s tests -v
```

Le projet contient actuellement **54 tests automatisés**.

Ils couvrent notamment :

- le calcul des statuts des lots ;
- les seuils et taux de défaut ;
- la validation des contrôles ;
- les changements d’état ;
- la lecture et l’écriture des fichiers CSV ;
- la détection et la résolution des anomalies ;
- le suivi des équipements ;
- la gestion des incidents ;
- la génération des rapports.

Chaque test utilise un dossier temporaire afin de ne pas modifier les données de
démonstration.

## Choix techniques

### Stockage dans des fichiers CSV et JSON

J’ai choisi d’utiliser des fichiers CSV et JSON pour garder le projet simple à
installer et permettre de consulter facilement les données enregistrées.

Cette solution m’a permis de me concentrer sur les règles métier, la
traçabilité et les tests sans dépendre d’une base de données.

Lors d’une écriture, les nouvelles données sont d’abord enregistrées dans un
fichier temporaire. L’ancienne version est également conservée dans un fichier
`.bak` afin de limiter les risques de perte en cas de problème pendant
l’enregistrement.

### Séparation de l’interface et de la logique métier

La logique du projet n’est pas directement écrite dans les fenêtres Tkinter.

Les interfaces appellent des services, qui appliquent ensuite les règles de
validation et utilisent le module de stockage. Cela permet de conserver un code
plus facile à tester et à faire évoluer.

### Données de démonstration séparées

Les données présentes dans `samples/` servent de base de démonstration.

Elles sont copiées dans `data/` lors du premier lancement. L’utilisateur peut
ainsi modifier, supprimer ou compléter les données sans altérer les exemples
d’origine.

La commande suivante permet de restaurer les données initiales :

```powershell
py -3 main.py restore
```

## Limites actuelles

Cette version est conçue comme une démonstration locale utilisée par une seule
personne.

Elle ne possède pas encore :

- de base de données centralisée ;
- de véritable authentification ;
- de gestion sécurisée des rôles ;
- de fonctionnement simultané sur plusieurs postes ;
- de sauvegarde distante ;
- d’historique infalsifiable des modifications.

Je ne compte pas pousuivre ces étapes, car cela reste un prototype qui a un usage personnel.
Une version destinée à un usage réel en entreprise demanderait notamment une
base de données, une API, des comptes utilisateurs et une gestion plus stricte
des autorisations.

Les règles métier et le fonctionnement du stockage sont présentés plus en détail
dans les [notes techniques](docs/technical-notes.md).

## Auteur

**Raphael Cordelle**  
Étudiant ingénieur à l’ESIEE Paris
