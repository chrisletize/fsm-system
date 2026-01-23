# Comprehensive Help System Design

## Vision

Every page in the FSM system should have context-sensitive, data-aware help that teaches users through their actual data. The goal: anyone with basic computer, reading, and writing skills can effectively learn and use the system through exploration and the help interface.

## Core Principles

### 1. Live, Data-Aware Examples
- Help boxes use **real loaded data** as examples, not generic placeholders
- When a report is generated, help explains what the **actual numbers mean**
- Examples reference the user's real customer names, date ranges, and values

**Example**: Instead of "The report shows invoices from the selected date range"
→ "Your report shows 51 matched records from December 2025, representing $2,878.37 in collected tax"

### 2. Progressive Disclosure
- Help appears when relevant to current state
- Before upload: "How to export files from ServiceFusion"
- During upload: "What date ranges were detected in your files"  
- After generation: "What each column means in your specific report"

### 3. Context-Sensitive Content
- Help changes based on what's visible on screen
- Empty state help: How to get started
- Data loaded help: How to interpret what you're seeing
- Error state help: What went wrong and how to fix it

### 4. Always Accessible
- Every page has a help button (? icon or "Help" text)
- Help can be toggled on/off
- Help persists across page refreshes (localStorage preference)
- Help doesn't obstruct workflow

## Implementation Pattern

### Tax Report Page Example

#### Help State 1: Initial Page Load (No Files)
**Help Box Title**: "Getting Started with Tax Reports"

**Content**:
```
This tool matches your ServiceFusion Tax Report with Transaction Report to calculate 
cash-basis tax liability for North Carolina sales tax filing.

You need TWO files from ServiceFusion:

1. Tax Report:
   - Reports → Tax Report
   - Set date range: [explain what range to use]
   - Export to Excel
   
2. Transaction Report (Customer Transactions):
   - Reports → Customer Transaction Report  
   - Same date range as Tax Report
   - Export to Excel

Both files must cover the same time period. You can upload them in any order.
```

#### Help State 2: First File Uploaded
**Help Box Title**: "Next: Upload [Tax Report / Transaction Report]"

**Content** (dynamic based on what's loaded):
```
✓ Tax Report uploaded: December 1-31, 2025
  - 95 invoices found
  - 8 NC counties detected

○ Transaction Report needed
  - Must cover December 2025 (or wider range)
  - Click the blue zone below to upload
  
Once both files are uploaded, the Generate Report button will activate.
```

#### Help State 3: Both Files Uploaded (Ready to Generate)
**Help Box Title**: "Ready to Generate"

**Content**:
```
✓ Tax Report: Dec 1-31, 2025 (95 invoices)
✓ Transaction Report: Dec 1-31, 2025

The system will match invoices by Job# to determine when tax was actually collected.

Not all invoices will match (some may not be paid yet). The report will show:
- Only invoices paid during the transaction report date range
- Breakdown by county and tax rate
- Total tax collected for NC DOR filing
```

#### Help State 4: Report Generated
**Help Box Title**: "Understanding Your Tax Report"

**Content** (using actual data from the generated report):
```
Your December 2025 cash-basis tax report shows:

MATCHED RECORDS: 51 out of 95 invoices
- These invoices were paid during December 2025
- Total tax collected: $2,878.37

UNMATCHED RECORDS: 44 invoices
- These jobs were completed in December but not paid yet
- Tax will be reported when payment is received in a future month

COUNTY BREAKDOWN:
[Show actual counties and amounts from their report]

WHAT TO DO WITH THIS REPORT:
1. Use the county totals for NC-5 tax filing
2. Save this report for your records
3. The unmatched invoices will appear in future reports when paid
```

## Help System Features

### Global Features
- **Toggle button**: Persistent on/off state
- **Keyboard shortcut**: F1 or ? key
- **Print-friendly**: Help content can be printed
- **Mobile-responsive**: Collapsible on small screens

### Per-Page Features
- **Context detection**: Automatically shows relevant help
- **Search**: Find help topics (future enhancement)
- **History**: "What was I just looking at?" (future enhancement)
- **Feedback**: "Was this helpful?" button

## Technical Implementation

### Frontend Structure
```javascript
// Help box component
class HelpBox {
  constructor(elementId) {
    this.element = document.getElementById(elementId);
    this.visible = localStorage.getItem('helpVisible') === 'true';
    this.currentState = 'initial';
  }
  
  updateState(newState, data = {}) {
    this.currentState = newState;
    this.render(data);
  }
  
  render(data) {
    const content = this.getContentForState(this.currentState, data);
    this.element.innerHTML = content;
  }
  
  getContentForState(state, data) {
    // Return appropriate help content based on state and data
  }
}
```

### CSS Guidelines
```css
.help-box {
  background: var(--bg-help, #f8f9fa);
  border-left: 4px solid var(--accent-color);
  padding: 1rem;
  margin: 1rem 0;
  border-radius: 4px;
  font-size: 0.95rem;
  line-height: 1.6;
}

.help-box-hidden {
  display: none;
}

.help-toggle {
  position: sticky;
  top: 1rem;
  right: 1rem;
  background: var(--accent-color);
  color: white;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
```

## Help Content Writing Guidelines

### Voice and Tone
- **Friendly but professional**: Like a helpful coworker, not a robot
- **Action-oriented**: Tell users what to do, not just what things are
- **Confident**: "Click Generate Report" not "You might want to consider clicking..."
- **Specific**: Use actual data, actual file names, actual numbers

### Structure
1. **Lead with the action**: What can the user do right now?
2. **Explain the why**: Why does this matter?
3. **Show with examples**: Use their real data to illustrate
4. **Anticipate questions**: Address common confusion points

### Example - Good vs Bad

**❌ Bad Help Text**:
```
This page shows tax information. Upload files to see reports.
```

**✅ Good Help Text**:
```
Your December 2025 report matched 51 invoices to payment dates, showing 
$2,878.37 in tax collected across 8 NC counties. Use these county totals 
when filing your NC-5 form. The 44 unmatched invoices weren't paid yet - 
they'll appear in future reports when payment is received.
```

## Rollout Plan

### Phase 1: Tax Report Page (CURRENT SPRINT)
- Implement all 4 help states for tax report
- Test with Michele's real workflows
- Gather feedback on helpfulness

### Phase 2: Statement Generator
- Add help for upload process
- Explain statement details
- Guide through batch generation

### Phase 3: Future FSM Pages
- Customer management help
- Job creation help
- Scheduling help
- Each page gets comprehensive help on launch

## Success Metrics

**We'll know the help system works when:**
- Michele can use new features without calling Chris
- New office staff can learn the system in <30 minutes
- Support questions drop by 80%
- Users say "Oh, I didn't know it could do that!" when reading help

## Maintenance

- **Review help quarterly**: Does it match current UI?
- **Update with new features**: Help written before feature ships
- **Watch for patterns**: If users ask the same question 3x, add help
- **Keep it current**: Remove outdated references immediately

---

**Last Updated**: 2026-01-22
**Status**: Concept - ready for implementation
**Owner**: Chris (with Claude's help)
