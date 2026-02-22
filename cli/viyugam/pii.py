"""
pii.py — PII redaction before any text reaches Claude.
Strips emails, phone numbers, and large currency amounts.
"""
import re

_RULES = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'), "<EMAIL>"),
    (re.compile(r'\b\d{10}\b'),                                            "<PHONE>"),
    (re.compile(r'(₹|\$)\s?\d{1,3}(,\d{3})*(\.\d+)?'),                   "<AMOUNT>"),
]

def redact(text: str) -> str:
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text
