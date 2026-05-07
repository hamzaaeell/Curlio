"""
CLI entry point for the job scraper.

Usage:
    # Run everything
    python run.py

    # Run specific boards / categories / regions
    python run.py --boards LEVER ASHBY --categories DEVOPS AI_ML --regions INTL

    # Print DB stats
    python run.py --stats

    # Export results to JSON
    python run.py --export jobs_export.json
"""

import asyncio
import argparse
import json
import logging
import sys

from job_search.runner import run_all
from job_search.database import init_db, stats, get_jobs
from job_search.config import JOB_BOARDS, JOB_CATEGORIES, REGION_GROUPS

# ---------------------------------------------------------------------------
# Logging setup — matches the format in your screenshot
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("job_search.log", encoding="utf-8"),
    ],
)

# Suppress noisy third-party loggers
logging.getLogger("curl_cffi").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description="Job board scraper")

    parser.add_argument(
        "--boards",
        nargs="+",
        choices=list(JOB_BOARDS.keys()),
        help="Job boards to scrape (default: all)",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=list(JOB_CATEGORIES.keys()),
        help="Job categories to search (default: all)",
    )
    parser.add_argument(
        "--regions",
        nargs="+",
        choices=list(REGION_GROUPS.keys()),
        help="Region groups to target (default: all)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print database statistics and exit",
    )
    parser.add_argument(
        "--export",
        metavar="FILE",
        help="Export all jobs to a JSON file and exit",
    )

    args = parser.parse_args()

    if args.stats:
        init_db()
        s = stats()
        print(json.dumps(s, indent=2))
        return

    if args.export:
        init_db()
        jobs = get_jobs(limit=10_000)
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)
        print(f"Exported {len(jobs)} jobs to {args.export}")
        return

    asyncio.run(
        run_all(
            boards=args.boards,
            categories=args.categories,
            regions=args.regions,
        )
    )


if __name__ == "__main__":
    main()
