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
