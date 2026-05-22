# Room 48 — Running Fully Offline on Your Laptop

This guide gets Room 48 running on your laptop with **no internet required at all** after the one-time setup. Pick the path that suits you.

## What works offline

| Feature | Offline? |
| --- | --- |
| Birth chart (planets, lagnam, nakshatram) | ✅ Yes |
| All yoga detection (Pancha Mahapurusha, Raja, Kuja Dosha, etc.) | ✅ Yes |
| Vimshottari Dasha periods and sub-periods | ✅ Yes |
| Detailed text report (rule-based interpretation) | ✅ Yes |
| LLM-narrated flowing prose (the "astrologer reading") | ✅ Yes — needs Ollama (free, runs locally) |
| The one-time installation step | ❌ Needs internet once |

You have **two paths**. Pick one.

---

## Path 1: Rules-only mode (simplest, no AI)

You get the full chart, all yogas, and a detailed text report. You don't get the flowing LLM-narrated prose paragraphs — instead you get a structured rule-based report. For most users this is plenty.

### Step 1 — Install Python (one-time, requires internet)

If you already have Python 3.10 or newer, skip this.

- **Mac**: open Terminal, type `python3 --version`. If it says 3.10+, you're set. Otherwise install from https://www.python.org/downloads/.
- **Windows**: download from https://www.python.org/downloads/ and **tick "Add Python to PATH"** in the installer.
- **Linux**: you almost certainly have it already.

### Step 2 — Unzip Room 48 and install dependencies (one-time, requires internet)

1. Unzip `room48.zip` to somewhere on your laptop, e.g. `~/Desktop/room48`.
2. Open a Terminal (Mac/Linux) or PowerShell (Windows).
3. Navigate to the folder:
   ```
   cd ~/Desktop/room48
   ```
4. Install the Python dependencies:
   ```
   pip install -r requirements.txt
   ```
   This downloads about 50MB of packages. Takes 1–2 minutes.

### Step 3 — Run it (offline from here on)

To generate a reading, run:

```
python -m kerala_astro.offline
```

It will ask you a few questions (name, date of birth, time, place, lat/lon), then print a full astrological report.

Or if you have your birth details in a JSON file:

```
python -m kerala_astro.offline --input my_birth.json --output my_reading.txt
```

That's it. **No internet needed.** Run it on a plane, in a basement, anywhere.

### Sharing with friends (Path 1)

For friends to use it on their own laptop:

1. Email them `room48.zip` and this guide.
2. They follow Steps 1–3 above.
3. They run `python -m kerala_astro.offline` to get their reading.

If you want them to use it from *your* laptop, you can run the web service (`uvicorn kerala_astro.api.main:app --port 8000`) and they can point a browser at `http://your-laptop-ip:8000/docs` — but that only works when they're on the same Wi-Fi network as you.

---

## Path 2: Offline + LLM prose narration (with Ollama)

This adds the flowing astrologer-style prose. You install **Ollama** (a free tool that runs LLMs on your own laptop) and Room 48 talks to it instead of to Anthropic over the internet.

> **Hardware check**: you'll need at least 8GB of RAM for the small model, 16GB for the better one. A reasonably new laptop is fine. Apple Silicon Macs and laptops with NVIDIA GPUs are noticeably faster.

### Step 1 — Do everything from Path 1 first

Install Python, unzip Room 48, run `pip install -r requirements.txt`. Same as above.

### Step 2 — Install Ollama (one-time, requires internet)

1. Go to **https://ollama.com/download**
2. Download the installer for your OS.
3. Run the installer. On Mac, drag Ollama to Applications. On Windows, run the .exe.
4. Open Ollama once to start the background service. You'll see a small icon in your menu bar / system tray.

### Step 3 — Download an AI model (one-time, requires internet)

Open a Terminal and run **one** of these:

```
# Recommended starting point — about 5GB, runs on 8GB RAM
ollama pull llama3.1:8b

# Better quality if you have 16GB+ RAM — about 9GB
ollama pull qwen2.5:14b

# Best quality if you have a strong machine — about 40GB
ollama pull llama3.1:70b
```

The download takes a few minutes depending on your internet speed. After this, **no more internet needed**.

### Step 4 — Verify Ollama is running

```
curl http://localhost:11434/api/tags
```

You should see JSON listing the models you've pulled. If you get "connection refused", make sure Ollama is running (look for the icon in your menu bar / system tray).

### Step 5 — Generate a reading with LLM prose

```
python -m kerala_astro.offline --input sample_birth.json --output reading.md
```

