# UNIVERSAL TRADE PAY — New independent website

This is a separate Flask project. It does not modify the existing Render demo.

## Included
- Responsive dark-blue/white public website pages
- Personal and corporate account request form
- Login with hashed passwords
- Admin approval workflow
- Customer dashboard and internal demonstration transfers
- Admin dashboard for account approvals and test balances
- SQLite database and Render deployment blueprint

## Local run
1. Install Python 3.10+.
2. Run `pip install -r requirements.txt`.
3. Set environment variables `SECRET_KEY`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`.
4. Run `python app.py` and visit `http://localhost:5000`.

## Render deployment
Create a NEW Web Service from this project/repository. Do not select or change the existing Universal Trade Pay service. Render can use `render.yaml`. Add `ADMIN_EMAIL` and a strong `ADMIN_PASSWORD` in the new service's environment settings. The included free-plan blueprint uses an ephemeral SQLite file for preview only: Render free web services do not support persistent disks, so demo accounts and balances can be lost when the service restarts, spins down or redeploys. For persistent records, switch to a paid service with a persistent disk or configure a managed database.

## Important demo boundaries
Balances and transfers are simulated, closed-loop records only. No bank, card, crypto-wallet, deposit, withdrawal, or external payment network is connected. Contact form messages are not emailed; connect a mail provider before relying on it. KYC details are currently basic text fields and are not document verification. Do not collect real identity documents or real financial information until secure storage, privacy notices, access controls, and compliance review are in place.

Change the default Flask secret key before deployment. The included free Render preview does not preserve its SQLite database. Use a paid persistent disk or managed database before relying on saved records. This starter is a functional demonstration foundation, not a licensed financial service.
