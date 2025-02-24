from datetime import datetime
from flask import Flask, request, jsonify, render_template, url_for, session, redirect, flash, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from twilio.rest import Client
import os
import secrets
import re
from functools import wraps
from flask_mail import Mail, Message
from flask_migrate import Migrate
import random
import logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config.from_prefixed_env()
app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key')

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///events.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
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

        try:
            guest = Guest(firstname=firstname, lastname=lastname, phone=phone, email=email)
            db.session.add(guest)
            db.session.commit()
            
            flash('¡Registro exitoso! Te notificaremos cuando tu registro sea aprobado.', 'success')
            return redirect(url_for('status'))
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
def approve_guest(guest_id):
    guest = Guest.query.get(guest_id)
    
    if not guest:
        return jsonify({'error': 'Guest not found'}), 404
        
    guest.approved = True
    db.session.commit()
    
    # Send SMS notification
    try:
        send_approval_notification(guest)  # Send email and/or SMS
    except Exception as e:
        print(f"Notification failed: {str(e)}")
    
    return jsonify({
        'id': guest.id,
        'approved': True,
        'message': 'Guest approved and notified'
    })

def get_rejection_message(guest_name):
    return f"""Querido/a {guest_name},

Muchas gracias por tu amable confirmación. Nos llena de alegría saber que querías acompañarnos en este día tan especial.

Debido a la capacidad limitada del lugar, lamentablemente no podremos incluir a todos los que se registraron, y sentimos mucho informarte que en esta ocasión no podremos contar con tu presencia.

Apreciamos mucho tu cariño y comprensión, y esperamos poder celebrar juntos en otra oportunidad.

Con mucho cariño,
{BRIDE_AND_GROOM}"""

def get_approval_message(guest_name, access_code):
    return f"""Querido/a {guest_name},

¡Estamos felices de confirmarte que formas parte de nuestra celebración! Queremos compartir contigo todos los detalles de nuestro gran día, así que hemos preparado un sitio web privado donde encontrarás toda la información sobre la boda.

Para acceder, utiliza los siguientes datos:
URL: {RSVP_WEBSITE_URL}
Código de acceso: {access_code}

¡Nos emociona mucho celebrar juntos este momento tan especial! Nos vemos pronto.

Con amor,
{BRIDE_AND_GROOM}"""

def send_approval_notification(guest):
    """Send approval notification with access code via WhatsApp (primary) or SMS (fallback)"""
    message = get_approval_message(f"{guest.firstname} {guest.lastname}", guest.access_code)
    
    # First try WhatsApp
    try:
        whatsapp = twilio_client.messages.create(
            body=message,
            from_=f"whatsapp:{TWILIO_NUMBER}",
            to=f"whatsapp:{guest.phone}",
            status_callback=url_for('twilio_status', _external=True)
        )
        app.logger.info(f"WhatsApp notification sent to {guest.phone}: {whatsapp.sid}")
        
        # Also send email if available
        if guest.email:
            msg = Message(
                'Confirmación de Invitación - Boda de Arami y Alberto',
                recipients=[guest.email],
                html=message.replace('\n', '<br>')
            )
            mail.send(msg)
        return True
    except Exception as wa_error:
        app.logger.warning(f"WhatsApp notification failed: {str(wa_error)}")
        
        # Fallback to SMS
        try:
            sms = twilio_client.messages.create(
                body=message,
                from_=TWILIO_NUMBER,
                to=guest.phone
            )
            app.logger.info(f"SMS notification sent to {guest.phone}: {sms.sid}")
            return True
        except Exception as sms_error:
            app.logger.error(f"Both WhatsApp and SMS notification failed. SMS error: {str(sms_error)}")
            return False

