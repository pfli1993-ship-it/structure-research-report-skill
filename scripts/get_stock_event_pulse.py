#!/usr/bin/env python3

"""Build a Futu-backed stock pulse pack for structured research reports."""

import argparse
import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ensure_futu_opend import ensure_opend

try:
    from futu import OpenQuoteContext, RET_OK
    from futu import KLType, AuType
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
    if math.isnan(number) or number < 0:
        return None
    return number


def safe_get(row, key, default=None):
    try:
        value = row.get(key, default)
    except AttributeError:
        value = default
    if value is None:
        return default
    try:
        if hasattr(value, "item"):
            value = value.item()
    except Exception:
        pass
    return value


def df_records(data, limit=None):
    if data is None or getattr(data, "empty", False):
        return []
    if limit:
        data = data.tail(limit)
    records = []
    for _, row in data.iterrows():
        item = {}
        for key, value in row.items():
            if hasattr(value, "item"):
                value = value.item()
            value = jsonable(value)
            item[key] = value
        records.append(item)
    return records


def jsonable(value):
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if hasattr(value, "value"):
        try:
            return jsonable(value.value)
        except Exception:
            pass
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def call_section(name, errors, fn):
    try:
        return fn()
    except Exception as error:
        errors[name] = str(error)
        return None


def check_ret(ret, data, action):
    if ret != RET_OK:
        raise RuntimeError(f"{action} failed: {data}")
    return data


def fetch_snapshot(ctx, code, target_price):
    data = check_ret(*ctx.get_market_snapshot([code]), action="get_market_snapshot")
    if data is None or data.empty:
        raise RuntimeError("Futu returned an empty market snapshot.")
    row = data.iloc[0]
    price = clean_number(safe_get(row, "last_price"))
    market_cap = clean_number(safe_get(row, "total_market_val"))
    target_market_cap = None
    if target_price is not None and price and market_cap:
        target_market_cap = market_cap * target_price / price
    return {
        "code": safe_get(row, "code", code),
        "name": safe_get(row, "name", ""),
        "update_time": safe_get(row, "update_time", ""),
        "last_price": price,
        "target_price": target_price,
        "market_cap": market_cap,
        "target_market_cap": target_market_cap,
        "currency": safe_get(row, "currency", ""),
        "pe_ttm": clean_number(safe_get(row, "pe_ttm_ratio")),
        "pe_static": clean_number(safe_get(row, "pe_ratio")),
        "pb": clean_number(safe_get(row, "pb_ratio")),
    }


def fetch_kline(ctx, code, days):
    end = date.today()
    start = end - timedelta(days=max(days + 20, 45))
    ret, data, page_key = ctx.request_history_kline(
        code,
        start=start.isoformat(),
        end=end.isoformat(),
        ktype=KLType.K_DAY,
        autype=AuType.QFQ,
        max_count=120,
    )
    check_ret(ret, data, "request_history_kline")
    while page_key is not None:
        ret, more, page_key = ctx.request_history_kline(
            code,
            start=start.isoformat(),
            end=end.isoformat(),
            ktype=KLType.K_DAY,
            autype=AuType.QFQ,
            max_count=120,
            page_req_key=page_key,
        )
        check_ret(ret, more, "request_history_kline page")
        if more is not None and not more.empty:
            try:
                import pandas as pd
                data = pd.concat([data, more], ignore_index=True)
            except Exception:
                data = data._append(more, ignore_index=True)
    if data is None or data.empty:
        raise RuntimeError("Futu returned empty kline data.")
    return df_records(data.tail(days))


def moving_average(values, window):
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def summarize_technical(kline):
    closes = [clean_number(x.get("close")) for x in kline]
    highs = [clean_number(x.get("high")) for x in kline]
    volumes = [clean_number(x.get("volume")) for x in kline]
    closes = [x for x in closes if x is not None]
    highs = [x for x in highs if x is not None]
    volumes = [x for x in volumes if x is not None]
    if len(closes) < 2:
        return {"summary": "K线样本不足，暂不判断。"}

    latest = closes[-1]
    first = closes[0]
    ma5 = moving_average(closes, 5)
    ma10 = moving_average(closes, 10)
    ma20 = moving_average(closes, 20)
    one_month_return = (latest / first - 1) * 100 if first else None
    high_20_prev = max(highs[-21:-1]) if len(highs) >= 21 else max(highs[:-1])
    breakout = latest > high_20_prev if high_20_prev else False
    volume_ratio = None
    if len(volumes) >= 6 and sum(volumes[-6:-1]) > 0:
        volume_ratio = volumes[-1] / (sum(volumes[-6:-1]) / 5)

    trend_parts = []
    if ma20 and latest > ma20:
        trend_parts.append("收盘价位于20日均线之上")
    elif ma20:
        trend_parts.append("收盘价仍在20日均线之下")
    if ma5 and ma10 and ma5 > ma10:
        trend_parts.append("短均线偏强")
    elif ma5 and ma10:
        trend_parts.append("短均线尚未走强")
    if breakout:
        trend_parts.append("接近或突破近20日高点")
    if volume_ratio and volume_ratio >= 1.5:
        trend_parts.append("成交量较近5日均量明显放大")

    return {
        "latest_close": latest,
        "one_month_return_pct": one_month_return,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "prev_20d_high": high_20_prev,
        "breakout_20d_high": breakout,
        "latest_volume_vs_5d_avg": volume_ratio,
        "summary": "；".join(trend_parts) if trend_parts else "走势未出现明显突破信号。",
    }


def fetch_capital_flow(ctx, code):
    # period_type=2 is DAY in the bundled futuapi helper; using the integer keeps
    # this script compatible with SDK builds that do not export PeriodType.
    ret, data = ctx.get_capital_flow(code, period_type=2)
    check_ret(ret, data, "get_capital_flow")
    records = df_records(data, limit=30)
    main_values = [clean_number(x.get("main_in_flow")) for x in records]
    main_values = [x for x in main_values if x is not None]
    recent_sum = sum(main_values[-5:]) if main_values else None
    direction = None
    if recent_sum is not None:
        direction = "净流入" if recent_sum > 0 else "净流出" if recent_sum < 0 else "基本持平"
    return {
        "recent_records": records[-10:],
        "recent_5d_main_in_flow": recent_sum,
        "direction": direction,
    }


def fetch_capital_distribution(ctx, code):
    data = check_ret(*ctx.get_capital_distribution(code), action="get_capital_distribution")
    if data is None or data.empty:
        return {}
    row = data.iloc[0]
    result = {}
    for key in [
        "capital_in_super", "capital_out_super",
        "capital_in_big", "capital_out_big",
        "capital_in_mid", "capital_out_mid",
        "capital_in_small", "capital_out_small",
    ]:
        result[key] = clean_number(safe_get(row, key))
    result["net_super_big"] = (
        (result.get("capital_in_super") or 0)
        + (result.get("capital_in_big") or 0)
        - (result.get("capital_out_super") or 0)
        - (result.get("capital_out_big") or 0)
    )
    return result


def fetch_top_brokers(ctx, code):
    if not code.upper().startswith("HK."):
        return {"note": "十大买卖经纪商接口仅适用于港股正股及基金。"}
    data = check_ret(*ctx.get_top_ten_buy_sell_brokers(code), action="get_top_ten_buy_sell_brokers")
    records = df_records(data)
    buys = [x for x in records if x.get("buy_sell_type") == 1][:10]
    sells = [x for x in records if x.get("buy_sell_type") == 2][:10]
    return {"buy": buys, "sell": sells}


def fetch_analyst_consensus(ctx, code):
    data = check_ret(*ctx.get_research_analyst_consensus(code), action="get_research_analyst_consensus")
    return data or {}


