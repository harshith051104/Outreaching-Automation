# Why LinkedIn Shows Login Page Again (and how to watch it live)

## The Core Problem: Browser Fingerprint Mismatch

LinkedIn session cookies are **tied to the browser that created them**.

### What happens during your Dashboard reconnect:
1. `_start_session_pw()` opens a **VISIBLE Chrome** (`headless=False`)
2. You log in manually
3. LinkedIn records: "This session belongs to a regular Chrome on Windows"
4. Cookies are saved to MongoDB
5. **Browser closes**

### What happens during Playwright task execution:
1. `linkedin_runner.py` spawns a **NEW subprocess**
2. The subprocess loads cookies and calls `_send_connection_request_pw()`
3. This creates a **NEW headless browser** (`headless=True`, the default)
4. Your saved cookies are loaded into this totally new browser
5. LinkedIn detects: "Wait! These cookies came from a visible Chrome, but now they're in a headless browser. Different fingerprint = suspicious!"
6. **Result: LinkedIn invalidates the session and redirects to login**

### Why it fails even after successful reconnect:
- **Different browser type**: Visible Chrome vs headless Chrome = different `navigator` and fingerprint
- **New browser per task**: Every approval creates a brand new browser process instead of reusing the one you logged in with
- **Missing session persistence**: The warm session pool in `linkedin_session_manager.py` is pre-loaded on startup, but the subprocess runner ignores it completely

---

## How to Watch Playwright Live (on your desktop)

The IDE tool environment cannot show browser windows. You must run from **your desktop**:

### Step 1: Open Command Prompt
- Press `Win + R`, type `cmd`, press Enter
- Or right-click Start Menu → "Terminal"

### Step 2: Navigate to your project
```bash
cd "C:\Users\sriha\My work\Outreach\ai_outreach_v2_md_agents"
```

### Step 3: Run the visible browser script
```bash
python run_linkedin_visible.py
```

A **real Chrome window will pop up on your screen** and you'll see:
1. LinkedIn feed load with your saved cookies
2. Navigate to the profile
3. Scan for the Connect button
4. Take screenshots

You'll see exactly why it's failing.

---

## The Fix: Two Options

### Option A — Quick Fix: Run headless=False (visible browser for everything)

Change in `app/config/settings.py`:
```python
# Before
LINKEDIN_HEADLESS: bool = True

# After
LINKEDIN_HEADLESS: bool = False
```

**Result**: Every task opens a visible Chrome window. Better session persistence, but browser windows pop up during API calls.

### Option B — Correct Fix: Reuse warm session browser

Instead of spawning a new subprocess, use `linkedin_session_manager.py` which keeps a browser warm:

1. Server starts → `warm_active_sessions()` opens a browser with your cookies
2. Task runs → Use the WARM browser (don't spawn a new one)
3. Return the result

This is what `linkedin_session_manager.py` warm pool was designed for, but `linkedin_runner.py` ignores it and creates new browsers every time.

---

## Why the "Connect button not found" errors happen

Even when the session works, LinkedIn's UI is constantly changing:
- Button text changes: "Connect" → "Invite" → "Follow"
- CSS selectors get renamed
- Modals have different structures

The 14+ selectors in `send_selectors` might not match the actual buttons.

The diagnostic script (`run_linkedin_visible.py`) will show you the ACTUAL button text and aria-labels on the page, so you can update selectors.
