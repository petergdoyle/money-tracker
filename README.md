# 💰 money-tracker

A self-hosted personal finance engine and dashboard for tracking recurring bills, credit card balances, savings buckets, and projecting cashflow liquidity over time.

---

## ✨ Features

- 📊 **Cashflow & Balance Projections**: Visual 30/60/90-day liquidity timeline forecasting future balances based on upcoming bills, subscriptions, and income paydays.
- 💳 **Credit Card & Utilization Tracking**: Monitor credit balances, overall limits, utilization percentages, statement dates, and minimum payments.
- 📄 **Bill & Subscription Manager**: Track recurring obligations, due dates, payment frequencies, categories, and auto-pay statuses.
- 🎯 **Target Savings Buckets (Sinking Funds)**: Set up goal buckets (e.g. Emergency Fund, Vacation, Car Maintenance) with visual progress gauges and instant deposit/withdrawal logging.
- 🧾 **Audit Trail & Activity Log**: Automatic transaction logging for balance updates, deposits, withdrawals, and manual payments.

---

## 🚀 Quick Start (Local Development)

### 1. Set Up Environment & Dependencies
```bash
make setup
```

### 2. Launch Local Dev Server
```bash
make dev-up
```
Access the application in your browser at: **`http://localhost:8220`**

### 3. Check Status or Stop
```bash
make dev-status
make dev-down
```

---

## 🐳 Docker Deployment

```bash
# Build production image
make docker-build

# Run container stack
make docker-up
```

Data is stored persistently in `./data/money_tracker.db` via host bind-mounts.
