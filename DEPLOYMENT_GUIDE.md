# Room 48 — Beginner's Deployment Guide

Welcome. This guide will get **Room 48** running on a server and shared with your friends. It assumes you've never deployed software before. Take your time — none of this is hard, but every step matters.

We'll cover three paths, from easiest to most flexible:

- **Path A (recommended):** Run on **Railway** — a friendly cloud platform. Total time: ~30 minutes. Cost: ~$5/month + Anthropic API usage.
- **Path B:** Run on **Render** — similar to Railway. Roughly the same cost.
- **Path C:** Run on your own laptop and share via **ngrok** — free, but your laptop must stay on.

You only need to pick one path. I recommend **Path A**.

---

## Before you start — get your Anthropic API key

Room 48 uses Anthropic's Claude to write the astrology narratives. You need an API key.

1. Go to **https://console.anthropic.com/**
2. Sign up (free) with an email.
3. Add a payment method. Anthropic gives you a small free credit to start; after that, **each full horoscope reading costs roughly $0.05–$0.15** depending on length and model. With prompt caching (which Room 48 uses automatically), repeat readings cost much less.
4. Go to **API Keys** → **Create Key**. Copy the key. It looks like `sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`.
5. **Save it somewhere safe.** You'll need it in a few minutes. If you lose it, you can always create a new one.

> **Cost tip**: Set a monthly spend limit in your Anthropic console (Settings → Billing → Limits). If 50 friends try Room 48 at once, you don't want a $500 surprise bill. Start with a $20/month cap — you can always raise it.

---

## Path A — Deploy on Railway (recommended)

Railway is a hosting service designed to be the simplest possible thing for non-engineers. You upload your code, it runs.

### Step A1 — Create accounts

1. **GitHub account**: go to https://github.com/signup and make a free account. (Railway pulls your code from GitHub.)
2. **Railway account**: go to https://railway.app and click **Login with GitHub**. This connects the two.

### Step A2 — Get the Room 48 code onto your computer

1. Download the **`room48.zip`** file (the same one you received with this guide).
2. Unzip it. You'll see a folder called `kerala_astro` containing all the source code.
3. Rename the folder to whatever you like — say `room48-app` — and put it somewhere you can find it (Desktop is fine).

### Step A3 — Put the code on GitHub

1. On GitHub.com, click the **+** in the top right → **New repository**.
2. Name it `room48` (or anything you want). Leave everything else default. Click **Create repository**.
3. On the next page, GitHub shows commands. We'll use the **"uploading an existing file"** link instead — it's easier than the command line. Click that link.
4. Drag every file and folder from inside your `room48-app` folder into the upload area. *Not the outer folder itself — the contents.* So Railway sees `Dockerfile`, `requirements.txt`, `kerala_astro/` etc. at the top level.
5. Scroll down, click **Commit changes**.

### Step A4 — Deploy to Railway

1. Go to https://railway.app and click **New Project**.
2. Pick **Deploy from GitHub repo**.
3. Authorize Railway to see your GitHub, then pick the `room48` repository you just made.
4. Railway will start building. It sees the `Dockerfile` and knows what to do.
5. While it builds, click **Variables** in the side panel. Add a variable:
   - **Name**: `ANTHROPIC_API_KEY`
   - **Value**: paste the `sk-ant-...` key from earlier
6. Click **Settings** → scroll to **Networking** → click **Generate Domain**. Railway gives you a public URL like `room48-production-abcd.up.railway.app`.
7. Wait for the build to finish (1-3 minutes). When the status turns green, click the URL.

You should see a JSON page that starts with `"service": "Room 48 — Kerala Astrology API"`. **You're live.**

### Step A5 — Try it

In a browser, go to: `https://your-railway-url.up.railway.app/docs`

You'll see an interactive page (Swagger UI) listing all the endpoints. Click **POST /api/v1/narrative** → **Try it out** → fill in birth details → **Execute**. You'll see the LLM-generated reading appear below.

### Step A6 — Share with friends

Send them the URL. Anyone can use the `/docs` page to try it. Or if you want a nicer experience, see **Building a frontend** below.

---

## Path B — Deploy on Render

Render is very similar to Railway. Slightly more configuration but a generous free tier.

1. Make a GitHub repo and upload the code as in steps A2–A3 above.
2. Go to https://render.com → sign in with GitHub.
3. Click **New** → **Web Service** → connect to your repo.
4. Render auto-detects the Dockerfile. Settings to confirm:
   - **Environment**: Docker
   - **Region**: pick the one closest to your users (Singapore for India, Frankfurt for Europe, Oregon for US).
   - **Plan**: Starter ($7/month) for steady use, or Free (sleeps after 15 min of inactivity — fine for testing).
