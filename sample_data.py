"""Restauration explicite du jeu de démonstration fictif."""

import argparse
from pathlib import Path

from storage import CsvRepository, StorageError

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restaure les CSV fictifs livrés dans samples/."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="confirmer le remplacement des données sans question interactive",
    )
    args = parser.parse_args()
    if not args.yes:
        answer = input(
            "Les données actuelles seront sauvegardées en .bak puis remplacées. "
            "Saisir OUI pour continuer : "
        )
        if answer != "OUI":
            print("Restauration annulée.")
            return 0
    try:
        CsvRepository(ROOT).restore_sample_data()
    except StorageError as exc:
        print(f"Erreur : {exc}")
        return 1
    print("Données fictives de démonstration restaurées.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
