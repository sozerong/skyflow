# serializers.py
from rest_framework import serializers

class ObservationSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    direction = serializers.ChoiceField(choices=["past", "future"])
    time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')  # 시간 필드 추가
