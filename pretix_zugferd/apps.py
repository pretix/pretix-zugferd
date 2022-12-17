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
        compatibility = "pretix>=4.13.0"

        @property
        def description(self):
            t = gettext(
                "This plugin provides an invoice renderer that annotates pretix invoices with ZUGFeRD data, "
                "a structured data format for invoices used in Germany."
            )
            t += '<div class="text text-warning">'
            t += gettext(
                "ZUGFeRD is a complicated format and the automatic conversion of invoices does not work in all possible "
                "situations. The result quality will depend on the exact settings in use such as payment providers and needs "
                "to be verified individually."
            )
            t += "</div>"
            t += '<div class="text text-warning">'
            t += gettext(
                "Note: Use this plugin at your own risk. If there is a semantic difference between the XML and PDF "
                "contents in your ZUGFeRD invoices, you might legally owe the VAT to the financial authorities twice, "
                "since you then legally sent two invoices. We tried our best to avoid this, but we do not assume "
                "any liability. Please check the output of this plugin with your tax or legal attorney before use."
            )
            t += "</div>"
            return mark_safe(t)

    def ready(self):
        from . import signals  # NOQA


