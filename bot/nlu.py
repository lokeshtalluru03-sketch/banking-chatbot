"""
NLU = Natural Language Understanding.

Two jobs:
 1. Intent classification  -> "what does the customer want?"
 2. Entity extraction      -> "which details did they give?" (amount, accounts)

We use TF-IDF + Logistic Regression: fast, explainable, runs offline.
Production banks often use the same idea with bigger models (BERT, LLMs).
"""
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from .intents import INTENT_EXAMPLES

CONFIDENCE_THRESHOLD = 0.30  # below this we say "I didn't understand"


class IntentClassifier:
    def __init__(self):
        texts, labels = [], []
        for intent, examples in INTENT_EXAMPLES.items():
            texts.extend(examples)
            labels.extend([intent] * len(examples))
        self.model = make_pipeline(
            # char n-grams make it robust to typos ("balnce", "trasnfer")
            TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), lowercase=True),
            LogisticRegression(max_iter=2000, C=10),
        )
        self.model.fit(texts, labels)

    def predict(self, text: str):
        probs = self.model.predict_proba([text])[0]
        best = probs.argmax()
        intent = str(self.model.classes_[best])
        confidence = float(probs[best])
        if confidence < CONFIDENCE_THRESHOLD:
            return "unknown", confidence
        return intent, confidence


ACCOUNT_ALIASES = {
    "checking": ["checking", "chequing", "current"],
    "savings": ["savings", "saving"],
}


def extract_amount(text: str):
    """Find a money amount like $500, 500, 1,250.75, 200 dollars."""
    match = re.search(r"\$?\s?(\d{1,3}(?:,\d{3})+|\d+)(\.\d{1,2})?", text)
    if not match:
        return None
    value = match.group(1).replace(",", "") + (match.group(2) or "")
    return round(float(value), 2)


def extract_accounts(text: str):
    """Return (from_account, to_account) if mentioned, e.g. 'from checking to savings'."""
    t = text.lower()

    def find(word_group):
        for acct, aliases in ACCOUNT_ALIASES.items():
            if any(a in word_group for a in aliases):
                return acct
        return None

    from_acct = to_acct = None
    m_from = re.search(r"from (\w+)", t)
    m_to = re.search(r"(?:to|into) (?:my )?(\w+)", t)
    if m_from:
        from_acct = find(m_from.group(1))
    if m_to:
        to_acct = find(m_to.group(1))
    # Infer the other side when only one is given
    if to_acct and not from_acct:
        from_acct = "checking" if to_acct == "savings" else "savings"
    if from_acct and not to_acct:
        to_acct = "savings" if from_acct == "checking" else "checking"
    return from_acct, to_acct


def extract_single_account(text: str):
    t = text.lower()
    for acct, aliases in ACCOUNT_ALIASES.items():
        if any(a in t for a in aliases):
            return acct
    return None
