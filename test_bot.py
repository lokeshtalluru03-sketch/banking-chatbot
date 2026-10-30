"""Run with:  python test_bot.py   (or pytest test_bot.py)"""
import tempfile
from pathlib import Path

from bot import BankAPI, BankingBot, Session


def make():
    db = Path(tempfile.mkdtemp()) / "test.db"
    bank = BankAPI(db_path=db, reset=True)
    return bank, BankingBot(bank), Session("alex", "Alex Morgan")


def test_balance():
    bank, bot, s = make()
    assert "Checking" in bot.handle(s, "what's my balance?")
    assert "savings" in bot.handle(s, "how much is in my savings").lower()


def test_transactions():
    _, bot, s = make()
    assert "| Date |" in bot.handle(s, "show my recent transactions")


def test_transfer_full_flow():
    bank, bot, s = make()
    before = bank.get_balances("alex")
    r = bot.handle(s, "move $200 from checking to savings")
    assert "confirm" in r.lower()
    r = bot.handle(s, "yes")
    assert "Done" in r
    after = bank.get_balances("alex")
    assert round(before["checking"]["balance"] - after["checking"]["balance"], 2) == 200


def test_transfer_slot_filling():
    _, bot, s = make()
    assert "how much" in bot.handle(s, "I want to transfer money").lower()
    assert "direction" in bot.handle(s, "150").lower()
    assert "confirm" in bot.handle(s, "savings to checking").lower()
    assert "cancelled" in bot.handle(s, "no").lower()


def test_insufficient_funds():
    _, bot, s = make()
    bot.handle(s, "transfer 9999 from checking to savings")
    assert "Insufficient" in bot.handle(s, "yes")


def test_block_card():
    bank, bot, s = make()
    bot.handle(s, "I lost my card")
    assert "blocked" in bot.handle(s, "yes")
    assert bank.get_card("alex")["status"] == "blocked"


def test_fraud_escalation():
    _, bot, s = make()
    r = bot.handle(s, "there's a charge on my statement I didn't make")
    assert "CASE-" in r and s.events[-1]["escalated"]


def test_pii_masked():
    _, bot, s = make()
    r = bot.handle(s, "my card 4111 1111 1111 1234 was stolen")
    assert "4111" not in s.events[-1]["message"] and "hidden" in r


def test_typo_robustness():
    _, bot, s = make()
    assert "Checking" in bot.handle(s, "chek my balnce")


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"✓ {t.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
