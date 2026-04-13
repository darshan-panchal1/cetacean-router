import math
from typing import List, Tuple
from shapely.geometry import LineString
from shapely import wkt as shapely_wkt

__all__ = [
    "haversine_distance",
    "calculate_route_distance",
    "create_route_buffer",
    "point_in_sector",
    "interpolate_waypoint",
    "calculate_bearing",
]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    '''
    Calculate the great circle distance between two points on Earth.
    Returns distance in nautical miles.
    '''
    # Radius of Earth in nautical miles
    R = 3440.065
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def calculate_route_distance(waypoints: List[Tuple[float, float]]) -> float:
    '''Calculate total distance for a route with multiple waypoints.'''
    total_distance = 0.0
    for i in range(len(waypoints) - 1):
        lat1, lon1 = waypoints[i]
        lat2, lon2 = waypoints[i + 1]
        total_distance += haversine_distance(lat1, lon1, lat2, lon2)
    return total_distance


def create_route_buffer(waypoints: List[Tuple[float, float]],
                        buffer_degrees: float = 0.5) -> str:
    '''
    Create a buffered polygon around a route for risk assessment.
    Returns WKT string.
    '''
    if len(waypoints) < 2:
        # Fallback: small bounding box around single point
        lat, lon = waypoints[0]
        b = buffer_degrees
        return (
            f"POLYGON(({lon-b} {lat-b}, {lon+b} {lat-b}, "
            f"{lon+b} {lat+b}, {lon-b} {lat+b}, {lon-b} {lat-b}))"
        )
    line = LineString([(lon, lat) for lat, lon in waypoints])
    buffered = line.buffer(buffer_degrees)
    return buffered.wkt


def point_in_sector(point: Tuple[float, float],
                    sector_bounds: dict) -> bool:
    '''Check if a point is within a sector boundary.'''
    lat, lon = point
    return (sector_bounds['lat_min'] <= lat <= sector_bounds['lat_max'] and
            sector_bounds['lon_min'] <= lon <= sector_bounds['lon_max'])


def interpolate_waypoint(start: Tuple[float, float],
                         end: Tuple[float, float],
                         fraction: float) -> Tuple[float, float]:
    '''Interpolate a point between start and end.'''
    lat = start[0] + (end[0] - start[0]) * fraction
    lon = start[1] + (end[1] - start[1]) * fraction
    return (lat, lon)


def calculate_bearing(lat1: float, lon1: float,
                      lat2: float, lon2: float) -> float:
    '''Calculate bearing from point 1 to point 2 in degrees.'''
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    x = math.sin(delta_lon) * math.cos(lat2_rad)
    y = (math.cos(lat1_rad) * math.sin(lat2_rad) -
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360