5. Under **Environment Variables**, add `ANTHROPIC_API_KEY` with your key.
6. Click **Create Web Service**. Render builds and deploys; you'll get a URL like `https://room48.onrender.com`.

Same `/docs` page as Path A.

---

## Path C — Run on your laptop, share via ngrok

This is the cheapest way (free) but your laptop must stay on and connected to the internet while friends are using it. Good for quick demos to a few people.

### Step C1 — Install Python

- **Mac**: open Terminal, run `python3 --version`. If you see `Python 3.10` or higher, you're set. If not, install from https://www.python.org/downloads/.
- **Windows**: install from https://www.python.org/downloads/. **Important**: at the installer screen, tick "Add Python to PATH" before clicking Install.
- **Linux**: you almost certainly already have it.

### Step C2 — Get the code and install dependencies

1. Unzip `room48.zip` into a folder, say `~/Desktop/room48-app`.
2. Open a Terminal (Mac/Linux) or PowerShell (Windows).
3. Navigate into the folder:
   ```
   cd ~/Desktop/room48-app
   ```
   (On Windows, this is `cd %USERPROFILE%\Desktop\room48-app`)
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   This might take 1–2 minutes.

### Step C3 — Set your API key and start the server

Mac/Linux:
```
export ANTHROPIC_API_KEY=sk-ant-your-key-here
uvicorn kerala_astro.api.main:app --host 0.0.0.0 --port 8000
```

Windows PowerShell:
```
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
uvicorn kerala_astro.api.main:app --host 0.0.0.0 --port 8000
```

You should see something like:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Open http://localhost:8000/docs in a browser. Try a request.

### Step C4 — Expose to friends with ngrok

