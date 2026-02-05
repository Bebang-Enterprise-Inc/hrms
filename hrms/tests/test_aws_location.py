import unittest
from unittest.mock import patch, MagicMock
from hrms.utils.aws_location import AWSLocationService

class TestAWSLocationService(unittest.TestCase):

    def setUp(self):
        self.service = AWSLocationService()

    @patch('boto3.client')
    def test_reverse_geocode_success(self, mock_boto_client):
        """Test reverse geocoding returns address"""
        # Mock AWS response
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.search_place_index_for_position.return_value = {
            'Results': [{
                'Place': {
                    'Label': 'SM Megamall, Ortigas Center, Pasig City'
                }
            }]
        }

        # Test
        service = AWSLocationService()
        address = service.reverse_geocode(14.5858, 121.0594)

        # Assert
        self.assertEqual(address, 'SM Megamall, Ortigas Center, Pasig City')
        mock_client.search_place_index_for_position.assert_called_once_with(
            IndexName='explore.place.Grab',
            Position=[121.0594, 14.5858],
            MaxResults=1
        )

    @patch('boto3.client')
    def test_reverse_geocode_no_results(self, mock_boto_client):
        """Test reverse geocoding with no results"""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.search_place_index_for_position.return_value = {
            'Results': []
        }

        service = AWSLocationService()
        address = service.reverse_geocode(0.0, 0.0)

        self.assertIsNone(address)
