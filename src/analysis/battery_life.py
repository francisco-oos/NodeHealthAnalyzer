from datetime import timedelta

import pandas as pd

from src.database.database import get_app_settings


SPIKE_JUMP_MV = 120


def prepare_battery_dataframe(df):
    """
    Prepare dataframe for battery analysis.

    Standardizes:
    - timestamp
    - voltage_mv
    - charge_percent

    The original dataframe is not modified.
    """

    df = df.copy()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    df["voltage_mv"] = pd.to_numeric(
        df["voltage_mv"],
        errors="coerce"
    )

    if "charge_percent" in df.columns:
        df["charge_percent"] = pd.to_numeric(
            df["charge_percent"],
            errors="coerce"
        )

    df = df.dropna(
        subset=["timestamp", "voltage_mv"]
    )

    df = df.sort_values("timestamp")

    return df


def get_operational_voltage_data(df):
    """
    Return records useful for discharge analysis.

    Seismic and BIT are preferred because No acquisition
    may contain special readings or spikes.
    """

    df = prepare_battery_dataframe(df)

    if "acq_type" in df.columns:
        operational_df = df[
            df["acq_type"].isin(["Seismic", "BIT"])
        ].copy()

        if not operational_df.empty:
            return operational_df

    return df


def remove_voltage_spikes(df):
    """
    Remove isolated voltage spikes from analysis data.

    This avoids distorted trend lines and unrealistic predictions.
    """

    df = df.copy()

    if len(df) < 3:
        return df

    df["voltage_diff"] = df["voltage_mv"].diff().abs()

    cleaned_df = df[
        (df["voltage_diff"].isna())
        |
        (df["voltage_diff"] <= SPIKE_JUMP_MV)
    ].copy()

    return cleaned_df


def calculate_battery_health(
    current_voltage,
    optimal_voltage,
    critical_voltage
):
    """
    Estimate operational battery health percentage.

    This is not chemical battery capacity.
    It estimates where current voltage sits between:
    - configured optimal voltage
    - configured critical voltage
    """

    if current_voltage is None or pd.isna(current_voltage):
        return None

    if optimal_voltage <= critical_voltage:
        return None

    health = (
        (current_voltage - critical_voltage)
        /
        (optimal_voltage - critical_voltage)
    ) * 100

    health = max(0, min(100, health))

    return health


def classify_battery_condition(battery_health):
    """
    Convert battery health percentage into an operational label.
    """

    if battery_health is None or pd.isna(battery_health):
        return "Unknown"

    if battery_health >= 85:
        return "Excellent"

    if battery_health >= 70:
        return "Good"

    if battery_health >= 50:
        return "Warning"

    return "Critical"


def calculate_slope_per_day(df, column):
    """
    Calculate linear slope per day.

    Example:
    -8.5 means the node loses 8.5 mV per day.

    Returns:
    - slope
    - intercept
    - start_time
    """

    df = df.dropna(
        subset=["timestamp", column]
    ).copy()

    if len(df) < 2:
        return None, None, None

    start_time = df["timestamp"].min()

    df["days_from_start"] = (
        df["timestamp"] - start_time
    ).dt.total_seconds() / 86400

    if df["days_from_start"].max() == 0:
        return None, None, None

    x = df["days_from_start"]
    y = df[column]

    denominator = ((x - x.mean()) ** 2).sum()

    if denominator == 0:
        return None, None, None

    slope = (
        ((x - x.mean()) * (y - y.mean())).sum()
        /
        denominator
    )

    intercept = y.mean() - slope * x.mean()

    return slope, intercept, start_time


def calculate_battery_stability(df):
    """
    Estimate voltage stability.

    Stable:
    smooth voltage behavior

    Moderate:
    some voltage jumps

    Unstable:
    many voltage jumps
    """

    df = df.copy()

    if len(df) < 3:
        return "Low", "Unknown"

    df["voltage_diff"] = df["voltage_mv"].diff().abs()

    spike_count = int(
        (df["voltage_diff"] > SPIKE_JUMP_MV).sum()
    )

    total_records = len(df)

    if total_records == 0:
        return "Low", "Unknown"

    spike_ratio = spike_count / total_records

    if spike_ratio <= 0.01:
        return "High", "Stable"

    if spike_ratio <= 0.05:
        return "Medium", "Moderate"

    return "Low", "Unstable"


