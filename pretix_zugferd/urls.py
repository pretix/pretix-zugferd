from django.urls import path

from .views import (
    SettingsView
)

urlpatterns = [
    path('control/event/<str:organizer>/<str:event>/settings/zugferd/',
        SettingsView.as_view(), name='settings'),
]