def send_rejection_notification(guest):
    """Send rejection notification"""
    message = get_rejection_message(f"{guest.firstname} {guest.lastname}")
    
    try:
        # Try WhatsApp first
        whatsapp = twilio_client.messages.create(
            body=message,
            from_=f"whatsapp:{TWILIO_NUMBER}",
            to=f"whatsapp:{guest.phone}",
            status_callback=url_for('twilio_status', _external=True)
        )
        app.logger.info(f"WhatsApp rejection sent to {guest.phone}: {whatsapp.sid}")
        
        # Also send email if available
        if guest.email:
            msg = Message(
                'Actualización sobre tu registro - Boda de Arami y Alberto',
                recipients=[guest.email],
                html=message.replace('\n', '<br>')
            )
            mail.send(msg)
        return True
    except Exception as wa_error:
        app.logger.warning(f"WhatsApp rejection failed: {str(wa_error)}")
        
        # Fallback to SMS
        try:
            sms = twilio_client.messages.create(
                body=message,
                from_=TWILIO_NUMBER,
                to=guest.phone
            )
            app.logger.info(f"SMS rejection sent to {guest.phone}: {sms.sid}")
            return True
        except Exception as sms_error:
            app.logger.error(f"Both WhatsApp and SMS rejection failed. SMS error: {str(sms_error)}")
            return False

@app.route('/admin')
@requires_auth
def admin_panel():
    try:
        guests = Guest.query.order_by(Guest.registered_at.desc()).all()
        app.logger.info(f"Retrieved {len(guests)} guests from database")
        return render_template('admin.html', guests=guests, couple_names=BRIDE_AND_GROOM)
    except Exception as e:
        app.logger.error(f"Error in admin panel: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error interno del servidor: {str(e)}'
        }), 500

@app.route('/admin/approve/<int:guest_id>', methods=['POST'])
@requires_auth
def admin_approve_guest(guest_id):
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

@app.route('/admin/reject/<int:guest_id>', methods=['POST'])
@requires_auth
def admin_reject_guest(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    
    if send_rejection_notification(guest):
        # Delete the guest after sending notification
        db.session.delete(guest)
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Invitado rechazado y notificado exitosamente'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Error al enviar la notificación de rechazo'
        })

@app.route('/approve/<int:guest_id>', methods=['POST'])
def approve_guest_admin(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    
    if not guest.approved:
        guest.approved = True
        db.session.commit()
        
        try:
            message = twilio_client.messages.create(
                body=f"Your RSVP access code: {guest.access_code}",
                from_=f"whatsapp:{os.getenv('TWILIO_PHONE_NUMBER')}",
                to=f"whatsapp:{guest.phone}"
            )
        except Exception as e:
            app.logger.error(f"Failed to send WhatsApp: {str(e)}")
    
    return jsonify({
        "status": "approved",
        "access_code": guest.access_code
    })

@app.route('/reject/<int:guest_id>', methods=['POST'])
def reject_guest(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    db.session.delete(guest)
    db.session.commit()
    return jsonify({"status": "deleted"})

def send_whatsapp(phone, access_code):
    """Send access code via WhatsApp with Twilio"""
    try:
        message = twilio_client.messages.create(
            body=f"Your RSVP access code is: {access_code}\nExpires in 24 hours.",
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

@app.route('/test')
def test_route():
    results = []
    test_phone = "+595972581488"  # Your phone number
    test_message = "Test message from your RSVP system!"
    
    try:
        # Test WhatsApp (primary)
        whatsapp = twilio_client.messages.create(
            body=test_message,
            from_=f"whatsapp:{TWILIO_NUMBER}",
            to=f"whatsapp:{test_phone}",
            status_callback=url_for('twilio_status', _external=True)
        )
        results.append(f"WhatsApp message sent successfully! Message SID: {whatsapp.sid}")
    except Exception as wa_error:
        results.append(f"WhatsApp test failed: {str(wa_error)}")
        
        # Try SMS as fallback
        try:
            sms = twilio_client.messages.create(
                body=f"{test_message} (SMS fallback)",
                from_=TWILIO_NUMBER,
                to=test_phone
            )
            results.append(f"Fallback SMS sent successfully! Message SID: {sms.sid}")
        except Exception as sms_error:
            results.append(f"SMS fallback also failed: {str(sms_error)}")
    
    return "<br>".join(results), 200

if __name__ == '__main__':
    app.run(port=8086)
