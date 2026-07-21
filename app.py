import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta

import database as db
import projections as proj

# --- Page Configuration ---
st.set_page_config(
    page_title="Money Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database tables & migrations
db.init_db()

# --- Sidebar: Household Perspective & Admin ---
with st.sidebar:
    st.title("🏡 Household Context")
    
    people_list = db.fetch_people()
    perspective_options = ["🏠 Entire Household (All Combined)"] + [f"👤 {p}" for p in people_list if p != "Shared / Household"]
    
    selected_perspective = st.selectbox(
        "View Perspective",
        options=perspective_options,
        index=0,
        help="Switch view perspective between the full household or individual person"
    )

    include_shared = True
    if selected_perspective != "🏠 Entire Household (All Combined)":
        active_person = selected_perspective.replace("👤 ", "")
        include_shared = st.checkbox(f"Include 'Shared / Household' items with {active_person}", value=True)
    else:
        active_person = "ALL"

    st.markdown("---")
    
    # Household Members Management
    with st.expander("👥 Manage Household Members"):
        new_person = st.text_input("New Member Name", key="input_new_person")
        if st.button("Add Member", key="btn_add_person", icon=":material/person:"):
            if new_person.strip():
                db.add_person(new_person.strip())
                st.success(f"Added member '{new_person.strip()}'!")
                st.rerun()

    # Custom Category Management
    with st.expander("🏷️ Manage Custom Categories"):
        cat_name = st.text_input("Category Name", key="input_new_cat")
        cat_type = st.radio("Category Type", ["Bill / Expense", "Savings Goal"], horizontal=True)
        if st.button("Add Category", key="btn_add_cat", icon=":material/label:"):
            if cat_name.strip():
                type_key = "bill" if "Bill" in cat_type else "savings"
                db.add_category(cat_name.strip(), type_key)
                st.success(f"Added category '{cat_name.strip()}'!")
                st.rerun()

# --- Helper Filter Function ---
def filter_by_owner(items, owner_key="owner"):
    if active_person == "ALL":
        return items
    if include_shared:
        return [item for item in items if item.get(owner_key) in [active_person, "Shared / Household"]]
    return [item for item in items if item.get(owner_key) == active_person]

# --- Fetch Data & Apply Filter ---
raw_cards = db.fetch_all("cards")
raw_bills = db.fetch_all("bills")
raw_income = db.fetch_all("income")
raw_buckets = db.fetch_all("savings_buckets")
raw_transactions = db.fetch_all("transactions")

cards = filter_by_owner(raw_cards)
bills = filter_by_owner(raw_bills)
income_sources = filter_by_owner(raw_income)
savings_buckets = filter_by_owner(raw_buckets)
transactions = filter_by_owner(raw_transactions)

bill_categories = db.fetch_categories("bill")
savings_categories = db.fetch_categories("savings")

# --- Title Header ---
st.title("💰 Money Tracker")
st.caption(f"Perspective: **{selected_perspective}** | Multi-Person Household Cashflow, Bills & Savings")

# --- Top Navigation Tabs ---
tab_overview, tab_bills, tab_cards, tab_savings, tab_history = st.tabs([
    "📊 Overview & Projections",
    "📄 Bills & Income",
    "💳 Credit Cards",
    "🎯 Savings Buckets",
    "🧾 Transaction History"
])

# ==============================================================================
# TAB 1: OVERVIEW & CASHFLOW PROJECTIONS
# ==============================================================================
with tab_overview:
    # Key Summary Metrics
    total_card_balance = sum(c["balance"] for c in cards)
    total_credit_limit = sum(c["limit_amount"] for c in cards)
    utilization_pct = (total_card_balance / total_credit_limit * 100) if total_credit_limit > 0 else 0.0

    total_monthly_bills = sum(b["amount"] for b in bills if b.get("is_active", 1))
    total_savings = sum(s["current_balance"] for s in savings_buckets)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Credit Card Debt", f"${total_card_balance:,.2f}", delta=f"{utilization_pct:.1f}% Utilization", delta_color="inverse")
    m2.metric("Monthly Obligations", f"${total_monthly_bills:,.2f}", help="Total active recurring monthly obligations in this view")
    m3.metric("Savings Buckets", f"${total_savings:,.2f}", help="Sum of funds in targeted savings buckets in this view")
    m4.metric("Active Cards", f"{len(cards)} Cards", help=f"Total Credit Limit: ${total_credit_limit:,.2f}")

    st.markdown("---")

    # Projection Controls
    st.subheader("Cashflow Projection Forecast")

    col_ctrl1, col_ctrl2 = st.columns([1, 2])
    with col_ctrl1:
        starting_cash = st.number_input(
            "Current checking/liquid cash balance ($)",
            min_value=0.0,
            value=3500.0,
            step=100.0,
            format="%.2f",
            key="proj_starting_cash"
        )
    with col_ctrl2:
        forecast_days = st.segmented_control(
            "Forecast horizon",
            options=[30, 60, 90],
            default=60,
            format_func=lambda x: f"{x} Days",
            key="proj_days"
        )

    # Calculate Projections
    df_proj = proj.calculate_cashflow_projection(starting_cash, bills, income_sources, days_ahead=forecast_days)

    # Plotly Forecast Chart
    fig = go.Figure()
    
    # Balance Line
    fig.add_trace(go.Scatter(
        x=df_proj["date"],
        y=df_proj["projected_balance"],
        mode="lines+markers",
        name="Projected Balance",
        line=dict(color="#3B82F6", width=3),
        hovertemplate="<b>Date:</b> %{x|%b %d, %Y}<br><b>Projected Cash:</b> $%{y:,.2f}<extra></extra>"
    ))

    # Zero Line Baseline
    fig.add_hline(y=0, line_dash="dash", line_color="#EF4444", annotation_text="Zero Liquidity Threshold")

    fig.update_layout(
        title=f"Projected Liquid Cash Balance ({selected_perspective} - Next {forecast_days} Days)",
        xaxis_title="Date",
        yaxis_title="Balance ($)",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=400,
        margin=dict(l=20, r=20, t=40, b=20)
    )

    st.plotly_chart(fig, width="stretch")

    # Upcoming Bills Table (Next 14 Days)
    st.subheader("Upcoming Bills & Paydays (Next 14 Days)")
    df_upcoming = df_proj[(df_proj["events"] != "None") & (df_proj["date"] <= date.today() + timedelta(days=14))]
    
    if not df_upcoming.empty:
        st.dataframe(
            df_upcoming[["date_str", "events", "net_change", "projected_balance"]],
            column_config={
                "date_str": "Date",
                "events": "Scheduled Event(s)",
                "net_change": st.column_config.NumberColumn("Net Change", format="$%.2f"),
                "projected_balance": st.column_config.NumberColumn("Ending Cash", format="$%.2f"),
            },
            hide_index=True,
            width="stretch"
        )
    else:
        st.info("No scheduled bills or paydays due in the next 14 days.")


# ==============================================================================
# TAB 2: BILLS & INCOME MANAGER
# ==============================================================================
with tab_bills:
    col_b1, col_b2 = st.columns(2)

    with col_b1:
        st.subheader("Recurring Bills & Subscriptions")
        
        with st.container(border=True):
            with st.expander("➕ Add New Bill", expanded=False):
                with st.form("add_bill_form", clear_on_submit=True):
                    name = st.text_input("Bill Name", placeholder="e.g. Electric Utility")
                    amount = st.number_input("Amount ($)", min_value=0.0, step=5.0)
                    due_day = st.number_input("Due Day of Month (1-31)", min_value=1, max_value=31, value=1)
                    frequency = st.selectbox("Frequency", ["Monthly", "Bi-Weekly", "Annual"])
                    category = st.selectbox("Category", bill_categories)
                    owner = st.selectbox("Assign to Person / Household", people_list)
                    auto_pay = st.checkbox("Auto-Pay Enabled", value=False)
                    submitted = st.form_submit_button("Save Bill", icon=":material/add:")

                    if submitted and name and amount > 0:
                        db.add_bill(name, amount, due_day, frequency, category, 1 if auto_pay else 0, owner=owner)
                        st.success(f"Added bill '{name}' for {owner}!")
                        st.rerun()

        # Display Existing Bills
        if bills:
            for b in bills:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    owner_tag = f" | 👤 `{b.get('owner', 'Shared / Household')}`"
                    c1.markdown(f"**{b['name']}**  \n`:material/calendar_today:` Due: Day {b['due_day']} | `{b['category']}`{owner_tag}")
                    c2.markdown(f"### ${b['amount']:,.2f}")
                    if b['auto_pay']:
                        c2.caption("⚡ Auto-Pay Active")
                    
                    if c3.button("Delete", key=f"del_bill_{b['id']}", icon=":material/delete:"):
                        db.delete_record("bills", b['id'])
                        st.rerun()
        else:
            st.info("No recurring bills recorded for this perspective.")

    with col_b2:
        st.subheader("Income & Paydays")

        with st.container(border=True):
            with st.expander("➕ Add Income Source", expanded=False):
                with st.form("add_income_form", clear_on_submit=True):
                    source = st.text_input("Income Source", placeholder="e.g. Primary Paycheck")
                    inc_amount = st.number_input("Amount per Paycheck ($)", min_value=0.0, step=50.0)
                    inc_freq = st.selectbox("Frequency", ["Bi-Weekly", "Weekly", "Semi-Monthly", "Monthly"])
                    next_pay = st.date_input("Next Paydate", value=date.today())
                    inc_owner = st.selectbox("Assign to Person", people_list)
                    inc_submitted = st.form_submit_button("Save Income Source", icon=":material/add:")

                    if inc_submitted and source and inc_amount > 0:
                        db.add_income(source, inc_amount, inc_freq, next_pay.isoformat(), owner=inc_owner)
                        st.success(f"Added income '{source}' for {inc_owner}!")
                        st.rerun()

        # Display Income Sources
        if income_sources:
            for inc in income_sources:
                with st.container(border=True):
                    ic1, ic2, ic3 = st.columns([3, 2, 1])
                    owner_tag = f" | 👤 `{inc.get('owner', 'Shared / Household')}`"
                    ic1.markdown(f"**{inc['source']}**  \n`:material/update:` {inc['frequency']} | Next: `{inc['next_paydate']}`{owner_tag}")
                    ic2.markdown(f"### ${inc['amount']:,.2f}")

                    if ic3.button("Delete", key=f"del_inc_{inc['id']}", icon=":material/delete:"):
                        db.delete_record("income", inc['id'])
                        st.rerun()
        else:
            st.info("No income sources recorded for this perspective.")


# ==============================================================================
# TAB 3: CREDIT CARDS & UTILIZATION
# ==============================================================================
with tab_cards:
    st.subheader("Credit Card Balances & Utilization")

    with st.container(border=True):
        with st.expander("➕ Add New Credit Card", expanded=False):
            with st.form("add_card_form", clear_on_submit=True):
                card_name = st.text_input("Card Name", placeholder="e.g. Amex Gold")
                card_balance = st.number_input("Current Balance ($)", min_value=0.0, step=10.0)
                card_limit = st.number_input("Credit Limit ($)", min_value=1.0, step=100.0, value=5000.0)
                card_apr = st.number_input("APR (%)", min_value=0.0, step=0.1, value=19.99)
                card_stmt_day = st.number_input("Statement Day", min_value=1, max_value=31, value=1)
                card_due_day = st.number_input("Payment Due Day", min_value=1, max_value=31, value=15)
                card_min_pay = st.number_input("Minimum Payment ($)", min_value=0.0, step=5.0, value=25.0)
                card_owner = st.selectbox("Card Owner", people_list)
                
                card_submitted = st.form_submit_button("Save Credit Card", icon=":material/add:")

                if card_submitted and card_name:
                    db.add_card(card_name, card_balance, card_limit, card_apr, card_stmt_day, card_due_day, card_min_pay, owner=card_owner)
                    st.success(f"Added card '{card_name}' for {card_owner}!")
                    st.rerun()

    if cards:
        grid_cols = st.columns(len(cards) if len(cards) <= 3 else 3)
        for i, card in enumerate(cards):
            col_target = grid_cols[i % len(grid_cols)]
            with col_target:
                with st.container(border=True):
                    util = (card['balance'] / card['limit_amount'] * 100) if card['limit_amount'] > 0 else 0
                    st.markdown(f"### 💳 {card['name']}")
                    st.caption(f"Owner: 👤 `{card.get('owner', 'Shared / Household')}`")
                    st.markdown(f"**Balance:** `${card['balance']:,.2f}` / `${card['limit_amount']:,.2f}`")
                    st.progress(min(util / 100.0, 1.0), text=f"Utilization: {util:.1f}%")

                    st.caption(f"APR: {card['apr']}% | Due Day: {card['due_day']} | Min Pay: ${card['minimum_payment']:,.2f}")

                    # Balance update popover
                    with st.popover("Edit Balance / Details", icon=":material/edit:"):
                        new_bal = st.number_input("Update Balance ($)", value=float(card['balance']), key=f"nb_{card['id']}")
                        new_limit = st.number_input("Update Limit ($)", value=float(card['limit_amount']), key=f"nl_{card['id']}")
                        new_card_owner = st.selectbox("Card Owner", people_list, index=people_list.index(card.get('owner', 'Shared / Household')) if card.get('owner') in people_list else 0, key=f"no_{card['id']}")
                        if st.button("Save Changes", key=f"save_card_{card['id']}"):
                            db.update_card(
                                card['id'], card['name'], new_bal, new_limit, 
                                card['apr'], card['statement_day'], card['due_day'], card['minimum_payment'], owner=new_card_owner
                            )
                            db.log_transaction("Card Update", new_bal, f"Updated balance for {card['name']}", card['name'], owner=new_card_owner)
                            st.rerun()

                    if st.button("Delete Card", key=f"del_card_{card['id']}", icon=":material/delete:"):
                        db.delete_record("cards", card['id'])
                        st.rerun()
    else:
        st.info("No credit cards recorded for this perspective.")


# ==============================================================================
# TAB 4: SAVINGS BUCKETS (SINKING FUNDS)
# ==============================================================================
with tab_savings:
    st.subheader("Target Savings Buckets")

    with st.container(border=True):
        with st.expander("➕ Create New Savings Bucket", expanded=False):
            with st.form("add_bucket_form", clear_on_submit=True):
                bucket_name = st.text_input("Bucket Name", placeholder="e.g. Emergency Fund")
                bucket_target = st.number_input("Target Goal ($)", min_value=1.0, step=100.0, value=1000.0)
                bucket_curr = st.number_input("Current Balance ($)", min_value=0.0, step=50.0, value=0.0)
                bucket_cat = st.selectbox("Category", savings_categories)
                bucket_owner = st.selectbox("Assign Owner", people_list)
                bucket_icon = st.selectbox("Icon", [":material/shield:", ":material/flight_takeoff:", ":material/build:", ":material/home:", ":material/savings:", ":material/trending_up:"])

                bucket_submitted = st.form_submit_button("Save Savings Bucket", icon=":material/add:")

                if bucket_submitted and bucket_name:
                    db.add_savings_bucket(bucket_name, bucket_target, bucket_curr, bucket_cat, owner=bucket_owner, icon=bucket_icon)
                    st.success(f"Created bucket '{bucket_name}'!")
                    st.rerun()

    if savings_buckets:
        s_cols = st.columns(len(savings_buckets) if len(savings_buckets) <= 3 else 3)
        for idx, bucket in enumerate(savings_buckets):
            col_target = s_cols[idx % len(s_cols)]
            with col_target:
                with st.container(border=True):
                    prog = (bucket['current_balance'] / bucket['target_amount'] * 100) if bucket['target_amount'] > 0 else 0
                    st.markdown(f"### {bucket.get('icon', ':material/savings:')} {bucket['name']}")
                    st.caption(f"Owner: 👤 `{bucket.get('owner', 'Shared / Household')}` | Category: `{bucket['category']}`")
                    st.markdown(f"**Saved:** `${bucket['current_balance']:,.2f}` of `${bucket['target_amount']:,.2f}`")
                    st.progress(min(prog / 100.0, 1.0), text=f"Progress: {prog:.1f}%")

                    # Deposit / Withdraw Controls
                    d_col, w_col = st.columns(2)
                    with d_col:
                        with st.popover("➕ Deposit", icon=":material/add:"):
                            dep_amt = st.number_input("Deposit ($)", min_value=1.0, step=10.0, key=f"dep_{bucket['id']}")
                            if st.button("Add Funds", key=f"btn_dep_{bucket['id']}"):
                                db.update_savings_balance(bucket['id'], dep_amt)
                                db.log_transaction("Savings Deposit", dep_amt, f"Deposited to {bucket['name']}", bucket['name'], owner=bucket.get('owner', 'Shared / Household'))
                                st.rerun()

                    with w_col:
                        with st.popover("➖ Withdraw", icon=":material/remove:"):
                            wth_amt = st.number_input("Withdraw ($)", min_value=1.0, step=10.0, key=f"wth_{bucket['id']}")
                            if st.button("Withdraw Funds", key=f"btn_wth_{bucket['id']}"):
                                db.update_savings_balance(bucket['id'], -wth_amt)
                                db.log_transaction("Savings Withdrawal", wth_amt, f"Withdrew from {bucket['name']}", bucket['name'], owner=bucket.get('owner', 'Shared / Household'))
                                st.rerun()

                    if st.button("Delete Bucket", key=f"del_bucket_{bucket['id']}", icon=":material/delete:"):
                        db.delete_record("savings_buckets", bucket['id'])
                        st.rerun()
    else:
        st.info("No savings buckets recorded for this perspective.")


# ==============================================================================
# TAB 5: TRANSACTION HISTORY
# ==============================================================================
with tab_history:
    st.subheader("Transaction & Activity Log")

    if transactions:
        df_trans = pd.DataFrame(transactions)
        st.dataframe(
            df_trans[["created_at", "type", "amount", "description", "reference_name", "owner"]],
            column_config={
                "created_at": "Timestamp",
                "type": "Type",
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                "description": "Description",
                "reference_name": "Reference",
                "owner": "Owner / Perspective"
            },
            hide_index=True,
            width="stretch"
        )
    else:
        st.info("No transactions logged for this perspective.")
