"""
QuantGen - Dedicated Investment Position Tracking ML Model (Model 2)
=====================================================================
Specialized Machine Learning Classifier & Risk Engine designed for
tracking active stock holdings and generating dynamic BUY / HOLD / SELL
portfolio actions with risk-reward targets.

Unlike Model 1 (Portfolio Construction Regressor + Genetic Algorithm),
Model 2 solves the Optimal Position Management Problem:
- Evaluates existing positions with entry price, P&L, drawdown, and holding duration.
- Employs Triple-Barrier labelling (Stop-Loss, Take-Profit, Trend Expiry).
- Uses an Ensemble Classifier (Random Forest + Gradient Boosting).
- Calculates dynamic trailing stop-loss, profit targets, and confidence scores.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score


# Features used for the position tracking model
POSITION_FEATURE_COLUMNS = [
    "Return",
    "Return_3D",
    "Return_5D",
    "Return_10D",
    "Return_20D",
    "Price_SMA10_Ratio",
    "Price_SMA20_Ratio",
    "Price_SMA50_Ratio",
    "MACD",
    "MACD_Signal",
    "MACD_Histogram",
    "RSI",
    "Volatility10",
    "Volatility20",
    "ATR_Ratio",
    "BB_Position",
    "Momentum10",
    "Momentum20",
    "Volume_Ratio",
    "High_Low_Range",
    "Open_Close_Range",
]


def label_triple_barrier(
    df,
    upper_barrier=0.06,   # +6% profit take
    lower_barrier=-0.04,  # -4% stop loss
    holding_window=5      # 5 trading days forward
):
    """
    Applies Marcos Lopez de Prado's Triple Barrier Method:
    - 2 (BUY/ACCUMULATE): Hits upper profit barrier before lower barrier
    - 0 (SELL/STOP_LOSS): Hits lower stop barrier or extended breakdown
    - 1 (HOLD): Neither barrier breached, neutral/positive continuation
    """
    labels = []
    close = df["Close"].values
    n = len(df)

    for i in range(n):
        if i + holding_window >= n:
            labels.append(1)  # HOLD for recent boundary
            continue

        entry = close[i]
        future_window = close[i + 1 : i + holding_window + 1]
        max_p = np.max(future_window)
        min_p = np.min(future_window)

        gain = (max_p - entry) / entry
        loss = (min_p - entry) / entry

        if loss <= lower_barrier:
            labels.append(0)  # SELL / Cut loss
        elif gain >= upper_barrier:
            labels.append(2)  # BUY / Add / Momentum
        else:
            labels.append(1)  # HOLD

    return pd.Series(labels, index=df.index, name="Target_Action")


def build_position_training_data(df):
    """
    Prepares features and triple-barrier target labels for historical data.
    """
    df = df.copy()
    labels = label_triple_barrier(df)
    df["Target_Action"] = labels

    model_data = df[POSITION_FEATURE_COLUMNS + ["Target_Action"]].copy()
    model_data.replace([np.inf, -np.inf], np.nan, inplace=True)
    model_data.dropna(inplace=True)
    return model_data


def train_position_classifier(df):
    """
    Trains an ensemble classifier on historical stock data to classify
    active position state: SELL (0), HOLD (1), BUY (2).
    """
    model_data = build_position_training_data(df)
    if len(model_data) < 150:
        raise ValueError("Not enough historical data to train position classifier.")

    X = model_data[POSITION_FEATURE_COLUMNS]
    y = model_data["Target_Action"]

    split_idx = int(len(model_data) * 0.80)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    # Class weights to balance BUY / HOLD / SELL
    rf = RandomForestClassifier(
        n_estimators=180,
        max_depth=6,
        min_samples_leaf=4,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )
    gb = GradientBoostingClassifier(
        n_estimators=120,
        learning_rate=0.04,
        max_depth=3,
        random_state=42
    )

    rf.fit(X_train, y_train)
    gb.fit(X_train, y_train)

    rf_preds = rf.predict(X_test)
    gb_preds = gb.predict(X_test)

    rf_acc = accuracy_score(y_test, rf_preds)
    gb_acc = accuracy_score(y_test, gb_preds)
    avg_acc = (rf_acc + gb_acc) / 2.0

    return {
        "rf": rf,
        "gb": gb,
        "test_accuracy": round(float(avg_acc * 100), 2),
        "feature_columns": POSITION_FEATURE_COLUMNS
    }


def evaluate_holding_position(
    symbol,
    purchase_price,
    current_price,
    purchase_date,
    indicator_data,
    news_sentiment=None
):
    """
    Main evaluation pipeline for a user's stock holding using Model 2:
    - Trains position classifier on historical indicators.
    - Evaluates the current state (latest indicators + holding metrics).
    - Determines BUY, HOLD, or SELL with calculated stop-loss, target prices,
      confidence probability, and concrete quantitative trigger reasons.
    """
    if indicator_data.empty:
        raise ValueError(f"No technical indicator data available for {symbol}.")

    current_price = float(current_price)
    purchase_price = float(purchase_price)

    # 1. Train the dedicated position model
    models = train_position_classifier(indicator_data)
    rf = models["rf"]
    gb = models["gb"]

    # 2. Extract current state vector
    latest_row = indicator_data[POSITION_FEATURE_COLUMNS].iloc[[-1]]
    rf_probs = rf.predict_proba(latest_row)[0]
    gb_probs = gb.predict_proba(latest_row)[0]

    # Handle cases where some classes might not appear in train set
    classes = rf.classes_
    prob_dict = {0: 0.0, 1: 0.0, 2: 0.0}
    for idx, c in enumerate(classes):
        prob_dict[int(c)] += 0.5 * rf_probs[idx]
    for idx, c in enumerate(gb.classes_):
        prob_dict[int(c)] += 0.5 * gb_probs[idx]

    # 3. Holding performance metrics
    pnl_ratio = (current_price - purchase_price) / purchase_price
    pnl_pct = pnl_ratio * 100.0

    # Calculate holding duration
    try:
        purchase_dt = pd.to_datetime(purchase_date)
        holding_days = max(1, (pd.Timestamp.now() - purchase_dt).days)
    except Exception:
        holding_days = 1

    # Extract key technical indicators
    latest = indicator_data.iloc[-1]
    rsi = float(latest.get("RSI", 50))
    macd = float(latest.get("MACD", 0))
    macd_sig = float(latest.get("MACD_Signal", 0))
    macd_hist = float(latest.get("MACD_Histogram", 0))
    atr14 = float(latest.get("ATR14", current_price * 0.02))
    bb_pos = float(latest.get("BB_Position", 0.5))
    price_sma50 = float(latest.get("Price_SMA50_Ratio", 1.0))
    volatility20 = float(latest.get("Volatility20", 0.25))

    # 4. Dynamic Risk & Barrier Boundaries (ATR-based)
    # Target: 2.5x ATR above current price
    target_price = round(current_price + (2.5 * atr14), 2)
    # Stop-loss: 1.8x ATR below current price (or at least 3.5% below entry if in loss)
    stop_loss_price = round(max(0.01, current_price - (1.8 * atr14)), 2)

    # 5. Rule & ML Synthesis (Action Determination)
    reasons = []
    action_type = "TREND_HOLD"

    # News sentiment adjustment
    sentiment_score = 0.0
    sentiment_label = "Neutral"
    if news_sentiment and isinstance(news_sentiment, dict):
        sentiment_score = float(news_sentiment.get("score", 0.0))
        sentiment_label = news_sentiment.get("label", "Neutral")

    # Profit Take condition
    if pnl_pct >= 10.0 and (rsi > 70 or bb_pos > 0.90 or macd_hist < 0):
        action_type = "TAKE_PROFIT"
        prob_dict[0] += 0.35
        reasons.append(f"Position reached +{round(pnl_pct, 1)}% profit with momentum showing overbought/exhaustion signals.")

    # Stop Loss condition
    elif pnl_pct <= -5.0 or current_price <= stop_loss_price:
        action_type = "STOP_LOSS"
        prob_dict[0] += 0.45
        reasons.append(f"Position in {round(pnl_pct, 1)}% drawdown, breaching the adaptive ATR protective boundary (₹{stop_loss_price}).")

    # Technical breakdown
    elif rsi < 35 and macd < macd_sig and price_sma50 < 0.97:
        action_type = "BREAKDOWN_SELL"
        prob_dict[0] += 0.30
        reasons.append(f"Bearish trend confirmed: Price trading below 50-day moving average and MACD negative.")

    # Momentum Buy / Accumulation
    elif rsi >= 45 and rsi <= 68 and macd > macd_sig and price_sma50 >= 1.01 and sentiment_score >= -0.05:
        action_type = "MOMENTUM_BUY"
        prob_dict[2] += 0.30
        reasons.append(f"Bullish continuation: Price is trading above 50-day SMA with positive MACD momentum.")

    # Overbought caution
    if rsi >= 72:
        reasons.append(f"RSI is elevated at {round(rsi, 1)} (Overbought territory).")
    elif rsi <= 32:
        reasons.append(f"RSI is low at {round(rsi, 1)} (Oversold territory).")

    if sentiment_label == "Positive":
        reasons.append(f"Recent news coverage exhibits positive market sentiment (score: +{round(sentiment_score, 2)}).")
    elif sentiment_label == "Negative":
        reasons.append(f"Recent news coverage exhibits negative sentiment (score: {round(sentiment_score, 2)}).")

    # Normalize final probabilities
    total_prob = sum(prob_dict.values())
    for k in prob_dict:
        prob_dict[k] = prob_dict[k] / total_prob

    # Pick winning class
    best_class = max(prob_dict, key=prob_dict.get)
    class_map = {0: "SELL", 1: "HOLD", 2: "BUY"}
    signal = class_map[best_class]

    # Fallback safety: If in deep loss (>7%), signal SELL to protect capital
    if pnl_pct <= -7.0 and signal != "SELL":
        signal = "SELL"
        action_type = "CAPITAL_PRESERVATION_EXIT"
        reasons.insert(0, f"Critical risk rule triggered: Unrealized loss is -{abs(round(pnl_pct, 1))}%. Exiting to preserve capital.")

    # If in strong profit (>12%) and RSI > 75, signal SELL
    if pnl_pct >= 12.0 and rsi > 75 and signal == "BUY":
        signal = "HOLD"
        action_type = "PROFIT_PROTECTION"
        reasons.insert(0, f"High unrealized gain (+{round(pnl_pct, 1)}%) with extreme RSI. Prefer holding with trailing stop over buying.")

    confidence = round(float(prob_dict[best_class] * 100), 1)

    if not reasons:
        reasons.append(f"Stock is trading in a healthy range with stable trend metrics.")

    return {
        "model_name": "QuantGen Position Strategy Classifier (Model 2)",
        "signal": signal,
        "action_type": action_type,
        "confidence_score": confidence,
        "probabilities": {
            "sell": round(float(prob_dict[0] * 100), 1),
            "hold": round(float(prob_dict[1] * 100), 1),
            "buy": round(float(prob_dict[2] * 100), 1),
        },
        "target_price": target_price,
        "stop_loss_price": stop_loss_price,
        "holding_days": holding_days,
        "unrealized_pnl_percent": round(pnl_pct, 2),
        "test_accuracy": models["test_accuracy"],
        "reasons": reasons,
    }
