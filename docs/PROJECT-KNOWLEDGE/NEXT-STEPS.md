# FieldKit - Next Steps Action Plan
*Created: 2026-02-10*

## Immediate Next Session (Customer Management)

### Goal: Complete Customer CRUD Interface
Build the customer management pages so you can view, add, edit, and search customers through the web interface.

---

## Part 1: Customer List Page (2-3 hours)

### Features to Build:
1. **Customer List Table**
   - Property name (clickable to detail page)
   - Customer type badge (Multi Family, Contractors, Residential)
   - City, State
   - Status badge (Active/Inactive with colors)
   - Contact count
   - Actions (View, Edit, Delete icons)

2. **Search & Filters**
   - Search bar (property name, city, management company)
   - Filter dropdowns:
     - Customer Type (All, Multi Family, Contractors, Residential)
     - Status (All, Active, Inactive)
     - City (All, Charlotte, other cities)
   - "Clear Filters" button

3. **Sorting**
   - Click column headers to sort
   - Property Name (A-Z, Z-A)
   - Created Date (Newest, Oldest)
   - Status

4. **Pagination**
   - 50 customers per page
   - Page numbers at bottom
   - "Previous" and "Next" buttons
   - "Showing 1-50 of 2,476" counter

5. **Quick Actions**
   - "Add Customer" button (top right, prominent)
   - Bulk actions (future: bulk status change, bulk delete)

### Files to Create:
- `app.py` - Add `/customers` route
- `templates/customers_list.html` - Customer list page
- `static/css/customers.css` - Customer-specific styles (if needed)

---

## Part 2: Customer Detail Page (2 hours)

### Features to Build:
1. **Customer Header**
   - Property name (large, prominent)
   - Status badge
   - Customer type badge
   - "Edit" and "Delete" buttons

2. **Customer Info Card**
   - Address (with map link to Google Maps)
   - Management Company (with link to company page - future)
   - Payment terms
   - Billing email
   - Created date, Created by
   - Last updated date, Last updated by

3. **Contacts Section**
   - List all contacts
   - Primary contact highlighted
   - Name, Title, Phone, Email
   - "Add Contact" button
   - Edit/Delete icons per contact

4. **Notes Section**
   - Chronological list of notes
   - Author, timestamp
   - "Add Note" button
   - Quick note types: General, Service, Billing, Sales

5. **Tags Section**
   - Display all tags as colored badges
   - "Add Tag" input
   - Click tag to remove

6. **Activity History**
   - Timeline of changes
   - Created, Updated, Status changes
   - Contact additions/changes
   - Notes added

7. **Quick Actions**
   - "Create Job" (disabled, Phase 4)
   - "View Invoices" (disabled, Phase 5)
   - "Email Customer" (future)

### Files to Create:
- `app.py` - Add `/customers/<id>` route
- `templates/customer_detail.html` - Customer detail page

---

## Part 3: Add/Edit Customer Forms (2-3 hours)

### Add Customer Modal/Page:
1. **Form Fields**
   - Property Name * (required)
   - Customer Type * (dropdown: Multi Family, Contractors, Residential, Commercial)
   - Status * (dropdown: Active, Inactive, On Hold, Lead)
   - Management Company (dropdown with "Add New")
   - Address
   - Address 2
   - City
   - State (dropdown: NC, SC, GA, FL, VA, TN)
   - Zip
   - Billing Email
   - Payment Terms (dropdown: Net 30, Net 15, Due on Receipt)
   - Notes (textarea)

2. **Primary Contact Section** (on same form)
   - First Name
   - Last Name
   - Title
   - Office Phone
   - Mobile Phone
   - Email
   - Checkbox: "Add as primary contact"

3. **Form Validation**
   - Required fields marked with *
   - Property name must be unique per company
   - Email format validation
   - Phone format validation (optional)
   - Zip code format

4. **Save Behavior**
   - "Save" button
   - "Save & Add Another" button
   - "Cancel" button
   - Success message: "Customer added successfully!"
   - Redirect to customer detail page after save

### Edit Customer:
- Same form as Add Customer
- Pre-populated with existing data
- Save updates with audit trail (updated_by, updated_at)

### Files to Create:
- `app.py` - Add `/customers/new` and `/customers/<id>/edit` routes
- `templates/customer_form.html` - Form template (used for both add/edit)
- Form validation JavaScript

---

## Part 4: Contact Management (1-2 hours)

