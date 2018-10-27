from django.dispatch import receiver

from pretix.base.signals import register_invoice_renderers


@receiver(register_invoice_renderers, dispatch_uid="classic_zugferd_invoice_renderer")
def register_infoice_renderers(sender, **kwargs):
    from .invoice import ZugferdInvoiceRenderer
    return ZugferdInvoiceRenderer
