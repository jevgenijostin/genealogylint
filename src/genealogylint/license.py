"""Demo-only checksum patterned after ScamSniff; no payment/security boundary."""
import re

FREE_LIMIT = 100


def create_demo_key(payload="DEMO2026"):
    if not re.fullmatch(r"[A-Z0-9]{8}", payload):
        raise ValueError("Use exactly eight uppercase letters or digits")
    checksum = 0
    for char in payload:
        checksum = (checksum * 31 + ord(char)) % 65536
    return f"GL-PRO-{payload}-{checksum:04X}"


def is_valid_license(key):
    key = (key or "").strip().upper()
    match = re.fullmatch(r"GL-PRO-([A-Z0-9]{8})-([A-F0-9]{4})", key)
    return bool(match and create_demo_key(match[1]) == key)


def enforce(count, key, batch=False):
    if (count > FREE_LIMIT or batch) and not is_valid_license(key):
        raise ValueError("Trees over 100 individuals and batch mode require a local demo PRO license")
