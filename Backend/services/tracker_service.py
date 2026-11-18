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
        purchase_time = holding.get("purchase_time", "09:30")
        invested_amount = holding.get("invested_amount", 50000)

        try:
            invested_amount = float(invested_amount)
            if invested_amount <= 0:
                invested_amount = 50000.0
        except (ValueError, TypeError):
            invested_amount = 50000.0

        try:
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

            # Generate tailored notification title & message
            if action_type == "TAKE_PROFIT":
                title = f"Take-Profit Opportunity on {symbol}"
                message = (
                    f"{symbol} has gained +{pnl_pct}% to ₹{current_price}. "
                    f"Model 2 detected overbought resistance near target ₹{target}. "
                    f"Consider locking in profits or trailing your stop."
                )
                severity = "warning"
            elif action_type in ["STOP_LOSS", "CAPITAL_PRESERVATION_EXIT"]:
                title = f"Risk Alert: Stop-Loss Triggered for {symbol}"
                message = (
                    f"{symbol} has dropped {pnl_pct}% to ₹{current_price}, "
                    f"breaching the protective threshold ₹{stop_loss}. "
                    f"Model 2 advises exiting to protect remaining capital."
                )
                severity = "critical"
            elif action_type == "MOMENTUM_BUY":
                title = f"Buy / Accumulate Signal on {symbol}"
                message = (
                    f"Strong bullish momentum on {symbol} at ₹{current_price}. "
                    f"Price is trading above key moving averages with target set to ₹{target}."
                )
                severity = "success"
            elif action_type == "BREAKDOWN_SELL":
                title = f"Trend Weakening Alert on {symbol}"
                message = (
                    f"{symbol} is under technical pressure below 50-day SMA. "
                    f"Model 2 signals SELL to prevent further drawdown."
                )
                severity = "warning"
            else:
                title = f"Position Stable: {symbol} in HOLD Zone"
                message = (
                    f"{symbol} is holding steady at ₹{current_price} ({'+' if pnl_pct >= 0 else ''}{pnl_pct}%). "
                    f"Next upside target: ₹{target} | Stop-loss: ₹{stop_loss}."
                )
                severity = "info"

            alert_id = f"alert-{symbol}-{int(time.time())}-{index}"

            alerts.append({
                "id": alert_id,
                "symbol": symbol,
                "signal": signal,
                "action_type": action_type,
                "title": title,
                "message": message,
                "current_price": current_price,
                "purchase_price": purchase_price,
                "pnl_percent": pnl_pct,
                "target_price": target,
                "stop_loss_price": stop_loss,
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
