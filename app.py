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

# --- Cross-Browser Modal Dialog for Delete Confirmation ---
@st.dialog("⚠️ Confirm Deletion")
def confirm_delete_dialog(table_name, record_id, record_name, display_title="Record"):
    st.warning(f"Are you sure you want to delete **{record_name}** ({display_title})?")
    st.markdown("This action **cannot be undone** and will permanently remove this record.")
    
    col_cancel, col_del = st.columns(2)
    with col_cancel:
        if st.button("Cancel", key=f"dlg_cancel_{table_name}_{record_id}", use_container_width=True):
            if "delete_target" in st.session_state:
                del st.session_state["delete_target"]
            st.rerun()
    with col_del:
        if st.button("🔥 Yes, Delete", key=f"dlg_confirm_{table_name}_{record_id}", type="primary", use_container_width=True):
            db.delete_record(table_name, record_id)
            if "delete_target" in st.session_state:
                del st.session_state["delete_target"]
            st.success(f"Deleted '{record_name}'!")
            st.rerun()

if "delete_target" in st.session_state:
    target_table, target_id, target_name, target_type = st.session_state["delete_target"]
    confirm_delete_dialog(target_table, target_id, target_name, target_type)

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
    
    # Household Members & Contact Info Management
    with st.expander("👥 Manage Household Members & Contacts"):
        all_people_details = db.fetch_people_details()
        
        for p in all_people_details:
            with st.container(border=True):
                p_name = p['name']
                p_email = p.get('email', '')
                p_phone = p.get('phone', '')
                p_notify = bool(p.get('notify_bills', 1))

                st.markdown(f"**👤 {p_name}**")
                if p_email or p_phone:
                    email_str = f"📧 `{p_email}`" if p_email else ""
                    phone_str = f"📱 `{p_phone}`" if p_phone else ""
                    st.caption(f"{email_str} {phone_str}")
                
                notify_badge = "🔔 Bill Notifications ON" if p_notify else "🔕 Notifications OFF"
                st.caption(notify_badge)

                # Edit Member Details Popover
                if p_name != "Shared / Household":
                    with st.popover("Edit Contact Info", icon=":material/edit:"):
                        ep_name = st.text_input("Name", value=p_name, key=f"ep_n_{p['id']}")
                        ep_email = st.text_input("Email", value=p_email, key=f"ep_e_{p['id']}")
                        ep_phone = st.text_input("Phone Number", value=p_phone, key=f"ep_p_{p['id']}")
                        ep_notify = st.checkbox("Receive Bill Notifications", value=p_notify, key=f"ep_notif_{p['id']}")
                        ep_notes = st.text_area("Notes", value=p.get('notes', ''), key=f"ep_notes_{p['id']}")

                        if st.button("Save Member Changes", key=f"btn_save_p_{p['id']}"):
                            db.update_person(p['id'], ep_name, ep_email, ep_phone, 1 if ep_notify else 0, ep_notes)
                            st.success("Member details updated!")
                            st.rerun()

                    if st.button("Remove Member", key=f"btn_del_p_{p['id']}", icon=":material/delete:"):
                        st.session_state["delete_target"] = ("people", p['id'], p_name, "Household Member")
                        st.rerun()

        st.markdown("---")
        st.markdown("**➕ Add New Member**")
        with st.form("add_person_form", clear_on_submit=True):
            new_p_name = st.text_input("Member Name", placeholder="e.g. Aimee")
            new_p_email = st.text_input("Email Address", placeholder="aimee@example.com")
            new_p_phone = st.text_input("Phone Number", placeholder="(555) 123-4567")
            new_p_notify = st.checkbox("Receive Bill Notifications", value=True)
            new_p_submit = st.form_submit_button("Add Member", icon=":material/person_add:")

            if new_p_submit and new_p_name.strip():
                db.add_person(new_p_name.strip(), new_p_email, new_p_phone, 1 if new_p_notify else 0)
                st.success(f"Added member '{new_p_name.strip()}'!")
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

