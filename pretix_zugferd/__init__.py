from django.apps import AppConfig
from django.utils.translation import ugettext_lazy


class PluginApp(AppConfig):
    name = 'pretix_zugferd'
    verbose_name = 'ZUGFeRD invoices for pretix'

    class PretixPluginMeta:
        name = ugettext_lazy('ZUGFeRD invoices for pretix')
        author = 'Raphael Michel'
        description = ugettext_lazy('Invoice renderer that annotates pretix invoices with ZUGFeRD data')
        visible = True
        version = '1.0.0'

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'pretix_zugferd.PluginApp'
