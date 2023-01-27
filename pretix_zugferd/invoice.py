import bleach
import logging
import os
import subprocess
import tempfile
import unicodedata
from collections import defaultdict
from decimal import Decimal
from django.conf import settings
from django.contrib.staticfiles import finders
from django.utils.functional import lazy
from django.utils.translation import gettext as _, pgettext
from drafthorse.models.accounting import ApplicableTradeTax
from drafthorse.models.document import Document
from drafthorse.models.note import IncludedNote
from drafthorse.models.party import TaxRegistration
from drafthorse.models.payment import PaymentTerms
from drafthorse.models.references import AdditionalReferencedDocument
from drafthorse.models.tradelines import LineItem
from drafthorse.pdf import attach_xml
from pretix.base.invoice import ClassicInvoiceRenderer, Modern1Renderer
from pretix.base.models.tax import EU_COUNTRIES

logger = logging.getLogger(__name__)


def remove_control_characters(s):
    if s is None:
        return None
    return "".join(
        ch for ch in str(s) if unicodedata.category(ch)[0] != "C" or ch == "\n"
    )


class ZugferdMixin:
    profile = "EXTENDED"
    schema = "EXTENDED"
    guideline_id = "urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended"

    def _zugferd_generate_document(self, invoice):
        cc = invoice.event.currency
        doc = Document()
        if self.profile == "EXTENDED":
            doc.context.test_indicator = invoice.invoice_no == "PREVIEW"
            doc.header.name = "RECHNUNG"
            doc.header.languages.add(invoice.locale[:2])
        doc.context.guideline_parameter.id = self.guideline_id
        doc.header.id = invoice.number
        doc.header.type_code = "380"
        doc.header.issue_date_time = invoice.date
        # ITEMS
        taxvalue_map = defaultdict(Decimal)
        grossvalue_map = defaultdict(Decimal)
        total = Decimal("0.00")
        for line in invoice.lines.all():
            factor = -1 if line.gross_value < 0 else 1
            li = LineItem()
            exemption_reason = None
            if line.tax_rate == Decimal("0.00"):
                if invoice.reverse_charge:
                    category = "AE"  # Reverse charge
                elif str(invoice.invoice_from_country) in EU_COUNTRIES and str(invoice.invoice_to_country) not in EU_COUNTRIES:
                    category = "O"  # Services outside scope of tax
                else:
                    # We don't know with pretix' information whether this is Z ("zero-rated goods"), E ("exempt from tax")
                    # or something else. Let's assume E and refer to the notes.
                    category = "E"
                    exemption_reason = pgettext("zugferd", "See invoice notes for more information")
            else:
                category = "S"  # Standard rate
            li.document.line_id = str(line.position + 1)
            desc = remove_control_characters(
                bleach.clean(line.description.replace("<br />", "\n"), tags=[])
            )
            li.product.name = desc.split("\n")[0]
            li.product.description = desc
            li.agreement.gross.amount = (
                (line.net_value * factor).quantize(Decimal("0.0001"))
            )
            li.agreement.gross.basis_quantity = (Decimal("1.0000") * factor, "C62")
            li.agreement.net.amount = (
                (line.net_value * factor).quantize(Decimal("0.0001"))
            )
            li.agreement.net.basis_quantity = (Decimal("1.0000") * factor, "C62")
            li.delivery.billed_quantity = (Decimal("1.0000") * factor, "C62")
            li.settlement.trade_tax.type_code = "VAT"
            li.settlement.trade_tax.category_code = category
            li.settlement.trade_tax.rate_applicable_percent = line.tax_rate
            if exemption_reason:
                li.settlement.trade_tax.exemption_reason = exemption_reason
            li.settlement.monetary_summation.total_amount = (
                line.net_value * factor
            )
            doc.trade.items.add(li)
            taxvalue_map[line.tax_rate, category, exemption_reason] += line.tax_value
            grossvalue_map[line.tax_rate, category, exemption_reason] += line.gross_value
            total += line.gross_value

        doc.trade.agreement.seller.name = remove_control_characters(
            invoice.invoice_from_name
        )
        lines = remove_control_characters(invoice.invoice_from.strip()).split("\n")
        doc.trade.agreement.seller.address.postcode = remove_control_characters(
            invoice.invoice_from_zipcode
        )
        doc.trade.agreement.seller.address.line_one = lines[0].strip()
        if len(lines) > 1:
            doc.trade.agreement.seller.address.line_two = ", ".join(lines[1:]).strip()
        doc.trade.agreement.seller.address.city_name = remove_control_characters(
            invoice.invoice_from_city
        )
        doc.trade.agreement.seller.address.country_id = str(
            remove_control_characters(invoice.invoice_from_country)
        )

        if invoice.invoice_from_tax_id:
            doc.trade.agreement.seller.tax_registrations.add(
                TaxRegistration(
                    id=("FC", remove_control_characters(invoice.invoice_from_tax_id))
                )
            )

        if invoice.invoice_from_vat_id:
            doc.trade.agreement.seller.tax_registrations.add(
                TaxRegistration(
                    id=("VA", remove_control_characters(invoice.invoice_from_vat_id))
                )
            )

        if invoice.event.settings.zugferd_seller_contact_name:
            doc.trade.agreement.seller.contact.person_name = invoice.event.settings.zugferd_seller_contact_name
        if invoice.event.settings.zugferd_seller_contact_email:
            doc.trade.agreement.seller.contact.email.address = invoice.event.settings.zugferd_seller_contact_email
        if invoice.event.settings.zugferd_seller_contact_phone:
            doc.trade.agreement.seller.contact.telephone.number = invoice.event.settings.zugferd_seller_contact_phone

        doc.trade.agreement.buyer.name = remove_control_characters(
            invoice.invoice_to_company or invoice.invoice_to_name
        )
        doc.trade.agreement.buyer.address.postcode = remove_control_characters(
            invoice.invoice_to_zipcode
        )
        if invoice.invoice_to_company and invoice.invoice_to_name:
            doc.trade.agreement.buyer.address.line_one = remove_control_characters(
                invoice.invoice_to_name
            )
            doc.trade.agreement.buyer.address.line_two = remove_control_characters(
                invoice.invoice_to_street
            )
        else:
            doc.trade.agreement.buyer.address.line_one = remove_control_characters(
                invoice.invoice_to_street
            )
        doc.trade.agreement.buyer.address.city_name = remove_control_characters(
            invoice.invoice_to_city
        )
        doc.trade.agreement.buyer.address.country_id = remove_control_characters(
            str(invoice.invoice_to_country)
        )

        if invoice.invoice_to_vat_id:
            doc.trade.agreement.buyer.tax_registrations.add(
                TaxRegistration(
                    id=("VA", remove_control_characters(invoice.invoice_to_vat_id))
                )
            )

        if invoice.event.settings.get("zugferd_include_delivery_date", as_type=bool):
            ds = [l.event_date_to or l.event_date_from for l in invoice.lines.all() if l.event_date_to or l.event_date_from]
            if ds:
                doc.trade.delivery.event.occurrence = max(ds)

        note = IncludedNote()
        note.content.add(_("Order code: {code}").format(code=invoice.order.full_code))
        doc.header.notes.add(note)

        if not invoice.event.has_subevents:
            if invoice.event.settings.show_date_to and invoice.event.date_to:
                p_str = remove_control_characters(
                    str(invoice.event.name)
                    + " - "
                    + pgettext("invoice", "{from_date}\nuntil {to_date}").format(
                        from_date=invoice.event.get_date_from_display(),
                        to_date=invoice.event.get_date_to_display(),
                    )
                )
            else:
                p_str = remove_control_characters(
                    str(invoice.event.name)
                    + " - "
                    + invoice.event.get_date_from_display()
                )
        else:
            p_str = remove_control_characters(str(invoice.event.name))
        note = IncludedNote()
        note.content.add(p_str)
        doc.header.notes.add(note)

        if invoice.internal_reference:
            note = IncludedNote()
            note.content.add(
                pgettext("invoice", "Customer reference: {reference}").format(
                    reference=remove_control_characters(invoice.internal_reference)
                )
            )
            doc.header.notes.add(note)

        if invoice.introductory_text:
            note = IncludedNote()
            note.content.add(remove_control_characters(invoice.introductory_text.replace("<br />", " / ")))
            doc.header.notes.add(note)

        if invoice.additional_text:
            note = IncludedNote()
            note.content.add(remove_control_characters(invoice.additional_text.replace("<br />", " / ")))
            doc.header.notes.add(note)

        if invoice.footer_text:
            note = IncludedNote()
            note.content.add(remove_control_characters(invoice.footer_text.replace("<br />", " / ")))
            doc.header.notes.add(note)

        pt = PaymentTerms()
        pt.description = remove_control_characters(invoice.payment_provider_text.replace("<br />", " / "))
        pt.due = invoice.order.expires

        lp = invoice.order.payments.exclude(provider__in=("giftcard", "offsetting", "free", "manual", "boxoffice")).order_by('local_id').last()
        print(lp)
        if lp and lp.provider == "banktransfer":
            if invoice.event.settings.payment_banktransfer_bank_details_type == 'sepa':
                doc.trade.settlement.payment_means.type_code = "30"
                doc.trade.settlement.payment_means.payee_account.iban = invoice.event.settings.payment_banktransfer_bank_details_sepa_iban
                doc.trade.settlement.payment_means.payee_institution.bic = invoice.event.settings.payment_banktransfer_bank_details_sepa_bic

            else:
                doc.trade.settlement.payment_means.type_code = "58"
        elif lp and lp.provider == "sepadebit":
            doc.trade.settlement.payment_means.type_code = "59"
            doc.trade.settlement.payment_means.payer_account.iban = lp.info_data.get("iban")
            doc.trade.settlement.creditor_reference_id = invoice.event.settings.payment_sepadebit_creditor_id
            pt.debit_mandate_id = lp.info_data.get("reference")
        else:
            doc.trade.settlement.payment_means.type_code = "ZZZ"

        doc.trade.settlement.payment_reference = invoice.order.full_code
        doc.trade.settlement.currency_code = cc
        if invoice.payment_provider_text:
            doc.trade.settlement.payment_means.information.add(
                remove_control_characters(invoice.payment_provider_text.replace("<br />", " / "))
            )
        doc.trade.settlement.terms.add(pt)

        if invoice.is_cancellation:
            ref = AdditionalReferencedDocument()
            ref.issuer_assigned_id = invoice.refers.number
            ref.date_time_string = invoice.refers.date
            ref.type_code = "AWR"

        taxtotal = Decimal(0)
        for idx, gross in grossvalue_map.items():
            rate, category, exemption_reason = idx
            tax = taxvalue_map[idx]
            trade_tax = ApplicableTradeTax()
            trade_tax.calculated_amount = tax
            trade_tax.basis_amount = gross - tax
            trade_tax.type_code = "VAT"
            trade_tax.category_code = category
            if exemption_reason:
                trade_tax.exemption_reason = exemption_reason
            trade_tax.rate_applicable_percent = Decimal(rate)
            doc.trade.settlement.trade_tax.add(trade_tax)
            taxtotal += tax

        doc.trade.settlement.monetary_summation.line_total = total - taxtotal
        doc.trade.settlement.monetary_summation.charge_total = Decimal("0.00")
        doc.trade.settlement.monetary_summation.allowance_total = Decimal("0.00")
        doc.trade.settlement.monetary_summation.tax_basis_total = total - taxtotal
        doc.trade.settlement.monetary_summation.tax_total = (taxtotal, cc)
        doc.trade.settlement.monetary_summation.grand_total = total
        doc.trade.settlement.monetary_summation.due_amount = total
        return doc

    def generate(self, invoice):
        fname, ftype, content = super().generate(invoice)

        if not invoice.invoice_from_name or not invoice.invoice_to_country or not invoice.invoice_from_country:
            return fname, ftype, content

        try:
            xml = self._zugferd_generate_document(invoice).serialize(schema="FACTUR-X_" + self.schema)
        except Exception as e:
            logger.exception(
                "Could not generate ZUGFeRD data for invoice {}".format(invoice.number)
            )
            raise e

        with tempfile.TemporaryDirectory() as tdir:
            with open(os.path.join(tdir, "in.pdf"), "wb") as f:
                f.write(content)
            subprocess.run(
                [
                    settings.CONFIG_FILE.get("tools", "gs", fallback="gs"),
                    "-dPDFA=3",
                    "-dBATCH",
                    "-dNOPAUSE",
                    "-dNOOUTERSAVE",
                    "-sColorConversionStrategy=UseDeviceIndependentColor",
                    "-sFONTPATH={}".format(
                        os.path.dirname(finders.find("fonts/OpenSans-Regular.ttf"))
                    ),
                    "-sProcessColorModel=DeviceCMYK",
                    "-sDEVICE=pdfwrite",
                    "-dPDFACompatibilityPolicy=1",
                    "-sOutputFile={}".format(os.path.join(tdir, "out.pdf")),
                    os.path.join(tdir, "in.pdf"),
                ],
                check=True,
            )
            with open(os.path.join(tdir, "out.pdf"), "rb") as f:
                content = f.read()

        content = attach_xml(content, xml, self.profile)
        return fname, ftype, content


