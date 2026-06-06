def calculate_health_score(voltage, charge, gps_quality):
    score = 100

    try:
        voltage = float(voltage)
    except:
        voltage = 0

    try:
        charge = float(charge)
    except:
        charge = 0

    try:
        gps_quality = float(gps_quality)
    except:
        gps_quality = 0

    if voltage < 3800:
        score -= 40
    elif voltage < 3900:
        score -= 25
    elif voltage < 4000:
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