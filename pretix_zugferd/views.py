from django import forms
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField

from pretix.base.forms import SettingsForm
from pretix.base.models import Event
from pretix.control.views.event import EventSettingsFormView, EventSettingsViewMixin


class ZugferdSettingsForm(SettingsForm):
    zugferd_seller_contact_name = forms.CharField(
        label=_("Seller contact name"),
        help_text=_("Required for a valid XRechnung"),
        required=False,
    )
    zugferd_seller_contact_email = forms.EmailField(
        label=_("Seller contact email"),
        help_text=_("Required for a valid XRechnung"),
        required=False,
    )
    zugferd_seller_contact_phone = PhoneNumberField(
        label=_("Seller contact phone number"),
        help_text=_("Required for a valid XRechnung"),
        required=False,
        empty_value=None,
    )
    zugferd_include_delivery_date = forms.BooleanField(
        label=_("Include event date as delivery date"),
        required=False,
    )


class SettingsView(EventSettingsViewMixin, EventSettingsFormView):
    model = Event
    form_class = ZugferdSettingsForm
    template_name = 'pretix_zugferd/settings.html'
    permission = 'can_change_settings'

    def get_success_url(self) -> str:
        return reverse('plugins:pretix_zugferd:settings', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })
