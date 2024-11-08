# serializers.py
from rest_framework import serializers

class ObservationSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    direction = serializers.ChoiceField(choices=["-1", "1"])