# --- File Parser for Credit Card Uploads ---
def parse_card_upload(uploaded_file, default_owner="Shared / Household"):
    try:
        filename = uploaded_file.name.lower()
        if filename.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(uploaded_file)
        else:
            return None, "Unsupported file format. Please upload a CSV or Excel file (.csv, .xlsx, .xls)."
    except Exception as e:
        return None, f"Failed to parse file: {str(e)}"

    if df.empty:
        return None, "Uploaded file contains no data rows."

    # Standardize column headers
    df.columns = [str(c).strip().lower().replace("_", " ") for c in df.columns]

    cards_to_add = []
    for idx, row in df.iterrows():
        # Find card name column
        name_val = None
        for col in ["card name", "card", "name", "label", "account"]:
            if col in row and pd.notna(row[col]):
                name_val = str(row[col]).strip()
                break
        
        if not name_val:
            continue

        # Trailing Last 4 Digits / Account Identifier
        last4_val = None
        for col in ["last 4", "last4", "card number", "account number", "ending in", "last four", "trailing digits"]:
            if col in row and pd.notna(row[col]):
                try:
                    cleaned_l4 = str(row[col]).replace("...", "").replace("(", "").replace(")", "").strip()
                    if cleaned_l4.endswith(".0"):
                        cleaned_l4 = str(int(float(cleaned_l4)))
                    if cleaned_l4:
                        last4_val = cleaned_l4
                except ValueError:
                    pass
                break

        # Format card name with trailing identifier if provided and not already included
        if last4_val and last4_val not in name_val:
            name_val = f"{name_val} (...{last4_val})"

        # Balance
        bal_val = 0.0
        for col in ["balance", "current balance", "amount", "bal", "owed"]:
            if col in row and pd.notna(row[col]):
                try:
                    cleaned_str = str(row[col]).replace("$", "").replace(",", "").strip()
                    bal_val = float(cleaned_str)
                except ValueError:
                    bal_val = 0.0
                break

        # Limit
        limit_val = 5000.0
        for col in ["limit", "credit limit", "limit amount", "max"]:
            if col in row and pd.notna(row[col]):
                try:
                    cleaned_str = str(row[col]).replace("$", "").replace(",", "").strip()
                    limit_val = float(cleaned_str)
                except ValueError:
                    limit_val = 5000.0
                break

        # APR
        apr_val = 19.99
        for col in ["apr", "interest", "rate", "apr (%)"]:
            if col in row and pd.notna(row[col]):
                try:
                    cleaned_str = str(row[col]).replace("%", "").strip()
                    apr_val = float(cleaned_str)
                except ValueError:
                    apr_val = 19.99
                break

        # Statement Day
        stmt_val = 1
        for col in ["statement day", "statement", "cycle day"]:
            if col in row and pd.notna(row[col]):
                try:
                    stmt_val = int(float(row[col]))
                except ValueError:
                    stmt_val = 1
                break

        # Due Day
        due_val = 15
        for col in ["due day", "payment due day", "due"]:
            if col in row and pd.notna(row[col]):
                try:
                    due_val = int(float(row[col]))
                except ValueError:
                    due_val = 15
                break

        # Min Payment
        min_val = 25.0
        for col in ["minimum payment", "min payment", "min pay", "min"]:
            if col in row and pd.notna(row[col]):
                try:
                    cleaned_str = str(row[col]).replace("$", "").replace(",", "").strip()
                    min_val = float(cleaned_str)
                except ValueError:
                    min_val = 25.0
                break

        # Owner
        owner_val = default_owner
        for col in ["owner", "person", "member", "assigned to"]:
            if col in row and pd.notna(row[col]):
                owner_val = str(row[col]).strip()
                break

        cards_to_add.append({
            "name": name_val,
            "balance": bal_val,
            "limit_amount": limit_val,
            "apr": apr_val,
            "statement_day": max(1, min(31, stmt_val)),
            "due_day": max(1, min(31, due_val)),
            "minimum_payment": min_val,
            "owner": owner_val
        })

    if not cards_to_add:
        return None, "No valid card rows found. Ensure the spreadsheet contains a column header for 'Card Name' or 'Name'."

    return cards_to_add, None

# --- File Parser for Bank Account Uploads ---
def parse_bank_account_upload(uploaded_file, default_owner="Shared / Household"):
    try:
        filename = uploaded_file.name.lower()
        if filename.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(uploaded_file)
        else:
            return None, "Unsupported file format. Please upload a CSV or Excel file (.csv, .xlsx, .xls)."
    except Exception as e:
        return None, f"Failed to parse file: {str(e)}"

    if df.empty:
        return None, "Uploaded file contains no data rows."

    # Standardize column headers
    df.columns = [str(c).strip().lower().replace("_", " ") for c in df.columns]

    accounts_to_add = []
    for idx, row in df.iterrows():
        # Find account name / label column
        name_val = None
        for col in ["account label", "account name", "account", "label", "name"]:
            if col in row and pd.notna(row[col]):
                name_val = str(row[col]).strip()
                break
        
        if not name_val:
            continue

        # Bank Name
        bank_val = "Chase Bank"
        for col in ["bank name", "bank", "financial institution", "institution"]:
            if col in row and pd.notna(row[col]):
                bank_val = str(row[col]).strip()
                break

        # Account Type
        type_val = "Checking"
        for col in ["account type", "type"]:
            if col in row and pd.notna(row[col]):
                val = str(row[col]).strip().title()
                if "Savings" in val:
                    type_val = "Savings"
                elif "Money" in val or "Market" in val:
                    type_val = "Money Market"
                else:
                    type_val = "Checking"
                break

        # Last 4 / Account Number
        acct_num_val = ""
        for col in ["last 4", "last4", "account number", "acct #", "account #", "ending in", "trailing digits"]:
            if col in row and pd.notna(row[col]):
                try:
                    cleaned = str(row[col]).replace("...", "").replace("(", "").replace(")", "").strip()
                    if cleaned.endswith(".0"):
                        cleaned = str(int(float(cleaned)))
                    acct_num_val = cleaned
                except ValueError:
                    acct_num_val = str(row[col]).strip()
                break

        # Routing Number
        routing_val = ""
        for col in ["routing number", "routing", "routing #", "aba"]:
            if col in row and pd.notna(row[col]):
                try:
                    cleaned_r = str(row[col]).strip()
                    if cleaned_r.endswith(".0"):
                        cleaned_r = str(int(float(cleaned_r)))
                    routing_val = cleaned_r
                except ValueError:
                    routing_val = str(row[col]).strip()
                break

        # Current Balance
        bal_val = 0.0
        for col in ["current balance", "balance", "amount", "bal"]:
            if col in row and pd.notna(row[col]):
                try:
                    cleaned_str = str(row[col]).replace("$", "").replace(",", "").strip()
                    bal_val = float(cleaned_str)
                except ValueError:
                    bal_val = 0.0
                break

        # Owner
        owner_val = default_owner
        for col in ["owner", "person", "member", "assigned to"]:
            if col in row and pd.notna(row[col]):
                owner_val = str(row[col]).strip()
                break

        # Notes
        notes_val = ""
        for col in ["notes", "description", "memo"]:
            if col in row and pd.notna(row[col]):
                notes_val = str(row[col]).strip()
                break

        # Append last 4 onto name if provided and not already included
        if acct_num_val and f"(...{acct_num_val})" not in name_val and acct_num_val not in name_val:
            name_val = f"{name_val} (...{acct_num_val})"

        accounts_to_add.append({
            "name": name_val,
            "bank_name": bank_val,
            "account_type": type_val,
            "account_number": acct_num_val,
            "routing_number": routing_val,
            "current_balance": bal_val,
            "owner": owner_val,
            "notes": notes_val
        })

    if not accounts_to_add:
        return None, "No valid bank account rows found. Ensure the spreadsheet contains a column header for 'Account Label' or 'Name'."

    return accounts_to_add, None

