from django.urls import path
from .views import WeatherPredictionView

urlpatterns = [
    path('predict/', WeatherPredictionView.as_view(), name='predict'),
]
