import json
import os
import datetime

import stripe


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

EVENT_ICONS = {
    "customer.subscription.created": "🚀",
    "invoice.payment_succeeded": "💵",
}


class StripeReporter:
    def __init__(self, account_keys: dict):
        self.account_keys = account_keys
        self.results = {}

    @property
    def has_results(self):
        return any(self.results.values())

    def run(self):
        self.results = {}

        for name, key in self.account_keys.items():
            self.results[name] = self.events_for_key(key) + self.invoices_for_key(key)

    def events_for_key(self, stripe_key):
        """Get any events in the last 24 hours"""
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

            icon = EVENT_ICONS.get(event["type"], "")

            s = f"{icon} <a href='https://dashboard.stripe.com/events/{event['id']}'>{event['type']}</a>: {customer_email} {amount}"
            output.append(s)

        return output

    def invoices_for_key(self, stripe_key):
        """Get any open invoices"""
        stripe.api_key = stripe_key
        invoices = list(stripe.Invoice.list(limit=100, status="open"))

        output = []

        for invoice in invoices:
            amount = invoice["total"] / 100
            amount = f"${amount:.2f}"
            s = f"🧾 <a href='{invoice['hosted_invoice_url']}'>Open invoice</a>: {invoice['customer_email']} {amount} {invoice['collection_method']}"
            output.append(s)

        return output

    def print_results(self):
        print(json.dumps(self.results, indent=2))

    def email_results(self):
        html = "<h2>Stripe report for the last 24 hrs</h2>"
        for name, lines in self.results.items():
            if lines:
                html += f"<h3>{name}</h3>"
                html += "<ul>" + "".join([f"<li>{x}</li>" for x in lines]) + "</ul>"

        send_email(
            "Stripe Report", html, os.environ["TO_EMAIL"], os.environ["FROM_EMAIL"]
        )


def send_email(subject, html, to_email, from_email):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["Subject"] = subject

    msg.attach(MIMEText(html, "html"))

    print("Sending email")
    print(msg)

    mailServer = smtplib.SMTP(os.environ["SMTP_HOST"], os.environ.get("SMTP_PORT", 587))
    mailServer.ehlo()
    mailServer.starttls()
    mailServer.ehlo()
    mailServer.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
    to_email_list = [x.strip() for x in to_email.split(",")]
    mailServer.sendmail(from_email, to_email_list, msg.as_string())
    mailServer.close()


def stripe_keys_from_env():
    stripe_keys = {}

    # Load keys from environment (STRIPE_KEY_{name}=key)
    for v in os.environ:
        if v.startswith("STRIPE_KEY_"):
            name = v[11:]
            key = os.environ[v]
            stripe_keys[name] = key

    return stripe_keys


def cli():
    reporter = StripeReporter(account_keys=stripe_keys_from_env())
    reporter.run()
    reporter.print_results()
    if reporter.has_results:
        reporter.email_results()