### Add Contact Modal:
1. **Fields** (same as primary contact on customer form)
2. **Checkbox**: "Set as primary contact" (if checked, unset current primary)
3. **Save** → Adds contact, closes modal, refreshes contact list

### Edit Contact:
- Same modal, pre-populated
- Can change primary contact flag

### Delete Contact:
- Confirmation dialog: "Are you sure?"
- Soft delete (sets deleted_at)
- Cannot delete if only contact

### Files to Create:
- `app.py` - Add contact routes: `/customers/<id>/contacts/new`, `/contacts/<id>/edit`, `/contacts/<id>/delete`
- `templates/contact_modal.html` - Contact form modal

---

## Part 5: Customer Search (1 hour)

### Search Functionality:
1. **Search Input** (on customer list page)
   - Real-time search as you type
   - Searches: Property name, City, Management company name
   - Clear button (X) to reset search

2. **Backend Search**
   - SQL query with ILIKE for case-insensitive
   - Full-text search on property_name
   - Join with management_companies for company name search

3. **Search Results**
   - Highlight matching text
   - Show result count: "Found 47 customers matching 'apartment'"
   - No results message with suggestions

### Files to Update:
- `app.py` - Update `/customers` route to handle search parameter
- `templates/customers_list.html` - Add search input and JavaScript

---

## Technical Implementation Notes

### Database Queries Needed:

```python
# Customer list with pagination
def get_customers(company_key, page=1, per_page=50, search=None, filters=None):
    conn = get_db_connection(company_key)
    cursor = conn.cursor()
    
    query = """
        SELECT c.*, mc.name as management_company_name,
               COUNT(cc.id) as contact_count
        FROM customers c
        LEFT JOIN management_companies mc ON c.management_company_id = mc.id
        LEFT JOIN customer_contacts cc ON c.id = cc.customer_id AND cc.deleted_at IS NULL
        WHERE c.deleted_at IS NULL
    """
    
    # Add search
    if search:
        query += " AND c.property_name ILIKE %s"
    
    # Add filters
    if filters.get('customer_type'):
        query += " AND c.customer_type = %s"
    
    # Group by, order, limit
    query += " GROUP BY c.id, mc.name ORDER BY c.property_name LIMIT %s OFFSET %s"
    
    return results
```

### API Endpoints to Add:

```python
# Customer routes
GET  /customers                    # List customers
GET  /customers/<id>               # View customer
GET  /customers/new                # Add customer form
POST /customers                    # Create customer
GET  /customers/<id>/edit          # Edit customer form
POST /customers/<id>               # Update customer
POST /customers/<id>/delete        # Delete customer (soft)

# Contact routes
POST /customers/<id>/contacts      # Add contact
GET  /contacts/<id>/edit           # Edit contact form
POST /contacts/<id>                # Update contact
POST /contacts/<id>/delete         # Delete contact

# Note routes
POST /customers/<id>/notes         # Add note

# Tag routes
POST /customers/<id>/tags          # Add tag
POST /tags/<id>/delete             # Remove tag
```

---

## UI/UX Improvements

