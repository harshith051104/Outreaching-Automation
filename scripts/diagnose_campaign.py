"""
Read-only diagnostic for the 'not sending automatically' issue.

Dumps, for a campaign:
  1. Lead statuses (the scheduler only picks status == "new")
  2. scheduled_tasks state (what's pending/processing/executed/failed)
  3. Gmail account state (is_active / connection_error)
  4. emails collection state (sent/failed/draft)

NOTHING is modified. Pure reads.
"""

import os
import re
import sys
from collections import Counter
from pymongo import MongoClient

# The campaign inserted by scripts/insert_campaign.py
DEFAULT_CAMPAIGN_ID = "1d87aeff-f5b7-43a5-b0b5-88f7c3b1fc55"


def load_env(env_path):
    env_vars = {}
    if not os.path.exists(env_path):
        return env_vars
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^([^=]+)=(.*)$", line)
            if m:
                k, v = m.group(1).strip(), m.group(2).strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                env_vars[k] = v
    return env_vars


def main():
    env = load_env(".env")
    url = env.get("MONGODB_URL")
    db_name = env.get("MONGODB_DB_NAME", "outreach_ai")
    if not url:
        print("MONGODB_URL not found in .env")
        sys.exit(1)

    campaign_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CAMPAIGN_ID

    client = MongoClient(url, tlsAllowInvalidCertificates=True)
    db = client[db_name]
    print(f"Connected to DB: {db_name}")
    print(f"Inspecting campaign: {campaign_id}")
    print("=" * 70)

    # ── Campaign ──────────────────────────────────────────────────────────
    camp = db.campaigns.find_one({"id": campaign_id})
    if not camp:
        print("!! Campaign not found by id. Searching by name 'Market Stakeholder'...")
        camp = db.campaigns.find_one({"name": "Market Stakeholder"})
    if not camp:
        print("!! No campaign found. Listing all campaigns:")
        for c in db.campaigns.find({}, {"_id": 0, "id": 1, "name": 1, "status": 1}):
            print(f"   - {c.get('name')!r:35} id={c.get('id')} status={c.get('status')}")
        return

    campaign_id = camp["id"]
    user_id = camp.get("user_id")
    print(f"CAMPAIGN")
    print(f"  name           : {camp.get('name')}")
    print(f"  status         : {camp.get('status')}   <- must be 'active' to run")
    print(f"  user_id        : {user_id}")
    print(f"  gmail_account_id: {camp.get('gmail_account_id')}")
    print(f"  has subject_tpl : {bool(camp.get('subject_template'))}")
    print(f"  has body_tpl    : {bool(camp.get('body_template'))}")
    print(f"  #sequence_steps : {len(camp.get('sequence_steps') or [])}")
    print(f"  total_leads     : {camp.get('total_leads')}")
    print(f"  emails_sent     : {camp.get('emails_sent')}")
    print(f"  started_at      : {camp.get('started_at')}")
    print("-" * 70)

    # ── Leads ─────────────────────────────────────────────────────────────
    lead_status = Counter()
    no_email = 0
    total_leads = 0
    for lead in db.leads.find({"campaign_id": campaign_id}):
        total_leads += 1
        lead_status[lead.get("status", "<none>")] += 1
        if not (lead.get("email") or "").strip():
            no_email += 1
    print(f"LEADS (campaign_id == UUID): {total_leads}")
    for st, n in lead_status.most_common():
        flag = "  <- scheduler picks these" if st == "new" else ""
        print(f"  status={st!r:12} : {n}{flag}")
    print(f"  leads missing an email address: {no_email}")

    # leads mistakenly stored under the campaign NAME instead of the UUID
    name_leads = db.leads.count_documents({"campaign_id": camp.get("name")})
    if name_leads:
        print(f"  !! {name_leads} leads stored with campaign_id == NAME (not UUID) — invisible to scheduler")
    print("-" * 70)

    # ── scheduled_tasks ───────────────────────────────────────────────────
    task_status = Counter()
    task_by_step = Counter()
    failed_samples = []
    for t in db.scheduled_tasks.find({"campaign_id": campaign_id}):
        task_status[t.get("status", "<none>")] += 1
        task_by_step[t.get("step_number")] += 1
        if t.get("status") == "failed" and len(failed_samples) < 5:
            failed_samples.append((t.get("lead_id"), t.get("error", "")[:120]))
    total_tasks = sum(task_status.values())
    print(f"SCHEDULED_TASKS for campaign: {total_tasks}")
    if total_tasks == 0:
        print("  !! ZERO scheduled tasks — nothing was ever scheduled to send.")
    for st, n in task_status.most_common():
        print(f"  status={st!r:12} : {n}")
    if task_by_step:
        print(f"  by step_number : {dict(task_by_step)}")
    for lid, err in failed_samples:
        print(f"    failed lead={lid} err={err!r}")
    print("-" * 70)

    # ── emails ────────────────────────────────────────────────────────────
    email_status = Counter()
    email_err_samples = []
    for e in db.emails.find({"campaign_id": campaign_id}):
        email_status[e.get("status", "<none>")] += 1
        if e.get("status") == "failed" and len(email_err_samples) < 5:
            email_err_samples.append((e.get("to"), (e.get("error_message") or "")[:120]))
    total_emails = sum(email_status.values())
    print(f"EMAILS for campaign: {total_emails}")
    for st, n in email_status.most_common():
        print(f"  status={st!r:12} : {n}")
    for to, err in email_err_samples:
        print(f"    failed to={to} err={err!r}")
    print("-" * 70)

    # ── Gmail account ─────────────────────────────────────────────────────
    print("GMAIL ACCOUNTS")
    gid = camp.get("gmail_account_id")
    if gid:
        acct = db.gmail_accounts.find_one({"id": gid})
        if acct:
            print(f"  campaign's account {gid}:")
            print(f"    email          : {acct.get('email')}")
            print(f"    is_active      : {acct.get('is_active')}   <- must be True")
            print(f"    connection_err : {acct.get('connection_error')}")
            print(f"    has refresh_tok: {bool(acct.get('refresh_token'))}")
            print(f"    token_expiry   : {acct.get('token_expiry')}")
        else:
            print(f"  !! campaign gmail_account_id {gid} not found in gmail_accounts")
    else:
        print("  campaign has no gmail_account_id set")

    if user_id:
        print(f"  all active accounts for user {user_id}:")
        any_active = False
        for a in db.gmail_accounts.find({"user_id": user_id}):
            any_active = any_active or a.get("is_active")
            print(f"    - {a.get('email')} id={a.get('id')} is_active={a.get('is_active')} err={a.get('connection_error')}")
        if not any_active:
            print("    !! NO active Gmail account for this user — sends will fail.")
    print("=" * 70)
    print("Done (read-only, nothing modified).")


if __name__ == "__main__":
    main()
