from datetime import datetime
from flask import Flask, request, jsonify, render_template, url_for, session, redirect, flash, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from twilio.rest import Client
import os
import secrets
import re
import time
from functools import wraps
from flask_mail import Mail, Message
from flask_migrate import Migrate
import random
import logging
import threading
from datetime import timedelta

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config.from_prefixed_env()
app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key')
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.jinja_env.auto_reload = True

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///events.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Mail configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
mail = Mail(app)

# Twilio configuration
TWILIO_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)

# IP Whitelist configuration
allowed_ips = {'192.168.1.1', '127.0.0.1', '::1'}

# Couple names configuration
BRIDE_AND_GROOM = "Arami + Alberto"
RSVP_WEBSITE_URL = "http://127.0.0.1:8086/status"

# Database models
class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))
    max_guests = db.Column(db.Integer)
    
class RSVP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    guest_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')

class Guest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    access_code = db.Column(db.String(6), unique=True)
    approved = db.Column(db.Boolean, default=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, firstname, lastname, phone, email):
        self.firstname = firstname
        self.lastname = lastname
        self.phone = phone
        self.email = email
        self.access_code = ''.join(random.choices('0123456789', k=6))

# Initialize database
def init_db():
    with app.app_context():
        # Drop all tables
        db.drop_all()
        # Create all tables
        db.create_all()
        app.logger.info('Database tables created')
        
        # Create test user
        test_guest = Guest(
            firstname='Test',
            lastname='User',
            phone='+595972581488',
            email='test@example.com'
        )
        db.session.add(test_guest)
        db.session.commit()
        app.logger.info('Test user created')

init_db()

# Authentication decorators
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def check_auth(username, password):
    """Check if a username/password combination is valid."""
    return username == os.getenv('ADMIN_USER') and password == os.getenv('ADMIN_PASS')

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Acceso restringido. Por favor ingrese credenciales válidas.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

# Add approval state tracking
pending_approvals = {}

def admin_approve_guest(guest_id):
    if guest_id in pending_approvals:
        return jsonify({'error': 'Approval already in progress'}), 400

    pending_approvals[guest_id] = True
    try:
        guest = Guest.query.get_or_404(guest_id)
        guest.approved = True
        db.session.commit()
        
        if send_approval_notification(guest):
            return jsonify({
                'status': 'success',
                'message': 'Invitado aprobado y notificado exitosamente'
            })
        else:
            return jsonify({
                'status': 'warning',
                'message': 'Invitado aprobado pero hubo problemas al enviar la notificación'
            })
    finally:
        pending_approvals.pop(guest_id, None)

def approve_guest(guest_id):
    if guest_id in pending_approvals:
        return jsonify({'error': 'Approval already in progress'}), 400

    pending_approvals[guest_id] = True
    try:
        guest = Guest.query.get(guest_id)
        if not guest:
            return jsonify({'error': 'Guest not found'}), 404

        if guest.approved:
            return jsonify({'error': 'Guest already approved'}), 400

        guest.approved = True
        db.session.commit()

        send_approval_notification(guest)
        return jsonify({'message': 'Guest approved successfully'}), 200
    finally:
        pending_approvals.pop(guest_id, None)

lock = threading.Lock()

def debounced_approve_guest_admin(guest_id):
    with lock:
        if guest_id in pending_approvals:
            return jsonify({'error': 'Approval already in progress'}), 400
        
        pending_approvals[guest_id] = True
        try:
            guest = Guest.query.get_or_404(guest_id)
            
            if not guest.approved:
                guest.approved = True
                db.session.commit()
                
                if send_approval_notification(guest):
                    app.logger.info(f"Approval notification sent to guest {guest.id}")
                else:
                    app.logger.error(f"Failed to send approval notification to guest {guest.id}")
            
            return jsonify({
                "status": "approved",
                "access_code": guest.access_code
            })
        finally:
            pending_approvals.pop(guest_id, None)

def approve_guest_admin(guest_id):
    threading.Timer(1.0, debounced_approve_guest_admin, args=(guest_id,)).start()

@app.route('/approve/<int:guest_id>', methods=['POST'])
def approve_guest_admin_route(guest_id):
    if guest_id in pending_approvals:
        return jsonify({'error': 'Approval already in progress'}), 400
        
    pending_approvals[guest_id] = True
    try:
        guest = Guest.query.get_or_404(guest_id)
        
        if not guest.approved:
            guest.approved = True
            db.session.commit()
            
            if send_approval_notification(guest):
                app.logger.info(f"Approval notification sent to guest {guest.id}")
            else:
                app.logger.error(f"Failed to send approval notification to guest {guest.id}")
        
        return jsonify({
            "status": "approved",
            "access_code": guest.access_code
        })
    finally:
        pending_approvals.pop(guest_id, None)

