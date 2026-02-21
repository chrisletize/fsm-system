# FieldKit Development Workflow

## Purpose
This document captures the working patterns that have proven most effective for FieldKit development sessions. Follow this approach in every session to maintain code quality and avoid introducing regressions.

---

## Core Principle: Examine Before Touching

**Never make assumptions about file contents, line numbers, or code structure.**
Always read the actual current state of a file before modifying it.

This applies even when you think you know what's there — files change between sessions and assumptions cause broken logic.

---

## Standard Debugging Sequence

When something is broken, follow this order:

1. **Test the API directly** before looking at frontend code:
   ```bash
   curl -s http://localhost:5000/api/endpoint | python3 -m json.tool
   ```
   If the API returns correct data, the problem is frontend-only.

2. **Check browser console** for JavaScript errors — these pinpoint the exact line and error type.

3. **Check the actual file** using grep or sed to see current code state:
   ```bash
   grep -n "relevant_term" ~/fsm-system/backend/api/templates/file.html | head -40
   sed -n '540,560p' ~/fsm-system/backend/api/templates/file.html
   ```

4. **Check Flask logs** if the API itself is failing:
   ```bash
   sudo systemctl status fsm-statements | head -30
   ```

5. **Only then** write the fix with full context of what's actually there.

---

## Before Making Any Code Change

### For Simple Single-Line Fixes
1. Run `grep -n` to find the exact current line
2. Confirm it matches what you expect
3. Make the edit in nano

### For Complex Multi-Line Changes
1. **Read the entire relevant function** with `sed -n 'startline,endline p'`
2. Read surrounding context — what calls this function, what does it call
3. For changes touching shared infrastructure (branding, company selector, DB connections), read the whole file or at minimum all related functions
4. Write out the complete replacement block clearly before opening nano
5. Make the edit
6. Verify with `sed` after saving to confirm it looks right

### For New Features Touching Multiple Files
1. Read ALL files that will be modified before writing a single line
2. Map out the complete data flow: backend → API response → frontend consumption
3. Confirm field names match exactly between backend output and frontend expectations (this is where most bugs come from)
4. Implement backend first, test with curl, then implement frontend

---

## The File Read Rule

**When a task involves:**
- Inserting new code into an existing function
- Adding a new route that shares logic with existing routes
- Modifying how data is structured or returned
- Touching any file that other features depend on

**Always use `cat` on the full file first** (or at minimum the full relevant section), not just a grep snippet. Grep shows you the lines you searched for — it doesn't show you what's around them that your change might break.

Example of what went right in the Feb 21 session:
- Before touching tax_processor.py, read the entire file with `cat`
- Before touching tax-report.html, read the entire file with `cat`  
- Before touching generate_pdf_tax_report.py, read the entire file with `cat`
- This revealed that tax_processor.py was NOT importing `get_tax_breakdown` even though it was defined in nc_tax_rates.py — a bug that would have been invisible from grep alone

---

## Editing Files

### Always Use nano for Multi-Line Changes
```bash
nano +LINE_NUMBER ~/path/to/file.py
```

**Do NOT use sed for complex multi-line insertions.** Sed is reliable for single-line find-and-replace but frequently fails on multi-line blocks due to whitespace sensitivity and quote escaping. Use nano and make the edit manually.

**Sed is fine for:**
- Simple single-line replacements with unique text
- Quick verification of what's on a specific line

**Always use nano for:**
- Any insertion longer than one line
- Any change where indentation matters
- Any change near complex JavaScript or Python logic

### After Editing
Always verify the change looks right:
```bash
sed -n 'startline,endline p' ~/path/to/file
```

---

## Restart Command
```bash
sudo systemctl restart fsm-statements
```

Verify clean start:
```bash
sudo systemctl status fsm-statements | head -20
```

Look for `Active: active (running)` and no Python tracebacks in the output.

---

## Testing New Features

1. **Backend first** — test every new endpoint with curl before touching frontend
2. **Check response shape** — confirm field names in API response match exactly what frontend will consume
3. **Browser console** — always have F12 open during first test of new frontend code
4. **Network tab** — verify requests are hitting the right URLs and returning expected status codes
5. **Edge cases** — test empty states (no data loaded, no company selected) not just the happy path

---

## Common Pitfalls to Avoid

### API Response Shape Mismatch
The `/api/companies` endpoint returns `{ "companies": [...] }` not a bare array.
Always check: does the frontend consume `response` or `response.companies` or `response.data`?
When adding new endpoints, be consistent with existing patterns.

### Import Statements
When splitting logic into separate modules (like nc_tax_rates.py, tax_processor.py), always verify imports exist at the top of every file that uses the function. Python won't error until the function is actually called at runtime.

### Frontend Caching
The recency report uses `reportCache` keyed by company ID. This is intentional for UX but means Generate Report must clear the cache to get fresh data. Any feature that needs current data must account for this cache.

### Database Column Names
Phase 0 FSM databases use `customer_name`.
Phase 1 FieldKit databases will use `property_name`.
Don't mix these up when writing queries.

---

## Session Documentation

At the end of every session, create a session notes file covering:
- What was built or fixed
- Root cause of any bugs found
- Key decisions made and why
- Files modified
- Anything that needs follow-up testing

Commit to GitHub with a descriptive message:
```bash
cd ~/fsm-system
git add -A
git commit -m "Description of what changed and why"
git push
```

---

## Prompting Claude for This Workflow

Start sessions with:
> "We're working on FieldKit. Before making any changes to existing files, read the full file or relevant section first. Use nano for multi-line edits, not sed. Test APIs with curl before touching frontend. Follow the workflow in DEVELOPMENT_WORKFLOW.md."

Or simply reference this file:
> "Follow our standard workflow from DEVELOPMENT_WORKFLOW.md — examine before touching, read full files before complex changes, nano for edits, curl to test APIs first."
