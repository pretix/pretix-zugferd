from collections import defaultdict
import os
import subprocess

import bleach
from decimal import Decimal
import tempfile
from django.conf import settings

from django.contrib.staticfiles import finders
from django.utils.functional import lazy
from django.utils.translation import pgettext, ugettext as _
from drafthorse.models.document import Document
from drafthorse.models.tradelines import LineItem
from drafthorse.models.party import TaxRegistration
from drafthorse.models.accounting import ApplicableTradeTax
from drafthorse.models.references import AdditionalReferencedDocument
from drafthorse.models.note import IncludedNote
from drafthorse.models.payment import PaymentTerms
from drafthorse.pdf import attach_xml

from pretix.base.invoice import ClassicInvoiceRenderer


class ZugferdMixin:
    def _zugferd_generate_document(self, invoice):
        cc = invoice.event.currency
        doc = Document()
        doc.context.guideline_parameter.id = "urn:ferd:CrossIndustryDocument:invoice:1p0:extended"
        doc.context.test_indicator = (invoice.invoice_no == "PREVIEW")
        doc.header.id = invoice.number
        doc.header.name = "RECHNUNG"
        doc.header.type_code = "380"
        doc.header.issue_date_time = invoice.date
        doc.header.languages.add(invoice.locale[:2])

        doc.trade.agreement.seller.name = invoice.invoice_from_name
        lines = invoice.invoice_from.strip().split("\n")
        doc.trade.agreement.seller.address.line_one = lines[0].strip()
        if len(lines) > 1:
            doc.trade.agreement.seller.address.line_two = ', '.join(lines[1:]).strip()
        doc.trade.agreement.seller.address.postcode = invoice.invoice_from_zipcode
        doc.trade.agreement.seller.address.city_name = invoice.invoice_from_city
        doc.trade.agreement.seller.address.country_id = str(invoice.invoice_from_country)

        if invoice.invoice_from_tax_id:
            doc.trade.agreement.seller.tax_registrations.add(
                TaxRegistration(id=("FC", invoice.invoice_from_tax_id))
            )

        if invoice.invoice_from_vat_id:
            doc.trade.agreement.seller.tax_registrations.add(
                TaxRegistration(id=("VA", invoice.invoice_from_vat_id))
            )

        doc.trade.agreement.buyer.name = invoice.invoice_to_company or invoice.invoice_to_name
        if invoice.invoice_to_company and invoice.invoice_to_name:
            doc.trade.agreement.buyer.address.line_one = invoice.invoice_to_name
            doc.trade.agreement.buyer.address.line_two = invoice.invoice_to_street
        else:
            doc.trade.agreement.buyer.address.line_one = invoice.invoice_to_street
        doc.trade.agreement.buyer.address.postcode = invoice.invoice_to_zipcode
        doc.trade.agreement.buyer.address.city_name = invoice.invoice_to_city
        doc.trade.agreement.buyer.address.country_id = str(invoice.invoice_to_country)

        if invoice.invoice_to_vat_id:
            doc.trade.agreement.buyer.tax_registrations.add(
                TaxRegistration(id=("FC", invoice.invoice_to_vat_id))
            )

        note = IncludedNote()
        note.content.add(_("Order code: {code}").format(code=invoice.order.full_code))
        doc.header.notes.add(note)

        if not invoice.event.has_subevents:
            if invoice.event.settings.show_date_to and invoice.event.date_to:
                p_str = (
                        str(invoice.event.name) + ' - ' + pgettext('invoice', '{from_date}\nuntil {to_date}').format(
                    from_date=invoice.event.get_date_from_display(),
                    to_date=invoice.event.get_date_to_display())
                )
            else:
                p_str = (
                        str(invoice.event.name) + ' - ' + invoice.event.get_date_from_display()
                )
        else:
            p_str = invoice.event.name
        note = IncludedNote()
        note.content.add(p_str)
        doc.header.notes.add(note)

        if invoice.internal_reference:
            note = IncludedNote()
            note.content.add(
                pgettext('invoice', 'Customer reference: {reference}').format(reference=invoice.internal_reference)
            )
            doc.header.notes.add(note)

        if invoice.introductory_text:
            note = IncludedNote()
            note.content.add(invoice.introductory_text)
            doc.header.notes.add(note)

        if invoice.additional_text:
            note = IncludedNote()
            note.content.add(invoice.additional_text)
            doc.header.notes.add(note)

        if invoice.footer_text:
            note = IncludedNote()
            note.content.add(invoice.footer_text)
            doc.header.notes.add(note)

        if invoice.payment_provider_text:
            doc.trade.settlement.payment_means.information.add(
                invoice.payment_provider_text
            )

        pt = PaymentTerms()
        pt.description = invoice.payment_provider_text
        pt.due_date = invoice.order.expires
        doc.trade.settlement.terms.add(pt)

        if invoice.is_cancellation:
            ref = AdditionalReferencedDocument()
            ref.issue_date_time = invoice.refers.date
            ref.type_code = "AWR"
            ref.id = invoice.refers.number

        taxvalue_map = defaultdict(Decimal)
        grossvalue_map = defaultdict(Decimal)
        total = Decimal('0.00')
        for line in invoice.lines.all():
            factor = -1 if line.gross_value < 0 else 1
            li = LineItem()
            if line.tax_rate == Decimal("0.00"):
                if invoice.reverse_charge:
                    category = "AE"
                else:
                    category = "E"  # TODO: Always correct?
            else:
                category = "S"
            li.document.line_id = str(line.position + 1)
            li.agreement.gross.amount = ((line.net_value * factor).quantize(Decimal('0.0001')), cc)
            li.agreement.gross.basis_quantity = (Decimal('1.0000') * factor, 'C62')
            li.agreement.net.amount = ((line.net_value * factor).quantize(Decimal('0.0001')), cc)
            li.agreement.net.basis_quantity = (Decimal('1.0000') * factor, 'C62')
            li.delivery.billed_quantity = (Decimal('1.0000') * factor, 'C62')
            li.settlement.trade_tax.type_code = "VAT"
            li.settlement.trade_tax.category_code = category
            li.settlement.trade_tax.applicable_percent = line.tax_rate
            li.settlement.monetary_summation.total_amount = (line.net_value * factor, cc)
            desc = bleach.clean(line.description.replace("<br />", "\n"), tags=[])
            li.product.name = desc.split("\n")[0]
            li.product.description = desc
            doc.trade.items.add(li)
            taxvalue_map[line.tax_rate, category] += line.tax_value
            grossvalue_map[line.tax_rate, category] += line.gross_value
            total += line.gross_value

        doc.trade.settlement.payment_reference = invoice.order.full_code
        doc.trade.settlement.currency_code = cc

        taxtotal = Decimal(0)
        for idx, gross in grossvalue_map.items():
            rate, category = idx
            tax = taxvalue_map[idx]
            trade_tax = ApplicableTradeTax()
            trade_tax.calculated_amount = (tax, cc)
            trade_tax.basis_amount = (gross - tax, cc)
            trade_tax.type_code = "VAT"
            trade_tax.category_code = category
            trade_tax.applicable_percent = Decimal(rate)
            doc.trade.settlement.trade_tax.add(trade_tax)
            taxtotal += tax

        doc.trade.settlement.monetary_summation.line_total = (total - taxtotal, cc)
        doc.trade.settlement.monetary_summation.charge_total = (Decimal("0.00"), cc)
        doc.trade.settlement.monetary_summation.allowance_total = (Decimal("0.00"), cc)
        doc.trade.settlement.monetary_summation.tax_basis_total = (total - taxtotal, cc)
        doc.trade.settlement.monetary_summation.tax_total = (taxtotal, cc)
        doc.trade.settlement.monetary_summation.grand_total = (total, cc)
        doc.trade.settlement.monetary_summation.due_amount = (total, cc)

        return doc

    def generate(self, invoice):
        fname, ftype, content = super().generate(invoice)

        if not invoice.invoice_from_name:
            return fname, ftype, content

        xml = self._zugferd_generate_document(invoice).serialize()

        with tempfile.TemporaryDirectory() as tdir:
            with open(os.path.join(tdir, 'in.pdf'), 'wb') as f:
                f.write(content)
            subprocess.run([settings.CONFIG_FILE.get('tools', 'gs', fallback='gs'),
                            '-dPDFA=3', '-dBATCH', '-dNOPAUSE', '-dNOOUTERSAVE', '-dUseCIEColor',
                            '-sFONTPATH={}'.format(os.path.dirname(finders.find('fonts/OpenSans-Regular.ttf'))),
                            '-sProcessColorModel=DeviceCMYK', '-sDEVICE=pdfwrite', '-sPDFACompatibilityPolicy=1',
                            '-sOutputFile={}'.format(os.path.join(tdir, 'out.pdf')),
                            os.path.join(tdir, 'in.pdf')], check=True)
            with open(os.path.join(tdir, 'out.pdf'), 'rb') as f:
                content = f.read()

        content = attach_xml(content, xml, 'EXTENDED')
        return fname, ftype, content


class ZugferdInvoiceRenderer(ZugferdMixin, ClassicInvoiceRenderer):
    identifier = 'classic_zugferd'
    verbose_name = lazy(lambda a: "{} + ZUGFeRD".format(ClassicInvoiceRenderer.verbose_name), str)
