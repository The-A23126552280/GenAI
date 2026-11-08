"""External tools exposed to the agent.

Each tool is a plain Python function. The agent sees them as JSON schemas
(defined in TOOL_SCHEMAS) and calls them by name with keyword arguments.
"""

from __future__ import annotations

from typing import Any

import yfinance as yf


# ---------------------------------------------------------------------------
# Tool: EMI calculator
# ---------------------------------------------------------------------------
def calculate_emi(
    principal: float, annual_rate_percent: float, tenure_years: float
) -> dict[str, Any]:
    """Compute monthly EMI for a loan.

    Formula: EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    where r = monthly rate, n = number of months.
    """
    if principal <= 0 or annual_rate_percent < 0 or tenure_years <= 0:
        return {"error": "principal and tenure must be > 0; rate must be >= 0"}

    r = annual_rate_percent / 12 / 100
    n = int(round(tenure_years * 12))

    if r == 0:
        emi = principal / n
    else:
        emi = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)

    total_payment = emi * n
    total_interest = total_payment - principal

    return {
        "monthly_emi": round(emi, 2),
        "total_payment": round(total_payment, 2),
        "total_interest": round(total_interest, 2),
        "tenure_months": n,
    }


# ---------------------------------------------------------------------------
# Tool: Stock price
# ---------------------------------------------------------------------------
def get_stock_price(ticker: str) -> dict[str, Any]:
    """Fetch latest quote for a ticker symbol (e.g. 'AAPL', 'RELIANCE.BSE')."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        currency = info.get("currency", "USD")
        name = info.get("shortName") or info.get("longName") or ticker.upper()

        if price is None:
            return {"error": f"No live price available for '{ticker}'."}

        change = None
        change_pct = None
        if prev_close:
            change = round(price - prev_close, 2)
            change_pct = round((change / prev_close) * 100, 2)

        return {
            "ticker": ticker.upper(),
            "name": name,
            "price": round(float(price), 2),
            "currency": currency,
            "change": change,
            "change_pct": change_pct,
        }
    except Exception as e:  # pragma: no cover - network errors
        return {"error": f"Failed to fetch '{ticker}': {e}"}


# ---------------------------------------------------------------------------
# Tool: Company info
# ---------------------------------------------------------------------------
def get_company_info(ticker: str) -> dict[str, Any]:
    """Fetch fundamental info for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        return {
            "ticker": ticker.upper(),
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "dividend_yield": info.get("dividendYield"),
            "summary": (info.get("longBusinessSummary") or "")[:500],
        }
    except Exception as e:  # pragma: no cover
        return {"error": f"Failed to fetch info for '{ticker}': {e}"}


# ---------------------------------------------------------------------------
# Tool registry + JSON schemas (OpenAI function-calling format)
# ---------------------------------------------------------------------------
TOOL_REGISTRY: dict[str, callable] = {
    "calculate_emi": calculate_emi,
    "get_stock_price": get_stock_price,
    "get_company_info": get_company_info,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_emi",
            "description": "Calculate the monthly EMI for a loan given principal, annual interest rate (%), and tenure (years).",
            "parameters": {
                "type": "object",
                "properties": {
                    "principal": {
                        "type": "number",
                        "description": "Loan amount in currency units",
                    },
                    "annual_rate_percent": {
                        "type": "number",
                        "description": "Annual interest rate in percent (e.g. 8.5)",
                    },
                    "tenure_years": {
                        "type": "number",
                        "description": "Loan tenure in years (decimals allowed, e.g. 2.5)",
                    },
                },
                "required": ["principal", "annual_rate_percent", "tenure_years"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Fetch the latest stock price for a given ticker symbol (e.g. 'AAPL', 'MSFT', 'RELIANCE.BSE').",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Ticker symbol of the stock",
                    },
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_info",
            "description": "Fetch fundamental information (sector, market cap, P/E, summary) for a ticker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Ticker symbol of the company",
                    },
                },
                "required": ["ticker"],
            },
        },
    },
]
