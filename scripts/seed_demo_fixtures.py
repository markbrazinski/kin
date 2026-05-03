"""CLI wrapper: seed all four demo fixture records into local storage.

Usage (from repo root):
    .venv/bin/python scripts/seed_demo_fixtures.py [--storage PATH]

Default storage dir: storage/ (repo root). Same directory the FastAPI
server uses at http://127.0.0.1:8000.

Prints a summary of seeded records including their fixture UUIDs and
statuses. Safe to run multiple times — each run replaces existing
fixture records idempotently.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from integration.fixture_seed import seed_all
from integration.storage_adapter import StorageAdapter
from integration.system_clock import SYSTEM_CLOCK


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed KIN demo fixtures")
    parser.add_argument(
        "--storage",
        default=str(Path(__file__).parent.parent / "storage"),
        help="Path to storage directory (default: repo-root/storage)",
    )
    args = parser.parse_args()

    storage_dir = Path(args.storage)
    storage = StorageAdapter(storage_dir, SYSTEM_CLOCK)

    print(f"Seeding demo fixtures into {storage_dir} …")
    records = seed_all(storage)

    for name, record in records.items():
        print(f"  {name:12s}  id={record.id}  status={record.status}  lang={record.language}")

    print(f"\nDone. {len(records)} records seeded.")
    print(
        "\nPresentation mode IDs (for usePresentationMode.ts):\n"
        + "\n".join(f"  {name}: {record.id}" for name, record in records.items())
    )


if __name__ == "__main__":
    main()
