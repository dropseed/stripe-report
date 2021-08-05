import sys
import json
import os
import datetime

import stripe
import sentry_sdk


sentry_sdk.init(
    dsn=os.environ["SENTRY_DSN"], environment=os.environ.get("SENTRY_ENV", "production")
)


# Max 20
EVENT_TYPES = (
    # "customer.created",
    "customer.source.created",
    "customer.source.updated",
    "customer.subscription.created",
    "customer.subscription.deleted",
    "customer.subscription.trial_will_end",
    # "customer.subscription.updated",
    "invoice.payment_failed",
    "invoice.payment_succeeded",
)


class StripeReporter:
    def __init__(self):
        self.account_keys = {}
        self.results = {}

    def run(self):
        self.results = {}

        for name, key in self.account_keys.items():
            self.results[name] = self.events_for_key(key) + self.invoices_for_key(key)

    def events_for_key(self, stripe_key):
        ago = datetime.datetime.now() - datetime.timedelta(days=1)

        stripe.api_key = stripe_key
        events = list(stripe.Event.list(limit=100, types=EVENT_TYPES))

        output = []

        for event in events:
            created = datetime.datetime.fromtimestamp(event["created"])
            if created < ago:
                continue

            obj = event["data"]["object"]
            amount = obj.get("amount_paid", "")
            if amount:
                amount = amount / 100
                amount = f"${amount:.2f}"
            customer_email = obj.get("customer_email", "")

            icon = ""
            if event["type"] == "customer.subscription.created":
                icon = "🚀"
            elif event["type"] == "invoice.payment_succeeded":
                icon = "💵"

            s = f"{icon} <a href='https://dashboard.stripe.com/events/{event['id']}'>{event['type']}</a>: {customer_email} {amount}"
            output.append(s)

        return output

    def invoices_for_key(self, stripe_key):
        stripe.api_key = stripe_key
        invoices = list(stripe.Invoice.list(limit=100, status="open"))

        output = []

        for invoice in invoices:
            amount = invoice["total"] / 100
            amount = f"${amount:.2f}"
            s = f"🧾 <a href='{invoice['hosted_invoice_url']}'>Open invoice</a>: {invoice['customer_email']} {amount} {invoice['collection_method']}"
            output.append(s)

        return output


def email_results(results):
    html =  "<h2>Dropseed Stripe report for the last 24 hrs</h2>"
    for name, lines in results.items():
        if lines:
            html += f"<h3>{name}</h3>"
            html += "<ul>" + "".join([f"<li>{x}</li>" for x in lines]) + "</ul>"

    send_email("Dropseed Stripe Report", html, os.environ["EMAIL"], "Dropseed Reports <reports@dropseed.io>")


def send_email(subject, html, to_email, from_email):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(html, 'html'))

    mailServer = smtplib.SMTP(os.environ["SMTP_HOST"], os.environ.get("SMTP_PORT", 587))
    mailServer.ehlo()
    mailServer.starttls()
    mailServer.ehlo()
    mailServer.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
    mailServer.sendmail(from_email, to_email, msg.as_string())
    mailServer.close()


if __name__ == "__main__":
    reporter = StripeReporter()

    # name=key name=key etc
    stripe_input = os.environ["STRIPE_ACCOUNTS"]
    parts = stripe_input.split()
    for part in parts:
        name, key = part.split("=")
        reporter.account_keys[name] = key

    reporter.run()
    print(json.dumps(reporter.results, indent=2))
    if any(reporter.results.values()):
        email_results(reporter.results)
