from django.urls import path

from corridor.api import views

app_name = "api"

urlpatterns = [
    path("plans", views.PlanView.as_view(), name="plans"),
    path("geocode", views.GeocodeView.as_view(), name="geocode"),
    path("reverse", views.ReverseGeocodeView.as_view(), name="reverse"),
    path("health", views.HealthView.as_view(), name="health"),
]
