# SKF Boosting Ads Report Bot

Meta Ads রিপোর্ট অটোমেশন বট — Telegram থেকে command দিয়ে client দের ads report generate করুন।

## Features
- `/report` — সব client এর report
- `/report ClientName` — নির্দিষ্ট client এর report
- Date range: Today, Yesterday, 7/15/30/90 days, Custom
- Format: Text, PDF, Text+PDF
- Campaign-wise breakdown

## Setup

### 1. Environment Variables
`.env.example` কপি করে `.env` বানান:
```
cp .env.example .env
```
তারপর values fill করুন।

### 2. আপনার Telegram User ID জানুন
Telegram এ `@userinfobot` তে `/start` দিন।

### 3. নতুন Client যোগ করুন
`config.py` তে `CLIENTS` dict এ add করুন:
```python
"Client Name": {
    "account_id": "act_XXXXXXXXXX",
    "active": True,
},
```

## Railway Deploy

1. GitHub এ push করুন
2. railway.app এ নতুন project → GitHub repo connect করুন
3. Environment variables add করুন:
   - `TELEGRAM_BOT_TOKEN`
   - `META_ACCESS_TOKEN`
   - `ALLOWED_USER_IDS`
4. Deploy!

## Commands
| Command | কাজ |
|---------|-----|
| `/start` | Bot শুরু করুন |
| `/report` | সব client এর report |
| `/report SKF Boosting` | নির্দিষ্ট client |
| `/clients` | Client list |
| `/cancel` | বাতিল |
| `/help` | সাহায্য |