def calculate_confidence(df, slope, stability):
    """
    Estimate prediction confidence.

    Confidence depends on:
    - amount of data
    - time span
    - negative discharge slope
    - stability
    """

    if df.empty or slope is None:
        return "Low"

    total_days = (
        df["timestamp"].max() - df["timestamp"].min()
    ).total_seconds() / 86400

    record_count = len(df)

    if (
        record_count >= 30
        and total_days >= 7
        and slope < 0
        and stability == "Stable"
    ):
        return "High"

    if (
        record_count >= 10
        and total_days >= 3
        and slope < 0
    ):
        return "Medium"

    return "Low"


def estimate_remaining_life(
    current_voltage,
    voltage_slope,
    latest_time,
    critical_voltage
):
    """
    Estimate remaining days until configured critical voltage.

    Formula:
    remaining_days =
    (current_voltage - critical_voltage) / abs(voltage_slope)
    """

    if (
        current_voltage is None
        or pd.isna(current_voltage)
        or voltage_slope is None
        or voltage_slope >= 0
        or current_voltage <= critical_voltage
    ):
        return None, "", None

    remaining_days = (
        current_voltage - critical_voltage
    ) / abs(voltage_slope)

    replacement_timestamp = latest_time + timedelta(
        days=float(remaining_days)
    )

    replacement_date = replacement_timestamp.strftime(
        "%d/%m/%Y"
    )

    return (
        remaining_days,
        replacement_date,
        replacement_timestamp
    )


def validate_prediction(
    remaining_days,
    voltage_slope,
    settings
):
    """
    Prevent unrealistic predictions.

    Example:
    If result says replacement in 2041,
    but manufacturer expected life is 4 years,
    prediction is marked as not reliable.
    """

    if remaining_days is None or voltage_slope is None:
        return False, "No prediction"

    minimum_discharge = float(
        settings.get(
            "minimum_valid_discharge_mv_day",
            0.5
        )
    )

    manufacturer_life_years = float(
        settings.get(
            "manufacturer_life_years",
            4
        )
    )

    manufacturer_limit_days = (
        manufacturer_life_years * 365
    )

    if abs(voltage_slope) < minimum_discharge:
        return (
            False,
            "Discharge rate too small"
        )

    if remaining_days > manufacturer_limit_days:
        return (
            False,
            "Prediction exceeds manufacturer life"
        )

    return True, ""


def generate_recommendation(
    remaining_days,
    prediction_valid,
    battery_condition,
    confidence,
    settings
):
    """
    Generate operational recommendation.

    This is the user-facing decision helper.
    """

    if not prediction_valid:
        return "Prediction not reliable"

    alert_days = int(
        settings.get(
            "replacement_alert_days",
            90
        )
    )

    if battery_condition == "Critical":
        return "Replace battery soon"

    if remaining_days is not None and remaining_days <= 30:
        return "Replace battery soon"

    if remaining_days is not None and remaining_days <= alert_days:
        return "Plan battery replacement"

    if confidence == "Low":
        return "Monitor trend"

    return "Normal operation"


def calculate_mode_slopes(df):
    """
    Calculate voltage discharge slope by acquisition mode.

    Helps compare:
    - Seismic consumption
    - BIT consumption
    - No acquisition behavior
    """

    results = {}

    for acq_type in ["Seismic", "BIT", "No acquisition"]:
        if "acq_type" not in df.columns:
            results[acq_type] = None
            continue

        mode_df = df[
            df["acq_type"] == acq_type
        ].copy()

        mode_df = remove_voltage_spikes(mode_df)

        slope, _, _ = calculate_slope_per_day(
            mode_df,
            "voltage_mv"
        )

        results[acq_type] = slope

    return results


