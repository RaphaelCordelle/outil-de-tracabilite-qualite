# Rapport qualité — Quality Traceability Tool

**Généré le :** 2026-07-21 à 23:02:25 UTC+0200

> Prototype personnel inspiré d’un environnement de production électronique. Toutes les données et procédures sont fictives.

## Synthèse exécutive

Le jeu analysé contient **4 lots** et **3 contrôles**. La couverture de contrôle atteint **75.0 %** et le taux de défaut pondéré est de **3.60 %**.

## Indicateurs globaux

| Indicateur | Valeur |
|---|---|
| Total des lots | 4 |
| Lots conformes | 1 |
| Lots à contrôler | 1 |
| Lots rejetés | 1 |
| Lots sans contrôle | 1 |
| Lots archivés | 0 |
| Contrôles enregistrés | 3 |
| Quantité totale contrôlée | 250 |
| Défauts comptabilisés | 9 |
| Couverture des lots actifs | 75.0 % |
| Taux de défaut moyen pondéré | 3.60 % |

## Anomalies et alertes

- Lot LOT-20260704-004 sans contrôle qualité.

## Lots nécessitant une attention

| Lot | Produit | Ligne | Quantité | Statut |
|---|---|---|---|---|
| LOT-20260702-002 | MODULE_IO_B2 | LINE-02 | 300 | A_CONTROLER |
| LOT-20260703-003 | SENSOR_NODE_C1 | LINE-03 | 200 | REJETE |

## Défauts fréquents

| Type de défaut | défaut(s) |
|---|---|
| SOUDURE_FROIDE | 4 |
| TEST_ELECTRIQUE | 4 |
| DEFAUT_VISUEL | 1 |

## Indicateurs par ligne fictive

| Ligne | Contrôles | Quantité contrôlée | Taux pondéré |
|---|---|---|---|
| LINE-01 | 1 | 100 | 1.00 % |
| LINE-02 | 1 | 100 | 4.00 % |
| LINE-03 | 1 | 50 | 8.00 % |

## Règles actives

- Conforme : taux ≤ 2.00 %
- À contrôler : 2.00 % < taux ≤ 5.00 %
- Rejeté : taux > 5.00 %
- Alerte taux anormal : taux > 20.00 %

## Conclusion et limites

Cette synthèse illustre la consolidation de règles configurables sur un échantillon fictif. Elle ne constitue ni une décision industrielle réelle, ni une procédure de libération produit. Le stockage CSV est destiné à un prototype local mono-utilisateur.
