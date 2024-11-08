import requests
import math
import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import ObservationSerializer
from datetime import datetime, timedelta

interval_time = 7200
interval_hour = 2
class WeatherPredictionView(APIView):
    def get_weather_data(self, timestamp):
        url = 'https://apihub.kma.go.kr/api/typ01/url/upp_temp.php'
        params = {
            'tm': timestamp,
            'stn': 0,
            'pa': 0,
            'help': 0,
            'authKey': '',
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
        
        distance = adjusted_wind_speed * (time_interval / interval_time)  # km
        
        new_latitude = latitude + (distance / R) * math.cos(wind_direction_rad)
        new_longitude = longitude + (distance / R) * math.sin(wind_direction_rad) / math.cos(math.radians(latitude))
        
        return new_latitude, new_longitude

    def post(self, request):
        serializer = ObservationSerializer(data=request.data)
        if serializer.is_valid():
            latitude = serializer.validated_data['latitude']
            longitude = serializer.validated_data['longitude']
            direction = serializer.validated_data['direction']
            
            positions = {}
            current_time = datetime.now()
            total_distance_covered = 0
            target_distance = 250  # 북한에서 남한까지의 거리 (약 250 km)

            # 하루 단위의 바람 데이터 한 번만 가져오기
            timestamp_str = current_time.strftime('%Y%m%d') + '0000'
            timestamp = int(timestamp_str)
            weather_data = self.get_weather_data(timestamp)

            if weather_data:
                wind_speed = weather_data['wind_speed']
                wind_direction = weather_data['wind_direction']

                # 예측 범위 설정
                if direction == "-1":
                    hour_offsets = range(-6, 1)  # 과거 6시간
                else:
                    hour_offsets = range(1, 7)  # 미래 6시간

                for hour_offset in hour_offsets:
                    time_interval = abs(hour_offset) * interval_time  # 1시간 간격 (3600초)

                    # 위치 계산
                    new_lat, new_lon = self.calculate_new_position(
                        latitude, longitude, wind_speed, wind_direction, time_interval
                    )

                    # 위치와 누적 이동 거리 저장
                    prediction_time = (current_time + timedelta(hours=hour_offset*interval_hour)).strftime('%Y-%m-%d %H:%M:%S')
                    total_distance_covered += wind_speed * 0.8 * (time_interval / interval_time)  # 누적 이동 거리 계산

                    positions[hour_offset] = {
                        'prediction_time': prediction_time,
                        'latitude': new_lat,
                        'longitude': new_lon,
                        'cumulative_distance': total_distance_covered
                    }

                    # 목표 거리 도달 여부 확인
                    if total_distance_covered >= target_distance:
                        positions['arrival_time'] = prediction_time
                        break

                return Response(positions, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Failed to fetch weather data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