@app.route('/admin/approve/<int:guest_id>', methods=['POST'])
@requires_auth
def admin_approve_guest_route(guest_id):
    return admin_approve_guest(guest_id)

def send_whatsapp(phone, access_code):
    """Send access code via WhatsApp with Twilio"""
    try:
        message = get_approval_message("Test Guest", approved=True, access_code=access_code)
        message = twilio_client.messages.create(
            body=message,
            from_=f"whatsapp:{TWILIO_NUMBER}",
            to=f"whatsapp:{phone}",
            status_callback=url_for('twilio_status', _external=True)
        )
        app.logger.info(f"Sent WhatsApp to {phone}: {message.sid}")
        return True
    except Exception as e:
        app.logger.error(f"Twilio error: {str(e)}")
        return False

@app.route('/twilio/status', methods=['POST'])
def twilio_status():
    """Handle Twilio message status updates"""
    status = request.form.get('MessageStatus')
    message_sid = request.form.get('MessageSid')
    app.logger.debug(f"Twilio status: {message_sid} - {status}")
    return '', 200

@app.route('/')
def index():
    return 'RSVP System Running!'

@app.route('/events', methods=['POST'])
def create_event():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['name', 'date', 'location', 'max_guests']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Validate date format
    try:
        event_date = datetime.fromisoformat(data['date'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date format. Use ISO 8601 (e.g. 2025-03-15T19:00:00)'}), 400
    
    # Validate guest count
    try:
        max_guests = int(data['max_guests'])
        if max_guests < 1:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'error': 'max_guests must be a positive integer'}), 400
    
    # Create and save event
    new_event = Event(
        name=data['name'],
        date=event_date,
        location=data['location'],
        max_guests=max_guests
    )
    
    db.session.add(new_event)
    db.session.commit()
    
    return jsonify({
        'id': new_event.id,
        'name': new_event.name,
        'date': new_event.date.isoformat(),
        'location': new_event.location,
        'max_guests': new_event.max_guests,
        'current_rsvps': 0
    }), 201

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Clear any existing flash messages
        session.pop('_flashes', None)
        
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        phone = request.form.get('phone')
        email = request.form.get('email')

        # Validate all required fields
        if not all([firstname, lastname, phone, email]):
            flash('Por favor complete todos los campos requeridos', 'danger')
            return redirect(url_for('register'))

        # Validate phone number format
        if not phone.startswith('+') or not phone[1:].isdigit():
            flash('El número de teléfono debe incluir el código de país (ejemplo: +595972123456)', 'danger')
            return redirect(url_for('register'))

        # Check for existing registration
        existing_guest = Guest.query.filter_by(phone=phone).first()
        if existing_guest:
            flash('Este número de teléfono ya está registrado', 'warning')
            return redirect(url_for('register'))

        # Create new guest
        guest = Guest(firstname=firstname, lastname=lastname, phone=phone, email=email)
        db.session.add(guest)
        
        try:
            db.session.commit()
            flash('¡Registro exitoso! Te notificaremos cuando tu registro sea aprobado.', 'success')
        except Exception as e:
            app.logger.error(f'Error in registration: {str(e)}')
            db.session.rollback()
            flash('Error al procesar el registro. Por favor intente nuevamente.', 'danger')
        
        return redirect(url_for('register'))

    return render_template('register.html', couple_names=BRIDE_AND_GROOM)

@app.route('/status', methods=['GET', 'POST'])
def check_status():
    if request.method == 'POST':
        phone = request.form.get('phone')
        access_code = request.form.get('access_code')
        
        if not phone or not access_code:
            flash('Por favor ingrese su número de teléfono y código de acceso', 'error')
            return redirect(url_for('check_status'))
            
        guest = Guest.query.filter_by(phone=phone, access_code=access_code).first()
        
        if guest and guest.approved:
            return render_template('status_result.html', guest=guest)
        else:
            flash('No se encontró ningún registro con esas credenciales', 'warning')
    return render_template('status.html')

@app.route('/guests/<int:guest_id>/approve', methods=['PATCH'])
def approve_guest_route(guest_id):
    return approve_guest(guest_id)

