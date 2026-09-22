from dataclasses import dataclass
from datetime import time
from pathlib import Path
import json
import math

import pandas as pd

from src.database.database import get_app_base_path


PROFILE_FILE = get_app_base_path() / "data" / "battery_field_profiles.json"


@dataclass
class BatteryFieldConfig:
    rack_declared_charge: float = 90.0
    optimal_min_charge: float = 90.0
    warning_percent: float = 30.0
    critical_percent: float = 20.0
    bit_hour: int = 7
    bit_minute: int = 15
    gps_min_quality: float = 70.0
    gps_max_minutes: float = 20.0
    max_temperature_c: float = 45.0
    expected_drop_percent_day: float = 3.0
    accelerated_drop_factor: float = 2.0
    ignore_zero_charge: bool = True


def default_profiles():
    return {
        "Operativo normal": BatteryFieldConfig().__dict__,
        "Conservador": BatteryFieldConfig(
            rack_declared_charge=95,
            optimal_min_charge=90,
            warning_percent=40,
            critical_percent=25,
            gps_min_quality=70,
            gps_max_minutes=15,
            max_temperature_c=45,
            expected_drop_percent_day=2.5,
            accelerated_drop_factor=1.7,
            ignore_zero_charge=True,
        ).__dict__,
        "Agresivo": BatteryFieldConfig(
            rack_declared_charge=80,
            optimal_min_charge=80,
            warning_percent=25,
            critical_percent=15,
            gps_min_quality=60,
            gps_max_minutes=30,
            max_temperature_c=55,
            expected_drop_percent_day=5.0,
            accelerated_drop_factor=2.5,
            ignore_zero_charge=True,
        ).__dict__,
    }


def load_profiles():
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not PROFILE_FILE.exists():
        profiles = default_profiles()
        save_profiles(profiles)
        return profiles

    try:
        with PROFILE_FILE.open("r", encoding="utf-8") as file:
            profiles = json.load(file)

        if not profiles:
            profiles = default_profiles()
            save_profiles(profiles)

        return profiles

    except Exception:
        profiles = default_profiles()
        save_profiles(profiles)
        return profiles


def save_profiles(profiles):
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with PROFILE_FILE.open("w", encoding="utf-8") as file:
        json.dump(profiles, file, indent=4, ensure_ascii=False)


def save_profile(profile_name, config):
    profiles = load_profiles()
    profiles[profile_name] = config.__dict__.copy()
    save_profiles(profiles)


def config_from_dict(values):
    base = BatteryFieldConfig().__dict__.copy()
    base.update(values or {})
    return BatteryFieldConfig(**base)


def _to_float(value):
    try:
        if value is None or pd.isna(value):
            return None
        value = float(value)
        if math.isnan(value):
            return None
        return value
    except Exception:
        return None


def _parse_timestamp_column(df):
    df = df.copy()

    if "timestamp" not in df.columns:
        df["timestamp"] = pd.NaT
        return df

    if pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        return df

    raw = df["timestamp"].astype(str).str.strip()

    parsed = pd.to_datetime(
        raw,
        format="%d/%m/%Y %H:%M:%S",
        errors="coerce",
    )

    missing = parsed.isna()

    if missing.any():
        parsed_no_seconds = pd.to_datetime(
            raw[missing],
            format="%d/%m/%Y %H:%M",
            errors="coerce",
        )
        parsed.loc[missing] = parsed_no_seconds

    missing = parsed.isna()

    if missing.any():
        parsed_auto = pd.to_datetime(
            raw[missing],
            errors="coerce",
        )
        parsed.loc[missing] = parsed_auto

    df["timestamp"] = parsed
    return df