Room 48 auto-detects that Ollama is running and uses it. The first run can take 1–3 minutes because Ollama loads the model into memory; subsequent runs are faster.

To pick a specific model:

```
python -m kerala_astro.offline --input sample_birth.json \
    --mode ollama --model qwen2.5:14b --output reading.md
```

### Step 6 — Run the web service offline (optional)

To use the friendly web interface offline:

```
uvicorn kerala_astro.api.main:app --port 8000
```

Open **http://localhost:8000/docs** in your browser. The narrative endpoint will use Ollama automatically. To control which provider it uses:

| Goal | Set this environment variable before launching |
| --- | --- |
| Force Ollama | `ROOM48_USE_OLLAMA=1` |
| Use a specific Ollama model | `OLLAMA_MODEL=qwen2.5:14b` |
| Force Anthropic (cloud) | `ANTHROPIC_API_KEY=sk-ant-...` |

For example, on Mac/Linux:

```
ROOM48_USE_OLLAMA=1 OLLAMA_MODEL=qwen2.5:14b \
  uvicorn kerala_astro.api.main:app --port 8000
```

---

## Quick comparison: cloud vs local

| | Cloud (Anthropic) | Local (Ollama) |
| --- | --- | --- |
| **Internet required** | Yes, every reading | Only for setup |
| **Cost per reading** | $0.05–$0.15 | Free (uses your electricity) |
| **Quality of prose** | Excellent (Claude Opus 4.7) | Good (depends on model size) |
| **Speed** | ~10–20 seconds total | 1–3 minutes (CPU) / 20-40s (GPU) |
| **Privacy** | Birth details sent to Anthropic | Nothing leaves your laptop |
| **Hardware needed** | Any laptop | 8GB+ RAM recommended |

For a small group of friends, **Path 1 (rules-only)** is the simplest. If you want the prose paragraphs and your laptop has enough RAM, **Path 2 (Ollama)** is the privacy-preserving option.

---

## Sharing Room 48 with friends (offline edition)

You have two ways to share an offline copy:

### Option A: Send them everything

1. Email or USB-stick them `room48.zip` plus this guide.
2. They do the install on their own laptop.
3. Each friend has their own private copy. Nothing is shared.

### Option B: Host on your own laptop, friends connect over Wi-Fi

This only works while everyone is on the same network (like your home Wi-Fi).

1. On your laptop, run:
   ```
   uvicorn kerala_astro.api.main:app --host 0.0.0.0 --port 8000
   ```
2. Find your laptop's local IP address:
   - **Mac**: System Settings → Network → click the active network → look for "IP Address" (looks like 192.168.x.x).
   - **Windows**: open PowerShell, run `ipconfig`, look for "IPv4 Address" in your Wi-Fi adapter.
   - **Linux**: `hostname -I`.
3. Tell your friends to open `http://YOUR-LOCAL-IP:8000/docs` in their browser, e.g. `http://192.168.1.42:8000/docs`.
4. They can run readings as long as you keep your laptop on and the service running.

For Wi-Fi-network deployment that doesn't depend on a single laptop, the cloud deployment guide (`DEPLOYMENT_GUIDE.md`) is the better path.

---

## Troubleshooting

**"command not found: python" or "python is not recognized"**
Python isn't installed or isn't in your PATH. On Windows, re-run the Python installer and tick "Add Python to PATH". On Mac, try `python3` instead of `python`.

**"pip: command not found"**
On Mac/Linux, try `python3 -m pip install -r requirements.txt`. On Windows, try `py -m pip install -r requirements.txt`.

**"Could not reach Ollama at http://localhost:11434"**
Ollama isn't running. Look for the Ollama icon in your menu bar (Mac) or system tray (Windows). If it's not there, launch Ollama. If you're on Linux, run `ollama serve` in a separate terminal and leave it running.

**Ollama is running but Room 48 still falls back to rules mode**
You probably haven't pulled any models yet. Run `ollama pull llama3.1:8b` and try again.

**The LLM prose is bad / nonsensical / makes things up**
Smaller models are less reliable. Pull `qwen2.5:14b` (or larger if your RAM allows) for noticeably better quality. The 70b model is the most reliable but needs 40GB+ RAM.

**"timezone could not be determined"**
Add `--timezone Asia/Kolkata` (or your actual timezone) to your input JSON: `"timezone_name": "Asia/Kolkata"`.

**Reading takes forever**
Ollama on a CPU-only laptop is slow. The first run is the slowest (loading the model). Try a smaller model: `--model llama3.1:8b`. Or just use rules-only mode (`--mode rules`).
