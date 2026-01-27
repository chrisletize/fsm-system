# Session Notes - January 27, 2026

## Issues Addressed

### 1. Batch Email Generation Bugs
**Problem**: Michele reported two critical issues:
- Kleanit Florida batch emails produced empty zip files on Windows
- Get a Grip customer PDFs appeared in Kleanit Florida zip file

**Root Causes Identified**:
1. **Temp Directory Collision**: All batch operations used shared temp directory `/tmp/outlook_batch`, causing file contamination between sequential requests
2. **Windows Filename Incompatibility**: Customer names with `*` characters (e.g., `*Fl* Camden Aventura`) don't extract properly on Windows
3. **Inadequate Cleanup**: `os.rmdir()` only works on empty directories, leaving stale files
4. **Race Condition**: Switching companies before zip download completes sends wrong customer_ids with new company_id

**Fixes Implemented**:

#### A. Unique Temp Directories (COMPLETED ✅)
- Added `import uuid` and `import shutil` to app.py
- Changed all three temp directory locations to use unique identifiers:
  - Line 811: `temp_dir = f'/tmp/batch_statements_{uuid.uuid4().hex[:8]}'`
  - Line 982: `temp_dir = f'/tmp/outlook_email_{uuid.uuid4().hex[:8]}'`
  - Line 1085: `temp_dir = f'/tmp/outlook_batch_{uuid.uuid4().hex[:8]}'`

#### B. Robust Cleanup (COMPLETED ✅)
- Replaced all `os.rmdir(temp_dir)` with `shutil.rmtree(temp_dir, ignore_errors=True)`
- Applied to three locations (lines ~871, ~1037, ~1188)
- Forces removal of directories even with locked files

#### C. Windows-Compatible Filenames (COMPLETED ✅)
- Modified line 1117 in app.py to strip `*` characters:
  ```python
  clean_name = clean_customer_name(customer_name).replace('*', '').replace('  ', ' ').strip()
  ```
- Kleanit Florida PDFs now extract properly on Windows

#### D. Prevent Company Switching During Batch (IN PROGRESS ⚠️)
- Added code to disable company selector dropdown during batch email generation
- Modified `prepareBatchOutlookEmails()` function in index.html:
  - Line ~1068: Disable dropdown when batch starts
  - Line ~1102: Re-enable after successful completion
  - Line ~1108: Re-enable after error
- **ISSUE**: Dropdown not actually disabling - needs debugging

### 2. PDF Readability Improvements
**Problem**: Kleanit Charlotte and Kleanit Florida statements had colored backgrounds (green/blue) in invoice tables that were harder to read than Get a Grip and CTS cream backgrounds.

**Fix Implemented** (COMPLETED ✅):
- Modified `generate_pdf_statement.py` around line 102
- Added conditional logic to override `SECONDARY_COLOR` for Kleanit companies:
  ```python
  # Use cream color for Kleanit invoice backgrounds (better readability)
  if company_id in [1, 4]:  # Kleanit Charlotte and Kleanit South Florida
      SECONDARY_COLOR = colors.HexColor('#F5F5DC')  # Cream
  else:
      SECONDARY_COLOR = colors.HexColor(branding['secondary_color'])
  ```
- Result: All four companies now have cream-colored invoice backgrounds

## Testing Results

### Successful Tests ✅
1. Generated batch emails for all four companies - correct branding and customer data
2. Kleanit Florida PDFs now extract properly on Windows (asterisks removed from filenames)
3. PDF backgrounds now use cream color for better readability
4. Unique temp directories prevent file contamination between sequential batches

### Known Issues ⚠️
1. **Company dropdown not disabling during batch generation** - Code added but not functioning
   - Need to verify element ID is correct
   - May need to check browser console for JavaScript errors
2. **Race condition still possible** - Without working dropdown disable, users can still switch companies mid-batch

## Files Modified

### backend/api/app.py
- Added imports: `uuid`, `shutil`
- Lines 811, 982, 1085: Made temp directories unique with UUID
- Lines ~871, ~1037, ~1188: Improved cleanup with `shutil.rmtree()`
- Line 1117: Strip `*` from customer names for Windows compatibility

### scripts/generate_pdf_statement.py
- Lines 102-106: Override SECONDARY_COLOR for Kleanit companies to use cream (#F5F5DC)

### backend/api/templates/index.html
- Function `prepareBatchOutlookEmails()`: Added company dropdown disable/enable logic
  - Line ~1068: Disable dropdown on batch start
  - Line ~1102: Re-enable on success
  - Line ~1108: Re-enable on error

## Next Session Priorities

1. **DEBUG DROPDOWN DISABLE** (HIGH PRIORITY)
   - Check browser console for JavaScript errors
   - Verify `getElementById('company-select')` returns correct element
   - Test with console.log statements
   - Consider alternative approach if needed

2. **Additional Testing**
   - Test rapid sequential batch generation across companies
   - Test with different customer counts
   - Verify no temp directory buildup in `/tmp/`

3. **Future Enhancements**
   - Consider adding visual indicator when batch is processing
   - Add progress bar for large batches
   - Implement request cancellation if user navigates away

## Commands for Next Session

### Start Flask
```bash
cd ~/fsm-system
nohup python3 backend/api/app.py > flask.log 2>&1 &
```

### Check Flask Logs
```bash
tail -f ~/fsm-system/flask.log
```

### Monitor Temp Directories
```bash
ls -la /tmp/*batch* /tmp/*email* /tmp/*statement*
```

### Test Database Queries
```bash
psql -h localhost -U fsm_user -d fsm_system -c "SELECT id, name FROM companies;"
```

## Notes
- All changes tested successfully except dropdown disable functionality
- System more robust against race conditions and file conflicts
- PDF generation now professional and consistent across all companies
- Ready for Michele to use once dropdown disable is debugged
