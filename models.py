"""Objets métier du prototype de traçabilité qualité.

Les modèles ne contiennent aucune logique de stockage. Ils décrivent uniquement
les données échangées entre l'interface, le service métier et les rapports.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Lot:
    """Un lot fictif suivi par l'outil."""

    id_lot: str
    date_creation: str
    produit: str
    quantite_produite: int
    ligne_production: str
    statut: str = "SANS_CONTROLE"
    commentaire: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ControleQualite:
    """Un contrôle qualité rattaché à un lot."""

    id_controle: str
    id_lot: str
    date_controle: str
    quantite_controlee: int
    nombre_defauts: int
    type_defaut: str
    taux_defaut: float
    resultat: str
    commentaire: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LotDetails:
    """Vue consolidée d'un lot et de ses contrôles."""

    lot: Lot
    controles: tuple[ControleQualite, ...]
    total_controle: int
    total_defauts: int
    taux_defaut_pondere: float


@dataclass(frozen=True)
class QualitySummary:
    """Indicateurs globaux calculés à la demande."""

    total_lots: int
    lots_conformes: int
    lots_a_controler: int
    lots_rejetes: int
    lots_sans_controle: int
    lots_archives: int
    total_controles: int
    quantite_controlee: int
    nombre_defauts: int
    taux_defaut_moyen: float
