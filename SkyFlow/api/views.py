import requests
import math
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import ObservationSerializer
from datetime import datetime, timedelta

# 관측 지점 목록
OBSERVATION_POINTS = [
    {"stn": 47095, "latitude": 38.14788, "longitude": 127.3042},  # 철원
    {"stn": 47099, "latitude": 37.88588, "longitude": 126.76649},  # 파주
    {"stn": 47100, "latitude": 37.08, "longitude": 128.89},       # 태백(공군)
    {"stn": 47102, "latitude": 37.97396, "longitude": 124.71241}, # 백령도
    {"stn": 47104, "latitude": 37.80456, "longitude": 128.85535}, # 북강릉
    {"stn": 47114, "latitude": 37.33756, "longitude": 127.9466},  # 원주
    {"stn": 47120, "latitude": 37.25, "longitude": 127.0},        # 수원(공군)
    {"stn": 47130, "latitude": 36.99176, "longitude": 129.41278}, # 울진
    {"stn": 47134, "latitude": 36.63, "longitude": 128.35},       # 예천(공군)
    {"stn": 47135, "latitude": 36.22023, "longitude": 127.99457}, # 추풍령
    {"stn": 47140, "latitude": 36.0053, "longitude": 126.76135},  # 군산
    {"stn": 47142, "latitude": 35.9, "longitude": 128.64},        # 대구(공군)
    {"stn": 47149, "latitude": 36.7, "longitude": 126.49},        # 서산(공군)
    {"stn": 47155, "latitude": 35.1702, "longitude": 128.57285},  # 창원
    {"stn": 47158, "latitude": 35.13, "longitude": 126.8},        # 광주(공군)
    {"stn": 47161, "latitude": 35.09, "longitude": 128.06},       # 사천(공군)
    {"stn": 47229, "latitude": 36.62542, "longitude": 125.55951}, # 북격렬비도
    {"stn": 47230, "latitude": 37.2645, "longitude": 126.10297},  # 덕적도
    {"stn": 47261, "latitude": 34.55359, "longitude": 126.56897}, # 해남
    {"stn": 47810, "latitude": 37.36, "longitude": 127.26},       # 경기광주(공군)
    {"stn": 47884, "latitude": 33.25927, "longitude": 126.5176}   # 서귀포
]

interval_time = 21600  # 6시간 간격

def find_nearest_stations(latitude, longitude):
    """
    입력받은 위도, 경도 값을 기준으로 관측소 목록을 거리순으로 정렬
    """
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371  # 지구 반지름 (km)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    return sorted(
        OBSERVATION_POINTS,
        key=lambda point: haversine(latitude, longitude, point["latitude"], point["longitude"])
    )

class WeatherPredictionView(APIView):
    def get_weather_data(self, timestamp, latitude, longitude):
        """
        가장 가까운 관측소를 기준으로 기상 데이터를 가져오고, 실패 시 다음 관측소 시도
        """
        sorted_stations = find_nearest_stations(latitude, longitude)
        for station in sorted_stations:
            stn = int(station["stn"])
            url = 'https://apihub.kma.go.kr/api/typ01/url/kma_wpf.php'
            params = {
                'tm': timestamp,
                'stn': stn,
                'mode': 'H',
                'help': 0,
                'authKey': '',  # 실제 인증키를 입력하세요
            }

            try:
                response = requests.get(url, params=params)
                print(f"Request to STN {stn}, Status Code: {response.status_code}")
                response.raise_for_status()

                data_text = response.text
                lines = data_text.splitlines()

                if len(lines) < 3 or "#7777END" in lines[1]:
                    print(f"No valid data for STN {stn}, trying next station.")
                    continue

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
            except requests.exceptions.RequestException as e:
                print(f"Error fetching data from STN {stn}: {e}")
                continue

        return None  # 모든 관측소에서 데이터를 가져오지 못한 경우

    def calculate_new_position(self, latitude, longitude, wind_speed, wind_direction, time_interval):
        """
        풍향과 풍속 데이터를 사용하여 새로운 위치를 계산
        """
        wind_direction_rad = math.radians(wind_direction)
        R = 6371.0  # 지구 반지름 (km)

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
            
            input_time = input_time.replace(minute=0)
            timestamp = int(input_time.strftime('%Y%m%d%H%M'))
            
            print("Converted timestamp:", timestamp)

            positions = {}
            total_distance_covered = 0
            target_distance = 250  # 예측하려는 총 이동 거리 (250km)

            hour_offsets = range(-1, -81, -1)

            for hour_offset in hour_offsets:
                prediction_time = input_time + timedelta(hours=hour_offset)
                timestamp_str = prediction_time.strftime('%Y%m%d%H%M')

                weather_data = self.get_weather_data(timestamp_str, latitude, longitude)
                
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
