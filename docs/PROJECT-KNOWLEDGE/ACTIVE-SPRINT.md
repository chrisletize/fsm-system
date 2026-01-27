# Active Sprint

## Current Focus: Email Generation Stability & Bug Fixes

### Sprint Goal
Ensure batch email generation is rock-solid and reliable for daily use by Michele and team across all four companies.

### Active Tasks

#### 1. Fix Company Dropdown Disable During Batch Generation (IN PROGRESS) 🔴
**Priority**: CRITICAL
**Status**: Code added but not functioning
**Issue**: Company selector dropdown should be disabled during batch email generation to prevent race condition where switching companies mid-batch causes mixed customer data.

**What's Been Done**:
- Added code in `prepareBatchOutlookEmails()` function to disable/enable dropdown
- Code placed at line ~1068 (disable), ~1102 (re-enable success), ~1108 (re-enable error)

**What's Needed**:
- Debug why `companySelectDropdown.disabled = true` not working
- Check browser console for JavaScript errors
- Verify element ID 'company-select' is correct
- Test alternative approaches if needed

**Files**: `backend/api/templates/index.html`

### Completed This Sprint ✅

#### 1. Fixed Temp Directory Collisions
**Problem**: All batch operations shared `/tmp/outlook_batch`, causing file contamination
**Solution**: Implemented unique temp directories using UUID for each request
**Files Modified**: `backend/api/app.py` (lines 811, 982, 1085)

#### 2. Improved Cleanup Robustness
**Problem**: `os.rmdir()` failed on non-empty directories, leaving stale files
**Solution**: Replaced with `shutil.rmtree(temp_dir, ignore_errors=True)`
**Files Modified**: `backend/api/app.py` (lines ~871, ~1037, ~1188)

#### 3. Windows Filename Compatibility
**Problem**: Kleanit Florida customer names with `*` characters don't extract on Windows
**Solution**: Strip `*` characters from filenames before zip creation
**Files Modified**: `backend/api/app.py` (line 1117)

#### 4. PDF Readability Improvements
**Problem**: Kleanit colored backgrounds harder to read than cream
**Solution**: Override SECONDARY_COLOR to cream (#F5F5DC) for both Kleanit companies
**Files Modified**: `scripts/generate_pdf_statement.py` (lines 102-106)

### Testing Status

**Passing Tests** ✅
- Batch email generation for all four companies
- Correct company branding in all PDFs
- Windows extraction of Kleanit Florida files
- Sequential batch generation (no file contamination)
- PDF background colors (cream for all companies)

**Failing Tests** 🔴
- Company dropdown disable during batch generation

### Next Steps

1. Debug dropdown disable functionality (browser console + element inspection)
2. Test rapid company switching during batch operations
3. Monitor `/tmp/` for any temp directory buildup
4. Comprehensive testing with Michele on production workflows

### Definition of Done

Sprint complete when:
- [ ] Company dropdown reliably disabled during batch generation
- [ ] No race conditions possible when switching companies
- [ ] All batch operations tested across all four companies
- [ ] Michele confirms system is stable for daily use
- [ ] No temp directory accumulation after multiple batch operations

---

**Sprint Duration**: January 27, 2026
**Last Updated**: January 27, 2026 - End of Day
**Next Review**: Next development session
