from __future__ import annotations

from typing import Any

import requests

from app.core.config import settings

ALPHA_OVERVIEW_URL = "https://www.alphavantage.co/query"


def normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def _alpha_request(function_name: str, symbol: str) -> dict[str, Any] | None:
    try:
        response = requests.get(
            ALPHA_OVERVIEW_URL,
            params={
                "function": function_name,
                "symbol": normalize_symbol(symbol).replace("-", "."),
                "apikey": settings.alpha_vantage_api_key,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json() or {}
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def fetch_alpha_asset_overview(symbol: str) -> dict[str, Any] | None:
    normalized = normalize_symbol(symbol)
    if not settings.alpha_vantage_api_key or not normalized:
        return None

    payload = _alpha_request("OVERVIEW", normalized)
    if payload and (payload.get("Name") or payload.get("Description") or payload.get("AssetType")):
        return payload

    etf_profile = _alpha_request("ETF_PROFILE", normalized)
    if etf_profile and (etf_profile.get("holdings") or etf_profile.get("sectors") or etf_profile.get("net_assets")):
        sectors = etf_profile.get("sectors") if isinstance(etf_profile.get("sectors"), list) else []
        top_sector = None
        if sectors and isinstance(sectors[0], dict):
            top_sector = sectors[0].get("sector")
        net_assets = etf_profile.get("net_assets")
        description = "Exchange traded fund."
        if net_assets:
            description = f"Exchange traded fund with net assets of {net_assets}."
        return {
            "Symbol": normalized,
            "Name": f"{normalized} ETF",
            "AssetType": "ETF",
            "Currency": "USD",
            "Industry": top_sector,
            "Description": description,
        }

    if not isinstance(payload, dict):
        return None
    if payload.get("Note") or payload.get("Information") or payload.get("Error Message"):
        return None
    if not payload.get("Symbol") and not payload.get("Name") and not payload.get("Description"):
        return None
    return payload


def classify_asset_type(overview: dict[str, Any] | None) -> str:
    if not overview:
        return "equity"

    explicit = str(
        overview.get("AssetType")
        or overview.get("assetType")
        or overview.get("Type")
        or ""
    ).strip().lower()
    if explicit in {"etf", "fund", "exchange traded fund"}:
        return "etf"
    if explicit in {"stock", "equity", "common stock"}:
        return "equity"

    name = str(overview.get("Name") or "").lower()
    description = str(overview.get("Description") or "").lower()
    category = str(overview.get("Category") or "").lower()
    exchange = str(overview.get("Exchange") or "").lower()

    if "etf" in name or "exchange traded fund" in description:
        return "etf"
    if "fund" in name and ("index" in description or "exchange traded" in description or category):
        return "etf"
    if category.startswith("etf"):
        return "etf"
    if "arca" in exchange and "fund" in description:
        return "etf"
    return "equity"
