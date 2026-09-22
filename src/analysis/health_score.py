from src.database.database import get_app_settings


def calculate_health_score(voltage, charge, gps_quality):
    """
    Calculates operational node health score.

    Uses battery settings from database instead of fixed voltage values.
    """

    settings = get_app_settings()

    warning_voltage = float(settings.get("warning_voltage_mv", 3700))
    critical_voltage = float(settings.get("critical_voltage_mv", 3600))
    optimal_voltage = float(settings.get("optimal_voltage_mv", 4200))

    score = 100

    try:
        voltage = float(voltage)
    except Exception:
        voltage = 0

    try:
        charge = float(charge)
    except Exception:
        charge = 0

    try:
        gps_quality = float(gps_quality)
    except Exception:
        gps_quality = 0

    if voltage <= critical_voltage:
        score -= 50
    elif voltage <= warning_voltage:
        score -= 30
    elif voltage < optimal_voltage:
        score -= 10

    if charge < 40:
        score -= 35
    elif charge < 60:
        score -= 20
    elif charge < 75:
        score -= 10

    if gps_quality < 40:
        score -= 10
    elif gps_quality < 70:
        score -= 5

    return max(0, min(100, score))


def classify_node(score):
    if score >= 85:
        return "Excellent"

    if score >= 70:
        return "Good"

    if score >= 50:
        return "Warning"

    return "Critical"