"""Interface console interactive.

Ce module ne calcule aucune règle qualité : il collecte les saisies, appelle le
service puis présente le résultat. Cette séparation facilite les tests.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from models import ControleQualite, Lot, LotDetails, QualitySummary
from report import generate_report
from service import TraceabilityService
from storage import StorageError
from validation import ValidationError


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix} : ").strip()
    return value or default


def ask_integer(prompt: str, default: int | None = None) -> int:
    while True:
        value = ask(prompt, str(default) if default is not None else "")
        try:
            return int(value)
        except ValueError:
            print("Veuillez saisir un nombre entier.")


def confirm(prompt: str) -> bool:
    return ask(f"{prompt} (o/N)").casefold() in {"o", "oui"}


def show_lots(lots: list[Lot]) -> None:
    if not lots:
        print("Aucun lot trouvé.")
        return
    print(
        f"{'ID lot':<20} {'Produit':<20} {'Ligne':<10} "
        f"{'Quantité':>9}  {'Statut':<14}"
    )
    print("-" * 89)
    for lot in lots:
        print(
            f"{lot.id_lot:<20} {lot.produit:<20} {lot.ligne_production:<10} "
            f"{lot.quantite_produite:>9}  {lot.statut:<14}"
        )


def show_controls(controls: list[ControleQualite]) -> None:
    if not controls:
        print("Aucun contrôle enregistré.")
        return
    print(
        f"{'ID contrôle':<20} {'ID lot':<20} {'Date':<10} "
        f"{'Qté':>6} {'Défauts':>8} {'Taux':>8}  Résultat"
    )
    print("-" * 103)
    for control in controls:
        print(
            f"{control.id_controle:<20} {control.id_lot:<20} "
            f"{control.date_controle:<10} {control.quantite_controlee:>6} "
            f"{control.nombre_defauts:>8} {control.taux_defaut:>7.2f}%  "
            f"{control.resultat}"
        )


def show_details(details: LotDetails) -> None:
    lot = details.lot
    print(f"\nLOT {lot.id_lot}")
    print(f"  Création      : {lot.date_creation}")
    print(f"  Produit       : {lot.produit}")
    print(f"  Quantité      : {lot.quantite_produite}")
    print(f"  Ligne         : {lot.ligne_production}")
    print(f"  Statut        : {lot.statut}")
    print(f"  Commentaire   : {lot.commentaire or '—'}")
    print(f"  Total contrôlé: {details.total_controle}")
    print(f"  Total défauts : {details.total_defauts}")
    print(f"  Taux pondéré  : {details.taux_defaut_pondere:.2f} %")
    print("\nCONTRÔLES ASSOCIÉS")
    show_controls(list(details.controles))


def show_summary(summary: QualitySummary) -> None:
    print("SYNTHÈSE QUALITÉ")
    print(f"  Lots             : {summary.total_lots}")
    print(f"  Conformes         : {summary.lots_conformes}")
    print(f"  À contrôler       : {summary.lots_a_controler}")
    print(f"  Rejetés           : {summary.lots_rejetes}")
    print(f"  Sans contrôle     : {summary.lots_sans_controle}")
    print(f"  Archivés          : {summary.lots_archives}")
    print(f"  Contrôles         : {summary.total_controles}")
    print(f"  Taux moyen pondéré: {summary.taux_defaut_moyen:.2f} %")


class ConsoleApplication:
    """Menu interactif stable qui convertit les erreurs en messages lisibles."""

    MENU = """
=== Quality Traceability Tool ===
Prototype personnel — données intégralement fictives