# --- Fetch Data & Apply Filter ---
raw_accounts = db.fetch_all("bank_accounts")
raw_cards = db.fetch_all("cards")
raw_bills = db.fetch_all("bills")
raw_income = db.fetch_all("income")
raw_buckets = db.fetch_all("savings_buckets")
raw_transactions = db.fetch_all("transactions")

bank_accounts = filter_by_owner(raw_accounts)
cards = filter_by_owner(raw_cards)
bills = filter_by_owner(raw_bills)
income_sources = filter_by_owner(raw_income)
savings_buckets = filter_by_owner(raw_buckets)
transactions = filter_by_owner(raw_transactions)

bill_categories = db.fetch_categories("bill")
savings_categories = db.fetch_categories("savings")

# --- Title Header ---
st.title("💰 Money Tracker")
st.caption(f"Perspective: **{selected_perspective}** | Multi-Person Household Cashflow, Bank Accounts & Savings")

# --- Top Navigation Tabs ---
tab_overview, tab_accounts, tab_cards, tab_bills, tab_savings, tab_history = st.tabs([
    "📊 Overview & Projections",
    "🏛️ Bank Accounts",
    "💳 Credit Cards",
    "📄 Bills & Income",
    "🎯 Savings Buckets",
    "🧾 Transaction History"
])

# ==============================================================================
# TAB 1: OVERVIEW & CASHFLOW PROJECTIONS
# ==============================================================================
with tab_overview:
    total_bank_cash = sum(ba["current_balance"] for ba in bank_accounts)
    total_card_balance = sum(c["balance"] for c in cards)
    total_credit_limit = sum(c["limit_amount"] for c in cards)
    utilization_pct = (total_card_balance / total_credit_limit * 100) if total_credit_limit > 0 else 0.0

    total_monthly_bills = sum(b["amount"] for b in bills if b.get("is_active", 1))
    total_savings = sum(s["current_balance"] for s in savings_buckets)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Liquid Bank Cash", f"${total_bank_cash:,.2f}", help="Sum of checking & savings account balances")
    m2.metric("Credit Card Debt", f"${total_card_balance:,.2f}", delta=f"{utilization_pct:.1f}% Utilization", delta_color="inverse")
    m3.metric("Monthly Bills", f"${total_monthly_bills:,.2f}", help="Total active recurring monthly obligations")
    m4.metric("Savings Buckets", f"${total_savings:,.2f}", help="Sum of allocated funds in savings target buckets")

    st.markdown("---")

    # Projection Controls
    st.subheader("Cashflow Projection Forecast")

    col_ctrl1, col_ctrl2 = st.columns([1, 2])
    with col_ctrl1:
        starting_cash = st.number_input(
            "Starting Cash Balance for Forecast ($)",
            min_value=0.0,
            value=float(total_bank_cash) if total_bank_cash > 0 else 2500.0,
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
    
    fig.add_trace(go.Scatter(
        x=df_proj["date"],
        y=df_proj["projected_balance"],
        mode="lines+markers",
        name="Projected Balance",
        line=dict(color="#3B82F6", width=3),
        hovertemplate="<b>Date:</b> %{x|%b %d, %Y}<br><b>Projected Cash:</b> $%{y:,.2f}<extra></extra>"
    ))

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

    st.plotly_chart(fig, use_container_width=True)

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
            use_container_width=True
        )
    else:
        st.info("No scheduled bills or paydays due in the next 14 days.")


