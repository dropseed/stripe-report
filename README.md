# stripe-report

A dead-simple email digest of Stripe activity over the last 24 hours (meant to be sent daily).

```sh
pipx run --spec git+https://github.com/dropseed/stripe-report stripe-report
```

This is intended to help keep tabs on SaaS activity happening in Stripe.
Especially if you have the payment email notifications turned off,
or process check/ACH payments in Stripe and need to keep tabs on [open invoices](https://stripe.com/docs/invoicing/overview).

![CleanShot 2023-01-05 at 16 22 50](https://user-images.githubusercontent.com/649496/210891569-ab12d6b1-6d15-4972-b607-355e22be346d.png)

## Settings

All settings are configured by environment variables ([see GitHub Action example below](#github-actions)).

You can include multiple Stripe accounts in your report -- the account keys are parsed from env variables beginning with `STRIPE_KEY_`.
For example, `STRIPE_KEY_accountone=rk_live_...` and `STRIPE_KEY_accounttwo=rk_live_...`.

When creating Stripe API keys,
you should use [restricted keys](https://stripe.com/docs/keys#create-restricted-api-secret-key),
and give read permission to Events and Invoices.

## GitHub Actions

Set your repository secrets, then save this in a GitHub repo for a daily stripe report:

```yml
# .github/workflows/stripe-report.yml
name: stripe-report

on:
  schedule:
  - cron: 0 8 * * *
  workflow_dispatch: {}

jobs:
  send:
    runs-on: ubuntu-latest
    steps:
    - run: pipx run --spec git+https://github.com/dropseed/stripe-report stripe-report
      env:
        TO_EMAIL: me@example.com
        FROM_EMAIL: "Reports <reports@example.com>"
        SMTP_HOST: smtp.postmarkapp.com
        SMTP_USERNAME: ${{ secrets.POSTMARK_TOKEN }}
        SMTP_PASSWORD: ${{ secrets.POSTMARK_TOKEN }}
        STRIPE_KEY_mybusiness: ${{ secrets.STRIPE_KEY_MYBUSINESS }}
```
