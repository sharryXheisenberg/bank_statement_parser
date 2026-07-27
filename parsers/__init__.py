"""
Registry mapping a bank name (as returned by utils.bank_identifier) to the
module that knows how to turn that bank's PDF into a DataFrame.

Adding a new bank = write parsers/<bank>_parser.py with a build_dataframe(pdf_path)
function, then add one line here. main.py never needs to change.
"""

from parsers import hdfc_parser, sbi_parser

PARSER_REGISTRY = {
    "HDFC": hdfc_parser.build_dataframe,
    "SBI": sbi_parser.build_dataframe,
}