def calculate_battery_insight(df):
    """
    Main Battery Intelligence calculation for V1.1.

    Uses configurable settings from SQLite:
    - optimal voltage
    - warning voltage
    - critical voltage
    - manufacturer expected life
    - replacement alert days
    - minimum valid discharge rate

    This model is transparent and operational.
    It does not claim real chemical battery capacity.
    """

    settings = get_app_settings()

    optimal_voltage = float(
        settings.get("optimal_voltage_mv", 4200)
    )

    warning_voltage = float(
        settings.get("warning_voltage_mv", 3700)
    )

    critical_voltage = float(
        settings.get("critical_voltage_mv", 3600)
    )

    prepared_df = prepare_battery_dataframe(df)

    if prepared_df.empty:
        return {
            "current_voltage": None,
            "current_charge": None,
            "battery_health": None,
            "battery_condition": "Unknown",
            "voltage_slope_mv_day": None,
            "voltage_intercept": None,
            "voltage_start_time": None,
            "charge_slope_percent_day": None,
            "remaining_days": None,
            "replacement_date": "",
            "replacement_timestamp": None,
            "battery_stability": "Unknown",
            "confidence": "Low",
            "prediction_valid": False,
            "prediction_note": "No data",
            "recommendation": "Prediction not reliable",
            "critical_voltage": critical_voltage,
            "warning_voltage": warning_voltage,
            "optimal_voltage": optimal_voltage,
            "mode_slopes": {},
            "analysis_df": prepared_df,
        }

    latest_row = prepared_df.iloc[-1]

    current_voltage = latest_row.get("voltage_mv")
    current_charge = latest_row.get("charge_percent")
    latest_time = latest_row.get("timestamp")

    battery_health = calculate_battery_health(
        current_voltage,
        optimal_voltage,
        critical_voltage
    )

    battery_condition = classify_battery_condition(
        battery_health
    )

    operational_df = get_operational_voltage_data(
        prepared_df
    )

    cleaned_df = remove_voltage_spikes(
        operational_df
    )

    voltage_slope, voltage_intercept, voltage_start_time = (
        calculate_slope_per_day(
            cleaned_df,
            "voltage_mv"
        )
    )

    charge_slope = None

    if "charge_percent" in cleaned_df.columns:
        charge_df = cleaned_df[
            cleaned_df["charge_percent"] > 0
        ].copy()

        charge_slope, _, _ = calculate_slope_per_day(
            charge_df,
            "charge_percent"
        )

    _, battery_stability = calculate_battery_stability(
        prepared_df
    )

    confidence = calculate_confidence(
        cleaned_df,
        voltage_slope,
        battery_stability
    )

    remaining_days, replacement_date, replacement_timestamp = (
        estimate_remaining_life(
            current_voltage,
            voltage_slope,
            latest_time,
            critical_voltage
        )
    )

    prediction_valid, prediction_note = validate_prediction(
        remaining_days,
        voltage_slope,
        settings
    )

    if not prediction_valid:
        remaining_days = None
        replacement_date = ""
        replacement_timestamp = None

    recommendation = generate_recommendation(
        remaining_days,
        prediction_valid,
        battery_condition,
        confidence,
        settings
    )

    mode_slopes = calculate_mode_slopes(
        prepared_df
    )

    return {
        "current_voltage": current_voltage,
        "current_charge": current_charge,
        "battery_health": battery_health,
        "battery_condition": battery_condition,
        "voltage_slope_mv_day": voltage_slope,
        "voltage_intercept": voltage_intercept,
        "voltage_start_time": voltage_start_time,
        "charge_slope_percent_day": charge_slope,
        "remaining_days": remaining_days,
        "replacement_date": replacement_date,
        "replacement_timestamp": replacement_timestamp,
        "battery_stability": battery_stability,
        "confidence": confidence,
        "prediction_valid": prediction_valid,
        "prediction_note": prediction_note,
        "recommendation": recommendation,
        "critical_voltage": critical_voltage,
        "warning_voltage": warning_voltage,
        "optimal_voltage": optimal_voltage,
        "mode_slopes": mode_slopes,
        "analysis_df": cleaned_df,
    }


def build_voltage_trend_line(df, slope, intercept, start_time):
    """
    Build voltage trend line for plotting.

    Uses cleaned analysis dataframe.
    """

    if (
        df is None
        or df.empty
        or slope is None
        or intercept is None
        or start_time is None
    ):
        return None

    trend_df = df.copy()

    trend_df["days_from_start"] = (
        trend_df["timestamp"] - start_time
    ).dt.total_seconds() / 86400

    trend_df["trend_voltage"] = (
        intercept + slope * trend_df["days_from_start"]
    )

    return trend_df