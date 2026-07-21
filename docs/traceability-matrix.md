# Matrice de traçabilité exigences/tests

| Exigence | Cas | Implémentation principale | Statut |
|---|---|---|---|
| F-001 | T-001 | `TraceabilityService.create_lot` | Vérifié |
| F-002 | T-002 | index `_lots_by_id` | Vérifié |
| F-003 | T-004 | `update_lot` avec retour arrière | Vérifié |
| F-004, F-005 | T-005 | `search_lots`, `show_lots` | Vérifié |
| F-006 | T-003 | `validate_lot` | Vérifié |
| F-007, F-008 | T-006 | `add_control`, `calculate_defect_rate` | Vérifié |
| F-009, F-022 | T-009 | `determine_result`, configuration JSON | Vérifié |
| F-010 | T-010 | `consolidate_status` | Vérifié |
| F-011 | T-007 | `validate_control` | Vérifié |
| F-012 | T-008 | `validate_control` | Vérifié |
| F-013, F-015 | T-011 | `detect_anomalies` | Vérifié |
| F-014 | T-012 | détection et `repair_inconsistencies` | Vérifié |
| F-016 | T-013 | `generate_report` | Vérifié |
| F-017, F-018, F-021 | T-014 | `CsvRepository.export`, rechargement | Vérifié |
| F-019 | T-015 | `samples/`, restauration confirmée | Vérifié |
| F-020 | T-016 | `ConsoleApplication` | Vérifié |

La couverture supplémentaire porte sur N-003 (erreurs propres), N-004 (1 000 lots), N-007/N-009 (validation et intégrité), N-010 (présente matrice) et N-011 (documentation).
