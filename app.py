"""
Summit Ridge Bank — AI Banking Assistant (demo)
Run:  streamlit run app.py
Demo logins:  alex / demo123   or   priya / demo123
"""
import pandas as pd
import streamlit as st

from bot import BankAPI, BankingBot, Session

st.set_page_config(page_title="Summit Ridge Bank Assistant", page_icon="🏦", layout="wide")

st.markdown("""
<style>
  .brand {font-size:1.6rem;font-weight:700;color:#0B3D5C;margin-bottom:0}
  .tag {color:#5B7083;margin-top:0}
  div[data-testid="stMetricValue"] {font-size:1.4rem}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_bot():
    bank = BankAPI()
    return bank, BankingBot(bank)


bank, bot = load_bot()

# ------------------------------------------------------------------ login
if "session" not in st.session_state:
    st.markdown('<p class="brand">🏦 Summit Ridge Bank</p><p class="tag">AI Banking Assistant · demo</p>',
                unsafe_allow_html=True)
    col, _ = st.columns([1, 2])
    with col:
        with st.form("login"):
            st.subheader("Sign in")
            uid = st.text_input("Customer ID", value="alex")
            pwd = st.text_input("Password", type="password", value="demo123")
            if st.form_submit_button("Sign in", width="stretch"):
                name = BankAPI.authenticate(uid, pwd)
                if name:
                    st.session_state.session = Session(uid.lower().strip(), name)
                    st.session_state.chat = [{"role": "assistant", "content": bot.handle(st.session_state.session, "hello")}]
                    st.rerun()
                else:
                    st.error("Invalid credentials. Try alex / demo123.")
        st.caption("Demo accounts: **alex / demo123**, **priya / demo123**. Fictional data only.")
    st.stop()

session: Session = st.session_state.session

# ------------------------------------------------------------------ layout
left, right = st.columns([3, 2], gap="large")

with left:
    st.markdown(f'<p class="brand">🏦 Summit Ridge Bank</p><p class="tag">Signed in as {session.name}</p>',
                unsafe_allow_html=True)

    quick = ["What's my balance?", "Show recent transactions", "Move $100 from checking to savings",
             "I lost my card", "Branch hours", "Talk to an agent"]
    qcols = st.columns(3)
    clicked = None
    for i, q in enumerate(quick):
        if qcols[i % 3].button(q, width="stretch"):
            clicked = q

    chat_box = st.container(height=480)
    for m in st.session_state.chat:
        chat_box.chat_message(m["role"], avatar="🏦" if m["role"] == "assistant" else "🙂").markdown(m["content"])

    prompt = st.chat_input("Ask Ridge anything about your accounts…") or clicked
    if prompt:
        st.session_state.chat.append({"role": "user", "content": prompt})
        reply = bot.handle(session, prompt)
        st.session_state.chat.append({"role": "assistant", "content": reply})
        st.rerun()

with right:
    tab_acc, tab_ops = st.tabs(["💳 My accounts", "📊 Bot analytics (ops view)"])

    with tab_acc:
        bal = bank.get_balances(session.customer_id)
        c1, c2 = st.columns(2)
        c1.metric("Checking", f"${bal['checking']['balance']:,.2f}")
        c2.metric("Savings", f"${bal['savings']['balance']:,.2f}")
        card = bank.get_card(session.customer_id)
        st.write(f"Debit card ••{card['last4']} — **{card['status'].upper()}**")
        spend = bank.spending_by_category(session.customer_id)
        if spend:
            st.caption("Spending by category, last 30 days")
            st.bar_chart(pd.Series(spend, name="Spent ($)"), horizontal=True, color="#0B6E99")

    with tab_ops:
        st.caption("What a bank's operations team watches in real time.")
        # skip event 0: the automatic greeting sent at login
        user_ev = pd.DataFrame(session.events[1:])
        if user_ev.empty:
            st.info("Send a message to see live analytics.")
        else:
            total = len(user_ev)
            contained = (~user_ev["escalated"]).mean() * 100
            understood = (user_ev["intent"] != "unknown").mean() * 100
            m1, m2, m3 = st.columns(3)
            m1.metric("Messages", total)
            m2.metric("Containment", f"{contained:.0f}%", help="Share handled without a human")
            m3.metric("Understood", f"{understood:.0f}%", help="Share with a recognised intent")
            st.caption("Intent mix")
            st.bar_chart(user_ev["intent"].value_counts(), horizontal=True, color="#0B6E99")
            st.caption("Event log (PII already masked)")
            st.dataframe(user_ev[["ts", "intent", "confidence", "escalated", "pii_masked", "latency_ms", "message"]]
                         .iloc[::-1], hide_index=True, width="stretch")

    st.divider()
    if st.button("Sign out"):
        for k in ("session", "chat"):
            st.session_state.pop(k, None)
        st.rerun()
    st.caption("LLM fallback: " + ("**on** (Claude)" if bot.llm else "off — set ANTHROPIC_API_KEY to enable"))
