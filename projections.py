import pandas as pd
from datetime import date, timedelta, datetime

def calculate_cashflow_projection(starting_balance, bills, income_sources, days_ahead=60):
    """
    Projects daily liquid cash balances over N days into the future based on recurring bills and income.
    """
    today = date.today()
    end_date = today + timedelta(days=days_ahead)

    # Initialize daily ledger
    date_range = [today + timedelta(days=i) for i in range(days_ahead + 1)]
    ledger = {d: {"income": 0.0, "bills": 0.0, "events": []} for d in date_range}

    # 1. Project Income Deposits
    for inc in income_sources:
        try:
            next_pay = datetime.strptime(inc["next_paydate"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue

        curr_pay = next_pay
        freq = inc.get("frequency", "Bi-Weekly")
        amount = float(inc.get("amount", 0.0))
        source = inc.get("source", "Income")

        while curr_pay <= end_date:
            if curr_pay >= today:
                ledger[curr_pay]["income"] += amount
                ledger[curr_pay]["events"].append(f"💰 {source} (+${amount:,.2f})")

            # Advance next pay date based on frequency
            if freq == "Weekly":
                curr_pay += timedelta(weeks=1)
            elif freq == "Bi-Weekly":
                curr_pay += timedelta(weeks=2)
            elif "Semi-Monthly" in freq or "Twice" in freq:
                curr_pay += timedelta(days=15)
            elif freq == "Monthly":
                # Advance 1 month
                month = curr_pay.month % 12 + 1
                year = curr_pay.year + (curr_pay.month // 12)
                day = min(curr_pay.day, 28)
                curr_pay = date(year, month, day)
            else:
                # Custom / Flex -> default advance 14 days
                curr_pay += timedelta(days=14)

    # 2. Project Recurring Bills
    for bill in bills:
        if not bill.get("is_active", 1):
            continue

        due_day = int(bill.get("due_day", 1))
        amount = float(bill.get("amount", 0.0))
        name = bill.get("name", "Bill")
        freq = bill.get("frequency", "Monthly")

        # Project for each month in the range
        curr_year = today.year
        curr_month = today.month

        for m_offset in range((days_ahead // 28) + 2):
            target_month = (curr_month - 1 + m_offset) % 12 + 1
            target_year = curr_year + ((curr_month - 1 + m_offset) // 12)
            
            # Handle month end day caps (e.g. Feb 28/29)
            if target_month == 2:
                max_day = 29 if (target_year % 4 == 0 and (target_year % 100 != 0 or target_year % 400 == 0)) else 28
            elif target_month in [4, 6, 9, 11]:
                max_day = 30
            else:
                max_day = 31

            bill_date = date(target_year, target_month, min(due_day, max_day))

            if today <= bill_date <= end_date:
                ledger[bill_date]["bills"] += amount
                ledger[bill_date]["events"].append(f"📄 {name} (-${amount:,.2f})")

    # 3. Build Daily Cumulative Balance Series
    records = []
    running_balance = float(starting_balance)

    for d in date_range:
        day_inc = ledger[d]["income"]
        day_bills = ledger[d]["bills"]
        net_change = day_inc - day_bills
        running_balance += net_change

        records.append({
            "date": d,
            "date_str": d.strftime("%b %d, %Y"),
            "starting_balance": running_balance - net_change,
            "income": day_inc,
            "bills": day_bills,
            "net_change": net_change,
            "projected_balance": running_balance,
            "events": ", ".join(ledger[d]["events"]) if ledger[d]["events"] else "None"
        })

    df = pd.DataFrame(records)
    return df
