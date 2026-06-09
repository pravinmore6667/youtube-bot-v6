> ⚠️ **FREE-ONLY ARCHITECTURE**: This bot uses only approved free providers. Together AI, DeepInfra, SambaNova, and Grok are not supported.

# 🤖 Enterprise YouTube AI Automation Bot

A fully autonomous, self-healing, zero-cost (free-tier optimized) YouTube automation system that orchestrates AI providers to research, script, narrate, edit, and upload videos 24/7.

## 🌟 Project Overview

This bot completely automates the YouTube content creation lifecycle:
1. **Topic Generation & Research:** Selects trending topics based on the channel's niche.
2. **Scripting:** Writes highly engaging, retention-optimized scripts.
3. **Voiceover:** Generates human-like TTS (Text-to-Speech) using Edge-TTS.
4. **Video Assembly:** Fetches stock footage (Pexels/Pixabay), applies Ken Burns effects, background music, transitions, and text overlays via MoviePy.
5. **Thumbnails:** Generates thumbnails via Pollinations.ai.
6. **Upload:** Automatically uploads the video to YouTube via the Data API.

### 🧠 Enterprise AI Router & Failover
Never depend on a single AI provider again. The system uses a highly resilient, self-healing **AI Router** that dynamically routes requests between multiple free-tier and community providers based on live health scores (latency, success rate, failures).

**Supported Providers:**
- **Tier 1:** Gemini
- **Tier 2 (Free/Optional):** Groq, Cerebras, NVIDIA (free tier), OpenRouter (free models)
- **Tier 3 (Free Fallbacks):** Pollinations.ai, Puter, AI Horde

**Features:**
- **Zero-Cost Operation:** Prioritizes free models and community endpoints.
- **Auto-Recovery:** Temporarily degrades failing providers and background-probes them for recovery every 5 minutes.
- **State Checkpointing:** Resumes video generation exactly where it crashed.
- **Smart Continuation:** If an AI provider gets cut off mid-sentence due to context limits, the bot seamlessly resumes generation on the next provider without losing progress.

---

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/youtube-ai-bot.git
cd youtube-ai-bot
```

### 2. System Dependencies
You must have FFmpeg installed for video rendering:
- **Ubuntu/Debian:** `sudo apt update && sudo apt install -y ffmpeg`
- **Mac (Homebrew):** `brew install ffmpeg`
- **Windows:** Download from [FFmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

### 3. Create a Virtual Environment
Windows: `python -m venv .venv` and `.venv\Scripts\activate`
Linux/Mac: `python3 -m venv .venv` and `source .venv/bin/activate`

### 4. Install Requirements
```bash
pip install -r requirements.txt
```

### 5. Configure Environment
Copy the example environment file:
```bash
cp .env.example .env
```
Edit `.env` and fill in your API keys (you only need *at least one* AI key to start, though adding multiple ensures 100% uptime).

### 6. YouTube Authentication
To enable automatic uploads, you must authorize the bot with your Google Cloud account:
```bash
python auth_setup.py
```
This will open a browser window to authenticate and will automatically save your `YOUTUBE_REFRESH_TOKEN` to your `.env` file.

---

## 💻 Running the Application

### Startup Validation
Before running the bot, ensure your environment is configured correctly:
```bash
python main.py --setup-check
```

### Run 24/7 Background Bot & Dashboard
```bash
python main.py
```
This starts the background job scheduler and boots the web dashboard.

### Generate a Video Immediately
```bash
# Generate a video on an automatically selected topic
python main.py --run-now

# Generate a video on a specific topic
python main.py --run-now --topic "The Future of AI Agents"
```

---

## 📊 Web Dashboard

Access the fully-featured browser monitoring dashboard at:
**[http://localhost:5000](http://localhost:5000)** (or your configured `PORT`).

**Features:**
- **Live Provider Status:** See latency, success rates, and active fallback tiers for all AI providers.
- **Queue Management:** View pending, running, and failed jobs.
- **Live Logs:** Real-time, auto-refreshing system logs via SSE.
- **Outputs:** View and manage generated thumbnails and videos.
- **Metrics:** Track uploaded videos and channel performance.

---

## 🛠️ Troubleshooting & Recovery

- **ModuleNotFoundError / Import Errors:** Ensure your virtual environment is activated and you ran `pip install -r requirements.txt`.
- **"FFmpeg not found":** Ensure FFmpeg is installed at the system level and accessible in your environment's PATH.
- **"No AI provider available":** Ensure you've added at least one valid API key to your `.env` file. The router will automatically detect healthy keys.
- **Interrupted Generations:** If you cancel a job or the server loses power, you do not need to restart the entire video. Running `python main.py --run-now` will check the local SQLite database and resume the pipeline exactly where it left off.
