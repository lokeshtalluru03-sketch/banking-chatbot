# 🏦 Summit Ridge Bank — AI Banking Chatbot (Learning Project)

A working, end-to-end banking assistant that shows how real banks (US Bank, Bank of America's Erica, Capital One's Eno, etc.) structure their chatbots — built small enough to read in an afternoon.

> Summit Ridge Bank is fictional. All data is fake and generated locally.

## Run it

```bash
pip install -r requirements.txt
python test_bot.py          # 9 conversation tests
streamlit run app.py        # opens http://localhost:8501
```

Log in with **alex / demo123** or **priya / demo123**.

Optional: `export ANTHROPIC_API_KEY=...` to let Claude answer general banking questions the bot doesn't recognise (e.g. "what is an IRA?").

## What it can do

| Customer says | What happens |
|---|---|
| "What's my balance?" / "how much in savings" | Reads balances from the core-banking mock |
| "Show my recent transactions" | Table of transactions + a spending insight |
| "Move $200 from checking to savings" | Multi-turn transfer: asks for missing details, confirms, executes, checks funds and limits |
| "I lost my card" | Confirms, blocks the card, opens a case |
| "There's a charge I didn't make" | Opens a fraud case and escalates to humans |
| "Branch hours", "loan rates" | FAQ answers |
| "Talk to an agent" | Live-agent handoff with a reference number |
| "My card 4111 1111 1111 1234…" | Masks the number before anything is stored or logged |

## How it works (the real-world architecture in miniature)

```
Customer ──► Guardrails ──► NLU ──► Dialog Manager ──► Bank APIs ──► Reply
            (mask PII,     (intent +   (multi-turn      (balances,
             urgency)      entities)    slot filling)    transfers, cards)
                                  │
                                  └──► Analytics log  ──► Ops dashboard
```

| File | Role | Real-bank equivalent |
|---|---|---|
| `bot/guardrails.py` | Masks card numbers, SSNs, PINs; flags urgent words | PCI-DSS compliance, DLP filters |
| `bot/intents.py` | Labelled training examples | Thousands of tagged chat logs |
| `bot/nlu.py` | TF-IDF + logistic regression intent model, amount/account extraction | Dialogflow, Rasa, BERT or LLM classifiers |
| `bot/engine.py` | Routing, slot filling, confirmations, escalation, LLM fallback | Conversation orchestration layer |
| `bot/bank_api.py` | SQLite mock of accounts, transactions, cards, cases | Core banking, card management, CRM APIs |
| `app.py` | Chat UI + account panel + live ops analytics | Mobile app / web chat widget + monitoring |

## Key business concepts you'll see

- **Containment rate** – % of conversations solved without a human (banks target 60–80%).
- **Intent confidence** – low-confidence messages fall back safely instead of guessing.
- **Confirm before money moves** – every transfer is read back and needs an explicit "yes".
- **Escalation rules** – fraud and lost cards always create a case for human follow-up.
- **The LLM never touches account data** – it only answers general questions; actions go through deterministic, auditable code.

## Ideas to extend it

1. Add a new intent (e.g. `bill_pay`): add examples in `intents.py`, a branch in `engine.py`, a method in `bank_api.py`.
2. Swap the classifier for an LLM with tool calling (Claude tool use) and compare accuracy.
3. Add a FAQ search over policy documents (RAG).
4. Expose the bot as a REST API with FastAPI and plug it into a website widget.
5. Add real auth (OAuth + MFA) and an audit log table.
6. Track CSAT with a 👍/👎 after each answer.
