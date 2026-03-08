# Deal Finder — User Guide

## The Problem

Online deals are everywhere — flash sales, clearance events, limited-time discounts — scattered across dozens of retailer sites, deal forums, and RSS feeds. The challenge is that:

1. **Deals are time-sensitive.** A great discount might last hours. By the time you manually check a site, it's gone.
2. **Volume is overwhelming.** Hundreds of deals are posted daily. Most aren't worth your time. Sorting signal from noise is exhausting.
3. **Prices are hard to evaluate.** A product listed at "$49.99 — 60% off!" sounds great, but is the original price inflated? Is $49.99 actually a good deal for that item? Without knowing the fair market value, you can't tell.
4. **You have preferences.** You care about electronics but not fashion. You want discounts above 30%, not 10%. Generic deal alerts waste your attention.

Existing deal sites (Slickdeals, CamelCamelCamel, etc.) help, but they require you to actively browse, lack AI-powered price verification, and offer limited personalization.

## What Deal Finder Does

Deal Finder is an autonomous system that continuously monitors deal sources, uses AI to evaluate whether each deal is genuinely worth your attention, and sends you a notification only when it finds something that matches your preferences and exceeds your discount threshold.

**In short:** you set your preferences once, and Deal Finder does the rest — scanning, evaluating, and alerting — 24/7.

### How It Works (Step by Step)

```
    ┌─────────────┐
    │  RSS Feeds  │   Retailer sites, deal forums, aggregators
    └──────┬──────┘
           │  Every 5-15 minutes
           ▼
    ┌─────────────┐
    │  1. SCAN    │   Fetch feeds, parse new deals, discard duplicates
    └──────┬──────┘
           │  New deals found
           ▼
    ┌─────────────┐
    │ 2. EVALUATE │   AI estimates fair market value, calculates real discount
    └──────┬──────┘
           │  Discount exceeds your threshold?
           ▼
    ┌─────────────┐
    │  3. NOTIFY  │   AI crafts a personalized message, sends to your phone/email
    └─────────────┘
```

#### Step 1: Scan

The **Scanner Agent** monitors RSS feeds from deal sources you configure (or the defaults). Every 5-15 minutes it:

- Fetches the latest posts from each feed
- Extracts deal details: product name, listed price, description, URL
- Checks against deals already in the database to avoid duplicates
- Stores new deals for evaluation

You don't need to do anything here. The system runs on a schedule automatically.

#### Step 2: Evaluate

The **Evaluator Agent** takes each new deal and asks: *"Is this actually a good deal?"*

It does this by sending the deal's details (product description, brand, category) to an AI model (Claude via AWS Bedrock), which estimates the product's **fair market value** — what the item would typically sell for across retailers.

With the estimated value and the listed sale price, the system calculates a **real discount percentage**:

```
Real Discount = (Estimated Value - Sale Price) / Estimated Value × 100
```

For example:
- A wireless mouse listed at $19.99 "70% off"
- AI estimates fair value at $29.99
- Real discount: 33% — still decent, but not the 70% the retailer claims

Each deal is also assigned a **confidence score** — how certain the AI is in its estimate. Low-confidence estimates are flagged rather than acted on.

Only deals where the real discount exceeds your configured threshold (default: 20%) are passed to the notification step.

#### Step 3: Notify

The **Messenger Agent** takes qualifying deals and:

- Uses AI to craft a concise, personalized message highlighting why this deal matters to you
- Delivers the notification through your preferred channel(s)
- Tracks delivery to avoid sending duplicate alerts

A notification looks something like:

> **🔥 33% off Logitech MX Master 3S**
> $67.99 at Amazon (estimated value: $99.99)
> Category: Electronics — Peripherals
> [View Deal →]

## Your Preferences

You control what Deal Finder sends you through a set of preferences:

### Discount Threshold
The minimum real discount percentage a deal must have before you're notified. Default is **20%**. Set it higher (e.g. 40%) if you only want exceptional deals, or lower (e.g. 10%) if you want to see more.

### Preferred Categories
Select the product categories you care about. Deals outside these categories won't generate notifications. Examples:
- Electronics
- Home & Kitchen
- Gaming
- Tools & Hardware
- Outdoor & Sports

