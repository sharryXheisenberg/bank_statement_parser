"""
parsers/__init__.py

Auto-discovers every BankParser subclass in this package and builds
PARSER_REGISTRY: {bank_name: ParserClass}.

This is the Open/Closed Principle in practice: to add a new bank, you
write ONE new file (e.g. parsers/kotak_parser.py) defining a class that
subclasses BankParser, sets bank_name, and implements matches()/parse().
That's it -- this file, main.py, and everything else stays untouched. The
loop below finds it automatically at import time by scanning every module
in this package for BankParser subclasses.

(Contrast with the old approach: adding a bank meant editing a central
fingerprint dict in utils/bank_identifier.py AND a central registry dict
here. Both were "modification" in the OCP sense -- every new bank touched
shared, already-working code, which is exactly what OCP says to avoid.)
"""

from __future__ import annotations
import pkgutil
import importlib
import inspect

from parsers.base import BankParser

PARSER_REGISTRY: dict[str, type[BankParser]] = {}

_package = importlib.import_module(__name__)
for _, module_name, _ in pkgutil.iter_modules(_package.__path__):
    if module_name in ("base", "common"):
        continue  # infrastructure modules, not parser implementations
    module = importlib.import_module(f"{__name__}.{module_name}")
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, BankParser) and obj is not BankParser:
            PARSER_REGISTRY[obj.bank_name] = obj

del _package, module_name, module  # keep the package namespace clean


def identify_and_get_parser(first_page_text: str):
    """
    Given the raw text of a PDF's first pages, returns (bank_name, ParserClass)
    for the first registered parser whose matches() returns True, or
    (None, None) if nothing matches. Centralizes the "ask every registered
    parser if it recognizes this text" loop so main.py doesn't need to know
    how identification works internally.
    """
    for bank_name, parser_cls in PARSER_REGISTRY.items():
        try:
            if parser_cls.matches(first_page_text):
                return bank_name, parser_cls
        except Exception:
            # A misbehaving matches() in one parser must never break
            # identification for every other bank.
            continue
    return None, None
