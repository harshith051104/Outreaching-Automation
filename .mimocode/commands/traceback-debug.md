---
description: Diagnose and fix errors from pasted stack traces, HTTP error logs, or error messages. Traces the root cause through the codebase and applies a targeted fix.
---

# Traceback / Error Debug

You are diagnosing an error from a pasted traceback, HTTP error log, or error message. Your job is to trace the root cause and apply a minimal, correct fix.

## Input

The user will paste one of:
- A Python traceback (e.g., `Traceback (most recent call last): ...`)
- An HTTP error log (e.g., `INFO: 127.0.0.1 - "GET /api/path HTTP/1.1" 400 Bad Request`)
- A browser console error (e.g., `Error: A tree hydrated but...`)
- A build error (e.g., `Type error: Property 'x' does not exist on type 'Y'`)
- A server startup error (e.g., `pydantic.ValidationError: ...`)

If no error is provided, ask the user to paste it.

## Diagnosis Process

### Step 1: Parse the Error
Extract from the pasted error:
- **Error type**: What kind of error is it? (exception class, HTTP status, build error)
- **File + line**: Where in the code did it originate?
- **Key message**: What's the root cause hint?
- **Stack frames**: What's the call chain?

### Step 2: Read the Origin
- Read the file and line number from the top of the traceback
- If the error is in a library, trace back to the **project code** in the stack frames
- Read surrounding context (±30 lines) to understand the function

### Step 3: Trace the Cause
Based on the error type, check:

**Import/Module errors:**
- Is the module installed? Check `requirements.txt` or `package.json`
- Is the import path correct? Check the file structure
- Is there a circular import?

**Runtime errors (TypeError, ValueError, AttributeError):**
- Is the variable defined before use?
- Is the function signature correct? (check the definition)
- Is the data format what's expected? (check upstream callers)

**HTTP errors (400, 401, 403, 404, 500):**
- Is the route registered? Check `main.py` / router registration
- Is the auth dependency correct? Check token/session handling
- Is the request format correct? Check the endpoint's parameter types
- Is there a server-side exception? Check uvicorn/terminal output

**Config/Environment errors:**
- Is the env variable set? Check `.env` file
- Is the format correct? (JSON array vs plain string for lists)
- Is the dependency compatible? (e.g., passlib + bcrypt version mismatch)

**Frontend hydration/mismatch errors:**
- Is there a server/client branch (`typeof window !== 'undefined'`)?
- Is there a `Date.now()` or `Math.random()` in server-rendered code?
- Is the API base URL correct?

### Step 4: Apply Fix
- Use Edit to make the minimal correct fix
- If the fix is in `.env` or config, tell the user what to change
- If it's a dependency issue, tell the user what to install/update
- Verify the fix doesn't break other code (grep for other usages)

## Output Format

```
## Error Diagnosis

**Error**: <one-line summary>
**Root cause**: <what's actually wrong>
**Location**: `<file>` line <N>

### Fix Applied
<description of the fix>

### What Changed
<file path>: <brief description of the edit>

### Prevention
<optional: how to avoid this class of error in the future>
```

## Common Error Patterns Reference

| Error | Typical Cause | Typical Fix |
|-------|--------------|-------------|
| `CORS_ORIGINS` validation error | Env var is plain string, not JSON array | Change to `["http://localhost:3000"]` |
| `password cannot be longer than 72 bytes` | passlib + bcrypt 4.1+ incompatibility | Use bcrypt directly |
| `Missing code verifier` | OAuth PKCE flow not preserved across requests | Store flow state in memory/session |
| `401 Unauthorized` | Missing or expired JWT token | Check auth header / login flow |
| `Hydration mismatch` | Server/client rendering difference | Use `useEffect` for client-only code |
| `Module not found` | Missing install or wrong import path | Check requirements.txt / node_modules |

$ARGUMENTS
