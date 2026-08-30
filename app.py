import streamlit as st
import sqlite3
from datetime import date
from pathlib import Path

DB = Path("finance.db")
conn = sqlite3.connect(DB, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_date TEXT NOT NULL,
    tx_type TEXT NOT NULL,
    amount REAL NOT NULL,
    description TEXT,
    person TEXT,
    category TEXT
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS debts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    debt_type TEXT NOT NULL,
    person TEXT NOT NULL,
    amount REAL NOT NULL,
    paid REAL NOT NULL DEFAULT 0,
    description TEXT,
    created_date TEXT NOT NULL
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    amount REAL NOT NULL,
    frequency TEXT NOT NULL,
    next_date TEXT
)
""")
conn.commit()

def get_salary():
    row = cur.execute("SELECT value FROM settings WHERE key='salary'").fetchone()
    return float(row[0]) if row else 0.0

def set_salary(value):
    cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('salary',?)", (str(value),))
    conn.commit()

def money(x):
    return f"AED {x:,.2f}"

def add_tx(tx_type, amount, description="", person="", category=""):
    cur.execute(
        """INSERT INTO transactions(tx_date,tx_type,amount,description,person,category)
           VALUES(?,?,?,?,?,?)""",
        (str(date.today()), tx_type, amount, description, person, category)
    )
    conn.commit()

st.set_page_config(page_title="My Money", page_icon="💰", layout="centered")

st.markdown("""
<style>
.block-container {max-width: 760px; padding-top: 1rem;}
[data-testid="stMetric"] {
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 14px;
    padding: 12px;
}
.stButton button {border-radius: 12px; min-height: 46px;}
</style>
""", unsafe_allow_html=True)

st.title("💰 My Money")
st.caption("Simple personal finance tracker")

salary = get_salary()

rows = cur.execute("SELECT tx_type, amount FROM transactions").fetchall()
out_total = sum(a for t,a in rows if t == "OUT")
in_total = sum(a for t,a in rows if t == "IN")

lent_total = cur.execute("SELECT COALESCE(SUM(amount-paid),0) FROM debts WHERE debt_type='LENT'").fetchone()[0]
owed_total = cur.execute("SELECT COALESCE(SUM(amount-paid),0) FROM debts WHERE debt_type='OWED'").fetchone()[0]

remaining = salary + in_total - out_total - lent_total + owed_total

c1,c2 = st.columns(2)
c1.metric("💰 Salary", money(salary))
c2.metric("📤 OUT", money(out_total))

c3,c4 = st.columns(2)
c3.metric("📥 IN", money(in_total))
c4.metric("💵 Remaining", money(remaining))

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["Quick Add", "Lent / Owed", "Subscriptions", "History"])

with tab1:
    st.subheader("Salary")
    with st.form("salary_form"):
        amount = st.number_input("Monthly salary (AED)", min_value=0.0, value=salary, step=50.0)
        if st.form_submit_button("Save Salary", use_container_width=True):
            set_salary(amount)
            st.success("Salary saved.")
            st.rerun()

    st.subheader("Add OUT")
    with st.form("out_form"):
        amount = st.number_input("Amount (AED)", min_value=0.0, step=1.0, key="out_amt")
        desc = st.text_input("What was it?", key="out_desc")
        category = st.selectbox("Category", ["Food","Transport","Bills","Shopping","Cash","Other"], key="out_cat")
        if st.form_submit_button("➖ Add OUT", use_container_width=True):
            if amount > 0:
                add_tx("OUT", amount, desc, category=category)
                st.success("Expense added.")
                st.rerun()

    st.subheader("Add IN")
    with st.form("in_form"):
        amount = st.number_input("Amount (AED)", min_value=0.0, step=1.0, key="in_amt")
        desc = st.text_input("Source / reason", key="in_desc")
        if st.form_submit_button("➕ Add IN", use_container_width=True):
            if amount > 0:
                add_tx("IN", amount, desc)
                st.success("Income added.")
                st.rerun()

with tab2:
    st.subheader("Money I Lent")
    with st.form("lent_form"):
        person = st.text_input("Person")
        amount = st.number_input("Amount lent (AED)", min_value=0.0, step=1.0, key="lent_amt")
        desc = st.text_input("Note", key="lent_desc")
        if st.form_submit_button("🤝 Add Lent", use_container_width=True):
            if person and amount > 0:
                cur.execute(
                    "INSERT INTO debts(debt_type,person,amount,description,created_date) VALUES(?,?,?,?,?)",
                    ("LENT", person, amount, desc, str(date.today()))
                )
                conn.commit()
                st.success(f"{money(amount)} lent to {person}.")
                st.rerun()

    st.subheader("Money I Owe")
    with st.form("owed_form"):
        person = st.text_input("Person / company", key="owed_person")
        amount = st.number_input("Amount owed (AED)", min_value=0.0, step=1.0, key="owed_amt")
        desc = st.text_input("Note", key="owed_desc")
        if st.form_submit_button("📌 Add Owed", use_container_width=True):
            if person and amount > 0:
                cur.execute(
                    "INSERT INTO debts(debt_type,person,amount,description,created_date) VALUES(?,?,?,?,?)",
                    ("OWED", person, amount, desc, str(date.today()))
                )
                conn.commit()
                st.success(f"{money(amount)} owed to {person}.")
                st.rerun()

    st.divider()
    debts = cur.execute(
        "SELECT id,debt_type,person,amount,paid,description FROM debts ORDER BY id DESC"
    ).fetchall()

    for did, dtype, person, amount, paid, desc in debts:
        remaining_debt = amount - paid
        label = "You lent" if dtype == "LENT" else "You owe"
        st.write(f"**{person}** — {label}: {money(remaining_debt)}")
        if remaining_debt > 0:
            with st.form(f"pay_{did}"):
                pay = st.number_input("Payment / repayment (AED)", min_value=0.0,
                                      max_value=float(remaining_debt), step=1.0, key=f"p_{did}")
                if st.form_submit_button("Record payment", use_container_width=True):
                    new_paid = paid + pay
                    cur.execute("UPDATE debts SET paid=? WHERE id=?", (new_paid,did))
                    conn.commit()
                    if dtype == "LENT":
                        add_tx("IN", pay, f"Repayment from {person}", person)
                    else:
                        add_tx("OUT", pay, f"Payment to {person}", person)
                    st.rerun()

with tab3:
    st.subheader("Subscriptions")
    with st.form("sub_form"):
        name = st.text_input("Subscription name")
        amount = st.number_input("Amount (AED)", min_value=0.0, step=1.0, key="sub_amt")
        frequency = st.selectbox("Frequency", ["Monthly","Yearly"])
        if st.form_submit_button("➕ Add Subscription", use_container_width=True):
            if name and amount > 0:
                cur.execute(
                    "INSERT INTO subscriptions(name,amount,frequency,next_date) VALUES(?,?,?,?)",
                    (name, amount, frequency, str(date.today()))
                )
                conn.commit()
                st.success("Subscription added.")
                st.rerun()

    subs = cur.execute("SELECT id,name,amount,frequency FROM subscriptions ORDER BY id DESC").fetchall()
    if subs:
        for sid,name,amount,freq in subs:
            st.write(f"**{name}** — {money(amount)} / {freq.lower()}")
    else:
        st.info("No subscriptions yet.")

with tab4:
    st.subheader("Transaction History")
    txs = cur.execute(
        "SELECT tx_date,tx_type,amount,description,category FROM transactions ORDER BY id DESC"
    ).fetchall()
    if txs:
        for d,t,a,desc,cat in txs:
            sign = "+" if t == "IN" else "-"
            st.write(f"**{d} · {sign}{money(a)}** — {desc or cat or 'Transaction'}")
    else:
        st.info("No transactions yet.")

st.divider()
st.caption("All amounts are in AED. Data is stored locally in finance.db.")