1. Créer un lot                 8. Détecter les anomalies
2. Modifier un lot              9. Afficher la synthèse
3. Consulter un lot            10. Générer un rapport
4. Rechercher des lots         11. Exporter les données
5. Lister les lots             12. Consulter le journal d'audit
6. Ajouter un contrôle         13. Archiver ou réactiver un lot
7. Lister les contrôles        14. Corriger les champs dérivés
15. Restaurer la démonstration
0. Quitter
"""

    def __init__(self, service: TraceabilityService, root: Path) -> None:
        self.service = service
        self.root = root
        self.actions = {
            "1": self.create_lot,
            "2": self.update_lot,
            "3": self.show_lot,
            "4": self.search,
            "5": lambda: show_lots(self.service.lots),
            "6": self.add_control,
            "7": lambda: show_controls(self.service.controls),
            "8": self.show_anomalies,
            "9": lambda: show_summary(self.service.summary()),
            "10": self.generate_report,
            "11": self.export,
            "12": self.show_audit,
            "13": self.change_archive_state,
            "14": self.repair,
            "15": self.restore_demo,
        }

    def run(self) -> None:
        while True:
            print(self.MENU)
            choice = input("Choix : ").strip()
            if choice == "0":
                print("Au revoir.")
                return
            action = self.actions.get(choice)
            if action is None:
                print("Choix invalide.")
                continue
            try:
                action()
            except (ValidationError, StorageError, ValueError, OSError) as exc:
                print(f"Erreur : {exc}")

    def create_lot(self) -> None:
        suggested_id = self.service.next_lot_id()
        lot = Lot(
            id_lot=ask("Identifiant", suggested_id),
            date_creation=ask("Date (YYYY-MM-DD)", date.today().isoformat()),
            produit=ask("Référence produit fictive").upper(),
            quantite_produite=ask_integer("Quantité produite"),
            ligne_production=ask("Ligne de production").upper(),
            commentaire=ask("Commentaire (optionnel)"),
        )
        self.service.create_lot(lot)
        print(f"Lot {lot.id_lot} enregistré.")

    def update_lot(self) -> None:
        lot = self.service.require_lot(ask("Identifiant du lot").upper())
        updated = self.service.update_lot(
            lot.id_lot,
            date_creation=ask("Date", lot.date_creation),
            produit=ask("Produit", lot.produit).upper(),
            quantite_produite=ask_integer("Quantité", lot.quantite_produite),
            ligne_production=ask("Ligne", lot.ligne_production).upper(),
            commentaire=ask("Commentaire", lot.commentaire),
        )
        print(f"Lot {updated.id_lot} mis à jour et contrôles revalidés.")

    def show_lot(self) -> None:
        show_details(self.service.lot_details(ask("Identifiant du lot").upper()))

    def search(self) -> None:
        field = ask("Filtre (all, id, produit, ligne, statut)", "all").casefold()
        show_lots(self.service.search_lots(ask("Valeur recherchée"), field))

    def add_control(self) -> None:
        lot_id = ask("Identifiant du lot").upper()
        self.service.require_lot(lot_id)
        control = ControleQualite(
            id_controle=ask("Identifiant", self.service.next_control_id()).upper(),
            id_lot=lot_id,
            date_controle=ask("Date (YYYY-MM-DD)", date.today().isoformat()),
            quantite_controlee=ask_integer("Quantité contrôlée"),
            nombre_defauts=ask_integer("Nombre de défauts"),
            type_defaut=ask("Type de défaut").upper(),
            taux_defaut=0.0,
            resultat="",
            commentaire=ask("Commentaire (optionnel)"),
        )
        self.service.add_control(control)
        print(
            f"Contrôle {control.id_controle} enregistré : "
            f"{control.taux_defaut:.2f} %, résultat {control.resultat}."
        )

    def show_anomalies(self) -> None:
        anomalies = self.service.anomalies()
        if not anomalies:
            print("Aucune anomalie détectée.")
            return
        print(f"{len(anomalies)} anomalie(s) ou alerte(s) :")
        for item in anomalies:
            print(f"- {item}")

    def generate_report(self) -> None:
        path = generate_report(
            self.root, self.service.lots, self.service.controls, self.service.rules
        )
        print(f"Rapport créé : {path}")

    def export(self) -> None:
        path = self.service.repository.export(
            self.service.lots, self.service.controls, self.service.summary()
        )
        print(f"Export créé avec manifeste SHA-256 : {path}")

    def show_audit(self) -> None:
        events = self.service.repository.load_audit_events(limit=20)
        if not events:
            print("Le journal d'audit est vide.")
            return
        for event in events:
            print(
                f"{event['horodatage']} | {event['evenement']:<24} | "
                f"{event['type_entite']} {event['id_entite']} | {event['details']}"
            )

    def change_archive_state(self) -> None:
        lot = self.service.require_lot(ask("Identifiant du lot").upper())
        if lot.statut == "ARCHIVE":
            if confirm(f"Réactiver {lot.id_lot} ?"):
                self.service.restore_lot(lot.id_lot)
                print(f"Lot réactivé avec le statut {lot.statut}.")
        elif confirm(f"Archiver {lot.id_lot} ?"):
            self.service.archive_lot(lot.id_lot)
            print("Lot archivé. Son historique reste consultable.")

    def repair(self) -> None:
        if not confirm("Recalculer les taux, résultats et statuts incohérents ?"):
            print("Opération annulée.")
            return
        count = self.service.repair_inconsistencies()
        print(f"{count} champ(s) dérivé(s) corrigé(s).")

    def restore_demo(self) -> None:
        print("Cette opération remplace les données courantes et conserve des .bak.")
        if ask("Saisir OUI pour confirmer") != "OUI":
            print("Restauration annulée.")
            return
        self.service.repository.restore_sample_data()
        self.service = TraceabilityService(self.root)
        print("Jeu de démonstration fictif restauré.")
