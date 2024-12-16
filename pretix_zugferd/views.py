from django import forms
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField
from pretix.base.forms import SettingsForm
from pretix.base.models import Event
from pretix.control.views.event import EventSettingsFormView, EventSettingsViewMixin

from pretix_zugferd.invoice import ZugferdMixin


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
    zugferd_hide_label = forms.BooleanField(
        label=_("Hide label that advertises the included XRechnung"),
        required=False,
    )


class SettingsView(EventSettingsViewMixin, EventSettingsFormView):
    model = Event
    form_class = ZugferdSettingsForm
    template_name = "pretix_zugferd/settings.html"
    permission = "can_change_settings"

    def get_success_url(self) -> str:
        return reverse(
            "plugins:pretix_zugferd:settings",
            kwargs={
                "organizer": self.request.event.organizer.slug,
                "event": self.request.event.slug,
            },
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            **kwargs,
            is_zugferd_renderer=isinstance(
                self.request.event.invoice_renderer, ZugferdMixin
            ),
            is_xrechnung_renderer=(
                getattr(self.request.event.invoice_renderer, "profile", None)
                == "XRECHNUNG"
            ),
            has_leitweg_id=(
                self.request.event.settings.invoice_address_custom_field.localize("de")
                and "leitweg"
                in self.request.event.settings.invoice_address_custom_field.localize(
                    "de"
                ).lower()
            ),
            tax_rules_used=not self.request.event.tax_rules.exists()
            or not self.request.event.items.filter(tax_rule__isnull=True).exists(),
            tax_codes_used=not self.request.event.tax_rules.filter(
                code__isnull=True
            ).exists(),
        )
