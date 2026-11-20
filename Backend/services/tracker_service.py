"""
QuantGen - Portfolio Tracker & Real-Time Alert Service
======================================================
Monitors user stock holdings stored in the database, runs Model 2
(Position Strategy Classifier), evaluates market price movements,
and generates actionable BUY / HOLD / SELL strategy alerts for the dashboard.
"""

from datetime import datetime
import time

try:
    from ai_model.tracker import analyze_holding
except ImportError:
    from Backend.ai_model.tracker import analyze_holding


def generate_market_alerts(holdings):
    """
    Evaluates a list of user holdings against live market data using Model 2.
    Generates notification cards for any holding that hits critical conditions:
    - TAKE_PROFIT: Target reached or high gains with momentum exhaustion
    - STOP_LOSS: Protective boundary breached or critical drawdown
    - MOMENTUM_BUY / ACCUMULATE: Strong bullish continuation
    - TREND_HOLD / UPDATE: Regular status updates on portfolio health
    """
    if not holdings or not isinstance(holdings, list):
        return []

    alerts = []

    for index, holding in enumerate(holdings):
        symbol = str(holding.get("symbol", "")).strip().upper()
        if not symbol:
            continue

        purchase_date = holding.get("purchase_date")
        if not purchase_date:
            purchase_date = datetime.now().strftime("%Y-%m-%d")
        purchase_time = holding.get("purchase_time") or "09:30"
        invested_amount = holding.get("invested_amount", 50000)

        try:
            invested_amount = float(invested_amount)
            if invested_amount <= 0:
                invested_amount = 50000.0
        except (ValueError, TypeError):
            invested_amount = 50000.0

        try:
            if holding.get("current_price") and holding.get("recommendation"):
                analysis = holding
            else:
                analysis = analyze_holding(
                    symbol=symbol,
                    purchase_date=purchase_date,
                    purchase_time=purchase_time,
                    invested_amount=invested_amount
                )

            rec = analysis.get("recommendation", {})
            signal = rec.get("signal", "HOLD")
            action_type = rec.get("action_type", "TREND_HOLD")
            confidence = rec.get("confidence_score", 75.0)
            target = analysis.get("target_price", 0.0)
            stop_loss = analysis.get("stop_loss_price", 0.0)
            current_price = analysis.get("current_price", 0.0)
            purchase_price = analysis.get("purchase_price", 0.0)
            pnl_pct = analysis.get("profit_loss_percent", 0.0)
            reasons = rec.get("reasons", [])

            target_upside = round(((target - current_price) / current_price) * 100, 1) if current_price else 18.0
            stop_risk = round(((stop_loss - current_price) / current_price) * 100, 1) if current_price else -8.0

            # Generate tailored notification title & message for mid/long-term positional investors
            if action_type == "RIDE_MOMENTUM_RUN" or (action_type.startswith("RIDE") and pnl_pct >= 10.0):
                title = f"Bullish Surge: {symbol} Momentum Active"
                message = (
                    f"{symbol} surged +{pnl_pct}% to ₹{current_price}. "
                    f"Strong buying momentum active. Ride the trend toward target ₹{target} (+{target_upside}%) "
                    f"with protective trailing stop locked at ₹{stop_loss}."
                )
                severity = "success"
            elif action_type in ["TAKE_PROFIT", "TRIM_TAKE_PROFIT"]:
                title = f"Mid-Term Target Zone: {symbol}"
                message = (
                    f"{symbol} has gained +{pnl_pct}% to ₹{current_price}. "
                    f"Model 2 detects profit target reached near ₹{target}. "
                    f"Consider taking partial gains or trailing your stop-loss."
                )
                severity = "warning"
            elif action_type in ["STOP_LOSS", "STOP_LOSS_EXIT", "CAPITAL_PRESERVATION_EXIT"]:
                title = f"Positional Stop-Loss Alert: {symbol}"
                message = (
                    f"{symbol} is at ₹{current_price} ({pnl_pct}%), "
                    f"breaching the structural support threshold ₹{stop_loss} ({stop_risk}%). "
                    f"Model 2 advises capital preservation."
                )
                severity = "critical"
            elif action_type in ["STRONG_BUY_BREAKOUT", "MOMENTUM_BUY"]:
                title = f"Mid-Term Breakout Buy: {symbol}"
                message = (
                    f"Strong multi-week breakout on {symbol} at ₹{current_price}. "
                    f"Trading above 50D/100D SMAs with 1–3 month target ₹{target} (+{target_upside}%)."
                )
                severity = "success"
            elif action_type == "ACCUMULATE_DIP":
                title = f"Accumulation Opportunity: {symbol}"
                message = (
                    f"{symbol} is in a healthy pullback near 50-day support at ₹{current_price}. "
                    f"High-probability accumulation setup toward mid-term target ₹{target} (+{target_upside}%)."
                )
                severity = "success"
            elif action_type == "BREAKDOWN_SELL":
                title = f"Macro Trend Weakening: {symbol}"
                message = (
                    f"{symbol} has broken below 50D/100D moving averages at ₹{current_price}. "
                    f"Model 2 signals exit to avoid prolonged mid-term underperformance."
                )
                severity = "warning"
            else:
                title = f"Positional HOLD: {symbol} Trend Intact"
                message = (
                    f"{symbol} is holding steady at ₹{current_price} ({'+' if pnl_pct >= 0 else ''}{pnl_pct}%). "
                    f"1–3 Month Target: ₹{target} (+{target_upside}%) | Positional Stop: ₹{stop_loss} ({stop_risk}%)."
                )
                severity = "info"

            alert_id = f"alert-{symbol}-{int(time.time())}-{index}"

            alerts.append({
                "id": alert_id,
                "symbol": symbol,
                "signal": signal,
                "action_type": action_type,
                "horizon": "Mid/Long-Term (1–3 Months)",
                "title": title,
                "message": message,
                "current_price": current_price,
                "purchase_price": purchase_price,
                "pnl_percent": pnl_pct,
                "target_price": target,
                "target_upside_percent": target_upside,
                "stop_loss_price": stop_loss,
                "stop_loss_risk_percent": stop_risk,
                "confidence": confidence,
                "severity": severity,
                "reasons": reasons[:2],
                "timestamp": datetime.now().strftime("%I:%M %p, %d %b"),
                "is_read": False,
            })

        except Exception as err:
            print(f"Error checking market alert for {symbol}:", err)
            continue

    return alerts
