from django.conf.urls import url

from .views import (
    SettingsView
)

urlpatterns = [
    url(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/settings/zugferd/$',
        SettingsView.as_view(), name='settings'),
]
