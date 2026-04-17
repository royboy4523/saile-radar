"""
ProPublica Nonprofit Explorer API Client (Step 3.1)
Retrieves IRS Form 990 filings for nonprofit organizations by EIN.

Used to extract Part IX contractor expense data — the basis for VMS classification.
Responses are cached locally to avoid redundant API calls.

Usage:
    client = ProPublicaClient()
    filings = client.get_filings("34-0714585")   # Cleveland Clinic
    expenses = client.get_expenses("34-0714585")  # parsed contractor ratio
"""

import json
import logging
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "propublica"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://projects.propublica.org/nonprofits/api/v2"
RATE_LIMIT_SECONDS = 1.0  # ProPublica asks for courteous crawling


class ProPublicaClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "saile-radar-research/1.0"})
        self._last_call = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_call
        if elapsed < RATE_LIMIT_SECONDS:
            time.sleep(RATE_LIMIT_SECONDS - elapsed)
        self._last_call = time.time()

    def _cache_path(self, ein: str, endpoint: str) -> Path:
        clean_ein = ein.replace("-", "")
        return CACHE_DIR / f"{clean_ein}_{endpoint}.json"

    def _load_cache(self, ein: str, endpoint: str):
        path = self._cache_path(ein, endpoint)
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def _save_cache(self, ein: str, endpoint: str, data: dict):
        path = self._cache_path(ein, endpoint)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def get_organization(self, ein: str) -> dict | None:
        """Fetch organization summary from ProPublica. Returns None if not found."""
        cached = self._load_cache(ein, "org")
        if cached is not None:
            return cached

        clean_ein = ein.replace("-", "")
        url = f"{BASE_URL}/organizations/{clean_ein}.json"
        self._rate_limit()

        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 404:
                log.debug(f"EIN {ein}: not found in ProPublica")
                self._save_cache(ein, "org", {})
                return None
            resp.raise_for_status()
            data = resp.json()
            self._save_cache(ein, "org", data)
            return data
        except requests.RequestException as e:
            log.warning(f"EIN {ein}: API error — {e}")
            return None

    def get_filings(self, ein: str) -> list[dict]:
        """
        Return list of 990 filing summaries for an EIN, most recent first.
        Each item has: tax_prd_yr, formtype, pdf_url, totrevenue, totfuncexpns,
        totcntrbgfts, and contractor expense fields where available.
        """
        org = self.get_organization(ein)
        if not org or "filings_with_data" not in org:
            return []
        return org.get("filings_with_data", [])

    def get_expenses(self, ein: str) -> dict | None:
        """
        Parse contractor expense ratio from the most recent 990 filing.

        Returns a dict with:
            ein, tax_year, form_type,
            total_functional_expenses, contractor_fees,
            contractor_ratio,  (contractor_fees / total_functional_expenses)
            has_data           (False if no 990 or missing fields)
        """
        filings = self.get_filings(ein)
        if not filings:
            return {"ein": ein, "has_data": False, "reason": "no_990_found"}

        # Use the most recent filing with data
        filing = filings[0]

        total_expenses = filing.get("totfuncexpns")
        contractor_fees = filing.get("totcntrbgfts")  # Part IX line 11g — outside contractors

        if total_expenses is None or total_expenses == 0:
            return {"ein": ein, "has_data": False, "reason": "missing_expense_data",
                    "tax_year": filing.get("tax_prd_yr")}

        if contractor_fees is None:
            contractor_fees = 0

        ratio = contractor_fees / total_expenses if total_expenses > 0 else 0.0

        return {
            "ein": ein,
            "has_data": True,
            "tax_year": filing.get("tax_prd_yr"),
            "form_type": filing.get("formtype"),
            "total_functional_expenses": total_expenses,
            "contractor_fees": contractor_fees,
            "contractor_ratio": round(ratio, 4),
        }


def test_known_eins():
    """Quick smoke test against known nonprofit EINs from the planner."""
    client = ProPublicaClient()

    test_cases = [
        ("34-0714585", "Cleveland Clinic"),
        ("34-1982558", "University Hospitals Cleveland"),
    ]

    for ein, name in test_cases:
        log.info(f"\nTesting: {name} (EIN {ein})")
        expenses = client.get_expenses(ein)
        if expenses and expenses.get("has_data"):
            log.info(f"  Tax year:          {expenses['tax_year']}")
            log.info(f"  Form type:         {expenses['form_type']}")
            log.info(f"  Total expenses:    ${expenses['total_functional_expenses']:,.0f}")
            log.info(f"  Contractor fees:   ${expenses['contractor_fees']:,.0f}")
            log.info(f"  Contractor ratio:  {expenses['contractor_ratio']:.2%}")
        else:
            log.info(f"  No data: {expenses.get('reason', 'unknown')}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    test_known_eins()