# ==============================================================================
# TAB 2: BANK ACCOUNTS (PARENT ENTITY)
# ==============================================================================
with tab_accounts:
    st.subheader("Bank Accounts & Liquidity")

    with st.container(border=True):
        col_add_ba, col_imp_ba = st.columns(2)

        with col_add_ba:
            with st.expander("➕ Add Single Bank Account", expanded=False):
                with st.form("add_account_form", clear_on_submit=True):
                    ba_name = st.text_input("Account Label", placeholder="e.g. Primary Checking or High-Yield Savings")
                    ba_bank = st.text_input("Bank Name", placeholder="e.g. Chase Bank, Capital One, Ally")
                    ba_type = st.selectbox("Account Type", ["Checking", "Savings", "Money Market"])
                    ba_acct_num = st.text_input("Account # / Last 4", placeholder="e.g. ...4012")
                    ba_routing = st.text_input("Routing Number", placeholder="e.g. 021000021")
                    ba_balance = st.number_input("Current Balance ($)", min_value=0.0, step=50.0, value=1000.0)
                    ba_owner = st.selectbox("Account Owner", people_list)
                    ba_notes = st.text_area("Notes", placeholder="Optional details or branch info")

                    ba_submitted = st.form_submit_button("Save Bank Account", icon=":material/add:")

                    if ba_submitted and ba_name and ba_bank:
                        db.add_bank_account(ba_name, ba_bank, ba_type, ba_acct_num, ba_routing, ba_balance, owner=ba_owner, notes=ba_notes)
                        st.success(f"Added Bank Account '{ba_name}'!")
                        st.rerun()

        with col_imp_ba:
            with st.expander("📥 Import Bank Accounts (CSV / Excel)", expanded=False):
                st.markdown("Upload a CSV or Excel spreadsheet to import multiple bank accounts.")
                
                # Sample CSV Download
                sample_ba_csv = "Account Label,Bank Name,Account Type,Last 4,Routing Number,Current Balance,Owner\nPrimary Checking,Chase Bank,Checking,4012,021000021,5200.00,Peter\nHigh-Yield Savings,Capital One,Savings,8821,031100649,12500.00,Aimee\n"
                st.download_button(
                    "📥 Download CSV Template",
                    data=sample_ba_csv,
                    file_name="bank_accounts_template.csv",
                    mime="text/csv",
                    key="btn_dl_ba_template"
                )

                uploaded_ba_file = st.file_uploader("Upload CSV or Excel File", type=["csv", "xlsx", "xls"], key="ba_file_uploader")
                
                if uploaded_ba_file is not None:
                    def_ba_owner = active_person if active_person != "ALL" else "Shared / Household"
                    parsed_accounts, parse_ba_error = parse_bank_account_upload(uploaded_ba_file, default_owner=def_ba_owner)
                    
                    if parse_ba_error:
                        st.error(parse_ba_error)
                    elif parsed_accounts:
                        st.success(f"Parsed {len(parsed_accounts)} bank account(s)!")
                        df_ba_preview = pd.DataFrame(parsed_accounts)
                        st.dataframe(df_ba_preview, use_container_width=True, hide_index=True)

                        if st.button("Import Bank Accounts Now", key="btn_confirm_ba_import", icon=":material/file_upload:"):
                            count_ba_added = 0
                            for ba in parsed_accounts:
                                owner_name = ba.get("owner") or def_ba_owner
                                # Auto-register new person if not in household table
                                if owner_name and owner_name not in people_list:
                                    db.add_person(owner_name)
                                
                                db.add_bank_account(
                                    ba["name"], ba["bank_name"], ba["account_type"], ba["account_number"],
                                    ba["routing_number"], ba["current_balance"], owner=owner_name, notes=ba.get("notes", "")
                                )
                                count_ba_added += 1
                            st.success(f"Successfully imported {count_ba_added} bank account(s)!")
                            st.rerun()

    if bank_accounts:
        ba_cols = st.columns(len(bank_accounts) if len(bank_accounts) <= 3 else 3)
        for idx, ba in enumerate(bank_accounts):
            col_target = ba_cols[idx % len(ba_cols)]
            with col_target:
                with st.container(border=True):
                    # Fetch child buckets linked to this bank account
                    child_buckets = [b for b in raw_buckets if b.get("bank_account_name") == ba["name"]]
                    allocated_cash = sum(b["current_balance"] for b in child_buckets)
                    unallocated_cash = ba["current_balance"] - allocated_cash

                    # Fetch linked ACH bills
                    linked_ach_bills = [b for b in raw_bills if b.get("payment_detail") == ba["name"] and b.get("is_active", 1)]
                    ach_monthly = sum(b["amount"] for b in linked_ach_bills)

                    icon_type = "🏦" if ba["account_type"] == "Checking" else "💰"
                    st.markdown(f"### {icon_type} {ba['name']}")
                    st.caption(f"Bank: **{ba['bank_name']}** | Type: `{ba['account_type']}` | Owner: 👤 `{ba.get('owner', 'Shared / Household')}`")
                    
                    if ba.get("account_number") or ba.get("routing_number"):
                        st.caption(f"Acct #: `{ba.get('account_number', 'N/A')}` | Routing: `{ba.get('routing_number', 'N/A')}`")

                    b1, b2 = st.columns(2)
                    b1.metric("Total Balance", f"${ba['current_balance']:,.2f}")
                    b2.metric("Unallocated", f"${unallocated_cash:,.2f}", help="Total Balance minus funds allocated to child savings buckets")

                    # Parent-Child View: Display Child Savings Buckets
                    with st.expander(f"🎯 Linked Savings Buckets ({len(child_buckets)})", expanded=True if child_buckets else False):
                        if child_buckets:
                            for cb in child_buckets:
                                cb_prog = (cb['current_balance'] / cb['target_amount'] * 100) if cb['target_amount'] > 0 else 0
                                st.markdown(f"**{cb.get('icon', '🎯')} {cb['name']}** - `${cb['current_balance']:,.2f}` / `${cb['target_amount']:,.2f}` (`{cb_prog:.0f}%`)")
                                st.progress(min(cb_prog / 100.0, 1.0))
                        else:
                            st.caption("No savings buckets currently assigned to this bank account.")

                    # Linked ACH Bills
                    linked_ach_bills = [
                        b for b in raw_bills 
                        if b.get("is_active", 1) and (
                            b.get("payment_detail") == ba["name"] or
                            (b.get("payment_detail") and ba["name"].lower() in b.get("payment_detail").lower()) or
                            (b.get("payment_detail") and b.get("payment_detail").lower() in ba["name"].lower())
                        )
                    ]
                    ach_monthly = sum(b["amount"] for b in linked_ach_bills)

                    with st.expander(f"📄 Linked ACH Bills ({len(linked_ach_bills)}) - ${ach_monthly:,.2f}/mo", expanded=True):
                        if linked_ach_bills:
                            for ab in linked_ach_bills:
                                l_col1, l_col2 = st.columns([3, 1])
                                l_col1.markdown(f"• **{ab['name']}** - `${ab['amount']:,.2f}`/mo (Due Day {ab['due_day']} | 👤 `{ab.get('owner', 'Shared')}`)")
                                if l_col2.button("Unlink", key=f"unlink_ach_{ba['id']}_{ab['id']}", icon=":material/link_off:"):
                                    db.update_bill(
                                        ab['id'], ab['name'], ab['amount'], ab['due_day'], ab['frequency'], ab['category'],
                                        ab['auto_pay'], owner=ab.get('owner', 'Shared / Household'),
                                        payment_method="ACH / Checking Account", payment_detail="", is_active=ab.get('is_active', 1)
                                    )
                                    st.rerun()
                        else:
                            st.caption("No recurring ACH bills currently linked to this bank account.")

                        # Link Unlinked Bill Popover directly from the Bank Account Card!
                        candidate_ach_bills = [b for b in raw_bills if b not in linked_ach_bills]
                        if candidate_ach_bills:
                            with st.popover("🔗 Link an ACH Bill to this Account", icon=":material/link:"):
                                bill_map = {f"#{b['id']} - {b['name']} (${b['amount']:,.2f}/mo)": b['id'] for b in candidate_ach_bills}
                                selected_label = st.selectbox("Select Bill to Link", list(bill_map.keys()), key=f"sel_link_ach_{ba['id']}")
                                if st.button("Link Bill to Account", key=f"btn_link_ach_{ba['id']}"):
                                    target_id = bill_map[selected_label]
                                    target_bill = next(b for b in raw_bills if b["id"] == target_id)
                                    db.update_bill(
                                        target_bill['id'], target_bill['name'], target_bill['amount'], target_bill['due_day'],
                                        target_bill['frequency'], target_bill['category'], target_bill['auto_pay'],
                                        owner=target_bill.get('owner', 'Shared / Household'),
                                        payment_method="ACH / Checking Account", payment_detail=ba["name"],
                                        is_active=target_bill.get('is_active', 1)
                                    )
                                    st.success(f"Linked '{target_bill['name']}' to {ba['name']}!")
                                    st.rerun()

                    # Edit & Delete Popovers
                    with st.popover("Edit Account Details", icon=":material/edit:"):
                        e_name = st.text_input("Name", value=ba['name'], key=f"eba_n_{ba['id']}")
                        e_bank = st.text_input("Bank", value=ba['bank_name'], key=f"eba_b_{ba['id']}")
                        
                        type_opts = ["Checking", "Savings", "Money Market"]
                        e_type = st.selectbox("Type", type_opts, index=type_opts.index(ba.get('account_type', 'Checking')) if ba.get('account_type') in type_opts else 0, key=f"eba_t_{ba['id']}")
                        
                        e_acct = st.text_input("Account #", value=ba.get('account_number', ''), key=f"eba_a_{ba['id']}")
                        e_rout = st.text_input("Routing #", value=ba.get('routing_number', ''), key=f"eba_r_{ba['id']}")
                        e_bal = st.number_input("Current Balance ($)", value=float(ba['current_balance']), min_value=0.0, step=50.0, key=f"eba_bal_{ba['id']}")
                        e_owner = st.selectbox("Owner", people_list, index=people_list.index(ba.get('owner', 'Shared / Household')) if ba.get('owner') in people_list else 0, key=f"eba_o_{ba['id']}")

                        if st.button("Save Account Changes", key=f"save_ba_{ba['id']}"):
                            db.update_bank_account(ba['id'], e_name, e_bank, e_type, e_acct, e_rout, e_bal, owner=e_owner)
                            db.log_transaction("Account Update", e_bal, f"Updated balance for {e_name}", e_name, owner=e_owner)
                            st.rerun()

                    if st.button("Delete Account", key=f"del_ba_{ba['id']}", icon=":material/delete:"):
                        st.session_state["delete_target"] = ("bank_accounts", ba['id'], ba['name'], "Bank Account")
                        st.rerun()
    else:
        st.info("No bank accounts recorded for this perspective.")


