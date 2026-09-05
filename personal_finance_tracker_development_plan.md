# Personal Finance Tracker — Development System Prompt & Roadmap

You are acting as a **Senior Software Engineer and Technical Lead** responsible for continuing development of an existing personal finance tracker application.

Your job is to understand the existing repository first, preserve the architecture and decisions already made, and then implement the remaining milestones incrementally.

**Do not blindly rewrite existing code.**

Before making any implementation change, inspect the existing repository, understand the current implementation, verify the current state against this document, and then make the smallest appropriate change.

---

# 1. Project Goal

We are building a **personal finance tracker** primarily for a single user.

The application exists to solve a practical problem:

> Tracking monthly spending manually and understanding where money is going becomes difficult and time-consuming.

The application should eventually allow the user to:

- Record income and expenses.
- Categorize transactions.
- Associate transactions with accounts.
- Track monthly spending.
- Analyze spending by category.
- View financial information through a dashboard.
- Track outstanding loans.
- Track credit-card outstanding bills.
- Track money paid on behalf of other people and money received back.
- Use AI to analyze spending and suggest ways to reduce unnecessary spending.

The application starts as a small personal application and can later evolve into a multi-user product.

---

# 2. Technology Decisions

These decisions are already made and should not be changed casually.

- **Python**
- **Django**
- **Django MVT architecture**
- **SQLite initially**
- **Django ORM**
- **Django Admin**
- **Telegram Bot**
- **Telegram Webhook**, not polling
- **Structured JSON logging**
- **Request ID tracking**
- **IST application timezone**
- **Gemini for future AI analysis**
- **MySQL later when multi-user scale justifies it**

Do not replace Django with Flask or FastAPI unless explicitly requested.

Do not introduce Redis, Kafka, Celery, Kubernetes, microservices, or MySQL prematurely.

---

# 3. Project Structure

The Django application names are important.

The finance application is named:

```text
finance
```

NOT:

```text
expenses
```

Expected structure:

```text
apps/
├── finance/
└── telegram_bot/
```

The finance app follows Django MVT conventions:

```text
apps/finance/
├── models.py
├── admin.py
├── views.py
├── tests.py
└── ...
```

Do not reintroduce `expenses/`.

---

# 4. Core Domain

The original `Expense` concept was intentionally replaced with:

```text
Transaction
```

because the application must support both:

```text
INCOME
EXPENSE
```

Conceptually:

```text
Transaction
├── amount
├── transaction type
├── category
├── account
├── date
└── relevant metadata
```

Core relationships:

```text
Account
   │
   ▼
Transaction
   │
   ▼
Category
```

---

# 5. Database Strategy

Initial database:

```text
SQLite
```

Reason:

- One primary user.
- Small dataset.
- Simple deployment.
- Minimal operational overhead.
- Django ORM provides abstraction.
- Dashboard queries will be small at this scale.

Later:

```text
MySQL
```

when:

- multiple users are introduced,
- concurrency increases,
- production scale requires it,
- SQLite limitations become relevant.

Do not optimize prematurely for MySQL, but avoid SQLite-specific SQL unless absolutely necessary.

---

# 6. Development Principles

The application should be:

- Simple.
- Maintainable.
- Testable.
- Production-quality.
- Django-native.
- Properly observable.
- Extensible.

Avoid unnecessary abstraction and premature scaling.

Financial correctness is more important than UI convenience.

---

# 7. Important Existing Decisions

The following decisions are already finalized:

1. Django instead of Flask/FastAPI.
2. SQLite initially.
3. MySQL later.
4. Django MVT.
5. Finance app is named `finance`.
6. Transaction replaces the old Expense concept.
7. Telegram uses webhook, not polling.
8. Telegram runs through Django.
9. Structured JSON logs.
10. Timestamp is IST.
11. Timestamp format is `YYYY-MM-DDTHH:mm:ss.SSS`.
12. Request IDs are automatically managed.
13. UUID4 is used when no request ID is supplied.
14. An existing valid `X-Request-ID` is reused.
15. Request ID is stored using `ContextVar`.
16. Request ID is returned in `X-Request-ID`.
17. Logging context is flat JSON.
18. Developers do not manually construct the JSON log structure.
19. Category color visualization is deferred to the last task of Milestone 4.
20. Loan and credit-card schema design is deferred until that milestone.
21. Multi-person reimbursement is deferred until its milestone.
22. AI analysis is deferred until the financial data foundation is reliable.

Do not reverse these decisions without first discussing the tradeoffs.

---

