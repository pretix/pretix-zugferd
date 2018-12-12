from django.apps import AppConfig
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext, ugettext_lazy


class PluginApp(AppConfig):
    name = 'pretix_zugferd'
    verbose_name = 'ZUGFeRD invoices for pretix'

    class PretixPluginMeta:
        name = ugettext_lazy('ZUGFeRD invoices for pretix')
        author = 'Raphael Michel'
        visible = True
        version = '1.0.0'

        @property
        def description(self):
            t = ugettext('This plugin provides an invoice renderer that annotates pretix invoices with ZUGFeRD data, '
                         'a structured data format for invoices used in Germany.')
            t += '<div class="alert alert-legal">'
            t += ugettext(
                'Note: Use this plugin at your own risk. If there is a semantic difference between the XML and PDF '
                'contents in your ZUGFeRD invoices, you might legally owe the VAT to the financial authorities twice, '
                'since you then legally sent two invoices. We tried our best to avoid this, but we do not assume '
                'any liability. Please check the output of this plugin with your tax or legal attorney before use.'
            )
            t += '</div>'
            return mark_safe(t)

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'pretix_zugferd.PluginApp'