Leave empty to receive deals from all categories.

### Notification Channels
Choose how you want to be reached:

- **Pushover** (push notification to your phone) — fastest, recommended as primary
- **Email** — good for deal digests and detailed summaries

You can enable one or both. Each channel can be configured independently.

### Notification Rate
To avoid alert fatigue, Deal Finder limits the number of notifications per hour. The default is designed to surface only the best deals without flooding your phone.

## Notification Channels

### Pushover (Recommended)

Pushover is a mobile app that receives push notifications. It's the fastest way to get deal alerts.

**Setup:**
1. Install the [Pushover app](https://pushover.net/) on your phone (iOS or Android)
2. Create an account and note your **User Key**
3. Provide your User Key when setting up your Deal Finder account

Push notifications arrive within **2 minutes** of deal discovery. They include the deal title, price, discount, and a direct link.

### Email (SES)

Email notifications are sent via Amazon SES. You'll receive them at the email address associated with your account.

Email is better for:
- End-of-day deal digests (if configured)
- Detailed deal summaries with multiple items
- Backup channel if push notifications are missed

## What Makes Deal Finder Different

### AI-Verified Pricing
Most deal sites show the retailer's claimed discount. Deal Finder independently estimates the fair market value using AI, so you see the **real** discount — not inflated marketing numbers.

### Fully Autonomous
Once configured, the system runs without intervention. No tabs to check, no feeds to refresh, no apps to open. Deals come to you.

### Personalized Filtering
Every notification is filtered through your preferences. You only see deals in your categories, above your discount threshold, delivered to your preferred channels.

### No Browsing Required
Deal Finder is not a website you visit. It's a background service that surfaces deals to you proactively. There's a REST API for programmatic access if you want it, but the core experience is push notifications.

## Frequently Asked Questions

### What deal sources does it monitor?
Deal Finder scans RSS feeds from major deal aggregators, retailer deal pages, and community deal forums. The list of sources is configurable and can be expanded.

### How accurate is the AI price estimation?
The AI provides an estimate, not a guarantee. Each estimate includes a confidence score. High-confidence estimates (common products with well-known pricing) are very reliable. Niche or unusual items may have wider estimation ranges. The system errs on the side of caution — it would rather miss a borderline deal than send you a bad recommendation.

### How fast are notifications?
From the moment a deal appears in an RSS feed to the notification arriving on your phone: **under 2 minutes** in typical conditions. The pipeline runs every 5-15 minutes, so in the worst case, a deal posted just after a scan cycle completes will be picked up in the next cycle.

### Will I get spammed?
No. Deal Finder includes several anti-spam protections:
- **Discount threshold**: only deals above your minimum qualify
- **Category filtering**: only your preferred categories
- **Deduplication**: the same deal is never sent twice (24-hour deduplication window)
- **Rate limiting**: a maximum number of notifications per hour

### Can I adjust my preferences after setup?
Yes. Your discount threshold, preferred categories, and notification channels can be updated at any time via the REST API.

### What does it cost me?
Deal Finder is a self-hosted system. The AWS infrastructure costs approximately **$200-500/month** to run at full capacity. During low-usage periods, costs drop to as low as **$4-10/month** because the serverless architecture scales to near-zero when idle.

### Is my data private?
Deal Finder stores only the minimum data needed to operate: your email, notification preferences, and Pushover user key (if applicable). All data is encrypted at rest and in transit. The system runs entirely within your own AWS account — no data is shared with third parties.

## System Status & Roadmap

Deal Finder is currently under active development.

- ✅ **Infrastructure**: AWS networking, storage, and monitoring are deployed
- ✅ **Data Layer**: Database models, repository layer, and search client are built
- 🔜 **Core Pipeline**: Scanner, Evaluator, and Step Functions orchestration (next)
- 🔜 **Notifications + API**: Pushover, email delivery, and REST API
- 🔜 **Production Deploy**: End-to-end deployment and validation

The core pipeline (scanning, evaluation, notification) is the next milestone. Once complete, early users will be able to receive deal alerts.
