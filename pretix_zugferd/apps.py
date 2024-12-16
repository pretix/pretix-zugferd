from django.apps import AppConfig
from django.utils.safestring import mark_safe
from django.utils.translation import gettext, gettext_lazy

from . import __version__


class PluginApp(AppConfig):
    name = "pretix_zugferd"
    verbose_name = "ZUGFeRD invoices for pretix"

    class PretixPluginMeta:
        name = gettext_lazy("ZUGFeRD invoices")
        author = "Raphael Michel"
        visible = True
        version = __version__
        category = "FEATURE"
        compatibility = "pretix>=2024.11.0.dev0"

        @property
        def description(self):
            t = gettext(
                "This plugin provides an invoice renderer that annotates pretix invoices with ZUGFeRD data, "
                "a structured data format for invoices used in Germany."
            )
            return mark_safe(t)

    def ready(self):
        from . import signals  # NOQA