def render_chart(kline, chart_out, code):
    if not chart_out:
        chart_out = Path.cwd() / f"stock_pulse_{code.replace('.', '_')}_1m.png"
    else:
        chart_out = Path(chart_out).expanduser()
    chart_out.parent.mkdir(parents=True, exist_ok=True)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as error:
        return {"error": f"matplotlib unavailable: {error}"}

    dates = [str(x.get("time_key") or x.get("time") or "")[:10] for x in kline]
    closes = [clean_number(x.get("close")) for x in kline]
    volumes = [clean_number(x.get("volume")) or 0 for x in kline]
    if len([x for x in closes if x is not None]) < 2:
        return {"error": "not enough kline points to render chart"}

    fig, (ax_price, ax_vol) = plt.subplots(
        2, 1, figsize=(10.8, 5.8), dpi=160, sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )
    x_axis = list(range(len(closes)))
    ax_price.plot(x_axis, closes, color="#1f5fbf", linewidth=2.4)
    ax_price.fill_between(x_axis, closes, min(closes), color="#dce8ff", alpha=0.55)
    ax_price.set_title(f"{code} one-month price trend", loc="left", fontsize=14, fontweight="bold")
    ax_price.grid(True, axis="y", color="#e7e9ef")
    ax_price.spines[["top", "right"]].set_visible(False)
    ax_vol.bar(x_axis, volumes, color="#8b98a8", alpha=0.55)
    ax_vol.grid(True, axis="y", color="#edf0f4")
    ax_vol.spines[["top", "right"]].set_visible(False)
    step = max(1, len(x_axis) // 6)
    ax_vol.set_xticks(x_axis[::step])
    ax_vol.set_xticklabels(dates[::step], rotation=0, ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(chart_out, bbox_inches="tight")
    plt.close(fig)
    return {"path": str(chart_out)}


def main():
    parser = argparse.ArgumentParser(
        description="获取标的事件解读所需的富途行情、技术、资金、分析师共识与近一月走势图",
    )
    parser.add_argument("code", help="富途股票代码，如 HK.00700、US.AAPL、SH.600519")
    parser.add_argument("--target-price", type=float, help="研报目标价，用于估算目标价对应市值")
    parser.add_argument("--days", type=int, default=31, help="走势图和技术判断使用的最近交易日数量")
    parser.add_argument("--chart-out", help="走势图 PNG 输出路径；默认写入当前目录")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11111)
    parser.add_argument("--no-auto-start-opend", action="store_true")
    parser.add_argument("--opend-wait-seconds", type=float, default=12)
    args = parser.parse_args()

    opend_status = None
    if not args.no_auto_start_opend:
        opend_status = ensure_opend(args.host, args.port, args.opend_wait_seconds)
        if not opend_status.get("ok"):
            print(json.dumps({
                "code": args.code,
                "error": opend_status.get("error", "Futu OpenD is not available."),
                "opend": opend_status,
            }, ensure_ascii=False))
            sys.exit(1)

    errors = {}
    ctx = OpenQuoteContext(host=args.host, port=args.port)
    try:
        kline = call_section("kline", errors, lambda: fetch_kline(ctx, args.code, args.days)) or []
        technical = summarize_technical(kline) if kline else {"summary": "K线获取失败，暂不判断。"}
        chart = render_chart(kline, args.chart_out, args.code) if kline else {"error": "kline unavailable"}
        result = {
            "code": args.code,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "opend": opend_status,
            "snapshot": call_section("snapshot", errors, lambda: fetch_snapshot(ctx, args.code, args.target_price)),
            "analyst_consensus": call_section("analyst_consensus", errors, lambda: fetch_analyst_consensus(ctx, args.code)),
            "technical": technical,
            "capital_flow": call_section("capital_flow", errors, lambda: fetch_capital_flow(ctx, args.code)),
            "capital_distribution": call_section("capital_distribution", errors, lambda: fetch_capital_distribution(ctx, args.code)),
            "top_brokers": call_section("top_brokers", errors, lambda: fetch_top_brokers(ctx, args.code)),
            "kline": kline,
            "chart": chart,
            "limitations": {
                "news_and_announcements": "Current local Futu OpenAPI methods do not expose a news/announcement feed here; supplement with official filings plus Caixin and 36Kr when accessible, and cite visible source/date.",
                "user_discussion_sentiment": "Current local Futu OpenAPI methods do not expose community discussion heat or bull/bear comment consensus here; supplement with Xueqiu discussion/search observations and label methodology.",
            },
        }
        if errors:
            result["errors"] = errors
        print(json.dumps(jsonable(result), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"code": args.code, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
    finally:
        ctx.close()


if __name__ == "__main__":
    main()
