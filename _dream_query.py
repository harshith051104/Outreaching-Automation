import sqlite3, json, time, sys

DB = r"C:\Users\sriha\.local\share\mimocode\mimocode.db"
conn = sqlite3.connect(DB)
cursor = conn.cursor()
sys.stdout.reconfigure(encoding='utf-8')

# Get patches with file info
print("=== PATCHES WITH FILE INFO ===")
cursor.execute("""
    SELECT p.session_id, p.time_created, p.data
    FROM part p
    WHERE p.session_id IN (SELECT id FROM session WHERE project_id = '38afacbd-ca78-4ab7-b379-d801a2968d39')
      AND json_extract(p.data, '$.type') = 'patch'
    ORDER BY p.time_created
""")
for row in cursor.fetchall():
    sid, tc, data = row
    dt = time.strftime("%H:%M:%S", time.gmtime(tc / 1000))
    d = json.loads(data) if data else {}
    print(f"\n[{dt}] session={sid}")
    print(f"  keys: {list(d.keys())}")
    for k, v in d.items():
        if k != 'type':
            val_str = str(v)[:200] if v else "None"
            print(f"  {k}: {val_str}")

# Get checkpoint writer session text
print("\n\n=== CHECKPOINT WRITER SESSION TEXT ===")
writer_session = "ses_0fb9b6f25ffex4ct36rlRpGgKb"
cursor.execute("""
    SELECT p.time_created, json_extract(p.data, '$.text') as text
    FROM part p
    WHERE p.session_id = ?
      AND json_extract(p.data, '$.type') = 'text'
    ORDER BY p.time_created
""", (writer_session,))
for row in cursor.fetchall():
    tc, text = row
    if text:
        dt = time.strftime("%H:%M:%S", time.gmtime(tc / 1000))
        print(f"\n--- [{dt}] ---")
        print(text[:2000])

# Get tool calls from review session to see what files were modified
print("\n\n=== TOOL CALLS IN REVIEW SESSION (write/edit tools) ===")
review_session = "ses_0fba04fb0ffeVYefZsuTDdTSD6"
cursor.execute("""
    SELECT p.time_created, 
           json_extract(p.data, '$.tool') as tool,
           json_extract(p.data, '$.state.input') as input
    FROM part p
    WHERE p.session_id = ?
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') IN ('write', 'edit')
    ORDER BY p.time_created
""", (review_session,))
for row in cursor.fetchall():
    tc, tool, inp = row
    dt = time.strftime("%H:%M:%S", time.gmtime(tc / 1000))
    print(f"\n[{dt}] tool={tool}")
    if inp:
        inp_d = json.loads(inp) if isinstance(inp, str) else inp
        if isinstance(inp_d, dict):
            fp = inp_d.get('filePath', inp_d.get('file', '?'))
            print(f"  file: {fp}")

conn.close()
