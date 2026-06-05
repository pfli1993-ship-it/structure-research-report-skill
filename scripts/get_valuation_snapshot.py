#!/usr/bin/env python3

"""Fetch Futu valuation snapshots for structured research reports."""

import argparse
import json
import sys

try:
    from futu import OpenQuoteContext, RET_OK
except ImportError:
    print(json.dumps({
        "error": "futu-api is not installed. Run /install-futu-opend or install futu-api.",
    }, ensure_ascii=False))
    sys.exit(1)


def clean_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number < 0 else number


def currency_for_code(code):
    prefix = code.split(".", 1)[0].upper()
    return {
        "SH": "CNY",
        "SZ": "CNY",
        "HK": "HKD",
        "US": "USD",
        "SG": "SGD",
        "CC": "USD",
    }.get(prefix, "")


def main():
    parser = argparse.ArgumentParser(
        description="获取现价、现市值、目标价对应市值、PE-TTM 与 PB",
    )
    parser.add_argument("code", help="富途股票代码，如 SH.688222、US.AAPL")
    parser.add_argument("--target-price", type=float, help="研报目标价")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11111)
    args = parser.parse_args()

    context = OpenQuoteContext(host=args.host, port=args.port)
    try:
        ret, data = context.get_market_snapshot([args.code])
        if ret != RET_OK or data is None or data.empty:
            raise RuntimeError(str(data))

        row = data.iloc[0]
        price = clean_number(row.get("last_price"))
        market_cap = clean_number(row.get("total_market_val"))
        target_market_cap = None
        if args.target_price is not None and price and market_cap:
            target_market_cap = market_cap * args.target_price / price

        result = {
            "code": row.get("code", args.code),
            "name": row.get("name", ""),
            "update_time": row.get("update_time", ""),
            "last_price": price,
            "target_price": args.target_price,
            "market_cap": market_cap,
            "target_market_cap": target_market_cap,
            "market_cap_currency": row.get("currency", "") or currency_for_code(args.code),
            "pe_ttm": clean_number(row.get("pe_ttm_ratio")),
            "pe_static": clean_number(row.get("pe_ratio")),
            "pb": clean_number(row.get("pb_ratio")),
            "target_market_cap_assumption": "Current share count remains unchanged.",
        }
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"code": args.code, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
    finally:
        context.close()


if __name__ == "__main__":
    main()
