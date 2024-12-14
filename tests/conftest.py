import pytest
from datetime import datetime
from decimal import Decimal
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString
from pretix.base.models import (
    Event,
    InvoiceAddress,
    Order,
    OrderPayment,
    OrderPosition,
    Organizer,
)
from pytz import UTC


@pytest.fixture
def organizer():
    return Organizer.objects.create(name="Dummy", slug="dummy")


@pytest.fixture
@scopes_disabled()
def event(organizer):
    e = Event.objects.create(
        organizer=organizer,
        name="Dummy",
        slug="dummy",
        date_from=datetime(2017, 12, 27, 10, 0, 0, tzinfo=UTC),
        plugins="pretix.plugins.banktransfer,pretix_zugferd",
        is_public=True,
    )
    e.settings.locales = ["en", "de"]
    e.settings.payment_banktransfer__enabled = True
    e.settings.payment_banktransfer_bank_details_type = "sepa"
    e.settings.payment_banktransfer_bank_details_sepa_name = "Musterfirma"
    e.settings.payment_banktransfer_bank_details_sepa_iban = "DE1234567890"
    e.settings.payment_banktransfer_bank_details_sepa_bic = "GENODEMDEMO"
    e.settings.payment_banktransfer_bank_details_sepa_bank = "Musterbank"
    e.settings.invoice_address_asked = True
    e.settings.invoice_address_required = True
    e.settings.invoice_address_vatid = True
    e.settings.invoice_address_custom_field = LazyI18nString({"de": "Leitweg-ID"})
    e.settings.invoice_generate = "paid"
    e.settings.invoice_address_from_name = "Musterfirma"
    e.settings.invoice_address_from = "Baker Street 221B"
    e.settings.invoice_address_from_zipcode = "12345"
    e.settings.invoice_address_from_city = "Berlin"
    e.settings.invoice_address_from_country = "DE"
    e.settings.invoice_address_from_tax_id = "123/456/789"
    e.settings.invoice_address_from_vat_id = "DE123456789"
    e.settings.invoice_introductory_text = "Intro-Text"
    e.settings.invoice_additional_text = "Additional Text"
    e.settings.invoice_footer_text = "Footer-Text"
    return e


@pytest.fixture
@scopes_disabled()
def tax_rule(event):
    return event.tax_rules.create(
        rate=Decimal("19.00"),
        code="S",
    )


@pytest.fixture
@scopes_disabled()
def item(event, tax_rule):
    return event.items.create(
        name="Ticket",
        default_price=Decimal("100.00"),
        tax_rule=tax_rule,
    )


@pytest.fixture
@scopes_disabled()
def order(event, organizer, item):
    o = Order.objects.create(
        code="FOO",
        event=event,
        email="dummy@dummy.test",
        status=Order.STATUS_PENDING,
        testmode=False,
        secret="k24fiuwvu8kxz3y1",
        sales_channel=event.organizer.sales_channels.get(identifier="web"),
        datetime=datetime(2024, 12, 1, 10, 0, 0, tzinfo=UTC),
        expires=datetime(2024, 12, 10, 10, 0, 0, tzinfo=UTC),
        total=Decimal("100.00"),
        locale="en",
    )
    OrderPosition.objects.create(
        order=o,
        item=item,
        variation=None,
        price=Decimal("23"),
        attendee_name_parts={"_legacy": "Peter"},
        secret="z3fsn8jyufm5kpk768q69gkbyr5f4h6w",
        pseudonymization_id="ABCDEFGHKL",
    )
    InvoiceAddress.objects.create(
        order=o,
        company="Kundenfirma",
        name_parts={"_legacy": "Peter"},
        street="Sesamstraße 123",
        zipcode="54321",
        city="Bielefeld",
        country="DE",
        custom_field="9123-1234561-23",
        internal_reference="PO-12345",
        vat_id="DE987654321",
        vat_id_validated=True,
    )
    o.payments.create(
        state=OrderPayment.PAYMENT_STATE_CREATED,
        provider="banktransfer",
        amount=o.total,
    )
    return o