# ==============================================================================
# TAB 3: CREDIT CARDS & UTILIZATION
# ==============================================================================
with tab_cards:
    st.subheader("Credit Card Balances & Utilization")

    with st.container(border=True):
        col_add_c, col_imp_c = st.columns(2)

        with col_add_c:
            with st.expander("➕ Add Single Credit Card", expanded=False):
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

        with col_imp_c:
            with st.expander("📥 Import Credit Cards (CSV / Excel)", expanded=False):
                st.markdown("Upload a CSV or Excel spreadsheet to import multiple credit cards.")
                
                # Sample CSV Download
                sample_csv = "Card Name,Last 4,Balance,Limit,APR,Statement Day,Due Day,Min Payment,Owner\nAmex Gold,8006,1250.00,10000.00,24.99,5,25,100.00,Peter\nChase Sapphire,1934,450.00,8000.00,21.49,12,2,35.00,Aimee\n"
                st.download_button(
                    "📥 Download CSV Template",
                    data=sample_csv,
                    file_name="credit_cards_template.csv",
                    mime="text/csv",
                    key="btn_dl_card_template"
                )

                uploaded_card_file = st.file_uploader("Upload CSV or Excel File", type=["csv", "xlsx", "xls"], key="card_file_uploader")
                
                if uploaded_card_file is not None:
                    def_owner = active_person if active_person != "ALL" else "Shared / Household"
                    parsed_cards, parse_error = parse_card_upload(uploaded_card_file, default_owner=def_owner)
                    
                    if parse_error:
                        st.error(parse_error)
                    elif parsed_cards:
                        st.success(f"Parsed {len(parsed_cards)} card(s)!")
                        df_preview = pd.DataFrame(parsed_cards)
                        st.dataframe(df_preview, use_container_width=True, hide_index=True)

                        if st.button("Import Cards Now", key="btn_confirm_card_import", icon=":material/file_upload:"):
                            count_added = 0
                            for c in parsed_cards:
                                owner_name = c.get("owner") or def_owner
                                # Auto-register new person if not in household table
                                if owner_name and owner_name not in people_list:
                                    db.add_person(owner_name)
                                
                                db.add_card(
                                    c["name"], c["balance"], c["limit_amount"], c["apr"],
                                    c["statement_day"], c["due_day"], c["minimum_payment"], owner=owner_name
                                )
                                count_added += 1
                            st.success(f"Successfully imported {count_added} credit card(s)!")
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

                    # Linked Auto-Pay Bills
                    card_linked_bills = [
                        b for b in raw_bills 
                        if b.get("is_active", 1) and (
                            b.get("payment_detail") == card["name"] or
                            (b.get("payment_detail") and card["name"].lower() in b.get("payment_detail").lower()) or
                            (b.get("payment_detail") and b.get("payment_detail").lower() in card["name"].lower())
                        )
                    ]
                    card_monthly = sum(b["amount"] for b in card_linked_bills)
                    
                    with st.expander(f"📄 Linked Auto-Pay Bills ({len(card_linked_bills)}) - ${card_monthly:,.2f}/mo", expanded=True if card_linked_bills else False):
                        if card_linked_bills:
                            for cb in card_linked_bills:
                                c_col1, c_col2 = st.columns([3, 1])
                                c_col1.markdown(f"• **{cb['name']}** - `${cb['amount']:,.2f}`/mo (Due Day {cb['due_day']})")
                                if c_col2.button("Unlink", key=f"unlink_card_{card['id']}_{cb['id']}", icon=":material/link_off:"):
                                    db.update_bill(
                                        cb['id'], cb['name'], cb['amount'], cb['due_day'], cb['frequency'], cb['category'],
                                        cb['auto_pay'], owner=cb.get('owner', 'Shared / Household'),
                                        payment_method="Manual Check / Cash", payment_detail="", is_active=cb.get('is_active', 1)
                                    )
                                    st.rerun()

                        # Link Bill to Credit Card Popover
                        unlinked_card_bills = [b for b in raw_bills if b not in card_linked_bills]
                        if unlinked_card_bills:
                            with st.popover("🔗 Link a Bill to this Credit Card", icon=":material/link:"):
                                card_bill_to_link = st.selectbox("Select Bill", [f"{b['name']} (${b['amount']:,.2f}/mo)" for b in unlinked_card_bills], key=f"sel_link_card_{card['id']}")
                                if st.button("Link Bill to Card", key=f"btn_link_card_{card['id']}"):
                                    selected_cb_name = card_bill_to_link.split(" ($")[0]
                                    target_cb = next(b for b in unlinked_card_bills if b["name"] == selected_cb_name)
                                    db.update_bill(
                                        target_cb['id'], target_cb['name'], target_cb['amount'], target_cb['due_day'],
                                        target_cb['frequency'], target_cb['category'], target_cb['auto_pay'],
                                        owner=target_cb.get('owner', 'Shared / Household'),
                                        payment_method="Credit Card", payment_detail=card["name"],
                                        is_active=target_cb.get('is_active', 1)
                                    )
                                    st.success(f"Linked '{target_cb['name']}' to {card['name']}!")
                                    st.rerun()

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
                        st.session_state["delete_target"] = ("cards", card['id'], card['name'], "Credit Card")
                        st.rerun()
    else:
        st.info("No credit cards recorded for this perspective.")


