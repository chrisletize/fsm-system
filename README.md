# fsm-system
Custom Field Service Management system

## Outlook Email Integration (January 2026)

The system can generate PowerShell scripts that create Outlook email drafts with PDF statement attachments.

### Features
- Individual customer emails via button on customer cards
- Batch email generation for multiple selected customers
- Smart validation (blocks company emails, reports missing emails by name)
- PowerShell scripts create drafts for review before sending
- All emails automatically saved to Sent Items folder

### Usage
1. Click email button (individual or batch)
2. Download ZIP file containing PowerShell script + PDFs
3. Extract ZIP and run .ps1 file
4. Review drafts in Outlook
5. Send when ready

**One-time setup:** Run `Set-ExecutionPolicy RemoteSigned` in PowerShell as Administrator.

See `docs/PROJECT-KNOWLEDGE/SESSION-2026-01-23-outlook-integration.md` for complete details.

## Batch Email System (January 2026)

Complete batch email functionality for sending customer statements via Outlook.

### Features
- Individual customer emails via button on customer cards
- Batch email generation for multiple selected customers (QuickBooks-style checkbox UI)
- Smart validation (blocks company emails, reports missing emails by name)
- PowerShell scripts create Outlook drafts for review before sending
- All emails automatically saved to Sent Items folder
- Windows-compatible filenames and extraction

### Recent Bug Fixes (2026-01-27/28)
- ✅ Fixed temp directory collisions using UUID-based unique directories
- ✅ Fixed Windows filename compatibility (strips `*` characters)
- ✅ Improved cleanup robustness with `shutil.rmtree()`
- ✅ Standardized PDF backgrounds to cream for all companies
- ✅ Fixed company dropdown disable during batch operations

See `docs/FEATURES/BATCH-EMAIL-SYSTEM.md` for complete documentation.
