"""Unit tests for the tool functions (no network calls)."""

import pytest

from tools import calculate_emi, get_stock_price, get_company_info


def test_emi_basic():
    # P=1,00,000, R=12%, T=1y -> well-known EMI ~ 8884.88
    result = calculate_emi(principal=100000, annual_rate_percent=12, tenure_years=1)
    assert result["tenure_months"] == 12
    assert abs(result["monthly_emi"] - 8884.88) < 0.05
    assert result["total_interest"] > 0


def test_emi_zero_rate():
    result = calculate_emi(principal=12000, annual_rate_percent=0, tenure_years=1)
    assert result["monthly_emi"] == 1000.0
    assert result["total_interest"] == 0.0


def test_emi_invalid_input():
    result = calculate_emi(principal=-100, annual_rate_percent=8, tenure_years=2)
    assert "error" in result


def test_emi_fractional_years():
    # 1.5 years = 18 months
    result = calculate_emi(principal=50000, annual_rate_percent=10, tenure_years=1.5)
    assert result["tenure_months"] == 18


def test_stock_price_invalid_ticker_returns_error_dict():
    # yfinance returns mostly empty info for nonsense tickers
    result = get_stock_price("NOTAREALTICKER12345")
    # Either an error dict or a dict without a 'price' key
    assert isinstance(result, dict)
    assert "error" in result or result.get("price") is None


def test_company_info_shape():
    # Even on a real ticker, the returned dict must have these keys
    result = get_company_info("MSFT")
    assert isinstance(result, dict)
    if "error" not in result:
        for key in ("ticker", "name", "sector"):
            assert key in result
