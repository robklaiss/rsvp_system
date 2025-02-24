# RSVP System Testing Instructions

## 1. Web Interface Testing

### 1.1 Guest Registration
1. Access registration form: http://localhost:5000/register
2. **Valid Case**:
   - Name: `John Doe`
   - Phone: `+1234567890`
   - Email: `john@example.com` (optional)
   - Expected: Success message, redirect to status check

3. **Error Cases**:
   - **Missing Name**: Shows "Name and phone required"
   - **Invalid Phone**: `1234567890` (no +) → "Invalid phone format"
   - **Duplicate Phone**: Use same number twice → "Already registered"

### 1.2 Admin Approval
1. Login to admin: http://localhost:5000/admin
   - Credentials: From `.env` (admin/securepassword123)
2. Find pending guest
3. Click "Approve"
4. Verify:
   - Status changes to "Approved"
   - SMS sent (check Twilio console)
   - Email sent (if address provided)

### 1.3 Status Check
1. Visit http://localhost:5000/check-status
2. Enter approved phone number
3. Verify:
   - Approval status shown
   - Access code displayed

## 2. API Testing (cURL)

### 2.1 Register Guest
```bash
curl -X POST http://localhost:5000/guests \
-H "Content-Type: application/json" \
-d '{
  "name": "Alice Smith",
  "phone": "+441234567890",
  "email": "alice@example.com"
}'




Bulk approvals

# Get guest IDs first
curl -H "Authorization: Basic $(echo -n 'admin:securepassword123' | base64)" \
http://localhost:5000/guests

# Approve multiple
curl -X PATCH http://localhost:5000/guests/bulk-approve \
-H "Authorization: Basic $(echo -n 'admin:securepassword123' | base64)" \
-H "Content-Type: application/json" \
-d '{"ids": [1,2,3]}'



Export data

curl -H "Authorization: Basic $(echo -n 'admin:securepassword123' | base64)" \
http://localhost:5000/admin/export -o guests.csv




Edge case testing

International numbers

curl -X POST http://localhost:5000/guests \
-H "Content-Type: application/json" \
-d '{
  "name": "Léa Dubois",
  "phone": "+33123456789"
}'


Long names

curl -X POST http://localhost:5000/guests \
-H "Content-Type: application/json" \
-d '{
  "name": "Dr. Patricia María Hernández-López y Martínez",
  "phone": "+525512345678"
}'


Security Testing

Unauthorized Admin Access:
curl http://localhost:5000/guests
Should return 401 Unauthorized


SQL Injection Attempt:
curl -X POST http://localhost:5000/guests \
-H "Content-Type: application/json" \
-d '{"name": "Test", "phone": "+123\'; DROP TABLE guests;"}'
Should show validation error


5. Performance Testing

Simulate 10 concurrent registrations:
for i in {1..10}; do
  curl -s -X POST http://localhost:5000/guests \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"User $i\", \"phone\": \"+123456789$i\"}" &
done


Verification Checklist
[ ] New guests appear in admin dashboard
[ ] Approval triggers both SMS/email
[ ] CSV export contains all fields
[ ] All error cases handled with proper messages
[ ] API responses match OpenAPI spec
[ ] Mobile responsive design works

