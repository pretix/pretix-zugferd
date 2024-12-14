import os
from difflib import unified_diff
from drafthorse.utils import validate_xml
from xml.dom import minidom


def diff_xml(a, b):
    for line in unified_diff(a.splitlines(), b.splitlines()):
        print(line)


def prettify(xml, **kwargs):
    try:
        from lxml import etree
    except ImportError:
        reparsed = minidom.parseString(xml)
        return reparsed.toprettyxml(indent="\t")
    else:
        parser = etree.XMLParser(remove_blank_text=True, **kwargs)
        return etree.tostring(etree.fromstring(xml, parser), pretty_print=True)


def compare(result, expected, schema):
    expectedxml = prettify(
        expected,
        remove_comments=True,
    )
    resultxml = prettify(
        result,
        remove_comments=True,
    )

    # Validate that the sample file is valid, otherwise the test is moot
    validate_xml(xmlout=resultxml, schema=schema)
    validate_xml(xmlout=expectedxml, schema=schema)

    # Validate output XML and render a diff for debugging
    # skip first line (namespace order…)
    expectedxml = b"\n".join(expectedxml.split(b"\n")[1:]).decode().strip()
    resultxml = b"\n".join(resultxml.split(b"\n")[1:]).decode().strip()
    diff_xml(expectedxml, resultxml)

    # Compare output XML
    assert expectedxml == resultxml
