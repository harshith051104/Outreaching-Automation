with open('c:/Users/sriha/My work/Outreach/ai_outreach_v2_md_agents/app/services/linkedin_outreach_service.py', 'r') as f:
    content = f.read()

if "button span:has-text('Send')" in content:
    print("Edit successful - span selectors added")
else:
    print("Edit NOT found")

    # Find send_selectors
    idx = content.find("button:has-text('Done')")
    if idx != -1:
        print("Found at index", idx)
        print(repr(content[idx:idx+200]))