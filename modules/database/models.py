from modules.database.db import db
from datetime import datetime


class Transaction(db.Model):
    __tablename__ = "transactions"

    txn_id = db.Column(db.String, primary_key=True)

    description = db.Column(db.Text)
    clean_description = db.Column(db.Text)
    merchant_name = db.Column(db.Text)
    payment_channel = db.Column(db.Text)

    amount = db.Column(db.Float)
    type = db.Column(db.String)
    date = db.Column(db.String)
    weekday = db.Column(db.String)
    time_of_day = db.Column(db.String)
    balance_after_txn = db.Column(db.Float)

    category = db.Column(db.String)
    subcategory = db.Column(db.String)
    is_recurring = db.Column(db.Boolean)
    recurrence_interval = db.Column(db.String)
    confidence_score = db.Column(db.Float)
    is_suspicious = db.Column(db.Boolean)

    embedding_version = db.Column(db.Integer)
    raw_email_snippet = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'txn_id': self.txn_id,
            'description': self.description,
            'clean_description': self.clean_description,
            'merchant_name': self.merchant_name,
            'payment_channel': self.payment_channel,
            'amount': self.amount,
            'type': self.type,
            'date': self.date,
            'weekday': self.weekday,
            'time_of_day': self.time_of_day,
            'balance_after_txn': self.balance_after_txn,
            'category': self.category,
            'subcategory': self.subcategory,
            'is_recurring': self.is_recurring,
            'recurrence_interval': self.recurrence_interval,
            'confidence_score': self.confidence_score,
            'is_suspicious': self.is_suspicious,
            'embedding_version': self.embedding_version,
            'raw_email_snippet': self.raw_email_snippet,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Receipt(db.Model):
    __tablename__ = 'receipts'
    
    # Primary key
    receipt_id = db.Column(db.String(100), primary_key=True)
    
    # Receipt type and timing
    receipt_type = db.Column(db.String(50))  # digital, physical, etc.
    issue_date = db.Column(db.String(20))  # YYYY-MM-DD
    issue_time = db.Column(db.String(10))  # HH:MM
    
    # Merchant information
    merchant_name = db.Column(db.String(200))
    merchant_address = db.Column(db.String(500), nullable=True)
    merchant_gst = db.Column(db.String(50), nullable=True)
    
    # Financial details
    subtotal_amount = db.Column(db.Float)
    tax_amount = db.Column(db.Float)
    total_amount = db.Column(db.Float)
    
    # Payment information
    payment_method = db.Column(db.String(50))
    
    # Metadata
    extracted_confidence_score = db.Column(db.Float)
    is_suspicious = db.Column(db.Boolean, default=False)
    embedding_version = db.Column(db.Integer)
    
    # Store attachment info
    attachment_filename = db.Column(db.String(200), nullable=True)
    attachment_message_id = db.Column(db.String(100), nullable=True)
    attachment_id = db.Column(db.String(100), nullable=True)
    
    # Raw snippet from email
    raw_snippet = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'receipt_id': self.receipt_id,
            'receipt_type': self.receipt_type,
            'issue_date': self.issue_date,
            'issue_time': self.issue_time,
            'merchant_name': self.merchant_name,
            'merchant_address': self.merchant_address,
            'merchant_gst': self.merchant_gst,
            'subtotal_amount': self.subtotal_amount,
            'tax_amount': self.tax_amount,
            'total_amount': self.total_amount,
            'payment_method': self.payment_method,
            'extracted_confidence_score': self.extracted_confidence_score,
            'is_suspicious': self.is_suspicious,
            'embedding_version': self.embedding_version,
            'attachment_filename': self.attachment_filename,
            'attachment_message_id': self.attachment_message_id,
            'attachment_id': self.attachment_id,
            'raw_snippet': self.raw_snippet,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Wishlist(db.Model):
    __tablename__ = 'wishlist'
    
    # Primary key
    wishlist_id = db.Column(db.String(100), primary_key=True)
    
    # User identification
    user_email = db.Column(db.String(200), nullable=False, index=True)
    
    # Item details
    item_name = db.Column(db.String(200), nullable=False)
    expected_price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100))
    notes = db.Column(db.Text, nullable=True)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'wishlist_id': self.wishlist_id,
            'user_email': self.user_email,
            'item_name': self.item_name,
            'expected_price': self.expected_price,
            'category': self.category,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
