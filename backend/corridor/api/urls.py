from django.urls import path, re_path

from corridor.api import views

app_name = "api"

urlpatterns = [
    path("plans", views.PlanView.as_view(), name="plans"),
    re_path(r"^plans/(?P<plan_id>[0-9a-f]{16})$", views.PlanSnapshotView.as_view(), name="plan"),
    path("geocode", views.GeocodeView.as_view(), name="geocode"),
    path("reverse", views.ReverseGeocodeView.as_view(), name="reverse"),
    path("timezone", views.TimezoneView.as_view(), name="timezone"),
    path("health", views.HealthView.as_view(), name="health"),
]
