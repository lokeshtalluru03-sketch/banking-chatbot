"""
Guardrails = safety checks that run BEFORE and AFTER the AI.

Real banks are regulated, so a chatbot must:
 - never store or echo full card numbers / SSNs  (PCI-DSS, privacy laws)
 - never ask for passwords or PINs
 - escalate urgent situations (fraud, distress) to humans fast
"""
import re

CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PIN_RE = re.compile(r"\b(pin|password|passcode|otp)\b\s*(is|:)?\s*\S+", re.I)

URGENT_KEYWORDS = ["stolen", "fraud", "scam", "hacked", "unauthorized", "didn't make", "didn't authorize"]


def mask_sensitive(text: str):
    """Mask card numbers, SSNs and PINs. Returns (masked_text, list_of_what_was_found)."""
    found = []

    def mask_card(m):
        digits = re.sub(r"\D", "", m.group())
        found.append("card number")
        return f"****{digits[-4:]}"

    text = CARD_RE.sub(mask_card, text)
    if SSN_RE.search(text):
        found.append("SSN")
        text = SSN_RE.sub("***-**-****", text)
    if PIN_RE.search(text):
        found.append("PIN/password")
        text = PIN_RE.sub(lambda m: m.group(1) + " [REDACTED]", text)
    return text, found


def is_urgent(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in URGENT_KEYWORDS)


SENSITIVE_WARNING = (
    "🔒 For your security I've hidden the {items} you shared. "
    "Please never share full card numbers, SSNs, PINs or passwords in chat — "
    "Summit Ridge Bank will never ask for them."
)