### Color-Coded Elements:
- **Status badges**:
  - Active: Green background (#e8f5e9), green text (#2e7d32)
  - Inactive: Red background (#fce4ec), red text (#c2185b)
  - On Hold: Yellow background (#fff9c4), dark text (#f57f17)

- **Customer type badges**:
  - Multi Family: Blue (#e3f2fd, #1565c0)
  - Contractors: Orange (#fff3e0, #e65100)
  - Residential: Purple (#f3e5f5, #6a1b9a)
  - Commercial: Teal (#e0f2f1, #00695c)

### Icons to Use:
- 👁️ View (eye icon)
- ✏️ Edit (pencil icon)
- 🗑️ Delete (trash icon)
- ➕ Add (plus icon)
- 🔍 Search (magnifying glass)
- 📧 Email
- 📞 Phone
- 🏢 Building (management company)

---

## Testing Checklist

### For Each Feature:
- [ ] Works with Get a Grip data (2,476 customers)
- [ ] Company branding colors correct
- [ ] Pagination works correctly
- [ ] Search returns accurate results
- [ ] Forms validate properly
- [ ] Success/error messages display
- [ ] Audit trails recorded (created_by, updated_by)
- [ ] Soft deletes work (deleted_at set, not removed)
- [ ] Multi-contact support working
- [ ] Primary contact flag toggles correctly

### Cross-Browser Testing:
- [ ] Chrome/Edge
- [ ] Firefox
- [ ] Safari (if accessible)
- [ ] Mobile responsive

---

## After Customer Management Complete

### Production Deployment (1-2 hours)
1. **Set up systemd service**
   ```bash
   sudo nano /etc/systemd/system/fieldkit.service
   sudo systemctl enable fieldkit
   sudo systemctl start fieldkit
   ```

2. **Configure Nginx**
   ```bash
   sudo nano /etc/nginx/sites-available/fieldkit
   sudo ln -s /etc/nginx/sites-available/fieldkit /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

3. **SSL Certificate**
   ```bash
   sudo certbot --nginx -d fieldkit.cletize.com
   ```

4. **Test production**
   - Login as all user types
   - Test customer CRUD
   - Verify company switching
   - Check performance with 2,476 customers

### Import Other Companies (1 hour each)
1. Get Kleanit Charlotte export from ServiceFusion
2. Run import script: `./import_sf_customers.py Kleanit_Customers.xlsx kleanit_charlotte`
3. Verify import
4. Repeat for CTS
5. Repeat for Kleanit South Florida

### User Testing (Michele & Team)
1. Schedule training session
2. Walk through features
3. Get feedback
4. Make adjustments based on feedback
5. Document any issues
6. Plan fixes for next session

---

## Phase 1 Completion Criteria

### Must Have:
- ✅ Database architecture complete
- ✅ Authentication working
- ✅ Company switcher functional
- ✅ Dashboard with real data
- ⏳ Customer list with search/filters
- ⏳ Customer detail page
- ⏳ Add/edit customer forms
- ⏳ Contact management
- ⏳ All 4 companies have data imported
- ⏳ Production deployment
- ⏳ Michele tested and approved

### Nice to Have (can move to Phase 2):
- Customer notes with rich text
- Custom tags per company
- Customer merge/duplicate detection
- Export to CSV
- Advanced filters (date ranges, custom fields)
- Saved searches

---

## Estimated Timeline

### Next Session (Customer CRUD):
- **Duration**: 6-8 hours
- **Deliverables**: Complete customer management interface
- **Outcome**: Can add, view, edit, delete customers through web UI

### Session After That (Polish & Deploy):
- **Duration**: 3-4 hours
- **Deliverables**: Import other companies, production deployment
- **Outcome**: FieldKit live at fieldkit.cletize.com

### Total to Phase 1 Complete:
- **2-3 more sessions**
- **~15 hours of development**
- **Timeline**: 1-2 weeks

---

## Questions to Consider

### Before Next Session:
1. **Customer list**: Inline edit or separate page?
2. **Contact management**: Modal or separate page?
3. **Customer photos**: Should we support uploading company logos/photos?
4. **Bulk operations**: Priority for Phase 1 or Phase 2?
5. **Mobile interface**: How important is mobile for office staff?

### During Development:
1. **Performance**: Test with 2,476 customers - is pagination smooth?
2. **Search**: Real-time (as you type) or submit button?
3. **Validation**: Client-side JavaScript or server-side only?
4. **Errors**: How to display validation errors clearly?

---

## Resources for Next Session

### Have Ready:
- ✅ Flask app running on port 5001
- ✅ Database with 2,476 Get a Grip customers
- ✅ Authentication working
- ✅ Test user accounts (chris, michele, walter)

### Will Need:
- Icon library (Font Awesome or similar)
- Form validation JavaScript
- Modal library (or build custom)
- Pagination logic
- Search debounce function

---

## Success Metrics

### Phase 1 Complete When:
1. ✅ Michele can log in from any computer
2. ⏳ Michele can view all customers in clean list
3. ⏳ Michele can search for customers instantly
4. ⏳ Michele can add new customers in <2 minutes
5. ⏳ Michele can edit customer info easily
6. ⏳ Michele can manage multiple contacts per customer
7. ⏳ All 4 companies have their customer data
8. ⏳ System runs reliably without crashes
9. ⏳ Michele prefers FieldKit to ServiceFusion

### Business Impact:
- **Time saved**: 5-10 hours/week (no more QuickBooks sync fixes)
- **Multi-company workflow**: 10x faster (right-click to open tabs)
- **Data quality**: Complete audit trails, no lost changes
- **User satisfaction**: Michele actually enjoys using it!

---

*Next session goal: Make customer management so good that Michele never wants to open ServiceFusion again!* 🎯
