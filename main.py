import sys
import json
import os
import datetime
import socket
import ssl
import urllib.parse

import stripe
import requests
import sentry_sdk
from sentry_sdk.integrations.serverless import serverless_function


sentry_sdk.init(
    dsn=os.environ["SENTRY_DSN"], environment=os.environ.get("SENTRY_ENV", "production")
)


# max 20
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

    def load_data(self, data):
        print(f"Loading data")
        self.account_keys = data

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

    message = {
        "html": html,
        "to": [{"email": x} for x in os.environ["EMAILS"].split(",")],
        "subject": "Dropseed Stripe Report",
        "from_email": "reports@dropseed.io",
        "from_name": "Dropseed Reports",
    }

    print(json.dumps(message, indent=2))

    response = requests.post("https://mandrillapp.com/api/1.0/messages/send.json", json={"key": os.environ["MANDRILL_API_KEY"], "message": message})
    response.raise_for_status()


@serverless_function
def gcloud_handler(request):
    body = request.get_data(as_text=True)
    data = json.loads(body)
    pd = StripeReporter()
    pd.load_data(data)
    pd.run()

    if any(pd.results.values()):
        email_results(pd.results)

    return json.dumps(pd.results)


if __name__ == "__main__":
    pd = StripeReporter()
    pd.load_data(json.loads(sys.argv[1]))
    pd.run()
    print(json.dumps(pd.results, indent=2))
    # if any(pd.results.values()):
    #     email_results(pd.results)