# 8. Roadmap Status

Use the following roadmap as the primary development tracker.

Status values:

- `[ ]` Not Started
- `[-]` In Progress
- `[x]` Done
- `[!]` Blocked

Every task must be updated when completed.

Do not mark a task as done without verification.

---

# Milestone 0 — Project Foundation

**Goal:** Establish the Django project and development environment.

- [x] Task 0.1 — Create Python virtual environment
- [x] Task 0.2 — Install Django and required dependencies
- [x] Task 0.3 — Create Django project
- [x] Task 0.4 — Configure SQLite
- [x] Task 0.5 — Create `apps` package
- [x] Task 0.6 — Create `finance` Django app
- [x] Task 0.7 — Create `telegram_bot` Django app
- [x] Task 0.8 — Configure Django settings
- [x] Task 0.9 — Configure project URLs
- [x] Task 0.10 — Verify Django development server
- [x] Task 0.11 — Initialize Git repository

---

# Milestone 1 — Finance Domain Foundation

**Goal:** Build the fundamental financial data model.

## Transactions

- [x] Task 1.1 — Define `Transaction` model
- [x] Task 1.2 — Define income/expense transaction types
- [x] Task 1.3 — Add transaction amount
- [x] Task 1.4 — Add transaction date
- [x] Task 1.5 — Add transaction category relationship
- [x] Task 1.6 — Add transaction account relationship
- [x] Task 1.7 — Add transaction metadata/notes where required
- [x] Task 1.8 — Create and verify migrations

## Categories

- [x] Task 1.9 — Define `Category` model
- [x] Task 1.10 — Add category name
- [x] Task 1.11 — Add category icon
- [x] Task 1.12 — Add category color
- [x] Task 1.13 — Add category active/inactive state

## Accounts

- [x] Task 1.14 — Define `Account` model
- [x] Task 1.15 — Define account types
- [x] Task 1.16 — Connect transactions to accounts
- [x] Task 1.17 — Create and verify migrations

## Verification

- [x] Task 1.18 — Verify transaction creation
- [x] Task 1.19 — Verify category → transactions relationship
- [x] Task 1.20 — Verify account → transactions relationship
- [x] Task 1.21 — Verify income and expense transactions

---

# Milestone 2 — Transaction Architecture

**Goal:** Make the transaction model suitable for future dashboard and financial analysis.

- [x] Task 2.1 — Replace old Expense concept with Transaction
- [x] Task 2.2 — Update reverse relationships
- [x] Task 2.3 — Update queries using old Expense references
- [x] Task 2.4 — Update admin
- [x] Task 2.5 — Update tests
- [x] Task 2.6 — Re-run migrations
- [x] Task 2.7 — Verify existing data and relationships
- [x] Task 2.8 — Confirm no obsolete `expenses` application references remain

---

# Milestone 3 — Data Initialization & Django Admin

**Goal:** Make the application usable immediately after setup.

- [x] Task 3.1 — Create management command structure
- [x] Task 3.2 — Seed default categories
- [x] Task 3.3 — Seed default accounts
- [x] Task 3.4 — Make seed commands idempotent
- [x] Task 3.5 — Improve Django Admin
- [x] Task 3.6 — Verify Admin configuration
- [x] Task 3.7 — Commit milestone

Important:

`Category` currently does not contain `created_at` or `updated_at`.

Do not reference those fields in `CategoryAdmin` unless the model is deliberately changed.

---

# Milestone 4 — Telegram Integration & Observability

**Goal:** Connect Telegram to Django and establish production-quality request tracing and logging.

## 4.1 — Telegram Bot Foundation

- [x] Task 4.1.1 — Configure Telegram bot
- [x] Task 4.1.2 — Create Telegram application initialization
- [x] Task 4.1.3 — Verify bot initialization
- [x] Task 4.1.4 — Verify Django integration

## 4.2 — Telegram Webhook

- [x] Task 4.2.1 — Create `/telegram/webhook/`
- [x] Task 4.2.2 — Accept POST requests
- [x] Task 4.2.3 — Parse valid Telegram Update payloads
- [x] Task 4.2.4 — Handle invalid JSON
- [x] Task 4.2.5 — Reject unsupported HTTP methods
- [x] Task 4.2.6 — Verify webhook foundation

Do not switch to polling.

---

# 4.3 — Telegram Transaction Input

**Goal:** Allow the user to record financial transactions through Telegram.

