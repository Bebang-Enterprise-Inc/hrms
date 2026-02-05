"""Geographic utility functions for distance calculations"""

from math import radians, cos, sin, asin, sqrt


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates using Haversine formula

    Args:
        lat1: Latitude of first point (degrees)
        lon1: Longitude of first point (degrees)
        lat2: Latitude of second point (degrees)
        lon2: Longitude of second point (degrees)

    Returns:
        float: Distance in meters

    Example:
        >>> # Manila to Quezon City (~12km)
        >>> distance = calculate_haversine_distance(14.5995, 120.9842, 14.6760, 121.0437)
        >>> print(f"{distance/1000:.1f} km")
        12.4 km
    """
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    # Earth radius in meters
    r = 6371000

    return c * r
