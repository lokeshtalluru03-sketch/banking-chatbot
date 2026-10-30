"""
Dialog manager: the "brain" that decides what to say next.

Flow for every message:
  1. Guardrails  -> mask PII, detect urgency
  2. Pending flow? (e.g. waiting for transfer amount or a yes/no) -> continue it
  3. NLU         -> intent + entities
  4. Action      -> call the bank API
  5. Response    -> text back to the customer
  6. Log         -> analytics event (intent, confidence, escalation, latency)

Optional: if ANTHROPIC_API_KEY is set, unknown questions about general banking
are answered by an LLM, restricted to safe, non-account-specific answers.
"""
import os
import time
from dataclasses import dataclass, field

from .bank_api import BRANCH_INFO, LOAN_INFO, BankAPI
from .guardrails import SENSITIVE_WARNING, is_urgent, mask_sensitive
from .intents import NO_WORDS, YES_WORDS
from .nlu import IntentClassifier, extract_accounts, extract_amount, extract_single_account


@dataclass
class Session:
    customer_id: str
    name: str
    pending: dict = field(default_factory=dict)  # multi-turn state
    events: list = field(default_factory=list)   # analytics log


class BankingBot:
    def __init__(self, bank: BankAPI):
        self.bank = bank
        self.nlu = IntentClassifier()
        self.llm = self._init_llm()

    # ------------------------------------------------------------------ public
    def handle(self, session: Session, user_text: str) -> str:
        start = time.time()
        masked, found = mask_sensitive(user_text)
        prefix = SENSITIVE_WARNING.format(items=" and ".join(found)) + "\n\n" if found else ""

        if session.pending:
            intent, conf = "flow:" + session.pending["flow"], 1.0
            reply = self._continue_flow(session, masked)
        else:
            intent, conf = self.nlu.predict(masked)
            # Urgency overrides the classifier: fraud words always reach the fraud path
            if is_urgent(masked) and intent not in ("card_lost", "report_fraud"):
                intent = "report_fraud"
            reply = self._dispatch(session, intent, masked)

        escalated = intent in ("talk_to_agent", "report_fraud", "card_lost")
        session.events.append({
            "ts": time.strftime("%H:%M:%S"),
            "message": masked,
            "intent": intent,
            "confidence": round(conf, 2),
            "escalated": escalated,
            "pii_masked": bool(found),
            "latency_ms": int((time.time() - start) * 1000),
        })
        return prefix + reply

    # ---------------------------------------------------------------- routing
    def _dispatch(self, s: Session, intent: str, text: str) -> str:
        cid = s.customer_id
        if intent == "greeting":
            return (f"Hi {s.name.split()[0]}! 👋 I'm Ridge, your Summit Ridge Bank assistant. I can check balances, "
                    "show transactions, move money between your accounts, block a lost card, or report fraud.")

        if intent == "check_balance":
            bal = self.bank.get_balances(cid)
            which = extract_single_account(text)
            if which:
                b = bal[which]
                return f"Your **{which}** account (••{b['number']}) balance is **${b['balance']:,.2f}**."
            lines = [f"- **{t.title()}** (••{b['number']}): ${b['balance']:,.2f}" for t, b in bal.items()]
            total = sum(b["balance"] for b in bal.values())
            return "Here are your balances:\n" + "\n".join(lines) + f"\n\n**Total:** ${total:,.2f}"

        if intent == "recent_transactions":
            n = int(extract_amount(text) or 5)
            n = max(1, min(n, 15))
            tx = self.bank.get_transactions(cid, n)
            rows = "\n".join(
                f"| {t['ts'][:10]} | {t['description']} | {t['category']} | {'+' if t['amount'] > 0 else '−'}${abs(t['amount']):,.2f} |"
                for t in tx)
            spend = self.bank.spending_by_category(cid)
            top = next(iter(spend.items()), None)
            insight = f"\n\n💡 Your top spending category in the last 30 days is **{top[0]}** (${top[1]:,.2f})." if top else ""
            return f"Your last {len(tx)} transactions:\n\n| Date | Description | Category | Amount |\n|---|---|---|---|\n{rows}{insight}"

        if intent == "transfer_money":
            amount = extract_amount(text)
            from_acct, to_acct = extract_accounts(text)
            s.pending = {"flow": "transfer", "amount": amount, "from": from_acct, "to": to_acct}
            return self._next_transfer_step(s)

        if intent == "card_lost":
            card = self.bank.get_card(cid)
            if card["status"] == "blocked":
                return f"Your card ending **{card['last4']}** is already blocked. A replacement is on its way."
            s.pending = {"flow": "block_card"}
            return (f"I'm sorry to hear that. I can **block your debit card ending {card['last4']}** right now "
                    "so no one can use it. Shall I block it? (yes/no)")

        if intent == "report_fraud":
            case = self.bank.open_case(cid, "fraud", text)
            card = self.bank.get_card(cid)
            return (f"🚨 I've opened fraud case **{case}** and alerted our fraud team — a specialist will contact you shortly.\n\n"
                    f"As a precaution, would you also like me to block your card ending {card['last4']}? "
                    "Just say *block my card*.\n\nIf you're in immediate danger of losing funds, call the number on the back of your card.")

        if intent == "branch_hours":
            return BRANCH_INFO
        if intent == "loan_info":
            return LOAN_INFO
        if intent == "talk_to_agent":
            case = self.bank.open_case(cid, "agent_handoff", text)
            return (f"Connecting you with a live agent. Your reference is **{case}**. "
                    "Average wait time is about 3 minutes. I've shared this conversation so you won't need to repeat yourself.")
        if intent == "thanks_goodbye":
            return "You're welcome! Have a great day. 😊"

        return self._fallback(text)

    # ------------------------------------------------------------ multi-turn
    def _continue_flow(self, s: Session, text: str) -> str:
        flow = s.pending["flow"]
        t = text.lower().strip(" .!")

        if t in NO_WORDS:
            s.pending = {}
            return "No problem — I've cancelled that. Anything else I can help with?"

        if flow == "block_card":
            if t in YES_WORDS:
                case = self.bank.block_card(s.customer_id)
                s.pending = {}
                return (f"✅ Your card is now **blocked**. A replacement will arrive in 5–7 business days. "
                        f"Reference: **{case}**.")
            return "Please reply **yes** to block the card or **no** to cancel."

        if flow == "transfer":
            p = s.pending
            if p.get("awaiting") == "confirm":
                if t in YES_WORDS:
                    ok, result = self.bank.transfer(s.customer_id, p["from"], p["to"], p["amount"])
                    s.pending = {}
                    if not ok:
                        return f"❌ {result}"
                    bal = self.bank.get_balances(s.customer_id)
                    return (f"✅ Done! Moved **${p['amount']:,.2f}** from {p['from']} to {p['to']}. Reference **{result}**.\n\n"
                            f"New balances — Checking: ${bal['checking']['balance']:,.2f} · Savings: ${bal['savings']['balance']:,.2f}")
                return "Please reply **yes** to confirm the transfer or **no** to cancel."
            if p.get("awaiting") == "amount":
                p["amount"] = extract_amount(text)
                if p["amount"] is None:
                    return "I didn't catch an amount. How much would you like to transfer? (e.g. 250)"
            if p.get("awaiting") == "direction":
                p["from"], p["to"] = extract_accounts(text)
                if not p["from"]:
                    acct = extract_single_account(text)
                    if acct:
                        p["from"], p["to"] = acct, ("savings" if acct == "checking" else "checking")
            return self._next_transfer_step(s)

        s.pending = {}
        return self._fallback(text)

    def _next_transfer_step(self, s: Session) -> str:
        """Slot filling: ask for whatever is missing, then confirm."""
        p = s.pending
        if not p.get("amount"):
            p["awaiting"] = "amount"
            return "Sure — how much would you like to transfer?"
        if not p.get("from"):
            p["awaiting"] = "direction"
            return f"Got it, ${p['amount']:,.2f}. Which direction: **checking → savings** or **savings → checking**?"
        p["awaiting"] = "confirm"
        return (f"Please confirm: transfer **${p['amount']:,.2f}** from **{p['from']}** to **{p['to']}**? (yes/no)")

    # --------------------------------------------------------------- fallback
    def _fallback(self, text: str) -> str:
        if self.llm:
            try:
                return self._ask_llm(text)
            except Exception:
                pass
        return ("I'm not sure I understood that. I can help with **balances**, **transactions**, **transfers**, "
                "**lost cards**, **fraud**, **branch hours** and **loans** — or say *talk to an agent*.")

    def _init_llm(self):
        if not os.getenv("ANTHROPIC_API_KEY"):
            return None
        try:
            import anthropic
            return anthropic.Anthropic()
        except ImportError:
            return None

    def _ask_llm(self, text: str) -> str:
        system = ("You are Ridge, a virtual assistant for Summit Ridge Bank (a fictional demo bank). "
                  "Answer general banking questions briefly (under 120 words). You have NO access to account data, "
                  "so never invent balances, transactions or rates. Never ask for card numbers, PINs, passwords or SSNs. "
                  "No investment, tax or legal advice. If the question is off-topic or needs account action, "
                  "suggest the customer ask for a live agent.")
        resp = self.llm.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-haiku-5-5"),
            max_tokens=300, system=system,
            messages=[{"role": "user", "content": text}])
        return resp.content[0].text + "\n\n_(Answered by AI — general information only)_"
