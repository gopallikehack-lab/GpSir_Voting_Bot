# GpSir Voting Bot

Telegram voting/giveaway bot. Anyone who joins your channel can add their name as a
candidate; the bot posts their entry card in the channel with **Vote / Add Your Name /
Share** buttons. Votes only count from users who are members of that channel.

## How it works

1. `/start` → user must join your main private channel first (force-sub gate), sees a
   fancy-font welcome + your welcome image.
2. **Admin flow:** tap "Start Giveaway Setup" → add the bot as **admin** to the channel
   you want to run voting in → send that channel's `@username` or numeric ID → bot
   confirms it's an admin → send a giveaway title → bot generates a shareable
   "Add Your Name" link and posts an announcement in the channel.
3. **Participant flow:** anyone taps the link → must join the target channel → confirms
   → bot posts their entry card in the channel.
4. Anyone taps **Vote** on an entry card → bot checks they're a member of that channel
   and haven't already voted for that person → vote count updates live on the card.
5. Owner sends `/endvoting` in DM with the bot → voting locks, final ranked results are
   posted to the channel and to the owner.

## Files

- `api/index.py` — the whole bot (Flask webhook handler)
- `requirements.txt` — `Flask`, `requests`
- `vercel.json` — routes all requests to the Flask app
- `.env.example` — required environment variables (copy the values into Vercel's
  Environment Variables settings, not into a committed `.env`)

## 1. Create the bot

1. Talk to [@BotFather](https://t.me/BotFather), `/newbot`, set the username to
   `GpSir_Voting_Bot` (or whatever you registered).
2. Save the token it gives you — this is `BOT_TOKEN`.

## 2. Set up Upstash Redis

1. Create a free database at [upstash.com](https://upstash.com).
2. Copy the **REST URL** and **REST Token** from the database's "REST API" tab —
   these are `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`.

## 3. Deploy to Vercel

1. Push this folder to a new GitHub repo.
2. In Vercel, "Add New Project" → import that repo.
3. Under **Environment Variables**, add everything listed in `.env.example` with your
   real values:
   - `BOT_TOKEN`
   - `BOT_USERNAME` (no `@`)
   - `MAIN_CHANNEL_ID` (your channel's numeric id, e.g. `-1004297567227`)
   - `MAIN_CHANNEL_LINK` (the invite link)
   - `MAIN_CHANNEL_NAME` (display name shown to users)
   - `WELCOME_IMAGE_URL`
   - `UPSTASH_REDIS_REST_URL`
   - `UPSTASH_REDIS_REST_TOKEN`
4. Deploy. Note your deployment URL, e.g. `https://your-app.vercel.app`.

## 4. Make the bot an admin in your main channel

The bot needs to be an **admin** of `MAIN_CHANNEL_ID` itself, so it can check whether a
user has joined it (`getChatMember` requires the bot to have visibility into the chat).
Add `@GpSir_Voting_Bot` as admin in that channel too — this is separate from giveaway
owners adding it to *their* channels.

## 5. Set the Telegram webhook

Run this once (replace the token and URL):

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://your-app.vercel.app/api/webhook"
```

You should get `{"ok":true,"result":true,...}`.

## Notes / things you may want to extend

- **Auto-approve join requests:** if your channels use "approve join requests" instead
  of instant join, add a `chat_join_request` handler that calls
  `approveChatJoinRequest` — currently the bot just checks membership, it doesn't
  auto-approve.
- **Multiple giveaways per owner:** this version supports one active giveaway per admin
  at a time (keyed by their user ID). Running a second `/start → setup` overwrites the
  channel/title for a new giveaway once the previous one is ended.
- **Self-voting** is blocked; duplicate voting per person is blocked via a Redis set.
- All bot text uses `HTML` parse mode, matching your other bots.

