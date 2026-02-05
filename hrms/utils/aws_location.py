"""AWS Location Service wrapper for Grab Maps integration"""

import frappe
import boto3
from typing import Optional, Dict, Any

class AWSLocationService:
    """Wrapper for AWS Location Service with Grab Maps"""

    def __init__(self, region: str = 'ap-southeast-1'):
        """Initialize AWS Location Service client

        Args:
            region: AWS region (default: ap-southeast-1 for Southeast Asia)
        """
        self.region = region
        self.client = boto3.client('location', region_name=region)

        # Use existing resources
        self.place_index = 'explore.place.Grab'
        self.geofence_collection = 'explore.geofence-collection'
        self.route_calculator = 'explore.route-calculator.Grab'

    def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
        max_results: int = 1
    ) -> Optional[str]:
        """Convert lat/lng to human-readable address

        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            max_results: Maximum number of results (default: 1)

        Returns:
            Formatted address string or None if not found
        """
        try:
            response = self.client.search_place_index_for_position(
                IndexName=self.place_index,
                Position=[longitude, latitude],  # Note: lon, lat order
                MaxResults=max_results
            )

            if response.get('Results'):
                return response['Results'][0]['Place']['Label']

            return None

        except Exception as e:
            frappe.log_error(
                title="AWS Location Reverse Geocode Error",
                message=f"Error: {str(e)}\nLat: {latitude}, Lng: {longitude}"
            )
            return None

    def calculate_distance(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str = 'Car'
    ) -> Optional[Dict[str, Any]]:
        """Calculate distance and time between two points

        Args:
            origin_lat: Origin latitude
            origin_lng: Origin longitude
            dest_lat: Destination latitude
            dest_lng: Destination longitude
            travel_mode: Travel mode (default: Car)

        Returns:
            Dict with distance_km, duration_minutes, duration_seconds
        """
        try:
            response = self.client.calculate_route(
                CalculatorName=self.route_calculator,
                DeparturePosition=[origin_lng, origin_lat],
                DestinationPosition=[dest_lng, dest_lat],
                TravelMode=travel_mode,
                DistanceUnit='Kilometers'
            )

            summary = response['Summary']
            return {
                'distance_km': summary['Distance'],
                'duration_minutes': summary['DurationSeconds'] / 60,
                'duration_seconds': summary['DurationSeconds']
            }

        except Exception as e:
            frappe.log_error(
                title="AWS Location Distance Calculation Error",
                message=f"Error: {str(e)}"
            )
            return None

    def find_nearest_ob_location(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[Dict[str, Any]]:
        """Find nearest known OB location

        Args:
            latitude: Current latitude
            longitude: Current longitude

        Returns:
            Dict with location name, distance, within_geofence
        """
        from hrms.utils.geo import calculate_haversine_distance

        # Get all active OB locations
        locations = frappe.get_all(
            "BEI OB Location",
            filters={"is_active": 1},
            fields=["name", "location_name", "latitude", "longitude", "checkin_radius"]
        )

        if not locations:
            return None

        # Find nearest
        nearest = None
        min_distance = float('inf')

        for loc in locations:
            distance = calculate_haversine_distance(
                loc['latitude'], loc['longitude'],
                latitude, longitude
            )

            if distance < min_distance:
                min_distance = distance
                nearest = loc

        if nearest:
            return {
                'location_name': nearest['location_name'],
                'location_id': nearest['name'],
                'distance_meters': min_distance,
                'within_geofence': min_distance <= nearest['checkin_radius']
            }

        return None
