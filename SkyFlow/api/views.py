import requests
import math
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import ObservationSerializer
from datetime import datetime

class WeatherPredictionView(APIView):
    def get_weather_data(self):
        url = 'https://apihub.kma.go.kr/api/typ01/url/upp_temp.php'
        params = {
            'tm': 202410210000,
            'stn': 0,
            'pa': 0,
            'help': 0,
            'authKey': 'Qx0aZmAYR1OdGmZgGHdTPQ',
        }

        try:
            response = requests.get(url, params=params)
            print(f"Status Code: {response.status_code}")
            print(f"Response Text: {response.text}")
            response.raise_for_status()
            
            data_text = response.text
            lines = data_text.splitlines()
            for line in lines:
                if line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 8:
                    wind_direction = float(parts[6])
                    wind_speed = float(parts[7])
                    return {
                        'wind_direction': wind_direction,
                        'wind_speed': wind_speed
                    }
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from KMA API: {e}")
            return None


    def calculate_new_position(self, latitude, longitude, wind_speed, wind_direction, time_interval):
        wind_direction_rad = math.radians(wind_direction)
        R = 6371.0 
        
        movement_factor = 0.8
        adjusted_wind_speed = wind_speed * movement_factor
        
        distance = adjusted_wind_speed * (time_interval / 3600)  # km
        
        new_latitude = latitude + (distance / R) * math.cos(wind_direction_rad)
        
        new_longitude = longitude + (distance / R) * math.sin(wind_direction_rad) / math.cos(math.radians(latitude))
        
        return new_latitude, new_longitude


    def post(self, request):
        serializer = ObservationSerializer(data=request.data)
        if serializer.is_valid():
            latitude = serializer.validated_data['latitude']
            longitude = serializer.validated_data['longitude']
            
            try:
                weather_data = self.get_weather_data()
                if weather_data:
                    try:
                        wind_speed = weather_data['wind_speed']
                        wind_direction = weather_data['wind_direction']
                        time_interval = 3600  

                        new_lat, new_lon = self.calculate_new_position(
                            latitude, longitude, wind_speed, wind_direction, time_interval
                        )

                        return Response({
                            'predicted_start_latitude': new_lat,
                            'predicted_start_longitude': new_lon,
                            'initial_latitude': latitude,
                            'initial_longitude': longitude
                        })
                    except KeyError as e:
                        print(f"Error parsing weather data: {e}")
                        return Response(
                            {"error": "Invalid data format from weather API"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
                else:
                    print("Failed to fetch weather data")
                    return Response(
                        {"error": "Failed to fetch weather data"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            except Exception as e:
                print(f"Error during weather data processing: {e}")
                return Response(
                    {"error": "An error occurred while processing weather data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
