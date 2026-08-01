"""Structures de données utilisées par l'application."""

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
    etat_controle: str = "VALIDE"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class Equipement:
    """Un équipement générique suivi dans le parc local."""

    id_equipement: str
    nom: str
    categorie: str
    zone: str
    criticite: str
    statut: str
    description: str
    guide_fichier: str = ""
    commentaire: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class IncidentEquipement:
    """Un problème signalé sur un équipement."""

    id_incident: str
    id_equipement: str
    date_signalement: str
    gravite: str
    categorie: str
    description: str
    statut: str = "OUVERT"
    action: str = ""
    date_resolution: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class UtilisationEquipement:
    """Une session d'utilisation horodatée d'un équipement."""

    id_utilisation: str
    id_equipement: str
    debut: str
    fin: str
    utilisateur: str
    motif: str
    duree_minutes: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AnomalieDetectee:
    """Résultat structuré produit par le moteur de détection."""

    cle_anomalie: str
    source: str
    type_anomalie: str
    entite_type: str
    entite_id: str
    gravite: str
    description: str


@dataclass
class SuiviAnomalie:
    """État persistant du traitement humain d'une anomalie détectée."""

    id_anomalie: str
    cle_anomalie: str
    source: str
    type_anomalie: str
    entite_type: str
    entite_id: str
    gravite: str
    description: str
    statut: str
    commentaire: str
    date_detection: str
    date_mise_a_jour: str
    date_resolution: str = ""

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
