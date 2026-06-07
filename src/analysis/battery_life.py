from datetime import timedelta

import pandas as pd


OPTIMAL_VOLTAGE_MV = 4200
WARNING_VOLTAGE_MV = 3700
CRITICAL_VOLTAGE_MV = 3600

# Saltos mayores a esto se consideran eventos/picos,
# no necesariamente ciclos reales de batería.
SPIKE_JUMP_MV = 120


def prepare_battery_dataframe(df):
    """
    Prepare dataframe for battery analysis.

    This function standardizes:
    - timestamps
    - voltage values
    - charge percentage values

    It does not modify the original dataframe.
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
    Return data useful for battery discharge analysis.

    For V1.1 we avoid using 'No acquisition' for slope prediction,
    because those points often create vertical spikes or special readings
    that distort the real discharge trend.
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
    Remove isolated voltage spikes.

    A spike is a sudden jump up or down that can distort the trend.
    This does not mean the data is bad; it only means it should not be
    used for the simple V1.1 prediction model.
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


def calculate_battery_health(current_voltage):
    """
    Estimate battery health percentage.

    This is NOT a real chemical battery-health measurement.
    It is an operational estimate based on where the current voltage sits
    between an expected optimal voltage and the critical voltage.

    4200 mV = 100%
    3600 mV = 0%
    """

    if current_voltage is None or pd.isna(current_voltage):
        return None

    health = (
        (current_voltage - CRITICAL_VOLTAGE_MV)
        /
        (OPTIMAL_VOLTAGE_MV - CRITICAL_VOLTAGE_MV)
    ) * 100

    health = max(0, min(100, health))

    return health


def classify_battery_condition(battery_health):
    """
    Convert battery health percentage into operational condition.
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
    slope, intercept, start_time
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
    Estimate battery stability based on voltage variability.

    Stable:
    smooth discharge

    Moderate:
    some jumps or irregularity

    Unstable:
    many voltage jumps or inconsistent readings
    """

    df = df.copy()

    if len(df) < 3:
        return "Low", "Unknown"

    df["voltage_diff"] = df["voltage_mv"].diff().abs()

    spike_count = int(
        (df["voltage_diff"] > SPIKE_JUMP_MV).sum()
    )

    total_records = len(df)

    spike_ratio = spike_count / total_records

    if spike_ratio <= 0.01:
        return "High", "Stable"

    if spike_ratio <= 0.05:
        return "Medium", "Moderate"

    return "Low", "Unstable"


def calculate_confidence(df, slope, stability):
    """
    Basic confidence level for the prediction.

    Confidence depends on:
    - record count
    - time span
    - negative discharge slope
    - voltage stability
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


def estimate_remaining_life(current_voltage, voltage_slope, latest_time):
    """
    Estimate remaining days until critical voltage.

    Formula:
    remaining_days = (current_voltage - critical_voltage) / abs(slope)

    This only works if slope is negative.
    """

    if (
        current_voltage is None
        or pd.isna(current_voltage)
        or voltage_slope is None
        or voltage_slope >= 0
        or current_voltage <= CRITICAL_VOLTAGE_MV
    ):
        return None, "", None

    remaining_days = (
        current_voltage - CRITICAL_VOLTAGE_MV
    ) / abs(voltage_slope)

    replacement_timestamp = latest_time + timedelta(
        days=float(remaining_days)
    )

    replacement_date = replacement_timestamp.strftime(
        "%d/%m/%Y"
    )

    return remaining_days, replacement_date, replacement_timestamp


def calculate_mode_slopes(df):
    """
    Calculate voltage discharge slope by acquisition mode.

    This helps answer:
    - Does Seismic drain faster?
    - Does BIT consume differently?
    - Is No acquisition behaving abnormally?
    """

    results = {}

    for acq_type in ["Seismic", "BIT", "No acquisition"]:
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

    This model is intentionally simple and transparent:
    - uses operational voltage behavior
    - removes obvious spikes
    - estimates health from voltage position
    - calculates discharge slope
    - estimates remaining life to critical voltage

    It does NOT claim real chemical battery capacity.
    """

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
            "critical_voltage": CRITICAL_VOLTAGE_MV,
            "warning_voltage": WARNING_VOLTAGE_MV,
            "optimal_voltage": OPTIMAL_VOLTAGE_MV,
            "mode_slopes": {},
            "analysis_df": prepared_df,
        }

    latest_row = prepared_df.iloc[-1]

    current_voltage = latest_row.get("voltage_mv")
    current_charge = latest_row.get("charge_percent")
    latest_time = latest_row.get("timestamp")

    battery_health = calculate_battery_health(
        current_voltage
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
            latest_time
        )
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
        "critical_voltage": CRITICAL_VOLTAGE_MV,
        "warning_voltage": WARNING_VOLTAGE_MV,
        "optimal_voltage": OPTIMAL_VOLTAGE_MV,
        "mode_slopes": mode_slopes,
        "analysis_df": cleaned_df,
    }


def build_voltage_trend_line(df, slope, intercept, start_time):
    """
    Build voltage trend line for plotting.

    The trend uses the cleaned analysis dataframe.
    """

    if df.empty or slope is None or intercept is None or start_time is None:
        return None

    trend_df = df.copy()

    trend_df["days_from_start"] = (
        trend_df["timestamp"] - start_time
    ).dt.total_seconds() / 86400

    trend_df["trend_voltage"] = (
        intercept + slope * trend_df["days_from_start"]
    )

    return trend_df