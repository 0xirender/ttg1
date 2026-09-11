# Telegram Channel Automation (GUI in GitHub Actions)

Automated Telegram Web channel visit simulator running visibly inside GitHub Actions via **Xvfb (Virtual Desktop Display 1920x1080)**.

---

## 🚀 Setup & Deployment Guide

### 1. Upload to GitHub
Initialize git and push the contents of this folder to your GitHub repository:
```bash
git init
git add .
git commit -m "Initial commit for Telegram GUI Automation"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo-name>.git
git push -u origin main
```

---

### 2. Configure GitHub Secrets (Required)
Your sensitive credentials are never committed to GitHub directly. Instead, store them safely in **Repository Secrets**:

1. Go to your GitHub Repository.
2. Navigate to **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
3. Click **New repository secret**:
   - **Secret 1 (Required):**
     - **Name:** `TELEGRAM_SESSION`
     - **Secret:** *(Paste your Telethon session string)*
   - **Secret 2 (Optional - For 100% Privacy):**
     - **Name:** `CONFIG_PY`
     - **Secret:** *(Paste the entire text content of config.py)*
     - *If `CONFIG_PY` is set, the Action will automatically recreate `config.py` in memory at runtime, keeping your API_ID, API_HASH, and URLs completely secret!*

---

### 3. Running the Automation
1. In your GitHub repository, click on the **Actions** tab.
2. Select **Telegram Channel Automation (GUI)** from the left sidebar.
3. Click **Run workflow** $\rightarrow$ **Run workflow**.
4. The workflow will launch and run in an **Infinite Continuous Loop**:
   - Fetches channels live from `https://chvisit.pages.dev/chvisit.json`
   - Visits each channel sequentially with humanized typing, scrolling, reading dwell time, poll voting, and reactions
   - Takes a 2 to 5 minute break between cycles
   - Automatically refreshes channel list and restarts from channel #1 continuously