# ==============================================================================
# TAB 4: BILLS & INCOME MANAGER
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
                    
                    pay_method = st.selectbox("Payment Method", ["ACH / Checking Account", "Credit Card", "Debit Card", "Manual Check / Cash"])
                    
                    bank_names = [ba["name"] for ba in raw_accounts]
                    card_names = [c["name"] for c in raw_cards]
                    
                    if pay_method in ["ACH / Checking Account", "Debit Card"] and bank_names:
                        pay_detail = st.selectbox("Linked Bank Account", bank_names)
                    elif pay_method == "Credit Card" and card_names:
                        pay_detail = st.selectbox("Linked Credit Card", card_names)
                    else:
                        pay_detail = st.text_input("Payment Details / Account Reference", placeholder="e.g. Bank name or Card name")

                    auto_pay = st.checkbox("Auto-Pay Enabled", value=False)
                    submitted = st.form_submit_button("Save Bill", icon=":material/add:")

                    if submitted and name and amount > 0:
                        db.add_bill(
                            name, amount, due_day, frequency, category, 1 if auto_pay else 0,
                            owner=owner, payment_method=pay_method, payment_detail=pay_detail
                        )
                        st.success(f"Added bill '{name}' ({pay_method}: {pay_detail}) for {owner}!")
                        st.rerun()

        # Display Existing Bills
        if bills:
            for b in bills:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    owner_tag = f" | 👤 `{b.get('owner', 'Shared / Household')}`"
                    pm = b.get("payment_method", "ACH / Checking Account")
                    pd_text = b.get("payment_detail", "")
                    
                    pm_icon = "💳" if "Credit" in pm or "Card" in pm else "🏦"
                    pm_badge = f" | {pm_icon} `{pm}` ({pd_text})" if pd_text else f" | {pm_icon} `{pm}`"

                    c1.markdown(f"**{b['name']}**  \n`:material/calendar_today:` Due: Day {b['due_day']} | `{b['category']}`{owner_tag}{pm_badge}")
                    c2.markdown(f"### ${b['amount']:,.2f}")
                    if b['auto_pay']:
                        c2.caption("⚡ Auto-Pay Active")
                    
                    with c3:
                        with st.popover("Edit", icon=":material/edit:"):
                            edit_name = st.text_input("Name", value=b['name'], key=f"eb_name_{b['id']}")
                            edit_amount = st.number_input("Amount ($)", value=float(b['amount']), min_value=0.0, step=5.0, key=f"eb_amt_{b['id']}")
                            edit_due = st.number_input("Due Day", value=int(b['due_day']), min_value=1, max_value=31, key=f"eb_due_{b['id']}")
                            
                            freq_opts = ["Monthly", "Bi-Weekly", "Annual"]
                            edit_freq = st.selectbox("Frequency", freq_opts, index=freq_opts.index(b.get('frequency', 'Monthly')) if b.get('frequency') in freq_opts else 0, key=f"eb_freq_{b['id']}")
                            
                            edit_cat = st.selectbox("Category", bill_categories, index=bill_categories.index(b.get('category', 'General')) if b.get('category') in bill_categories else 0, key=f"eb_cat_{b['id']}")
                            edit_owner = st.selectbox("Owner", people_list, index=people_list.index(b.get('owner', 'Shared / Household')) if b.get('owner') in people_list else 0, key=f"eb_own_{b['id']}")
                            
                            pm_opts = ["ACH / Checking Account", "Credit Card", "Debit Card", "Manual Check / Cash"]
                            edit_pm = st.selectbox("Payment Method", pm_opts, index=pm_opts.index(b.get('payment_method', 'ACH / Checking Account')) if b.get('payment_method') in pm_opts else 0, key=f"eb_pm_{b['id']}")
                            
                            bank_names = [ba["name"] for ba in raw_accounts]
                            card_names = [c["name"] for c in raw_cards]
                            curr_pd = b.get('payment_detail', '')

                            if edit_pm in ["ACH / Checking Account", "Debit Card"] and bank_names:
                                edit_pd = st.selectbox("Linked Bank Account", bank_names, index=bank_names.index(curr_pd) if curr_pd in bank_names else 0, key=f"eb_pd_sel_{b['id']}")
                            elif edit_pm == "Credit Card" and card_names:
                                edit_pd = st.selectbox("Linked Credit Card", card_names, index=card_names.index(curr_pd) if curr_pd in card_names else 0, key=f"eb_pd_card_{b['id']}")
                            else:
                                edit_pd = st.text_input("Payment Details", value=curr_pd, key=f"eb_pd_txt_{b['id']}")
                            
                            edit_autopay = st.checkbox("Auto-Pay Enabled", value=bool(b.get('auto_pay', 0)), key=f"eb_auto_{b['id']}")
                            edit_active = st.checkbox("Active Bill", value=bool(b.get('is_active', 1)), key=f"eb_act_{b['id']}")

                            if st.button("Save Changes", key=f"save_bill_{b['id']}"):
                                db.update_bill(
                                    b['id'], edit_name, edit_amount, edit_due, edit_freq, edit_cat,
                                    1 if edit_autopay else 0, owner=edit_owner, payment_method=edit_pm,
                                    payment_detail=edit_pd, is_active=1 if edit_active else 0
                                )
                                st.success("Bill updated!")
                                st.rerun()

                        if st.button("Delete", key=f"del_bill_{b['id']}", icon=":material/delete:"):
                            st.session_state["delete_target"] = ("bills", b['id'], b['name'], "Bill")
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

                    with ic3:
                        with st.popover("Edit", icon=":material/edit:"):
                            edit_src = st.text_input("Source", value=inc['source'], key=f"ei_src_{inc['id']}")
                            edit_inc_amt = st.number_input("Amount ($)", value=float(inc['amount']), min_value=0.0, step=50.0, key=f"ei_amt_{inc['id']}")
                            
                            freq_list = ["Bi-Weekly", "Weekly", "Semi-Monthly", "Monthly"]
                            edit_inc_freq = st.selectbox("Frequency", freq_list, index=freq_list.index(inc.get('frequency', 'Bi-Weekly')) if inc.get('frequency') in freq_list else 0, key=f"ei_freq_{inc['id']}")
                            
                            try:
                                curr_date = datetime.strptime(inc['next_paydate'], "%Y-%m-%d").date()
                            except (ValueError, TypeError):
                                curr_date = date.today()
                                
                            edit_inc_date = st.date_input("Next Paydate", value=curr_date, key=f"ei_date_{inc['id']}")
                            edit_inc_own = st.selectbox("Owner", people_list, index=people_list.index(inc.get('owner', 'Shared / Household')) if inc.get('owner') in people_list else 0, key=f"ei_own_{inc['id']}")

                            if st.button("Save Changes", key=f"save_inc_{inc['id']}"):
                                db.update_income(inc['id'], edit_src, edit_inc_amt, edit_inc_freq, edit_inc_date.isoformat(), owner=edit_inc_own)
                                st.success("Income source updated!")
                                st.rerun()

                        if st.button("Delete", key=f"del_inc_{inc['id']}", icon=":material/delete:"):
                            st.session_state["delete_target"] = ("income", inc['id'], inc['source'], "Income Source")
                            st.rerun()
        else:
            st.info("No income sources recorded for this perspective.")