def load_message_templates():
    with open('sms-messages.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract messages using simple parsing
    not_approved = re.search(r'### Guest Not Approved\n```\n(.*?)\n```', content, re.DOTALL).group(1)
    approved = re.search(r'### Guest Approved\n```\n(.*?)\n```', content, re.DOTALL).group(1)
    
    return {
        'not_approved': not_approved,
        'approved': approved
    }

def get_approval_message(guest_name, approved=True, access_code=None):
    try:
        templates = load_message_templates()
        message = templates['approved'] if approved else templates['not_approved']
        message = message.replace('[Nombre]', guest_name).replace('[Arami & Alberto]', BRIDE_AND_GROOM)
        if approved and access_code:
            message = message.replace('[XXXX]', access_code)
        return message
    except Exception as e:
        app.logger.error(f"Error loading message template: {e}")
        return f"{'¡Bienvenido!' if approved else 'Lo sentimos,'} {guest_name}"

def send_approval_notification(guest):
    """Send approval notification via SMS and email"""
    message = get_approval_message(guest.firstname + ' ' + guest.lastname, 
                                 approved=guest.approved,
                                 access_code=guest.access_code)
    
    notification_sent = False
    errors = []

    # Send SMS
    try:
        sms = twilio_client.messages.create(
            body=message,
            from_=TWILIO_NUMBER,
            to=guest.phone
        )
        app.logger.info(f"SMS sent to {guest.phone}: {sms.sid}")
        notification_sent = True
    except Exception as e:
        app.logger.error(f"SMS failed: {str(e)}")
        errors.append(f"SMS: {str(e)}")

    # Send email
    try:
        email_subject = "Confirmación de Invitación - Boda de " + BRIDE_AND_GROOM
        msg = Message(
            subject=email_subject,
            sender=app.config['MAIL_USERNAME'],
            recipients=[guest.email]
        )
        
        # Create HTML version of the message with better formatting
        html_message = f"""
        <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f5f6fa;">
                <div style="max-width: 600px; margin: 0 auto; padding: 32px 16px;">
                    <div style="background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <div style="background-color: #2c3e50; padding: 24px; text-align: center;">
                            <h1 style="color: white; margin: 0; font-size: 24px;">Invitación a la Boda</h1>
                            <h2 style="color: #3498db; margin: 8px 0 0 0; font-size: 20px;">{BRIDE_AND_GROOM}</h2>
                        </div>
                        
                        <div style="padding: 24px;">
                            <p style="font-size: 16px; margin: 0 0 16px 0;">{message}</p>
                            
                            <div style="margin: 24px 0; padding: 16px; background-color: #f8f9fa; border-radius: 8px; border-left: 4px solid #3498db;">
                                <p style="margin: 0; color: #2c3e50;"><strong>Tu código de acceso:</strong></p>
                                <p style="font-size: 24px; margin: 8px 0 0 0; color: #3498db; font-weight: bold;">{guest.access_code}</p>
                            </div>
                            
                            <div style="margin-top: 24px; padding-top: 24px; border-top: 1px solid #eee; text-align: center;">
                                <p style="color: #666; font-size: 14px; margin: 0;">
                                    Si tienes alguna pregunta, no dudes en contactarnos.
                                </p>
                            </div>
                        </div>
                    </div>
                    
                    <div style="text-align: center; margin-top: 24px;">
                        <p style="color: #666; font-size: 12px; margin: 0;">
                            Este es un mensaje automático, por favor no respondas a este correo.
                        </p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        msg.html = html_message
        mail.send(msg)
        app.logger.info(f"Email sent to {guest.email}")
        notification_sent = True
    except Exception as e:
        app.logger.error(f"Email failed: {str(e)}")
        errors.append(f"Email: {str(e)}")

    if not notification_sent:
        error_msg = "All notification methods failed: " + "; ".join(errors)
        app.logger.error(error_msg)
        return False

    return True

@app.route('/login', methods=['GET', 'POST'])
def handle_login():
    phone = request.form['phone'].strip()
    access_code = request.form['access_code'].strip()
    
    guest = Guest.query.filter_by(
        phone=phone,
        access_code=access_code,
        approved=True
    ).first()

    if not guest:
        return render_template('login.html', 
            error="Invalid credentials or not approved"), 401

    session['guest_id'] = guest.id
    return redirect(url_for('private_details'))

@app.route('/private')
def private_details():
    guest = Guest.query.get(session['guest_id'])
    if not guest or not guest.approved:
        session.pop('guest_id', None)
        return redirect(url_for('login_form'))
        
    return render_template('private.html', guest=guest)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin_panel'))

@app.route('/test')
def test_route():
    results = []
    
    # Show the messages
    approval = get_approval_message("Juan Pérez", approved=True)
    
    results.append("<h2>Test Messages</h2>")
    results.append("<div style='margin: 20px; padding: 20px; border: 1px solid #ccc;'>")
    
    results.append("<h3>Approval Message:</h3>")
    results.append(f"<div style='background: #f5f5f5; padding: 10px; margin: 10px 0; font-family: monospace; white-space: pre-wrap;'>{approval}</div>")
    
    results.append("</div>")
    
    return ''.join(results)

@app.route('/test/add-guest')
def add_test_guest():
    try:
        guest = Guest(
            firstname="Test",
            lastname="Guest",
            phone="+1234567890",
            email="test@example.com"
        )
        db.session.add(guest)
        db.session.commit()
        return jsonify({
            'message': 'Test guest added',
            'guest_id': guest.id
        })
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/test/messages')
def view_test_messages():
    test_code = "1234"
    approved_msg = get_approval_message("Test Guest", approved=True, access_code=test_code)
    not_approved_msg = get_approval_message("Test Guest", approved=False)
    
    return jsonify({
        'approved': approved_msg,
        'not_approved': not_approved_msg,
        'test': {
            'guest_name': "Test Guest",
            'access_code': test_code
        }
    })

@app.route('/show-messages')
def show_messages():
    test_code = "5678"
    approved_msg = get_approval_message("Juan Pérez", approved=True, access_code=test_code)
    not_approved_msg = get_approval_message("Juan Pérez", approved=False)
    
    return f"""
    <html>
        <head>
            <title>Test Messages</title>
            <style>
                .message {{ padding: 10px; margin: 10px; border: 1px solid #ccc; }}
                .approved {{ background-color: #e6ffe6; }}
                .not-approved {{ background-color: #ffe6e6; }}
            </style>
        </head>
        <body>
            <h3>Approval Message (with code):</h3>
            <div class="message approved">
                {approved_msg}
            </div>
            <h3>Not Approved Message:</h3>
            <div class="message not-approved">
                {not_approved_msg}
            </div>
        </body>
    </html>
    """

@app.route('/admin/guests/create', methods=['POST'])
@requires_auth
def admin_create_guest():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['firstname', 'lastname', 'phone', 'email']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    # Validate phone number format
    if not data['phone'].startswith('+') or not data['phone'][1:].isdigit():
        return jsonify({'error': 'Phone number must include country code (e.g., +595972123456)'}), 400

    # Check for existing registration
    existing_guest = Guest.query.filter_by(phone=data['phone']).first()
    if existing_guest:
        return jsonify({'error': 'This phone number is already registered'}), 400

    # Create new guest
    guest = Guest(
        firstname=data['firstname'],
        lastname=data['lastname'],
        phone=data['phone'],
        email=data['email']
    )
    
    # Optionally set as approved directly
    if data.get('approved', False):
        guest.approved = True
    
    db.session.add(guest)
    
    try:
        db.session.commit()
        
        # Send notification if guest is approved
        if guest.approved:
            send_approval_notification(guest)
        
        return jsonify({
            'status': 'success',
            'message': 'Guest created successfully',
            'guest': {
                'id': guest.id,
                'firstname': guest.firstname,
                'lastname': guest.lastname,
                'phone': guest.phone,
                'email': guest.email,
                'approved': guest.approved,
                'access_code': guest.access_code
            }
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error creating guest: {str(e)}")
        return jsonify({'error': 'Error creating guest'}), 500

@app.route('/admin/delete-guest/<int:guest_id>', methods=['POST'])
def delete_guest(guest_id):
    try:
        guest = Guest.query.get_or_404(guest_id)
        db.session.delete(guest)
        db.session.commit()
        flash('Guest deleted successfully', 'success')
        return jsonify({'success': True, 'message': 'Guest deleted successfully'})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting guest: {str(e)}")
        return jsonify({'success': False, 'error': 'Error deleting guest'}), 500

@app.route('/admin')
def admin():
    guests = Guest.query.order_by(Guest.registered_at.desc()).all()
    return render_template('admin.html', 
                         guests=guests,
                         couple_names=BRIDE_AND_GROOM)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
