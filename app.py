import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Patient, Medication, Prescription, PrescriptionItem, ClinicalNote
from datetime import datetime
import pandas as pd
import plotly
import plotly.express as px
import json
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data/pms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables
with app.app_context():
    db.create_all()

# Utility functions
def create_backup():
    """Create database backup"""
    backup_dir = os.path.join(app.root_path, 'data', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'pms_backup_{timestamp}.db')
    # In a real app, you'd implement proper backup logic here
    return True

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'teacher':
            flash('You need to be a teacher to access this page.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
@login_required
def dashboard():
    # Create backup on each dashboard visit
    create_backup()
    
    # Get statistics
    stats = {
        'patient_count': Patient.query.count(),
        'medication_count': Medication.query.count(),
        'active_prescriptions': Prescription.query.filter_by(status='approved').count(),
        'low_stock': Medication.query.filter(Medication.quantity <= Medication.reorder_level).count()
    }
    
    # Create charts with proper error handling
    try:
        # Patients by gender chart
        gender_data = db.session.query(Patient.gender, db.func.count(Patient.id)).group_by(Patient.gender).all()
        gender_df = pd.DataFrame(gender_data, columns=['Gender', 'Count'])
        gender_fig = px.pie(gender_df, values='Count', names='Gender', title='Patients by Gender')
        gender_graph = json.dumps(gender_fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Medications by dosage form chart
        form_data = db.session.query(Medication.dosage_form, db.func.count(Medication.id)).group_by(Medication.dosage_form).all()
        form_df = pd.DataFrame(form_data, columns=['Dosage Form', 'Count'])
        form_fig = px.bar(form_df, x='Dosage Form', y='Count', title='Medications by Dosage Form')
        form_graph = json.dumps(form_fig, cls=plotly.utils.PlotlyJSONEncoder)
        
    except Exception as e:
        print(f"Error generating charts: {str(e)}")
        gender_graph = "{}"
        form_graph = "{}"
    
    return render_template('dashboard.html', 
                         stats=stats,
                         gender_graph=gender_graph,
                         form_graph=form_graph)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not check_password_hash(user.password, password):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('login'))
        
        login_user(user)
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/patients')
@login_required
def patients():
    patient_list = Patient.query.order_by(Patient.last_name).all()
    return render_template('patients.html', patients=patient_list)

@app.route('/medications')
@login_required
def medications():
    med_list = Medication.query.order_by(Medication.name).all()
    low_stock = Medication.query.filter(Medication.quantity <= Medication.reorder_level).all()
    return render_template('medications.html', medications=med_list, low_stock=low_stock)

@app.route('/prescriptions')
@login_required
def prescriptions():
    if current_user.role == 'teacher':
        prescription_list = Prescription.query.order_by(Prescription.date_prescribed.desc()).all()
    else:
        prescription_list = Prescription.query.filter_by(prescriber_id=current_user.id).order_by(Prescription.date_prescribed.desc()).all()
    return render_template('prescriptions.html', prescriptions=prescription_list)

@app.route('/calculators')
@login_required
def calculators():
    return render_template('calculators.html')

# API Endpoints for calculators
@app.route('/calculate/bmi', methods=['POST'])
@login_required
def calculate_bmi():
    data = request.get_json()
    try:
        weight = float(data['weight'])
        height = float(data['height'])
        bmi = weight / ((height/100) ** 2)
        
        if bmi < 18.5:
            category = "Underweight"
        elif 18.5 <= bmi < 25:
            category = "Normal weight"
        elif 25 <= bmi < 30:
            category = "Overweight"
        else:
            category = "Obese"
            
        return jsonify({
            'result': round(bmi, 2),
            'category': category,
            'status': 'success'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/calculate/creatinine_clearance', methods=['POST'])
@login_required
def calculate_ccr():
    data = request.get_json()
    try:
        age = int(data['age'])
        weight = float(data['weight'])
        scr = float(data['scr'])
        gender = data['gender']
        
        if gender == 'male':
            ccr = ((140 - age) * weight) / (72 * scr)
        else:
            ccr = 0.85 * ((140 - age) * weight) / (72 * scr)
            
        return jsonify({
            'result': round(ccr, 2),
            'status': 'success'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

# Patient CRUD operations
@app.route('/patient/add', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_patient():
    if request.method == 'POST':
        try:
            dob = datetime.strptime(request.form.get('dob'), '%Y-%m-%d')
            
            patient = Patient(
                patient_id=request.form.get('patient_id'),
                first_name=request.form.get('first_name'),
                last_name=request.form.get('last_name'),
                dob=dob,
                gender=request.form.get('gender'),
                blood_type=request.form.get('blood_type'),
                allergies=request.form.get('allergies'),
                medical_history=request.form.get('medical_history')
            )
            
            db.session.add(patient)
            db.session.commit()
            flash('Patient added successfully', 'success')
            return redirect(url_for('patients'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding patient: {str(e)}', 'danger')
    
    return render_template('add_patient.html')

@app.route('/patient/<int:id>')
@login_required
def view_patient(id):
    patient = Patient.query.get_or_404(id)
    prescriptions = Prescription.query.filter_by(patient_id=id).order_by(Prescription.date_prescribed.desc()).all()
    clinical_notes = ClinicalNote.query.filter_by(patient_id=id).order_by(ClinicalNote.date.desc()).all()
    return render_template('view_patient.html', patient=patient, prescriptions=prescriptions, clinical_notes=clinical_notes)

# Medication CRUD operations
@app.route('/medication/add', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_medication():
    if request.method == 'POST':
        try:
            medication = Medication(
                name=request.form.get('name'),
                generic_name=request.form.get('generic_name'),
                dosage_form=request.form.get('dosage_form'),
                strength=request.form.get('strength'),
                manufacturer=request.form.get('manufacturer'),
                quantity=int(request.form.get('quantity')),
                reorder_level=int(request.form.get('reorder_level')),
                indications=request.form.get('indications'),
                contraindications=request.form.get('contraindications'),
                side_effects=request.form.get('side_effects')
            )
            
            db.session.add(medication)
            db.session.commit()
            flash('Medication added successfully', 'success')
            return redirect(url_for('medications'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding medication: {str(e)}', 'danger')
    
    return render_template('add_medication.html')

# Prescription operations
@app.route('/prescription/create', methods=['GET', 'POST'])
@login_required
def create_prescription():
    if request.method == 'POST':
        try:
            # Create prescription
            prescription = Prescription(
                patient_id=int(request.form.get('patient_id')),
                prescriber_id=current_user.id,
                instructions=request.form.get('instructions'),
                status='pending' if current_user.role == 'student' else 'approved'
            )
            
            db.session.add(prescription)
            db.session.commit()
            
            # Add prescription items
            medication_ids = request.form.getlist('medication_id[]')
            dosages = request.form.getlist('dosage[]')
            frequencies = request.form.getlist('frequency[]')
            durations = request.form.getlist('duration[]')
            
            for med_id, dosage, frequency, duration in zip(medication_ids, dosages, frequencies, durations):
                item = PrescriptionItem(
                    prescription_id=prescription.id,
                    medication_id=int(med_id),
                    dosage=dosage,
                    frequency=frequency,
                    duration=duration
                )
                db.session.add(item)
            
            db.session.commit()
            flash('Prescription created successfully', 'success')
            return redirect(url_for('prescriptions'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating prescription: {str(e)}', 'danger')
    
    patients = Patient.query.order_by(Patient.last_name).all()
    medications = Medication.query.order_by(Medication.name).all()
    return render_template('create_prescription.html', patients=patients, medications=medications)

@app.route('/prescription/approve/<int:id>')
@login_required
@teacher_required
def approve_prescription(id):
    prescription = Prescription.query.get_or_404(id)
    prescription.status = 'approved'
    db.session.commit()
    flash('Prescription approved', 'success')
    return redirect(url_for('prescriptions'))

# Add clinical note
@app.route('/patient/<int:patient_id>/add_note', methods=['POST'])
@login_required
def add_clinical_note(patient_id):
    if request.method == 'POST':
        try:
            note = ClinicalNote(
                patient_id=patient_id,
                author_id=current_user.id,
                note_type=request.form.get('note_type'),
                content=request.form.get('content')
            )
            
            db.session.add(note)
            db.session.commit()
            flash('Clinical note added successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding note: {str(e)}', 'danger')
    
    return redirect(url_for('view_patient', id=patient_id))

# View prescription details
@app.route('/prescription/<int:id>')
@login_required
def view_prescription(id):
    prescription = Prescription.query.get_or_404(id)
    return render_template('view_prescription.html', prescription=prescription)

# Initialize first user if none exists
def initialize_first_user():
    with app.app_context():
        if not User.query.first():
            admin = User(
                username='admin',
                password=generate_password_hash('admin123', method='sha256'),
                role='teacher'
            )
            db.session.add(admin)
            db.session.commit()

if __name__ == '__main__':
    initialize_first_user()
    app.run(debug=True)
