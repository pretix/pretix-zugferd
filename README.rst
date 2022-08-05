ZUGFeRD invoices for pretix
===========================

This is a plugin for `pretix`_. It allows you to attach ZUGFeRD information to your invoices.

**PLEASE NOTE:** Use this plugin at your own risk. If there is a semantic difference between the XML and PDF contents in
your ZUGFeRD invoices, you might legally owe the VAT to the financial authorities **twice**, since you then generated two
invoices. We tried our best to avoid this, but we do not assume any liability. Please check the output of this plugin
with your tax or legal attorney before use.

Installation note
-----------------

This plugin requires ``ghostscript`` to be installed. If you have it installed in a nonstandard location, you can
specify it in your ``pretix.cfg``::

    [tools]
    gs=/usr/local/bin/gs


Development setup
-----------------

1. Make sure that you have a working `pretix development setup`_.

2. Clone this repository, eg to ``local/pretix-zugferd``.

3. Activate the virtual environment you use for pretix development.

4. Execute ``python setup.py develop`` within this directory to register this application with pretix's plugin registry.

5. Execute ``make`` within this directory to compile translations.

6. Restart your local pretix server. You can now use the plugin from this repository for your events by enabling it in
   the 'plugins' tab in the settings.


License
-------

Copyright 2018-2022 rami.io GmbH

Released under the terms of the Apache License 2.0


.. _pretix: https://github.com/pretix/pretix
.. _pretix development setup: https://docs.pretix.eu/en/latest/development/setup.html
