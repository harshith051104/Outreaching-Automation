---
description: Scan all files in a project for errors - missing imports, syntax issues, broken references, inconsistent APIs, and config problems. Reports findings and optionally fixes them.
---

# Codebase Error Scan

You are performing a comprehensive error scan of a codebase. Glob all source files, read each one systematically, and identify errors that would prevent the project from running correctly.

## Input

The user may provide:
- A project path to scan (default: current working directory)
- A specific area to focus on (e.g., "just the backend", "just the frontend")
- A specific error type to look for (e.g., "import errors", "config issues")

If no path is provided, use the current working directory.

## Scan Process

### Phase 1: Discovery
1. **Glob** all source files: `**/*.py`, `**/*.ts`, `**/*.tsx`, `**/*.js`, `**/*.jsx`
2. **Read** the entry point(s): `main.py`, `app.py`, `index.ts`, `layout.tsx`, etc.
3. **Read** config files: `.env`, `settings.py`, `package.json`, `requirements.txt`, `tsconfig.json`

### Phase 2: File-by-File Scan
For each source file, check for:

**Python files:**
- Missing imports (names used but not imported)
- Undefined references (functions/classes called but not defined or imported)
- Inconsistent function signatures (call site vs definition)
- Missing async/await on async calls
- Config references that don't match settings.py
- Route registration mismatches (defined but not registered, or registered but not defined)

**TypeScript/JavaScript files:**
- Missing imports
- Type mismatches (if TypeScript)
- API endpoint mismatches between frontend service and backend route
- Missing component props
- Broken relative import paths

**Cross-cutting checks:**
- Backend routes registered in main.py/app.py
- Frontend API service URLs match backend route prefixes
- Environment variables referenced but not in .env.example
- Database model fields used in services but not defined in models

### Phase 3: Fix (if requested)
If the user says "fix" or "fix it":
- For each error found, propose the fix
- Apply the fix using Edit
- Verify the fix doesn't introduce new issues

## Output Format

```
## Scan Results for <project>

### Summary
- Files scanned: N
- Errors found: N
- Critical: N | Warnings: N | Info: N

### Errors

#### 1. [CRITICAL] Missing import in `path/to/file.py` (line N)
- **Issue**: `function_name` is used but not imported
- **Fix**: Add `from module import function_name`

#### 2. [WARNING] Unused route in `path/to/routes.py` (line N)
- **Issue**: Route `/path` is defined but not registered in main.py
- **Fix**: Add `app.include_router(router, prefix="/path")`
```

## Execution Strategy

- Start with entry points and config to understand the architecture
- Use parallel reads for independent files
- Use grep to verify cross-file references (imports, function calls, route registrations)
- Prioritize CRITICAL errors (would prevent startup) over WARNINGs (suboptimal but functional)
- Track which files have been scanned to avoid re-reading

$ARGUMENTS
