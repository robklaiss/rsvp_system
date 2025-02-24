# RSVP System Setup

## Requirements
- Python 3.9+
- Twilio account
- WhatsApp-enabled number

## Installation
```bash
pip install -r requirements.txt
```

## Configuration
1. Create `.env` file
2. Set Twilio credentials
3. Set admin credentials

## Usage
```bash
flask run
```

Access admin interface at `/admin`

# RSVP System - Complete Testing Guide

## Test Environment Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start development server
flask run
```

## Feature Testing Checklist

### Guest Registration
```bash
# Valid registration
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Alice Smith", "phone":"+441234567890"}'

# Duplicate phone test  
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Bob Wilson", "phone":"+441234567890"}'

# Invalid format test
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{"phone":"+1234"}'
```
**Verify:**
- 201 Created for valid requests
- 409 Conflict for duplicates
- 400 Bad Request for invalid data

### Admin Interface
1. Visit `http://localhost:5000/admin`
2. Use credentials from `.env` file
3. Test actions:
   - Approve guest → Check WhatsApp message
   - Reject guest → Verify removal
   - Filter by approval status

```bash
# Manual approval test
curl -X POST http://localhost:5000/approve/1 \
  -u "admin:securepassword123"
```

### Guest Login & Private Access
```bash
# Successful login
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "phone=+441234567890&access_code=123456"

# Private access test
curl -b cookies.txt http://localhost:5000/private

# Invalid login test  
curl -X POST http://localhost:5000/login \
  -d "phone=+441234567890&access_code=wrongcode"
```
**Verify:**
- Redirect to private page after valid login
- 401 Unauthorized for invalid credentials
- Session persistence across requests

### Security Checks
```bash
# Admin access without credentials
curl http://localhost:5000/admin

# Private page without session
curl http://localhost:5000/private

# Session hijack test
curl -b "session=malicious_cookie" http://localhost:5000/private
```
**Verify:**
- 401 Unauthorized responses
- Session invalidation after logout

### WhatsApp Notifications
1. Check Twilio console for message SIDs
2. Verify message content:
   ```text
   Your RSVP access code is: 123456
   Expires in 24 hours
   ```
3. Test failed notifications by:
   - Using invalid Twilio credentials
   - Blocking WhatsApp service

## Troubleshooting
**Common Issues:**
- `IntegrityError`: Run `flask init-db`
- Missing WhatsApp: Verify Twilio number is WhatsApp-enabled
- Session issues: Clear browser cookies or use incognito mode

**View Logs:**
```bash
tail -f /var/log/flask.log | grep -E 'Twilio|ERROR'
```

## HostGator Deployment

1. SSH into server:
```bash
ssh username@yourdomain.com
cd public_html

# Create virtual environment
virtualenv venv --python=python3.9

# Install requirements
source venv/bin/activate
pip install -r requirements.txt

# Set permissions
chmod 644 wsgi.py
chmod 755 public_html
```

2. Update file paths in:
- `wsgi.py`
- `.htaccess`
- `app.py` (database path)

3. Enable mod_wsgi in cPanel
4. Set environment variables in cPanel's "Environment Variables" section

**Production Checklist:**
- [ ] Enable HTTPS
- [ ] Set `FLASK_ENV=production` 
- [ ] Rotate `SECRET_KEY`
- [ ] Configure database backups