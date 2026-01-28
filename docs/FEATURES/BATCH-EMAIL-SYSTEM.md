# Batch Email System Documentation

## Overview

The FSM Statement Generator includes a batch email system that allows Michele to send professional customer statements via Outlook with PowerShell automation. Implemented in January 2026 as part of Phase 0.

---

## Features

### Individual Customer Emails
- Click "📧 Email in Outlook" button on any customer card
- Downloads ZIP file containing PowerShell script + PDF + README
- Script creates Outlook draft with PDF attached
- User reviews and sends when ready
- Email automatically saved to Sent Items

### Batch Customer Emails
- Select multiple customers using checkboxes (QuickBooks-style UI)
- Click "📧 Email Selected in Outlook" in batch actions bar
- Smart validation before generation:
  - Lists customers missing email addresses by name
  - Lists customers with company email addresses by name
  - Shows count of valid customers to process
- Downloads ZIP with script + all PDFs + README
- Script creates all drafts in Outlook Drafts folder
- User reviews each draft and sends
- All emails saved to Sent Items

---

## Technical Architecture

### Backend Components

**1. outlook_integration.py** - PowerShell script generation module
- `generate_individual_email_script(customer, pdf_path, company_name)`
- `generate_batch_email_script(customers, company_name)`
- `save_script_to_file(script_content, filepath)` - UTF-8 BOM encoding

**2. API Endpoints (app.py)**

Individual Email:
```python
@app.route('/api/prepare-outlook-email/<int:customer_id>')
```

Batch Email:
```python
@app.route('/api/prepare-outlook-batch', methods=['POST'])
```

**Key Features**:
- UUID-based unique temp directories (prevents file contamination)
- Robust cleanup with `shutil.rmtree()`
- Windows-compatible filenames (strips `*` characters)
- Company email validation
- Professional naming with `clean_customer_name()`

### Frontend Components (index.html)

**Individual Email Button** - On customer cards with email addresses

**Batch Email Button** - In batch actions bar when customers selected

**Email Validation** - Blocks company addresses:
- office@getagripofcharlotte.com
- accountsreceivable@getagripofcharlotte.com
- accountsreceivable@kleanit.com
- office@ctsofraleigh.com
- accountsreceivable@ctsofraleigh.com
- office@kleanit.com

**Company Dropdown Locking** - Disables dropdown during batch operations to prevent race conditions

---

## User Workflows

### Individual Email
1. Navigate to statements page
2. Select company from dropdown
3. Find customer with outstanding balance
4. Click "📧 Email in Outlook"
5. Save ZIP file
6. Extract and run .ps1 file
7. Review draft in Outlook
8. Click Send

### Batch Email
1. Navigate to statements page
2. Select company from dropdown
3. Check boxes next to customers
4. Click "📧 Email Selected in Outlook"
5. Review validation popup
6. Save ZIP file
7. Extract and run .ps1 file
8. Confirm customer list
9. Open Outlook Drafts folder
10. Review and send each email

---

## PowerShell Scripts

### Script Features
- Colorful progress output (green success, red error, yellow warnings)
- PDF existence checking
- Error handling with troubleshooting tips
- Batch confirmation prompts
- Success/failure tracking
- Optional: Opens Drafts folder automatically

---

## One-Time Setup

PowerShell needs permission to run scripts (Windows security):

```powershell
# Open PowerShell as Administrator
Set-ExecutionPolicy RemoteSigned
```

Only needs to be done once per computer.

---

## ZIP File Contents

### Individual Email
```
Email_John_Smith_20260127.zip
├── README.txt
├── Email_John_Smith.ps1
└── Statement_John_Smith_20260127.pdf
```

### Batch Email
```
Batch_Email_Get_a_Grip_50_customers_2026-01-27.zip
├── README.txt
├── Batch_Email_50_Customers.ps1
├── Statement_Customer1.pdf
├── Statement_Customer2.pdf
... (all PDFs)
```

---

## Bug Fixes (2026-01-27/28)

### Fixed Issues
1. ✅ Temp directory collisions (UUID isolation)
2. ✅ Windows filename compatibility (strip asterisks)
3. ✅ Cleanup robustness (shutil.rmtree)
4. ✅ PDF readability (cream backgrounds)
5. ✅ Dropdown disable during batch (with debugging)

### Testing
- All features verified working
- Cross-platform tested (Linux server, Windows client)
- Console debugging confirms proper execution
- Michele actively using in production

---

## Performance Metrics

### Individual Email
- Generation Time: < 1 second
- PDF Size: ~50-200 KB
- ZIP Size: ~100-300 KB

### Batch Email
- Generation Time: ~3-5 seconds for 20 customers
- ZIP Size: ~2-5 MB for 20 customers

---

## Troubleshooting

### "Cannot be loaded because running scripts is disabled"
Run PowerShell as Administrator:
```powershell
Set-ExecutionPolicy RemoteSigned
```

### "Outlook draft doesn't open"
- Make sure Outlook is installed
- Try opening Outlook manually first
- Close any error dialogs

### "PDF file not found"
- Extract ALL files from ZIP
- Keep .ps1 and PDFs in same folder

---

## Code Locations

**Backend**:
- `backend/api/app.py` (lines 957-1200)
- `backend/api/outlook_integration.py`
- `scripts/generate_pdf_statement.py`

**Frontend**:
- `backend/api/templates/index.html` (lines 900-1130)

---

**Last Updated**: 2026-01-28  
**Status**: Production-ready ✅  
**Maintainer**: Chris Letize
