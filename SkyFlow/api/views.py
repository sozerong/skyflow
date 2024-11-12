import requests
import math
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import ObservationSerializer
from datetime import datetime, timedelta

interval_time = 7200 
interval_hour = 2

class WeatherPredictionView(APIView):
    def get_weather_data(self, timestamp):
        url = 'https://apihub.kma.go.kr/api/typ01/url/kma_wpf.php'
        params = {
            'tm': timestamp,
            'stn': 0,
            'mode': 'H',
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

            # 유효한 데이터가 있는지 확인
            if len(lines) < 3 or "#7777END" in lines[1]:
                print("No valid weather data found in the response.")
                return None

            for line in lines:
                if line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 8:
                    wind_direction = float(parts[6])  # WD
                    wind_speed = float(parts[7])      # WS
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

        movement_factor = 0.95
        adjusted_wind_speed = wind_speed * movement_factor
        
        distance = adjusted_wind_speed * (time_interval / 3600)  # km
        
        new_latitude = latitude - (distance / R) * math.cos(wind_direction_rad)
        new_longitude = longitude - (distance / R) * math.sin(wind_direction_rad) / math.cos(math.radians(latitude))
        
        return new_latitude, new_longitude

    def post(self, request):
        serializer = ObservationSerializer(data=request.data)
        if serializer.is_valid():
            latitude = serializer.validated_data['latitude']
            longitude = serializer.validated_data['longitude']
            input_time = serializer.validated_data['time']
            direction = serializer.validated_data['direction']
            
            # 받은 datetime 객체의 분을 00으로 설정
            input_time = input_time.replace(minute=0)
            
            # 수정된 시간을 YYYYMMDDHHMM 형식의 정수로 변환
            timestamp = int(input_time.strftime('%Y%m%d%H%M'))
            
            print("Converted timestamp:", timestamp)  # 디버그용 출력

            positions = {}
            total_distance_covered = 0
            target_distance = 250  # 예측하려는 총 이동 거리 (예: 250 km)

            # 과거로 시간 이동하며 데이터를 반복 호출하여 출발지 예측
            hour_offsets = range(-1, -121, -1)  

            for hour_offset in hour_offsets:
                prediction_time = input_time + timedelta(hours=hour_offset)
                timestamp_str = prediction_time.strftime('%Y%m%d%H%M')

                # 바람 데이터 호출
                weather_data = self.get_weather_data(timestamp_str)
                
                if weather_data:
                    wind_speed = weather_data['wind_speed']
                    wind_direction = weather_data['wind_direction']

                    time_interval = abs(hour_offset) * interval_time
                    new_lat, new_lon = self.calculate_new_position(
                        latitude, longitude, wind_speed, wind_direction, time_interval
                    )

                    total_distance_covered += wind_speed * 0.8 * (time_interval / interval_time)
                    positions[hour_offset] = {
                        'prediction_time': prediction_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'latitude': new_lat,
                        'longitude': new_lon,
                        'cumulative_distance': total_distance_covered
                    }

                    # 다음 위치 계산을 위해 좌표 업데이트
                    latitude, longitude = new_lat, new_lon

                    if total_distance_covered >= target_distance:
                        positions['departure_time'] = prediction_time.strftime('%Y-%m-%d %H:%M:%S')
                        break
                else:
                    positions[hour_offset] = {"error": "Failed to fetch weather data"}
                    break

            return Response(positions, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