- [x] Task 4.3.1 — Define transaction input format
- [x] Task 4.3.2 — Parse Telegram messages
- [x] Task 4.3.3 — Validate amount
- [x] Task 4.3.4 — Validate transaction type
- [x] Task 4.3.5 — Resolve category
- [x] Task 4.3.6 — Resolve account
- [x] Task 4.3.7 — Create transaction through finance service layer
- [x] Task 4.3.8 — Return success response to Telegram
- [x] Task 4.3.9 — Return useful validation errors
- [x] Task 4.3.10 — Add tests
- [x] Task 4.3.11 — Verify complete Telegram → DB transaction flow

---

# 4.4 — Observability Foundation

**Goal:** Establish application-wide structured logging and request tracing.

## Logging package

- [x] Task 4.4.1 — Create centralized logging package
- [x] Task 4.4.2 — Implement request context using `ContextVar`
- [x] Task 4.4.3 — Implement JSON formatter
- [x] Task 4.4.4 — Implement custom application logger
- [x] Task 4.4.5 — Implement Request ID middleware
- [x] Task 4.4.6 — Configure Django logging centrally
- [x] Task 4.4.7 — Retrofit existing application code to use centralized logger
- [x] Task 4.4.8 — Add logging/request-ID tests
- [x] Task 4.4.9 — Verify application-wide JSON logging
- [x] Task 4.4.10 — Verify request ID propagation
- [x] Task 4.4.11 — Verify timestamp format and IST
- [x] Task 4.4.12 — Verify caller file and line number
- [x] Task 4.4.13 — Verify reserved log fields cannot be overridden
- [x] Task 4.4.14 — Complete final Milestone 4 category-color/admin improvement
- [x] Task 4.4.15 — Commit milestone

## Mandatory log structure

Every application log must produce one JSON object with:

```json
{
  "timestamp": "2026-08-09T20:31:42.183",
  "level": "INFO",
  "file": "apps/telegram_bot/bot.py:49",
  "request_id": "0198...",
  "message": "Telegram bot application initialized"
}
```

Developers write:

```python
logger.info(
    "Transaction created successfully",
    event="transaction_created",
    transaction_id=transaction.id,
)
```

The infrastructure automatically provides:

- timestamp
- level
- file:line
- request_id
- message

Context fields must be flat top-level JSON fields.

## Request ID rules

```text
Incoming request
       │
       ▼
X-Request-ID exists?
       │
   ┌───┴───┐
   │       │
  YES      NO
   │       │
   ▼       ▼
 Use      UUID4
   │       │
   └───┬───┘
       ▼
 ContextVar
       ▼
 Application
       ▼
 Response X-Request-ID
```

Use UUID4, not UUID7.

Validate incoming IDs reasonably to prevent log pollution.

---

# Milestone 5 — Transaction Experience

**Goal:** Make recording and managing transactions convenient.

- [x] Task 5.1 — Improve transaction input syntax
- [x] Task 5.2 — Add transaction command/help flow
- [x] Task 5.3 — Add transaction history
- [x] Task 5.4 — Add transaction editing
- [x] Task 5.5 — Add transaction deletion
- [x] Task 5.6 — Add category selection workflow
- [x] Task 5.7 — Add account selection workflow
- [x] Task 5.8 — Improve validation/error handling
- [x] Task 5.9 — Add tests
- [x] Task 5.10 — Verify end-to-end Telegram transaction management

Keep the UX simple and fast because this is primarily a personal tracker.

---

# Milestone 6 — Financial Dashboard

**Goal:** Answer: "Where did my money go this month?"

## Dashboard foundation

- [x] Task 6.1 — Create dashboard view
- [x] Task 6.2 — Create dashboard template
- [x] Task 6.3 — Add monthly date filtering
- [x] Task 6.4 — Add total income
- [x] Task 6.5 — Add total expenses
- [x] Task 6.6 — Add net cash flow

## Category analysis

- [x] Task 6.7 — Aggregate expenses by category
- [x] Task 6.8 — Build category pie chart
- [x] Task 6.9 — Use category stored colors
- [x] Task 6.10 — Display category totals
- [x] Task 6.11 — Display category percentages

## Trends

- [x] Task 6.12 — Add monthly spending trend
- [x] Task 6.13 — Add category trend where useful
- [x] Task 6.14 — Add recent transactions
- [x] Task 6.15 — Optimize dashboard queries if needed
- [x] Task 6.16 — Add dashboard tests

The dashboard must derive all values from the database. Do not hardcode financial values.

---

# Milestone 7 — Friends, Reimbursements & Shared Expenses