Right now only you can use it (it's on your computer). To let friends use it:

1. Go to https://ngrok.com/ and sign up (free).
2. Install ngrok following their instructions for your OS.
3. Run their connection command (one-time setup with your authtoken — ngrok shows it on signup).
4. In a **second** Terminal window (leave the server running in the first):
   ```
   ngrok http 8000
   ```
5. ngrok shows a public URL like `https://random-words-1234.ngrok-free.app`. **That's your link.** Anyone with this URL can use Room 48 while your laptop is on.

> **Important**: every time you restart ngrok, the URL changes. For a stable URL you need a paid ngrok plan ($8/month) or you should use Railway (Path A) instead.

---

## Building a simple frontend (optional, but much nicer than `/docs`)

The `/docs` page works but looks like developer documentation. For a friendlier experience, you can build a simple web page with a form. Here's the easiest path:

1. Make a new file called `index.html` (anywhere).
2. Paste this in:

```html
<!DOCTYPE html>
<html>
<head>
  <title>Room 48 — Kerala Astrology</title>
  <style>
    body { font-family: Georgia, serif; max-width: 700px; margin: 2rem auto; padding: 1rem; }
    h1 { color: #6B2737; }
    label { display: block; margin-top: 1rem; }
    input { width: 100%; padding: 0.5rem; margin-top: 0.25rem; font-size: 1rem; }
    button { margin-top: 1.5rem; padding: 0.75rem 2rem; font-size: 1rem;
             background: #6B2737; color: white; border: none; cursor: pointer; }
    #result { margin-top: 2rem; white-space: pre-wrap; line-height: 1.6; }
  </style>
</head>
<body>
  <h1>Room 48</h1>
  <p>A Kerala-tradition astrological reading from your birth details.</p>

  <label>Name <input id="name" /></label>
  <label>Date of birth (YYYY-MM-DD) <input id="dob" placeholder="1990-06-15" /></label>
  <label>Time of birth (HH:MM, 24h) <input id="tob" placeholder="07:45" /></label>
  <label>Latitude (e.g. 8.5241 for Trivandrum) <input id="lat" /></label>
  <label>Longitude (e.g. 76.9366 for Trivandrum) <input id="lon" /></label>
  <label>Timezone (e.g. Asia/Kolkata) <input id="tz" value="Asia/Kolkata" /></label>

  <button onclick="go()">Generate Reading</button>
  <div id="result"></div>

  <script>
    const API_URL = "https://YOUR-RAILWAY-URL.up.railway.app";  // ← change this!

    async function go() {
      const res = document.getElementById("result");
      res.textContent = "Generating your reading... this takes about 20-30 seconds.";
      const [y, m, d] = document.getElementById("dob").value.split("-").map(Number);
      const [hh, mm] = document.getElementById("tob").value.split(":").map(Number);
      const r = await fetch(API_URL + "/api/v1/narrative", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          name: document.getElementById("name").value,
          year: y, month: m, day: d, hour: hh, minute: mm,
          latitude: parseFloat(document.getElementById("lat").value),
          longitude: parseFloat(document.getElementById("lon").value),
          timezone_name: document.getElementById("tz").value,
        }),
      });
      const data = await r.json();
      res.textContent = data.markdown || JSON.stringify(data, null, 2);
    }
  </script>
</body>
</html>
```

3. **Change `YOUR-RAILWAY-URL` to your real Railway URL** (the one from Step A4).
4. Save the file. Open it in any browser by double-clicking it. It works.
5. To host it publicly, put it on **Netlify Drop** (https://app.netlify.com/drop) — drag the `index.html` file, get a public URL. Free.

---

## Looking after Room 48 once it's live

### Check it's healthy

Visit `https://your-url/health`. You should see:
```json
{"status":"ok","service":"room48-kerala-astrology","version":"1.0.0","swiss_ephemeris":true}
```

If `status` is `degraded`, something is wrong with the astronomical engine — check the Railway logs.

### Watch your costs

- **Railway dashboard** → Usage tab: how much compute you're using.
- **Anthropic console** → Usage tab: how many tokens and how much it's costing.

Room 48 has three built-in cost controls:

1. **Prompt caching** is automatic. Looking at the response `usage` field, you'll see `cache_read_tokens` growing — those are cheap reads.
2. **Response cache** is on by default. If two people generate the *same* reading (same birth details, same options), the second one comes from disk — no LLM call at all.
3. **Parallel generation** is on by default. Doesn't reduce cost but makes the response feel much faster.

### Updating Room 48 with new features

When you have new code:

- **Path A/B (Railway/Render)**: drag the new files into your GitHub repo (use the **Add file → Upload files** button), commit. Railway/Render auto-redeploys in a couple of minutes.
- **Path C (laptop)**: just replace the files and restart `uvicorn`.

### Backing up the response cache

The response cache lives in `~/.room48/narrative_cache/`. If you want to keep readings even across redeployments, the docker-compose setup already mounts this as a persistent volume. On Railway, you'd add a Railway Volume mounted at `/root/.room48`.

---

## When things go wrong — common issues

**"Connection refused" or the page doesn't load**
The server isn't running. Railway: check the deployment status in the dashboard. Laptop: check the terminal where `uvicorn` was running.

**"LLM provider unavailable" or 503 error on `/api/v1/narrative`**
Your `ANTHROPIC_API_KEY` is missing or wrong. Check the variable in Railway/Render, or that `echo $ANTHROPIC_API_KEY` shows the right value on your laptop.

**"timezone could not be determined" error**
Send a `timezone_name` field with the request, like `"Asia/Kolkata"`. The auto-detection usually works but sometimes coordinates near borders confuse it.

**Reading takes 30+ seconds**
That's normal for a first-time, fully-generated reading. Repeat readings of the same chart are instant (response cache). To reduce time on first reading, you could request fewer sections by passing `"sections": ["overview", "yogas", "current_dasha"]` in the request.

**"422 Unprocessable Entity"**
A field in your request is invalid. The error message tells you which one — for example, day must be 1-31, year must be 1800-2200, language must be english/manglish/malayalam.

**The reading mentions a yoga or position that isn't in the chart**
Shouldn't happen — the LLM is heavily constrained. If it does, please save the request and response and report it; this is a real bug worth fixing.

---

## What's next

Once Room 48 is up, common next steps people ask about:

- **A nicer-looking frontend**: the `index.html` above is functional but plain. A designer friend or even a free template from https://html5up.net/ would dress it up.
- **Custom domain**: Railway and Render both let you point your own domain (like `room48.app`) at the service. Buy a domain from Cloudflare (~$10/year), follow their DNS instructions.
- **Rate limiting**: if Room 48 goes viral, you don't want one user blowing through your API budget. Add a tool like Cloudflare in front of the service to limit requests.
- **Login / saved readings**: if you want users to come back to past readings, that's a database + login flow. A bigger project — I'd suggest building it once you know who's actually using Room 48.

---

## Where to ask for help

- **Railway problems** → https://help.railway.app
- **Anthropic API problems** → https://support.claude.com
- **Code problems with Room 48 itself** → the README.md included with the project covers technical details; the Architecture section there is the map.

Good luck. Take it one step at a time.