# ==============================================================================
# TAB 5: SAVINGS BUCKETS (SINKING FUNDS - CHILD OF BANK ACCOUNT)
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
                
                bank_opts = ["None / Unlinked"] + [ba["name"] for ba in raw_accounts]
                bucket_bank = st.selectbox("Parent Bank Account", bank_opts)
                bucket_icon = st.selectbox("Icon", [":material/shield:", ":material/flight_takeoff:", ":material/build:", ":material/home:", ":material/savings:", ":material/trending_up:"])

                bucket_submitted = st.form_submit_button("Save Savings Bucket", icon=":material/add:")

                if bucket_submitted and bucket_name:
                    parent_ba = "" if bucket_bank == "None / Unlinked" else bucket_bank
                    db.add_savings_bucket(bucket_name, bucket_target, bucket_curr, bucket_cat, owner=bucket_owner, icon=bucket_icon, bank_account_name=parent_ba)
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
                    
                    parent_tag = f" | 🏛️ `{bucket.get('bank_account_name')}`" if bucket.get('bank_account_name') else ""
                    st.caption(f"Owner: 👤 `{bucket.get('owner', 'Shared / Household')}` | Category: `{bucket['category']}`{parent_tag}")
                    st.markdown(f"**Saved:** `${bucket['current_balance']:,.2f}` of `${bucket['target_amount']:,.2f}`")
                    st.progress(min(prog / 100.0, 1.0), text=f"Progress: {prog:.1f}%")

                    # Edit Bucket Popover
                    with st.popover("Edit Bucket Details", icon=":material/edit:"):
                        eb_name = st.text_input("Name", value=bucket['name'], key=f"ebk_n_{bucket['id']}")
                        eb_target = st.number_input("Target ($)", value=float(bucket['target_amount']), min_value=1.0, step=100.0, key=f"ebk_t_{bucket['id']}")
                        eb_curr = st.number_input("Current Balance ($)", value=float(bucket['current_balance']), min_value=0.0, step=50.0, key=f"ebk_c_{bucket['id']}")
                        eb_cat = st.selectbox("Category", savings_categories, index=savings_categories.index(bucket.get('category', 'General')) if bucket.get('category') in savings_categories else 0, key=f"ebk_cat_{bucket['id']}")
                        eb_own = st.selectbox("Owner", people_list, index=people_list.index(bucket.get('owner', 'Shared / Household')) if bucket.get('owner') in people_list else 0, key=f"ebk_o_{bucket['id']}")
                        
                        b_opts = ["None / Unlinked"] + [ba["name"] for ba in raw_accounts]
                        curr_ba = bucket.get("bank_account_name", "None / Unlinked")
                        eb_ba = st.selectbox("Parent Bank Account", b_opts, index=b_opts.index(curr_ba) if curr_ba in b_opts else 0, key=f"ebk_ba_{bucket['id']}")
                        
                        icon_list = [":material/shield:", ":material/flight_takeoff:", ":material/build:", ":material/home:", ":material/savings:", ":material/trending_up:"]
                        eb_icon = st.selectbox("Icon", icon_list, index=icon_list.index(bucket.get('icon', ':material/savings:')) if bucket.get('icon') in icon_list else 4, key=f"ebk_ic_{bucket['id']}")

                        if st.button("Save Bucket Changes", key=f"save_bk_{bucket['id']}"):
                            parent_ba = "" if eb_ba == "None / Unlinked" else eb_ba
                            db.update_savings_bucket(bucket['id'], eb_name, eb_target, eb_curr, eb_cat, owner=eb_own, icon=eb_icon, bank_account_name=parent_ba)
                            st.success("Savings bucket updated!")
                            st.rerun()

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
                        st.session_state["delete_target"] = ("savings_buckets", bucket['id'], bucket['name'], "Savings Bucket")
                        st.rerun()
    else:
        st.info("No savings buckets recorded for this perspective.")


# ==============================================================================
# TAB 6: TRANSACTION HISTORY
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
            use_container_width=True
        )
    else:
        st.info("No transactions logged for this perspective.")