class ZugferdInvoiceRenderer(ZugferdMixin, ClassicInvoiceRenderer):
    identifier = "classic_zugferd"
    verbose_name = lazy(
        lambda a: "{} + ZUGFeRD 2.2 Profil EXTENDED".format(ClassicInvoiceRenderer.verbose_name), str
    )


class Modern1ZugferdInvoiceRenderer(ZugferdMixin, Modern1Renderer):
    identifier = "modern1_zugferd"
    verbose_name = lazy(
        lambda a: "{} + ZUGFeRD 2.2 Profil EXTENDED".format(Modern1Renderer.verbose_name), str
    )


class Modern1ZugferdXRechnungInvoiceRenderer(ZugferdMixin, Modern1Renderer):
    identifier = "modern1_zugferd_xrechnung"
    profile = "XRECHNUNG"
    schema = "EN16931"
    guideline_id = "urn:cen.eu:en16931:2017#compliant#urn:xoev-de:kosit:standard:xrechnung_1.2"
    verbose_name = lazy(
        lambda a: "{} + ZUGFeRD 2.2 Profil XRECHNUNG".format(Modern1Renderer.verbose_name), str
    )

    def _zugferd_generate_document(self, invoice):
        doc = super()._zugferd_generate_document(invoice)
        doc.trade.agreement.buyer_reference = invoice.custom_field or "unknown"
        return doc
