from .models import db, Transaction, Receipt
from datetime import datetime


class TransactionRepository:
    """Repository for managing transactions in the database."""
    
    @staticmethod
    def add_transaction(transaction_dict):
        """Add a new transaction to the database."""
        try:
            # Check if transaction already exists
            if TransactionRepository.exists(transaction_dict.get('txn_id')):
                return False, "Transaction already exists"
            
            transaction = Transaction(
                txn_id=transaction_dict.get('txn_id'),
                description=transaction_dict.get('description'),
                clean_description=transaction_dict.get('clean_description'),
                merchant_name=transaction_dict.get('merchant_name'),
                payment_channel=transaction_dict.get('payment_channel'),
                amount=transaction_dict.get('amount'),
                type=transaction_dict.get('type'),
                date=transaction_dict.get('date'),
                weekday=transaction_dict.get('weekday'),
                time_of_day=transaction_dict.get('time_of_day'),
                balance_after_txn=transaction_dict.get('balance_after_txn'),
                category=transaction_dict.get('category'),
                subcategory=transaction_dict.get('subcategory'),
                is_recurring=transaction_dict.get('is_recurring', False),
                recurrence_interval=transaction_dict.get('recurrence_interval'),
                confidence_score=transaction_dict.get('confidence_score', 0.0),
                is_suspicious=transaction_dict.get('is_suspicious', False),
                embedding_version=transaction_dict.get('embedding_version', 1)
            )
            
            db.session.add(transaction)
            db.session.commit()
            return True, "Transaction added successfully"
        except Exception as e:
            db.session.rollback()
            return False, f"Error adding transaction: {str(e)}"
    
    @staticmethod
    def exists(txn_id):
        """Check if a transaction exists by txn_id."""
        return Transaction.query.filter_by(txn_id=txn_id).first() is not None
    
    @staticmethod
    def check_duplicate(date, amount, merchant):
        """Check for duplicate based on date, amount, and merchant."""
        return Transaction.query.filter_by(
            date=date,
            amount=amount,
            merchant_name=merchant
        ).first() is not None
    
    @staticmethod
    def get_all():
        """Get all transactions."""
        return Transaction.query.order_by(Transaction.created_at.desc()).all()
    
    @staticmethod
    def get_by_date_range(start_date, end_date):
        """Get transactions within a date range."""
        return Transaction.query.filter(
            Transaction.date >= start_date,
            Transaction.date <= end_date
        ).order_by(Transaction.date.desc()).all()
    
    @staticmethod
    def get_by_type(txn_type):
        """Get transactions by type (debit/credit)."""
        return Transaction.query.filter_by(type=txn_type).order_by(Transaction.created_at.desc()).all()
    
    @staticmethod
    def get_recent(limit=20):
        """Get the most recent transactions."""
        return Transaction.query.order_by(Transaction.created_at.desc()).limit(limit).all()


class ReceiptRepository:
    """Repository for managing receipts in the database."""
    
    @staticmethod
    def add_receipt(receipt_dict):
        """Add a new receipt to the database."""
        try:
            # Check if receipt already exists
            if ReceiptRepository.exists(receipt_dict.get('receipt_id')):
                return False, "Receipt already exists"
            
            receipt = Receipt(
                receipt_id=receipt_dict.get('receipt_id'),
                receipt_type=receipt_dict.get('receipt_type', 'digital'),
                issue_date=receipt_dict.get('issue_date'),
                issue_time=receipt_dict.get('issue_time'),
                merchant_name=receipt_dict.get('merchant_name'),
                merchant_address=receipt_dict.get('merchant_address'),
                merchant_gst=receipt_dict.get('merchant_gst'),
                subtotal_amount=receipt_dict.get('subtotal_amount', 0.0),
                tax_amount=receipt_dict.get('tax_amount', 0.0),
                total_amount=receipt_dict.get('total_amount', 0.0),
                payment_method=receipt_dict.get('payment_method'),
                extracted_confidence_score=receipt_dict.get('extracted_confidence_score', 0.0),
                is_suspicious=receipt_dict.get('is_suspicious', False),
                embedding_version=receipt_dict.get('embedding_version', 1),
                attachment_filename=receipt_dict.get('attachment_filename'),
                attachment_message_id=receipt_dict.get('attachment_message_id'),
                attachment_id=receipt_dict.get('attachment_id'),
                raw_snippet=receipt_dict.get('raw_snippet')
            )
            
            db.session.add(receipt)
            db.session.commit()
            return True, "Receipt added successfully"
        except Exception as e:
            db.session.rollback()
            return False, f"Error adding receipt: {str(e)}"
    
    @staticmethod
    def exists(receipt_id):
        """Check if a receipt exists by receipt_id."""
        return Receipt.query.filter_by(receipt_id=receipt_id).first() is not None
    
    @staticmethod
    def check_duplicate_by_message(message_id):
        """Check for duplicate receipt by Gmail message ID."""
        return Receipt.query.filter_by(attachment_message_id=message_id).first() is not None
    
    @staticmethod
    def get_all():
        """Get all receipts."""
        return Receipt.query.order_by(Receipt.created_at.desc()).all()
    
    @staticmethod
    def get_recent(limit=40):
        """Get the most recent receipts."""
        return Receipt.query.order_by(Receipt.created_at.desc()).limit(limit).all()
