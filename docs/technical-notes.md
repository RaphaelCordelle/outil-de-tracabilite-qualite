# Notes techniques

Ce document rassemble les informations utiles pour relire le code ou préparer
une présentation. Il complète le README sans reprendre chaque écran.

## Découpage

Le projet suit une architecture en couches légère :

| Module | Rôle |
|---|---|
| `models.py` | décrit les lots, contrôles, équipements et anomalies |
| `quality_rules.py` | calcule les résultats et valide les données |
| `storage.py` | lit et écrit les fichiers locaux |
| `services.py` | exécute les actions demandées par l’utilisateur |
| `reporting.py` | construit le rapport Markdown |
| `gui*.py` | affiche les pages et les formulaires |
| `main.py` | choisit le mode de démarrage |

L’interface ne modifie jamais directement un fichier. Elle appelle
`TraceabilityService`, qui valide la demande, enregistre la nouvelle valeur puis
ajoute un événement d’audit.

## Modes d'affichage

La vue choisie dans la barre supérieure détermine les pages et les actions visibles.
L'employé se concentre sur la saisie et les équipements. L'inspecteur qualité
valide les contrôles et traite les anomalies. Le manager voit aussi les réglages,
les exports et l'historique.

Il s'agit uniquement d'une adaptation de l'interface. Une version déployée en
entreprise devrait utiliser de vrais comptes et vérifier les droits dans le
service métier, pas seulement masquer des boutons.

## Changements d'état

Chaque état modifiable possède une action visible dans au moins une vue :

| Élément | Action prévue |
|---|---|
| lot | statut calculé depuis les contrôles, avec archivage et réactivation |
| contrôle | passage entre en attente, validé et annulé par le profil qualité |
| anomalie | acquittement, prise en charge ou justification ; résolution automatique |
| équipement | mise sous surveillance ou blocage selon la gravité des incidents actifs |
| incident | passage contrôlé d'ouvert à en cours, résolu puis clôturé ; le dernier incident bloquant libère l'équipement |
| utilisation | démarrage et fin horodatés |

## Règles qualité

Le taux d’un contrôle est calculé ainsi :

```text
nombre de défauts / quantité contrôlée × 100
```

Avec la configuration fournie :

- jusqu’à 2 % : `CONFORME` ;
- au-dessus de 2 % et jusqu’à 5 % : `A_CONTROLER` ;
- au-dessus de 5 % : `REJETE` ;
- au-dessus de 20 % : une alerte supplémentaire est créée.

Le statut d’un lot correspond au résultat le plus défavorable de ses contrôles
validés. Un contrôle en attente ou annulé ne participe pas aux indicateurs.

## Anomalies

La détection et le suivi sont séparés. Le moteur détecte une cause à partir des
données ; l’utilisateur gère ensuite son traitement avec un statut et un
commentaire.

Une anomalie peut être nouvelle, acquittée, en cours, ignorée avec justification
ou résolue. Elle n’est pas effacée du fichier de suivi : l’historique reste ainsi
visible dans l’audit et les exports. Si la cause disparaît, la résolution est
automatique. Si elle revient, l’anomalie est rouverte.

## Fichiers locaux

Les données actives se trouvent dans `data/`, qui n'est pas versionné. Lors du
premier lancement, le contenu fictif de `samples/` y est copié automatiquement.
La restauration est disponible en ligne de commande et dans la configuration Manager.

| Fichier | Contenu |
|---|---|
| `lots.csv` | lots et statuts consolidés |
| `controls.csv` | contrôles et états de validation |
| `anomaly_tracking.csv` | traitement des anomalies |
| `equipment.csv` | parc d’équipements |
| `equipment_issues.csv` | incidents |
| `equipment_usage.csv` | périodes d’utilisation |
| `audit_events.csv` | opérations importantes |

Avant de remplacer un CSV, le dépôt écrit d’abord un fichier temporaire. La
version précédente est conservée avec l’extension `.bak`. Les exports ajoutent
un manifeste SHA-256 pour permettre de vérifier qu’un fichier n’a pas changé.

Le journal d'audit conserve les changements importants avec leur date, l'élément
concerné et le profil d'affichage utilisé. Il sert à comprendre l'origine d'un
statut ou d'une correction. Le prototype ne stocke pas d'identité nominative.

## Tests

Les tests utilisent un dossier temporaire et ne touchent donc pas aux données de
démonstration. Ils sont répartis par sujet :

- exigences principales dans `test_requirements.py` ;
- erreurs de fichier et cas limites dans `test_robustness.py` ;
- équipements dans `test_equipment.py` ;
- anomalies dans `test_anomaly_workflow.py` ;
- démarrage graphique sans affichage dans `test_gui_structure.py` ;
- profils d'affichage dans `test_access_modes.py` ;
- recherche sur 1 000 lots dans `test_performance.py`.

## Limites connues

Le projet reste volontairement local et mono-utilisateur. Il ne gère ni
authentification, ni accès concurrents, ni synchronisation entre postes. Les
fiches équipements sont des rappels généraux : elles ne remplacent jamais une
notice constructeur, une formation ou une procédure de sécurité.
