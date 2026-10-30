"""
Training data for the intent classifier.

In a real bank this would come from thousands of labelled chat logs.
Here we use a small hand-written set so you can see exactly how it works.
Add more examples to any intent and the model gets better automatically.
"""

INTENT_EXAMPLES = {
    "greeting": [
        "hi", "hello", "hey there", "good morning", "good evening",
        "hi, I need some help", "hello bank", "hey",
    ],
    "check_balance": [
        "what is my balance", "check my balance", "how much money do I have",
        "show my account balance", "balance in checking", "what's in my savings",
        "how much is in my account", "current balance please", "account balance",
        "do I have enough money", "tell me my balance",
    ],
    "recent_transactions": [
        "show my recent transactions", "last transactions", "transaction history",
        "what did I spend recently", "show my last 5 transactions",
        "recent activity on my account", "list my purchases", "show statement",
        "where did my money go", "my spending this week",
    ],
    "transfer_money": [
        "transfer money", "send 200 to savings", "move $500 from checking to savings",
        "transfer funds between accounts", "I want to move money",
        "transfer 100 dollars", "move money to my savings account",
        "put 50 into savings", "transfer from savings to checking",
    ],
    "card_lost": [
        "I lost my card", "my card was stolen", "block my card", "freeze my debit card",
        "can't find my credit card", "someone stole my wallet", "lock my card",
        "disable my card", "my card is missing",
    ],
    "report_fraud": [
        "I see a charge I didn't make", "there is a fraudulent transaction",
        "unauthorized transaction on my account", "someone used my account",
        "I think I've been scammed", "suspicious activity on my account",
        "report fraud", "I didn't authorize this payment",
    ],
    "branch_hours": [
        "what are your branch hours", "when are you open", "branch timings",
        "is the branch open on saturday", "opening hours", "find nearest branch",
        "where is the closest atm", "atm near me", "branch location",
    ],
    "loan_info": [
        "what are your loan rates", "I want a personal loan", "home loan interest rate",
        "mortgage rates", "car loan", "how do I apply for a loan",
        "auto loan options", "can I get a loan",
    ],
    "talk_to_agent": [
        "talk to a human", "speak to an agent", "connect me to customer service",
        "I want a real person", "call me", "representative please",
        "this isn't helping, get me a person",
    ],
    "thanks_goodbye": [
        "thanks", "thank you", "bye", "that's all", "goodbye",
        "thanks for the help", "ok great thanks", "cheers",
    ],
}

# Messages the user can confirm/deny with during multi-step flows
YES_WORDS = {"yes", "y", "yeah", "yep", "confirm", "sure", "ok", "okay", "do it", "proceed"}
NO_WORDS = {"no", "n", "nope", "cancel", "stop", "don't", "dont"}
