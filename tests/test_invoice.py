import json
import os
import pytest
from decimal import Decimal
from django_scopes import scopes_disabled
from freezegun import freeze_time
from pretix.base.services.invoices import (
    generate_cancellation,
    generate_invoice,
    invoice_pdf_task,
)
from pypdf import PdfReader

from .utils import compare


def r(fname):
    with open(os.path.join(os.path.dirname(__file__) + "/results/", fname), "rb") as f:
        return f.read()


@pytest.mark.django_db
@scopes_disabled()
@freeze_time("2024-12-14 12:00:00+01:00")
def test_render_default_zugferd(event, order):
    event.settings.invoice_renderer = "modern1_zugferd"
    i = generate_invoice(order)
    invoice_pdf_task(i.pk)
    i.refresh_from_db()
    reader = PdfReader(i.file)
    xml = reader.attachments["factur-x.xml"][0]

    compare(xml, r("default.xml"), schema="FACTUR-X_EXTENDED")


@pytest.mark.django_db
@scopes_disabled()
@freeze_time("2024-12-14 12:00:00+01:00")
def test_no_zugferd_without_seller_country(event, order):
    event.settings.invoice_renderer = "modern1_zugferd"
    del event.settings.invoice_address_from_country
    i = generate_invoice(order)
    invoice_pdf_task(i.pk)
    i.refresh_from_db()
    reader = PdfReader(i.file)
    assert len(reader.attachments) == 0


@pytest.mark.django_db
@scopes_disabled()
@freeze_time("2024-12-14 12:00:00+01:00")
def test_no_zugferd_without_buyer_country(event, order):
    event.settings.invoice_renderer = "modern1_zugferd"
    ia = order.invoice_address
    ia.country = ""
    ia.save()
    i = generate_invoice(order)
    invoice_pdf_task(i.pk)
    i.refresh_from_db()
    reader = PdfReader(i.file)
    assert len(reader.attachments) == 0


@pytest.mark.django_db
@scopes_disabled()
@freeze_time("2024-12-14 12:00:00+01:00")
def test_no_zugferd_without_supported_buyer_country(event, order):
    event.settings.invoice_renderer = "modern1_zugferd"
    ia = order.invoice_address
    ia.country = "XK"
    ia.save()
    i = generate_invoice(order)
    invoice_pdf_task(i.pk)
    i.refresh_from_db()
    reader = PdfReader(i.file)
    assert len(reader.attachments) == 0


@pytest.mark.django_db
@scopes_disabled()
@freeze_time("2024-12-14 12:00:00+01:00")
def test_render_default_xrechnung(event, order):
    event.settings.invoice_renderer = "modern1_zugferd_xrechnung"
    event.settings.zugferd_seller_contact_name = "Max Muster"
    event.settings.zugferd_seller_contact_email = "buha@example.org"
    event.settings.zugferd_seller_contact_phone = "+4912345678"
    i = generate_invoice(order)
    invoice_pdf_task(i.pk)
    i.refresh_from_db()
    reader = PdfReader(i.file)
    xml = reader.attachments["factur-x.xml"][0]

    compare(xml, r("xrechnung.xml"), schema="FACTUR-X_EXTENDED")


@pytest.mark.django_db
@scopes_disabled()
@freeze_time("2024-12-14 12:00:00+01:00")
def test_tax_code_exempt(event, order, tax_rule):
    tax_rule.code = "E/VATEX-EU-79-C"
    tax_rule.rate = Decimal("0.00")
    tax_rule.save()
    op = order.positions.first()
    op._calculate_tax()
    op.save()
    event.settings.invoice_renderer = "modern1_zugferd"
    i = generate_invoice(order)
    invoice_pdf_task(i.pk)
    i.refresh_from_db()
    reader = PdfReader(i.file)
    xml = reader.attachments["factur-x.xml"][0]

    compare(xml, r("tax_code_exempt.xml"), schema="FACTUR-X_EXTENDED")


@pytest.mark.django_db
@scopes_disabled()
@freeze_time("2024-12-14 12:00:00+01:00")
def test_reverse_charge(event, order, tax_rule):
    tax_rule.custom_rules = json.dumps(
        [{"country": "DE", "address_type": "", "action": "reverse"}]
    )
    tax_rule.save()
    op = order.positions.first()
    op._calculate_tax()
    op.save()
    event.settings.invoice_renderer = "modern1_zugferd"
    i = generate_invoice(order)
    invoice_pdf_task(i.pk)
    i.refresh_from_db()
    reader = PdfReader(i.file)
    xml = reader.attachments["factur-x.xml"][0]

    compare(xml, r("tax_code_reverse_charge.xml"), schema="FACTUR-X_EXTENDED")


@pytest.mark.django_db
@scopes_disabled()
@freeze_time("2024-12-14 12:00:00+01:00")
def test_guess_tax_code(event, order, tax_rule):
    tax_rule.custom_rules = json.dumps(
        [{"country": "AU", "address_type": "", "action": "no"}]
    )
    tax_rule.code = None
    tax_rule.save()
    ia = order.invoice_address
    ia.country = "AU"
    ia.save()
    order.refresh_from_db()
    op = order.positions.first()
    op._calculate_tax()
    op.save()
    event.settings.invoice_renderer = "modern1_zugferd"
    i = generate_invoice(order)
    invoice_pdf_task(i.pk)
    i.refresh_from_db()
    reader = PdfReader(i.file)
    xml = reader.attachments["factur-x.xml"][0]

    compare(xml, r("tax_code_guess_AU.xml"), schema="FACTUR-X_EXTENDED")


@pytest.mark.django_db
@scopes_disabled()
@freeze_time("2024-12-14 12:00:00+01:00")
def test_delivery_date(event, order, tax_rule):
    event.settings.zugferd_include_delivery_date = True
    event.settings.invoice_renderer = "modern1_zugferd"
    i = generate_invoice(order)
    invoice_pdf_task(i.pk)
    i.refresh_from_db()
    reader = PdfReader(i.file)
    xml = reader.attachments["factur-x.xml"][0]

    compare(xml, r("delivery_dates.xml"), schema="FACTUR-X_EXTENDED")


@pytest.mark.django_db
@scopes_disabled()
@freeze_time("2024-12-14 12:00:00+01:00")
def test_paid(event, order, tax_rule):
    event.settings.invoice_renderer = "modern1_zugferd"
    order.payments.first().confirm()
    i = order.invoices.first()
    invoice_pdf_task(i.pk)
    i.refresh_from_db()
    reader = PdfReader(i.file)
    xml = reader.attachments["factur-x.xml"][0]

    compare(xml, r("paid.xml"), schema="FACTUR-X_EXTENDED")


@pytest.mark.django_db
@scopes_disabled()
@freeze_time("2024-12-14 12:00:00+01:00")
def test_cancellation(event, order):
    event.settings.invoice_renderer = "modern1_zugferd"
    i = generate_invoice(order)
    i2 = generate_cancellation(i)
    invoice_pdf_task(i2.pk)
    i2.refresh_from_db()
    reader = PdfReader(i2.file)
    xml = reader.attachments["factur-x.xml"][0]

    compare(xml, r("cancellation.xml"), schema="FACTUR-X_EXTENDED")
