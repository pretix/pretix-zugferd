from django.dispatch import receiver
from django.urls import resolve, reverse
from pretix.base.settings import settings_hierarkey
from pretix.base.signals import build_invoice_data, register_invoice_renderers
from pretix.control.signals import nav_event_settings


@receiver(register_invoice_renderers, dispatch_uid="classic_zugferd_invoice_renderer")
def register_1(sender, **kwargs):
    from .invoice import ZugferdInvoiceRenderer

    return ZugferdInvoiceRenderer


@receiver(register_invoice_renderers, dispatch_uid="modern1_zugferd_invoice_renderer")
def register_2(sender, **kwargs):
    from .invoice import Modern1ZugferdInvoiceRenderer

    return Modern1ZugferdInvoiceRenderer


@receiver(
    register_invoice_renderers,
    dispatch_uid="modern1_zugferd_xrechnung_invoice_renderer",
)
def register_3(sender, **kwargs):
    from .invoice import Modern1ZugferdXRechnungInvoiceRenderer

    return Modern1ZugferdXRechnungInvoiceRenderer


@receiver(nav_event_settings, dispatch_uid="zugferd_nav")
def navbar_info(sender, request, **kwargs):
    url = resolve(request.path_info)
    if not request.user.has_event_permission(
        request.organizer, request.event, "can_change_event_settings", request=request
    ):
        return []
    return [
        {
            "label": "ZUGFeRD",
            "url": reverse(
                "plugins:pretix_zugferd:settings",
                kwargs={
                    "event": request.event.slug,
                    "organizer": request.organizer.slug,
                },
            ),
            "active": url.namespace == "plugins:pretix_zugferd",
        }
    ]


@receiver(build_invoice_data, dispatch_uid="zugferd_build_invoice_data")
def recv_build_invoice_data(sender, invoice, **kwargs):
    invoice.plugin_data["zugferd"] = {
        "seller_contact_name": sender.settings.zugferd_seller_contact_name,
        "seller_contact_email": (
            sender.settings.zugferd_seller_contact_email
            or invoice.event.settings.contact_mail
        ),
        "seller_contact_phone": sender.settings.zugferd_seller_contact_phone,
    }
    invoice.save(update_fields=["plugin_data"])


settings_hierarkey.add_default("zugferd_hide_label", "True", default_type=bool)
