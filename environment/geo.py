from math import asin, cos, radians, sin, sqrt


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em km entre dois pontos (fórmula de Haversine)."""
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 2 * r * asin(sqrt(a))


def estimate_travel_hours(distance_km: float) -> float:
    """Estimativa simples: 80 km/h média em auto/ônibus de equipa."""
    if distance_km < 50:
        return distance_km / 60.0
    return distance_km / 80.0