---
description: Audit a list of features/changes against the codebase to check implementation status. Reads specific files and greps for patterns, then reports what's implemented vs missing.
---

# Feature Audit

You are auditing a set of features/improvements against the current codebase. For each item in the checklist below, systematically check whether it is implemented by reading the specified files and searching for the expected patterns.

## Input

The user will provide a feature checklist in one of these forms:
- A markdown plan with file paths and check criteria (like a production improvement plan)
- A list of features with expected file locations
- A task list from a planning document

If no checklist is provided, ask the user to paste one or point to a plan file.

## Process

For each feature/check item:

1. **Read** the specified files (use parallel reads when files are independent)
2. **Grep** for the expected patterns, function names, imports, or API endpoints
3. **Report** one of three statuses:
   - ✅ **IMPLEMENTED** - the feature exists and appears complete
   - ⚠️ **PARTIAL** - some pieces exist but others are missing
   - ❌ **NOT FOUND** - no evidence of implementation

4. For each item, provide:
   - The status (one of the above)
   - Specific evidence (file path, line numbers, function names found)
   - What's missing (if partial or not found)

## Output Format

Produce a summary table at the top:

```
| # | Feature | Status | Evidence |
|---|---------|--------|----------|
| 1 | ...     | ✅/⚠️/❌ | brief    |
```

Then a detailed section per item with the specific findings.

## Execution Strategy

- Use parallel tool calls whenever checking independent features
- For each feature, read the primary file first, then grep supporting files
- If a file doesn't exist, that's immediate ❌ status
- Look for both the implementation AND its integration (e.g., a route exists but is it registered in main.py?)
- Check both backend AND frontend when the feature spans both

## Common Check Patterns

- **API endpoint exists**: grep for `@router.get/post/put/delete` with the path
- **Function is called**: grep for the function name in consuming files
- **Import is wired up**: grep for the import statement in the entry point
- **Config is used**: grep for the setting name in service files
- **Frontend uses backend**: grep for the API call in frontend services

$ARGUMENTS