def prepare_field_dataframe(df, config):
    df = df.copy()

    if df.empty:
        return df

    df = _parse_timestamp_column(df)

    for column in [
        "voltage_mv",
        "charge_percent",
        "gps_quality",
        "temperature_c",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        else:
            df[column] = None

    if "acq_type" not in df.columns:
        df["acq_type"] = ""

    df["acq_type"] = df["acq_type"].fillna("").astype(str).str.strip()

    df = df.dropna(subset=["timestamp"])
    df = df.sort_values("timestamp")

    if config.ignore_zero_charge:
        df["charge_for_analysis"] = df["charge_percent"].where(
            df["charge_percent"] > 0
        )
    else:
        df["charge_for_analysis"] = df["charge_percent"]

    return df


def _first_valid(df, column):
    if df.empty or column not in df.columns:
        return None

    valid = df.dropna(subset=[column])

    if valid.empty:
        return None

    return valid.iloc[0]


def _last_valid(df, column):
    if df.empty or column not in df.columns:
        return None

    valid = df.dropna(subset=[column])

    if valid.empty:
        return None

    return valid.iloc[-1]


def _first_row_by_mode(df, mode):
    if df.empty or "acq_type" not in df.columns:
        return None

    mode_df = df[df["acq_type"].str.lower() == mode.lower()]

    if mode_df.empty:
        return None

    return mode_df.iloc[0]


def _first_gps_lock(df, config):
    if df.empty:
        return None

    gps_df = df[
        pd.to_numeric(df["gps_quality"], errors="coerce") >= config.gps_min_quality
    ]

    if gps_df.empty:
        return None

    return gps_df.iloc[0]


def _value(row, column):
    if row is None:
        return None
    return _to_float(row.get(column))


def _time_value(row):
    if row is None:
        return None
    return row.get("timestamp")


def _hours_between(start_time, end_time):
    if start_time is None or end_time is None:
        return None

    try:
        hours = (end_time - start_time).total_seconds() / 3600
        if hours < 0:
            return None
        return hours
    except Exception:
        return None


def _rate_per_day(start_value, end_value, hours):
    if (
        start_value is None
        or end_value is None
        or hours is None
        or hours <= 0
    ):
        return None

    days = hours / 24
    return (start_value - end_value) / days


def _integrate_hours_under_threshold(df, threshold):
    valid = df.dropna(subset=["timestamp", "charge_for_analysis"]).copy()

    if len(valid) < 2:
        return 0.0

    total_hours = 0.0
    rows = list(valid.itertuples(index=False))

    for previous, current in zip(rows[:-1], rows[1:]):
        previous_charge = getattr(previous, "charge_for_analysis", None)
        current_charge = getattr(current, "charge_for_analysis", None)
        previous_time = getattr(previous, "timestamp", None)
        current_time = getattr(current, "timestamp", None)

        if pd.isna(previous_charge) or pd.isna(current_charge):
            continue

        if previous_charge <= threshold or current_charge <= threshold:
            delta_hours = _hours_between(previous_time, current_time)
            if delta_hours is not None:
                total_hours += delta_hours

    return total_hours


def _detect_accelerated_drop(df, config):
    valid = df.dropna(subset=["timestamp", "charge_for_analysis"]).copy()

    if len(valid) < 3:
        return None, None, None

    valid["previous_time"] = valid["timestamp"].shift(1)
    valid["previous_charge"] = valid["charge_for_analysis"].shift(1)
    valid["hours"] = (
        valid["timestamp"] - valid["previous_time"]
    ).dt.total_seconds() / 3600

    valid["drop"] = valid["previous_charge"] - valid["charge_for_analysis"]

    valid = valid[
        (valid["hours"] > 0)
        &
        (valid["drop"] > 0)
    ].copy()

    if valid.empty:
        return None, None, None

    valid["drop_percent_day"] = valid["drop"] / (valid["hours"] / 24)

    threshold = max(
        config.expected_drop_percent_day * config.accelerated_drop_factor,
        config.expected_drop_percent_day + 2,
    )

    accelerated = valid[valid["drop_percent_day"] >= threshold]

    if accelerated.empty:
        return None, None, threshold

    row = accelerated.iloc[0]

    return (
        row.get("timestamp"),
        _to_float(row.get("drop_percent_day")),
        threshold,
    )


def _classify_and_explain(
    rack_gap,
    field_rate_percent_day,
    warning_hours,
    critical_hours,
    gps_minutes,
    max_temp,
    accelerated_time,
    final_charge,
    config,
):
    evidence = []
    probable_causes = []
    recommendations = []
    risk_points = 0

    if rack_gap is not None and rack_gap >= 15:
        risk_points += 25
        probable_causes.append("diferencia rack-campo anormal")
        evidence.append(f"diferencia rack-campo de {rack_gap:.1f}%")
        recommendations.append("revisar proceso de carga, reposo y lectura al salir del rack")

    if rack_gap is not None and rack_gap >= 25:
        probable_causes.append("posible lectura inflada durante carga o batería débil")

    if field_rate_percent_day is not None:
        if field_rate_percent_day >= config.expected_drop_percent_day * 3:
            risk_points += 30
            probable_causes.append("descarga acelerada en campo")
            evidence.append(f"descarga de {field_rate_percent_day:.2f}%/día")
            recommendations.append("revisar batería y comparar contra nodos del mismo lote")
        elif field_rate_percent_day >= config.expected_drop_percent_day * config.accelerated_drop_factor:
            risk_points += 20
            probable_causes.append("descarga mayor a la esperada")
            evidence.append(f"descarga de {field_rate_percent_day:.2f}%/día")

    if accelerated_time is not None:
        risk_points += 20
        probable_causes.append("inicio de caída acelerada detectado")
        evidence.append(f"caída acelerada desde {accelerated_time.strftime('%d/%m/%Y %H:%M')}")

    if warning_hours and warning_hours >= 24:
        risk_points += 15
        probable_causes.append("trabajo prolongado bajo warning")
        evidence.append(f"{warning_hours:.1f} h bajo warning")
        recommendations.append("simular retiro con warning más alto")

    if critical_hours and critical_hours > 0:
        risk_points += 25
        probable_causes.append("trabajo en zona crítica")
        evidence.append(f"{critical_hours:.1f} h bajo critical")
        recommendations.append("evitar operación bajo zona crítica para proteger vida útil")

    if gps_minutes is not None and gps_minutes > config.gps_max_minutes:
        risk_points += 10
        probable_causes.append("GPS prolongado")
        evidence.append(f"GPS tardó {gps_minutes:.1f} min")
        recommendations.append("revisar condiciones de plantado/GPS")

    if max_temp is not None and max_temp >= config.max_temperature_c:
        risk_points += 15
        probable_causes.append("temperatura elevada")
        evidence.append(f"temperatura máxima {max_temp:.1f} °C")
        recommendations.append("revisar exposición térmica o almacenamiento")

    if final_charge is not None and final_charge <= config.critical_percent:
        risk_points += 25
        probable_causes.append("terminó bajo critical")
        evidence.append(f"carga final {final_charge:.1f}%")

    if not evidence:
        evidence.append("sin señales fuertes de degradación con los parámetros actuales")
        probable_causes.append("operación aparentemente normal")
        recommendations.append("monitorear tendencia y comparar con campañas futuras")

    if risk_points >= 80:
        status = "Crítico"
    elif risk_points >= 55:
        status = "Alto"
    elif risk_points >= 30:
        status = "Atención"
    else:
        status = "Normal"

    if "datos insuficientes" not in probable_causes and len(evidence) <= 1:
        confidence = "Baja"
    elif risk_points >= 30:
        confidence = "Media"
    else:
        confidence = "Media"

    return {
        "status": status,
        "risk_score": min(100, risk_points),
        "probable_cause": " / ".join(dict.fromkeys(probable_causes)),
        "evidence": " | ".join(dict.fromkeys(evidence)),
        "recommendation": " | ".join(dict.fromkeys(recommendations)),
        "confidence": confidence,
    }


def _simulate_warning(df, config):
    valid = df.dropna(subset=["timestamp", "charge_for_analysis"]).copy()

    if valid.empty:
        return {
            "recommended_retrieval_time": None,
            "hours_saved_vs_final": None,
            "simulated_note": "sin datos válidos de carga",
        }

    below_warning = valid[valid["charge_for_analysis"] <= config.warning_percent]

    if below_warning.empty:
        return {
            "recommended_retrieval_time": None,
            "hours_saved_vs_final": None,
            "simulated_note": "no llegó al warning configurado",
        }

    retrieval_time = below_warning.iloc[0]["timestamp"]
    final_time = valid.iloc[-1]["timestamp"]
    hours_saved = _hours_between(retrieval_time, final_time)

    return {
        "recommended_retrieval_time": retrieval_time,
        "hours_saved_vs_final": hours_saved,
        "simulated_note": (
            f"con warning {config.warning_percent:.0f}% se habría marcado retiro "
            f"desde {retrieval_time.strftime('%d/%m/%Y %H:%M')}"
        ),
    }


def analyze_node_field_battery(serial_number, df, config):
    prepared = prepare_field_dataframe(df, config)

    if prepared.empty:
        return {
            "serial_number": serial_number,
            "status": "Sin datos",
            "risk_score": 0,
            "confidence": "Baja",
            "probable_cause": "datos insuficientes",
            "evidence": "no hay registros válidos",
            "recommendation": "importar CSV válido",
            "prepared_df": prepared,
        }

    first_row = _first_valid(prepared, "charge_for_analysis")
    if first_row is None:
        first_row = _first_valid(prepared, "voltage_mv")

    final_row = _last_valid(prepared, "charge_for_analysis")
    bit_row = _first_row_by_mode(prepared, "BIT")
    gps_row = _first_gps_lock(prepared, config)
    seismic_row = _first_row_by_mode(prepared, "Seismic")

    first_time = _time_value(first_row)
    final_time = _time_value(final_row)
    bit_time = _time_value(bit_row)
    gps_time = _time_value(gps_row)
    seismic_time = _time_value(seismic_row)

    first_charge = _value(first_row, "charge_for_analysis")
    final_charge = _value(final_row, "charge_for_analysis")
    bit_charge = _value(bit_row, "charge_for_analysis")
    gps_charge = _value(gps_row, "charge_for_analysis")
    seismic_charge = _value(seismic_row, "charge_for_analysis")

    first_voltage = _value(first_row, "voltage_mv")
    final_voltage = _value(final_row, "voltage_mv")
    seismic_voltage = _value(seismic_row, "voltage_mv")

    start_work_time = seismic_time or gps_time or bit_time or first_time
    start_work_charge = seismic_charge
    if start_work_charge is None:
        start_work_charge = gps_charge
    if start_work_charge is None:
        start_work_charge = bit_charge
    if start_work_charge is None:
        start_work_charge = first_charge

    start_work_voltage = seismic_voltage or first_voltage

    work_hours = _hours_between(start_work_time, final_time)
    gps_minutes = None

    if gps_time is not None and first_time is not None:
        gps_minutes = _hours_between(first_time, gps_time)
        gps_minutes = gps_minutes * 60 if gps_minutes is not None else None

    rack_gap = None
    if first_charge is not None:
        rack_gap = config.rack_declared_charge - first_charge

    field_loss = None
    if start_work_charge is not None and final_charge is not None:
        field_loss = start_work_charge - final_charge

    field_rate_percent_day = _rate_per_day(
        start_work_charge,
        final_charge,
        work_hours,
    )

    voltage_rate_mv_day = _rate_per_day(
        start_work_voltage,
        final_voltage,
        work_hours,
    )

    warning_hours = _integrate_hours_under_threshold(
        prepared,
        config.warning_percent,
    )

    critical_hours = _integrate_hours_under_threshold(
        prepared,
        config.critical_percent,
    )

    accelerated_time, accelerated_rate, accelerated_threshold = (
        _detect_accelerated_drop(prepared, config)
    )

    max_temp = None
    avg_temp = None

    if "temperature_c" in prepared.columns:
        temp = pd.to_numeric(prepared["temperature_c"], errors="coerce").dropna()

        if not temp.empty:
            max_temp = float(temp.max())
            avg_temp = float(temp.mean())

    classification = _classify_and_explain(
        rack_gap,
        field_rate_percent_day,
        warning_hours,
        critical_hours,
        gps_minutes,
        max_temp,
        accelerated_time,
        final_charge,
        config,
    )

    simulated = _simulate_warning(prepared, config)

    total_hours = _hours_between(first_time, final_time)

    result = {
        "serial_number": serial_number,
        "status": classification["status"],
        "risk_score": classification["risk_score"],
        "confidence": classification["confidence"],
        "rack_declared_charge": config.rack_declared_charge,
        "first_charge": first_charge,
        "bit_charge": bit_charge,
        "gps_charge": gps_charge,
        "seismic_charge": seismic_charge,
        "final_charge": final_charge,
        "rack_gap": rack_gap,
        "field_loss": field_loss,
        "field_rate_percent_day": field_rate_percent_day,
        "field_rate_percent_hour": (
            field_rate_percent_day / 24
            if field_rate_percent_day is not None
            else None
        ),
        "voltage_rate_mv_day": voltage_rate_mv_day,
        "total_hours": total_hours,
        "work_hours": work_hours,
        "warning_hours": warning_hours,
        "critical_hours": critical_hours,
        "gps_minutes": gps_minutes,
        "avg_temp": avg_temp,
        "max_temp": max_temp,
        "accelerated_time": accelerated_time,
        "accelerated_rate": accelerated_rate,
        "accelerated_threshold": accelerated_threshold,
        "probable_cause": classification["probable_cause"],
        "evidence": classification["evidence"],
        "recommendation": classification["recommendation"],
        "first_time": first_time,
        "bit_time": bit_time,
        "gps_time": gps_time,
        "seismic_time": seismic_time,
        "final_time": final_time,
        "recommended_retrieval_time": simulated["recommended_retrieval_time"],
        "hours_saved_vs_final": simulated["hours_saved_vs_final"],
        "simulated_note": simulated["simulated_note"],
        "prepared_df": prepared,
    }

    if len(prepared.dropna(subset=["charge_for_analysis"])) < 5:
        result["status"] = "Revisar"
        result["confidence"] = "Baja"
        result["probable_cause"] = "datos insuficientes"
        result["evidence"] = "menos de 5 registros válidos de carga"
        result["recommendation"] = "no concluir degradación; revisar CSV o importar más datos"

    return result


def analyze_field_battery_batch(nodes, get_records_by_serial, config):
    rows = []

    for node in nodes:
        serial_number = node.get("serial_number", "")

        if not serial_number:
            continue

        df = get_records_by_serial(serial_number)
        rows.append(
            analyze_node_field_battery(
                serial_number,
                df,
                config,
            )
        )

    rows.sort(
        key=lambda row: (
            row.get("risk_score", 0),
            row.get("field_rate_percent_day") or 0,
        ),
        reverse=True,
    )

    return rows


def format_optional_number(value, decimals=2, suffix=""):
    if value is None or pd.isna(value):
        return "N/D"

    return f"{value:.{decimals}f}{suffix}"


def format_optional_datetime(value):
    if value is None or pd.isna(value):
        return "N/D"

    return value.strftime("%d/%m/%Y %H:%M")
