from datetime import timedelta

import pandas as pd


CRITICAL_VOLTAGE_MV = 3600
WARNING_VOLTAGE_MV = 3700
BATTERY_RESET_JUMP_MV = 100


def prepare_battery_dataframe(df):
    df = df.copy()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    df["voltage_mv"] = pd.to_numeric(
        df["voltage_mv"],
        errors="coerce"
    )

    df["charge_percent"] = pd.to_numeric(
        df["charge_percent"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["timestamp", "voltage_mv"]
    )

    df = df.sort_values("timestamp")

    return df


def detect_voltage_cycles(df):
    """
    Detect physical battery cycles / replacements.

    Rule:
    If voltage jumps upward more than 100 mV,
    it is considered a new battery cycle.
    """

    df = prepare_battery_dataframe(df)

    if df.empty:
        return df, 0

    df["voltage_diff"] = df["voltage_mv"].diff()

    df["cycle_id"] = (
        df["voltage_diff"] > BATTERY_RESET_JUMP_MV
    ).cumsum() + 1

    total_cycles = int(df["cycle_id"].max())

    return df, total_cycles


def calculate_equivalent_charge_cycles(df):
    """
    iPhone-like estimated equivalent cycles.

    This is NOT real coulomb counting.
    It estimates cycles using accumulated charge drop.

    Example:
    80% -> 50% = 30% consumed
    90% -> 40% = 50% consumed
    Total = 80%
    When total reaches 100%, it approximates 1 cycle.
    """

    df = prepare_battery_dataframe(df)

    df = df.dropna(
        subset=["charge_percent"]
    )

    if len(df) < 2:
        return 0.0

    df["charge_drop"] = -df["charge_percent"].diff()

    df = df[
        df["charge_drop"] > 0
    ]

    total_consumed_percent = df["charge_drop"].sum()

    return total_consumed_percent / 100


def get_latest_voltage_cycle(df):
    df, total_cycles = detect_voltage_cycles(df)

    if df.empty:
        return df, total_cycles

    latest_cycle_id = df["cycle_id"].max()

    latest_cycle_df = df[
        df["cycle_id"] == latest_cycle_id
    ].copy()

    return latest_cycle_df, total_cycles


def calculate_slope_per_day(df, column):
    """
    Calculate linear slope per day.

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


def calculate_mode_slopes(df):
    """
    Calculate voltage discharge rate by acquisition type.
    """

    results = {}

    for acq_type in ["Seismic", "BIT", "No acquisition"]:
        mode_df = df[
            df["acq_type"] == acq_type
        ].copy()

        slope, _, _ = calculate_slope_per_day(
            mode_df,
            "voltage_mv"
        )

        results[acq_type] = slope

    return results


def calculate_confidence(df, slope):
    if df.empty or slope is None:
        return "Low"

    total_days = (
        df["timestamp"].max() - df["timestamp"].min()
    ).total_seconds() / 86400

    record_count = len(df)

    if record_count >= 30 and total_days >= 7 and slope < 0:
        return "High"

    if record_count >= 10 and total_days >= 3 and slope < 0:
        return "Medium"

    return "Low"


def calculate_battery_insight(df):
    """
    Main Battery Intelligence calculation.

    Uses latest voltage cycle only for prediction.
    """

    prepared_df = prepare_battery_dataframe(df)

    latest_cycle_df, physical_cycles = get_latest_voltage_cycle(
        prepared_df
    )

    equivalent_cycles = calculate_equivalent_charge_cycles(
        prepared_df
    )

    if latest_cycle_df.empty:
        return {
            "current_voltage": None,
            "current_charge": None,
            "voltage_slope_mv_day": None,
            "charge_slope_percent_day": None,
            "remaining_days": None,
            "replacement_date": "",
            "replacement_timestamp": None,
            "physical_cycles": 0,
            "equivalent_cycles": 0.0,
            "confidence": "Low",
            "critical_voltage": CRITICAL_VOLTAGE_MV,
            "warning_voltage": WARNING_VOLTAGE_MV,
            "mode_slopes": {},
        }

    voltage_slope, voltage_intercept, voltage_start_time = (
        calculate_slope_per_day(
            latest_cycle_df,
            "voltage_mv"
        )
    )

    charge_df = latest_cycle_df.dropna(
        subset=["charge_percent"]
    )

    charge_slope, _, _ = calculate_slope_per_day(
        charge_df,
        "charge_percent"
    )

    latest_row = latest_cycle_df.iloc[-1]

    current_voltage = latest_row.get("voltage_mv")
    current_charge = latest_row.get("charge_percent")
    latest_time = latest_row.get("timestamp")

    remaining_days = None
    replacement_date = ""
    replacement_timestamp = None

    if (
        voltage_slope is not None
        and voltage_slope < 0
        and current_voltage > CRITICAL_VOLTAGE_MV
    ):
        remaining_days = (
            current_voltage - CRITICAL_VOLTAGE_MV
        ) / abs(voltage_slope)

        replacement_timestamp = latest_time + timedelta(
            days=float(remaining_days)
        )

        replacement_date = replacement_timestamp.strftime(
            "%d/%m/%Y"
        )

    confidence = calculate_confidence(
        latest_cycle_df,
        voltage_slope
    )

    mode_slopes = calculate_mode_slopes(
        latest_cycle_df
    )

    return {
        "current_voltage": current_voltage,
        "current_charge": current_charge,
        "voltage_slope_mv_day": voltage_slope,
        "voltage_intercept": voltage_intercept,
        "voltage_start_time": voltage_start_time,
        "charge_slope_percent_day": charge_slope,
        "remaining_days": remaining_days,
        "replacement_date": replacement_date,
        "replacement_timestamp": replacement_timestamp,
        "physical_cycles": physical_cycles,
        "equivalent_cycles": equivalent_cycles,
        "confidence": confidence,
        "critical_voltage": CRITICAL_VOLTAGE_MV,
        "warning_voltage": WARNING_VOLTAGE_MV,
        "mode_slopes": mode_slopes,
        "latest_cycle_df": latest_cycle_df,
    }


def build_voltage_trend_line(df, slope, intercept, start_time):
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