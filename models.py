from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='student')  # 'student' or 'teacher'

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    blood_type = db.Column(db.String(5))
    allergies = db.Column(db.Text)
    medical_history = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Medication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    generic_name = db.Column(db.String(100))
    dosage_form = db.Column(db.String(50))  # tablet, capsule, injection, etc.
    strength = db.Column(db.String(50))     # 500mg, 10mg/mL, etc.
    manufacturer = db.Column(db.String(100))
    quantity = db.Column(db.Integer, default=0)
    reorder_level = db.Column(db.Integer, default=10)
    indications = db.Column(db.Text)
    contraindications = db.Column(db.Text)
    side_effects = db.Column(db.Text)

class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    prescriber_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_prescribed = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, approved, denied, dispensed
    instructions = db.Column(db.Text)
    patient = db.relationship('Patient', backref='prescriptions')
    prescriber = db.relationship('User', backref='prescriptions')

class PrescriptionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescription.id'), nullable=False)
    medication_id = db.Column(db.Integer, db.ForeignKey('medication.id'), nullable=False)
    dosage = db.Column(db.String(100), nullable=False)
    frequency = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.String(50))  # e.g., "7 days", "1 month"
    medication = db.relationship('Medication', backref='prescription_items')
    prescription = db.relationship('Prescription', backref='items')

class ClinicalNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    note_type = db.Column(db.String(50))  # progress, assessment, plan, etc.
    content = db.Column(db.Text, nullable=False)
    patient = db.relationship('Patient', backref='clinical_notes')
    author = db.relationship('User', backref='clinical_notes')