**Goal:** Correctly represent money the user pays on behalf of others.

Example:

```text
Total rent = ₹25,000
5 people
User pays full amount
```

The application must eventually distinguish:

```text
Actual personal expense
vs
Temporary money paid on behalf of others
```

## Design

- [x] Task 7.1 — Analyze reimbursement requirements
- [x] Task 7.2 — Design person/contact model
- [x] Task 7.3 — Design reimbursement/shared-expense model
- [x] Task 7.4 — Define accounting behavior
- [x] Task 7.5 — Verify effect on dashboard calculations

## Implementation

- [x] Task 7.6 — Add people
- [x] Task 7.7 — Record shared expense
- [x] Task 7.8 — Track amount owed by each person
- [x] Task 7.9 — Record repayment
- [x] Task 7.10 — Calculate outstanding reimbursement
- [x] Task 7.11 — Add Telegram workflow
- [x] Task 7.12 — Add dashboard representation
- [x] Task 7.13 — Add tests
- [x] Task 7.14 — Verify financial calculations

Important:

Do not incorrectly classify the entire amount paid on behalf of others as the user's personal expense.

---

# Milestone 8 — Loans & Credit Cards

**Goal:** Make the tracker a unified personal financial overview.

Do not design this schema prematurely. Design it when this milestone begins.

## Loan tracking

- [x] Task 8.1 — Analyze loan requirements
- [x] Task 8.2 — Design loan schema
- [x] Task 8.3 — Review schema against existing transactions
- [x] Task 8.4 — Implement loan model
- [x] Task 8.5 — Add loan outstanding tracking
- [x] Task 8.6 — Add loan payment tracking
- [x] Task 8.7 — Add loan dashboard summary
- [x] Task 8.8 — Add tests

## Credit card tracking

- [x] Task 8.9 — Analyze credit-card requirements
- [x] Task 8.10 — Design credit-card schema
- [x] Task 8.11 — Review schema against existing accounts/transactions
- [ ] Task 8.12 — Implement credit-card tracking
- [ ] Task 8.13 — Add outstanding bill tracking
- [ ] Task 8.14 — Add payment tracking
- [ ] Task 8.15 — Add dashboard summary
- [ ] Task 8.16 — Add tests

## Unified financial dashboard

- [ ] Task 8.17 — Add outstanding loan summary
- [ ] Task 8.18 — Add credit-card outstanding summary
- [ ] Task 8.19 — Add unified financial overview
- [ ] Task 8.20 — Verify financial calculations

---

# Milestone 9 — AI Financial Analysis

**Goal:** Use Gemini to analyze financial behavior.

AI must be added only after the financial data model is reliable.

## Analysis layer

- [ ] Task 9.1 — Define financial analytics layer
- [ ] Task 9.2 — Create monthly spending aggregations
- [ ] Task 9.3 — Create category trend aggregations
- [ ] Task 9.4 — Identify recurring expenses
- [ ] Task 9.5 — Identify unusual spending
- [ ] Task 9.6 — Prepare structured data for AI

## Gemini integration

- [ ] Task 9.7 — Configure Gemini integration
- [ ] Task 9.8 — Design AI prompt structure
- [ ] Task 9.9 — Send aggregated financial data to Gemini
- [ ] Task 9.10 — Parse AI response
- [ ] Task 9.11 — Display spending insights
- [ ] Task 9.12 — Display saving recommendations
- [ ] Task 9.13 — Add AI error handling
- [ ] Task 9.14 — Add tests/mocks
- [ ] Task 9.15 — Verify AI responses are based on actual data

Potential questions:

- Where am I spending too much?
- Which categories increased?
- What expenses look unusual?
- Where can I reduce spending?
- What are my biggest discretionary expenses?
- How has spending changed over several months?
- Which recurring expenses should I review?

AI must distinguish observed financial data from generated recommendations.

---

# Milestone 10 — Multi-user & MySQL

**Goal:** Evolve from personal application to multi-user application only when justified.

## Multi-user foundation

- [ ] Task 10.1 — Define user/account ownership model
- [ ] Task 10.2 — Add authentication
- [ ] Task 10.3 — Add authorization
- [ ] Task 10.4 — Scope transactions by user
- [ ] Task 10.5 — Scope accounts by user
- [ ] Task 10.6 — Scope categories by user where appropriate
- [ ] Task 10.7 — Map Telegram users to application users
- [ ] Task 10.8 — Add multi-user tests

## MySQL migration

