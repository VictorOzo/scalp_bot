"""Unit tests for Phase 1 settings and OANDA fetcher behavior."""

from __future__ import annotations

import importlib
import importlib.util
import os
import unittest
from typing import Any


class OandaIntegrationTestCase(unittest.TestCase):
    """Integration-style tests for existing Phase 1 connectivity functions."""

    @classmethod
    def setUpClass(cls) -> None:
        missing_packages = [
            package
            for package in ("oandapyV20", "pandas")
            if importlib.util.find_spec(package) is None
        ]
        if missing_packages:
            raise unittest.SkipTest(
                "Missing package(s) required for Phase 1 tests: "
                f"{', '.join(missing_packages)}"
            )

        required_env = {
            "OANDA_API_KEY": os.getenv("OANDA_API_KEY"),
            "OANDA_ACCOUNT_ID": os.getenv("OANDA_ACCOUNT_ID"),
        }
        missing_env = [name for name, value in required_env.items() if not value]
        if missing_env:
            raise unittest.SkipTest(
                "Missing environment variable(s) for OANDA integration tests: "
                f"{', '.join(missing_env)}"
            )

        cls.accounts = importlib.import_module("oandapyV20.endpoints.accounts")
        cls.fetcher = importlib.import_module("data.fetcher")
        cls.settings = importlib.import_module("config.settings")
        cls.pd = importlib.import_module("pandas")

    def test_authentication_returns_account_data(self) -> None:
        """Authentication via fetcher client should allow account data retrieval."""
        client = self.fetcher.get_oanda_client()
        endpoint = self.accounts.AccountSummary(accountID=self.settings.OANDA_ACCOUNT_ID)
        response: dict[str, Any] = client.request(endpoint)

        self.assertIsInstance(response, dict)
        self.assertIn("account", response)
        self.assertEqual(response["account"]["id"], self.settings.OANDA_ACCOUNT_ID)

    def test_get_candles_valid_instrument_returns_expected_structure(self) -> None:
        """Fetching EUR_USD candles should return non-empty normalized data."""
        df = self.fetcher.get_candles("EUR_USD", timeframe="M5", count=10)

        self.assertIsInstance(df, self.pd.DataFrame)
        self.assertEqual(list(df.columns), ["time", "open", "high", "low", "close", "volume"])
        self.assertGreater(len(df), 0)
        self.assertLessEqual(len(df), 10)

        self.assertTrue(self.pd.api.types.is_datetime64tz_dtype(df["time"]))
        for column in ["open", "high", "low", "close", "volume"]:
            self.assertTrue(self.pd.api.types.is_float_dtype(df[column]))

    def test_invalid_credentials_raise_exception(self) -> None:
        """Invalid API key should raise an exception on authenticated account request."""
        original_key = self.fetcher.OANDA_API_KEY
        try:
            self.fetcher.OANDA_API_KEY = "invalid_api_key_for_test"
            client = self.fetcher.get_oanda_client()
            endpoint = self.accounts.AccountSummary(accountID=self.settings.OANDA_ACCOUNT_ID)
            with self.assertRaises(Exception):
                client.request(endpoint)
        finally:
            self.fetcher.OANDA_API_KEY = original_key

    def test_invalid_instrument_raises_exception(self) -> None:
        """Invalid instrument should raise an API exception from get_candles."""
        with self.assertRaises(Exception):
            self.fetcher.get_candles("INVALID_INSTRUMENT", timeframe="M5", count=10)


if __name__ == "__main__":
    unittest.main()
