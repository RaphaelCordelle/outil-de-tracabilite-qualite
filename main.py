"""Point d'entrée du Quality Traceability Tool."""

from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from console_ui import ConsoleApplication, show_lots, show_summary
from report import generate_report
from service import TraceabilityService
from storage import StorageError
from validation import ValidationError

ROOT = Path(__file__).resolve().parent
VERSION = "1.1.1"


def configure_logging() -> None:
    """Conserve un journal technique borné à trois fichiers de 250 Ko."""

    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    handler = RotatingFileHandler(
        logs / "app.log",
        maxBytes=250_000,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prototype personnel de traçabilité qualité sur données fictives. "
            "Sans commande, l'interface interactive est lancée."
        )
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("interactive", help="ouvrir le menu console")
    subcommands.add_parser("demo", help="exécuter une démonstration non interactive")
    subcommands.add_parser("check", help="contrôler la cohérence des données")
    subcommands.add_parser("report", help="générer un rapport Markdown")
    subcommands.add_parser("export", help="exporter CSV, JSON et manifeste SHA-256")
    return parser


def run_demo(service: TraceabilityService) -> None:
    """Présente le scénario principal sans modifier les données métier."""

    print("=== DÉMONSTRATION QUALITY TRACEABILITY TOOL ===")
    print("Prototype personnel — données et procédures intégralement fictives.\n")
    show_summary(service.summary())
    print("\nLOTS DISPONIBLES")
    show_lots(service.lots)
    print("\nRECHERCHE PRODUIT : MODULE")
    show_lots(service.search_lots("MODULE", "produit"))
    print("\nCONTRÔLE DE COHÉRENCE")
    anomalies = service.anomalies()
    if anomalies:
        for anomaly in anomalies:
            print(f"- {anomaly}")
    else:
        print("Aucune anomalie détectée.")
    report_path = generate_report(ROOT, service.lots, service.controls, service.rules)
    export_path = service.repository.export(
        service.lots, service.controls, service.summary()
    )
    print(f"\nRapport généré : {report_path}")
    print(f"Export vérifiable : {export_path}")


def execute(args: argparse.Namespace, service: TraceabilityService) -> int:
    if args.command in (None, "interactive"):
        ConsoleApplication(service, ROOT).run()
        return 0
    if args.command == "demo":
        run_demo(service)
        return 0
    if args.command == "check":
        anomalies = service.anomalies()
        show_summary(service.summary())
        print()
        if anomalies:
            print(f"{len(anomalies)} anomalie(s) ou alerte(s) détectée(s) :")
            for anomaly in anomalies:
                print(f"- {anomaly}")
        else:
            print("Aucune anomalie détectée.")
        return 0
    if args.command == "report":
        path = generate_report(ROOT, service.lots, service.controls, service.rules)
        print(f"Rapport créé : {path}")
        return 0
    if args.command == "export":
        path = service.repository.export(
            service.lots, service.controls, service.summary()
        )
        print(f"Export créé : {path}")
        return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return execute(args, TraceabilityService(ROOT))
    except (StorageError, ValidationError, OSError, ValueError) as exc:
        logging.exception("Erreur bloquante")
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOpération interrompue.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