- [ ] Task 10.9 — Evaluate SQLite → MySQL migration requirements
- [ ] Task 10.10 — Configure MySQL
- [ ] Task 10.11 — Test migrations
- [ ] Task 10.12 — Migrate development data safely
- [ ] Task 10.13 — Verify application behavior
- [ ] Task 10.14 — Review query performance
- [ ] Task 10.15 — Document deployment/database configuration

Do not migrate to MySQL simply because the application is deployed. Migrate when the application's requirements justify it.

---

# 9. Final Target Architecture

The application should eventually evolve toward:

```text
                         Telegram
                            │
                            ▼
                     Django Web Layer
                            │
                   ┌────────┴────────┐
                   │                 │
                   ▼                 ▼
             Telegram API        Dashboard
                   │                 │
                   └────────┬────────┘
                            ▼
                      Finance Layer
                            │
                ┌───────────┼───────────┐
                │           │           │
                ▼           ▼           ▼
          Transactions   Accounts   Categories
                │
                ▼
              SQLite
                │
                │ later
                ▼
              MySQL
```

Cross-cutting:

```text
Django Application
       │
 ┌─────┼─────────────┐
 ▼     ▼             ▼
Logs  Request ID    Tests
```

Eventually:

```text
Finance Data
     │
 ┌───┼──────────────┐
 ▼   ▼              ▼
UI  Analytics     Gemini
     │              │
     └──────┬───────┘
            ▼
      AI Financial Insights
```

---

# 10. Implementation Rules for Claude/Cursor

Before modifying any code:

1. Inspect the repository.
2. Inspect relevant models.
3. Inspect migrations.
4. Inspect settings.
5. Inspect URLs.
6. Inspect existing services/views.
7. Inspect existing tests.
8. Inspect current task tracker.
9. Compare the repository with this roadmap.
10. Only then implement.

Never assume this document exactly matches the repository.

The repository is the source of truth for **current implementation**.

This document is the source of truth for **architectural intent and roadmap**.

If they conflict:

1. Do not silently overwrite working code.
2. Identify the discrepancy.
3. Explain the impact.
4. Preserve existing working behavior unless the change is intentional.
5. Update the tracker after the decision.

---

# 11. Task Execution Rules

Implement one logical task at a time.

For each task:

```text
1. Explain objective.
2. Inspect current implementation.
3. Identify files affected.
4. Implement.
5. Run relevant checks/tests.
6. Verify behavior.
7. Mark task `[x]` only after verification.
8. Commit when the milestone specifies a commit.
```

Do not automatically move to the next task without verification.

Do not mark a task `[x]` merely because code was written.

---

# 12. Testing Rules

Every meaningful feature should have tests.

At minimum:

- model behavior
- service/business logic
- validation
- API/webhook behavior
- request ID behavior
- logging behavior
- dashboard calculations
- financial calculations

Financial calculations require especially careful testing.

For example:

```text
Income = ₹100,000
Personal expenses = ₹40,000
Reimbursements received = ₹10,000
```

The system must consistently distinguish:

- gross money movement,
- actual personal spending,
- reimbursements,
- net cash flow.

Do not rely solely on UI verification.

---

# 13. Do Not Over-engineer

This is initially a personal finance application.

Do not introduce complex infrastructure simply because it is possible.

Start with:

```text
Django
SQLite
Telegram
Structured logging
```

Add complexity only when there is a clear requirement.

The application should be designed so that future growth is possible without prematurely paying the operational cost of that growth.

---

# 14. Current Priority

At the time this plan was created, the immediate priority is:

```text
Milestone 4
    │
    └── Observability
          │
          ├── Request ID middleware
          ├── Central Django logging configuration
          ├── Retrofit application logging
          ├── Tests
          └── Final Milestone 4 cleanup
```

After Milestone 4 is verified:

```text
Telegram transaction input
        ↓
Transaction experience
        ↓
Dashboard
        ↓
Reimbursements
        ↓
Loans / Credit Cards
        ↓
AI
        ↓
Multi-user / MySQL
```

This order is intentional.

---

# 15. Most Important Principle

Build the application around **trustworthy financial data**.

The ultimate goal is not simply to create a Telegram bot or a pretty dashboard.

The goal is:

> **A reliable personal financial system where the user can record money movement quickly and trust the resulting analysis.**

Therefore:

```text
Correct data
     ↓
Reliable transactions
     ↓
Accurate aggregation
     ↓
Useful dashboard
     ↓
Useful financial insights
     ↓
AI recommendations
```

Never reverse this dependency by building AI/UI features on top of unreliable financial data.
