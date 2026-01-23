# Session Notes: January 23, 2026 - Outlook Email Integration

## Overview
Implemented complete Outlook email integration allowing Michele to generate PowerShell scripts that create Outlook drafts with PDF statement attachments for customer review before sending.

## What Was Built

### Backend Components
1. **outlook_integration.py** - PowerShell script generator module
   - `generate_individual_email_script()` - Single customer email
   - `generate_batch_email_script()` - Multiple customer batch emails
   - `save_script_to_file()` - Saves scripts with proper UTF-8 BOM encoding

2. **API Endpoints in app.py**
   - `/api/prepare-outlook-email/<customer_id>` - Individual customer email package
   - `/api/prepare-outlook-batch` - Batch email package for multiple customers

### Frontend Features (index.html)
1. **Individual Email Button** - Appears on customer cards with email addresses
   - Downloads ZIP containing PowerShell script + PDF
   - Button feedback: "📧 Email in Outlook" → "⏳ Preparing..." → "✅ Downloaded!"

2. **Batch Email Button** - Appears in batch actions bar
   - Smart validation with detailed feedback:
     - Lists customers missing email addresses by name
     - Lists customers with company email addresses by name
     - Shows count of valid customers to process
   - Downloads ZIP with batch script + all PDFs

### Email Validation
Blocks emails to company addresses to prevent internal loops:
- office@getagripofcharlotte.com
- accountsreceivable@getagripofcharlotte.com
- accountsreceivable@kleanit.com
- office@ctsofraleigh.com
- accountsreceivable@ctsofraleigh.com
- office@kleanit.com

### Company Name Mapping
Maps database names to official business names in emails:
- Kleanit Charlotte → "Kleanit"
- Kleanit South Florida → "Kleanit"
- Get a Grip Resurfacing of Charlotte → "Get a Grip Resurfacing of Charlotte"
- CTS of Raleigh → "CTS of Raleigh"

## How It Works

### User Workflow - Individual Email
1. Click "📧 Email in Outlook" button on customer card
2. Download ZIP file (Email_CustomerName.zip)
3. Extract ZIP contents
4. Right-click .ps1 file → "Run with PowerShell"
5. Review draft in Outlook
6. Click Send when ready
7. Email saved to Sent Items automatically

### User Workflow - Batch Email
1. Select multiple customers using checkboxes
2. Click "📧 Email Selected in Outlook" button
3. Review validation popup (shows any issues)
4. Download ZIP file (Batch_Email_CompanyName_X_customers_DATE.zip)
5. Extract ZIP contents
6. Right-click .ps1 file → "Run with PowerShell"
7. Review customer list, confirm to proceed
8. Script creates all drafts in Outlook Drafts folder
9. Open Drafts folder, review each email
10. Send emails individually as needed

### PowerShell Script Features

**Individual Script:**
- Colorful progress output (Cyan, Green, Red, Yellow)
- PDF existence validation before creating draft
- Error handling with troubleshooting tips
- Opens Outlook draft immediately with `$mail.Display()`
- Includes customer name, total due, company branding

**Batch Script:**
- Customer list preview with confirmation prompt
- Progress counter (e.g., "[3/32] Processing Customer...")
- Saves drafts to Outlook Drafts folder using `$mail.Save()`
- Success/error tracking with detailed summary
- Option to open Drafts folder after completion
- Handles missing PDFs gracefully with specific error messages

## Technical Details

### File Generation
- PDFs use `clean_customer_name()` function for proper Title Case formatting
- PowerShell scripts saved with UTF-8 BOM encoding for compatibility
- ZIP files include README with detailed instructions
- All files use consistent naming: "Statement - Customer Name.pdf"

### PowerShell Array Syntax Fix
Original syntax using `[...]` caused "Missing type name after '[']" error.
Fixed by using proper PowerShell array syntax: `@(...)`

### Company Email Detection
Uses case-insensitive matching: `.toLowerCase()` for reliability

## One-Time Windows Setup
PowerShell execution policy must allow scripts:
```powershell
Set-ExecutionPolicy RemoteSigned
```
Run once per Windows machine as Administrator.

## Debugging Journey

### Challenge 1: JavaScript Backtick Corruption
**Problem:** Copy-paste corrupted template literals - backticks became mixed with single quotes
**Example:** `` fetch(`...'); `` instead of `` fetch(`...`); ``
**Solution:** Manual editing in nano to fix mismatched quotes
**Lesson:** Template literals with backticks don't survive copy-paste reliably

### Challenge 2: Route Definition Location
**Problem:** Outlook routes defined AFTER `if __name__ == '__main__'` block
**Impact:** Routes never registered with Flask when run via systemd
**Solution:** Moved route definitions before the main execution block
**Lesson:** All @app.route decorators must be defined before conditional execution

### Challenge 3: Duplicate Route Breaking Subsequent Routes
**Problem:** Duplicate `/tax-report` route at line 893 caused 404 on all routes after it
**Solution:** Deleted duplicate route definition
**Lesson:** Flask silently fails to register routes after encountering duplicates

### Challenge 4: PowerShell Dollar Sign Escaping
**Problem:** Template literal used `` `$$ `` for escaping, resulting in literal backticks in output
**Solution:** Changed to `$$` (PowerShell handles its own escaping)
**Example:** `` `$$($customer.TotalDue) `` → `$($customer.TotalDue)`

### Challenge 5: PowerShell Array Syntax
**Problem:** Used `[...]` for array, PowerShell interpreted as type cast
**Error:** "Missing type name after '[']"
**Solution:** Changed to `@(...)` (proper PowerShell array syntax)

## Files Modified
- `backend/api/app.py` - Added Outlook endpoints and company name mapping
- `backend/api/templates/index.html` - Added email buttons and validation
- `backend/api/outlook_integration.py` - NEW: PowerShell script generator

## Testing Results
✅ Individual email generation - All companies
✅ Batch email generation - All companies  
✅ PDF filename formatting - Clean Title Case
✅ Company email blocking - All addresses caught
✅ Missing email validation - Shows customer names
✅ PowerShell execution - Fast draft creation
✅ Outlook integration - Drafts created successfully
✅ Multi-company support - Proper branding per company

## Performance Notes
Michele reported PowerShell draft creation was "honestly faster than expected" - excellent user experience for batch operations with 30+ customers.

## User Feedback
"FRIG YEAH DUDE! that feels so awesome and professional and smart!" - Chris
Feature provides professional, detailed validation that makes the system feel intelligent and trustworthy.

## Future Considerations
- Current implementation uses PowerShell + Outlook (Windows only)
- Alternative: Direct SMTP could enable cross-platform support
- Trade-off: Current approach allows review before sending (important for AR)
- Email tracking: All emails saved to Sent Items for record-keeping

## Success Metrics
- Replaces manual statement emailing workflow
- Provides safety through draft review process
- Smart validation prevents common errors
- Professional appearance builds user confidence
- Fast enough for batch operations (30+ customers)
