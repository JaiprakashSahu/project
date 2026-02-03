"""
Transaction Database Module
SQLite database for storing enriched transaction records from Gmail/Receipts.
Uses SQLAlchemy with exact schema as specified.
"""

import json
import requests
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# Initialize separate SQLAlchemy instance for transaction database
txn_db = SQLAlchemy()

# LLM Configuration
LM_API_URL = "http://172.16.122.48:1234/v1/chat/completions"
MODEL = "qwen2.5-coder-3b-instruct-mlx"


class Transaction(txn_db.Model):
    """
    Transaction model with EXACT schema as specified.
    Stores enriched transaction records from Gmail/Receipt processing.
    """
    __tablename__ = 'transactions'
    
    # Primary key
    txn_id = txn_db.Column(txn_db.Text, primary_key=True)
    
    # Description fields
    description = txn_db.Column(txn_db.Text)
    clean_description = txn_db.Column(txn_db.Text)
    
    # Merchant information
    merchant_name = txn_db.Column(txn_db.Text)
    payment_channel = txn_db.Column(txn_db.Text)
    
    # Transaction details
    amount = txn_db.Column(txn_db.Float)
    type = txn_db.Column(txn_db.Text)  # credit/debit
    date = txn_db.Column(txn_db.Text)
    weekday = txn_db.Column(txn_db.Text)
    time_of_day = txn_db.Column(txn_db.Text)
    balance_after_txn = txn_db.Column(txn_db.Float)
    
    # Categorization
    category = txn_db.Column(txn_db.Text)
    subcategory = txn_db.Column(txn_db.Text)
    
    # Recurrence tracking
    is_recurring = txn_db.Column(txn_db.Boolean, default=False)
    recurrence_interval = txn_db.Column(txn_db.Text)
    
    # Metadata
    confidence_score = txn_db.Column(txn_db.Float)
    is_suspicious = txn_db.Column(txn_db.Boolean, default=False)
    embedding_version = txn_db.Column(txn_db.Integer)
    
    # Raw data
    raw_email_snippet = txn_db.Column(txn_db.Text)
    
    # Timestamps
    created_at = txn_db.Column(txn_db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert model to dictionary"""
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


class TransactionDB:
    """
    Repository class for Transaction database operations.
    Handles CRUD operations with exception handling.
    """
    
    @staticmethod
    def add_transaction(txn_dict):
        """
        Add a new transaction to the database.
        
        Args:
            txn_dict: Dictionary with transaction fields
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Check if transaction already exists
            if TransactionDB.transaction_exists(txn_dict.get('txn_id')):
                print(f"⚠️  Transaction already exists: {txn_dict.get('txn_id')}")
                return False, "Transaction already exists"
            
            # Create transaction object
            transaction = Transaction(
                txn_id=txn_dict.get('txn_id'),
                description=txn_dict.get('description'),
                clean_description=txn_dict.get('clean_description'),
                merchant_name=txn_dict.get('merchant_name'),
                payment_channel=txn_dict.get('payment_channel'),
                amount=txn_dict.get('amount'),
                type=txn_dict.get('type'),
                date=txn_dict.get('date'),
                weekday=txn_dict.get('weekday'),
                time_of_day=txn_dict.get('time_of_day'),
                balance_after_txn=txn_dict.get('balance_after_txn'),
                category=txn_dict.get('category'),
                subcategory=txn_dict.get('subcategory'),
                is_recurring=txn_dict.get('is_recurring', False),
                recurrence_interval=txn_dict.get('recurrence_interval'),
                confidence_score=txn_dict.get('confidence_score', 0.0),
                is_suspicious=txn_dict.get('is_suspicious', False),
                embedding_version=txn_dict.get('embedding_version', 1),
                raw_email_snippet=txn_dict.get('raw_email_snippet', '')
            )
            
            txn_db.session.add(transaction)
            txn_db.session.commit()
            
            print(f"✅ Transaction inserted: {txn_dict.get('txn_id')} | {txn_dict.get('merchant_name')} | ₹{txn_dict.get('amount')}")
            return True, "Transaction added successfully"
            
        except Exception as e:
            txn_db.session.rollback()
            error_msg = f"Error adding transaction: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg
    
    @staticmethod
    def transaction_exists(txn_id):
        """
        Check if a transaction exists by txn_id.
        
        Args:
            txn_id: Transaction ID to check
            
        Returns:
            bool: True if exists, False otherwise
        """
        try:
            return Transaction.query.filter_by(txn_id=txn_id).first() is not None
        except Exception as e:
            print(f"❌ Error checking transaction existence: {str(e)}")
            return False
    
    @staticmethod
    def get_all():
        """
        Get all transactions from the database.
        
        Returns:
            list: List of Transaction objects
        """
        try:
            return Transaction.query.order_by(Transaction.created_at.desc()).all()
        except Exception as e:
            print(f"❌ Error fetching all transactions: {str(e)}")
            return []
    
    @staticmethod
    def get_by_id(txn_id):
        """
        Get a transaction by its ID.
        
        Args:
            txn_id: Transaction ID
            
        Returns:
            Transaction or None
        """
        try:
            return Transaction.query.filter_by(txn_id=txn_id).first()
        except Exception as e:
            print(f"❌ Error fetching transaction by ID: {str(e)}")
            return None
    
    @staticmethod
    def delete_all():
        """
        Delete all transactions from the database.
        WARNING: This is destructive!
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            count = Transaction.query.count()
            Transaction.query.delete()
            txn_db.session.commit()
            print(f"🗑️  Deleted all transactions (count: {count})")
            return True, f"Deleted {count} transactions"
        except Exception as e:
            txn_db.session.rollback()
            error_msg = f"Error deleting transactions: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg


# ==================== LLM INTEGRATION ====================

def call_llm_for_info(text):
    """
    Send transaction text to LLM for extraction.
    
    Args:
        text: Raw text from email/receipt
        
    Returns:
        str: LLM response text or None on error
    """
    headers = {"Content-Type": "application/json"}

    prompt = f"""Extract the transaction details from the text below.

Return ONLY this exact format. EACH FIELD MUST BE ON ITS OWN LINE.
NO quotes, NO commas, NO JSON, NO extra text, NO code blocks.

txn_id:
description:
clean_description:
merchant_name:
merchant_type:
payment_channel:
amount:
type:
date:
weekday:
time_of_day:
balance_after_txn:
category:
subcategory:
transaction_mode:
is_recurring:
recurrence_interval:
confidence_score:
is_high_value:
is_suspicious:
embedding_version:

Text:
{text}
"""

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 500
    }

    try:
        print(f"🔄 Calling LLM API: {LM_API_URL}")
        response = requests.post(LM_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        info_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        print(f"✅ LLM response received ({len(info_text)} chars)")
        return info_text
        
    except requests.exceptions.Timeout:
        print(f"❌ LLM API timeout after 30 seconds")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ LLM API error: {str(e)}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error calling LLM: {str(e)}")
        return None


def parse_llm_response(info_text):
    """
    Parse LLM response text into a dictionary.
    
    Args:
        info_text: Raw LLM response
        
    Returns:
        dict: Parsed transaction data
    """
    if not info_text:
        return None
    
    result = {}
    lines = info_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if ':' not in line:
            continue
            
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'").strip()
        result[key] = value
    
    return sanitize_transaction_dict(result)


def sanitize_transaction_dict(raw_dict):
    """
    Convert string values to appropriate types and add defaults.
    
    Args:
        raw_dict: Dictionary with string values from LLM
        
    Returns:
        dict: Sanitized dictionary with proper types
    """
    sanitized = {}
    
    # String fields
    sanitized['txn_id'] = raw_dict.get('txn_id', f"TXN_{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
    sanitized['description'] = raw_dict.get('description', '')
    sanitized['clean_description'] = raw_dict.get('clean_description', '')
    sanitized['merchant_name'] = raw_dict.get('merchant_name', 'Unknown')
    sanitized['payment_channel'] = raw_dict.get('payment_channel', 'Unknown')
    sanitized['weekday'] = raw_dict.get('weekday', '')
    sanitized['time_of_day'] = raw_dict.get('time_of_day', '')
    sanitized['category'] = raw_dict.get('category', 'Other')
    sanitized['subcategory'] = raw_dict.get('subcategory', '')
    sanitized['recurrence_interval'] = raw_dict.get('recurrence_interval') or None
    
    # Type field (credit/debit)
    type_value = raw_dict.get('type', '').lower()
    if 'credit' in type_value:
        sanitized['type'] = 'credit'
    elif 'debit' in type_value:
        sanitized['type'] = 'debit'
    else:
        sanitized['type'] = 'unknown'
    
    # Date field
    date_str = raw_dict.get('date', '')
    if date_str and date_str.lower() not in ['', 'unknown', 'none', 'null']:
        sanitized['date'] = date_str
    else:
        sanitized['date'] = datetime.now().strftime('%Y-%m-%d')
    
    # Float fields
    try:
        sanitized['amount'] = float(raw_dict.get('amount', 0))
    except (ValueError, TypeError):
        sanitized['amount'] = 0.0
    
    try:
        balance_str = raw_dict.get('balance_after_txn', '')
        if balance_str and balance_str.lower() not in ['', 'unknown', 'none', 'null']:
            sanitized['balance_after_txn'] = float(balance_str)
        else:
            sanitized['balance_after_txn'] = None
    except (ValueError, TypeError):
        sanitized['balance_after_txn'] = None
    
    try:
        sanitized['confidence_score'] = float(raw_dict.get('confidence_score', 0.5))
    except (ValueError, TypeError):
        sanitized['confidence_score'] = 0.5
    
    # Boolean fields
    is_recurring_str = raw_dict.get('is_recurring', 'false').lower()
    sanitized['is_recurring'] = is_recurring_str in ['true', 'yes', '1']
    
    is_suspicious_str = raw_dict.get('is_suspicious', 'false').lower()
    sanitized['is_suspicious'] = is_suspicious_str in ['true', 'yes', '1']
    
    # Integer field
    try:
        sanitized['embedding_version'] = int(raw_dict.get('embedding_version', 1))
    except (ValueError, TypeError):
        sanitized['embedding_version'] = 1
    
    return sanitized


def save_llm_transaction(text_source, raw_snippet=None):
    """
    Complete pipeline: Extract transaction from text using LLM and save to DB.
    
    This is the main helper function that:
    1. Calls LLM API with transaction text
    2. Parses the response
    3. Converts to proper types
    4. Saves to database
    
    Args:
        text_source: Raw text from Gmail snippet or receipt
        raw_snippet: Optional raw email snippet to store
        
    Returns:
        tuple: (success: bool, message: str, txn_id: str or None)
    """
    try:
        print(f"\n{'='*80}")
        print(f"🔍 Processing transaction from text source...")
        print(f"{'='*80}")
        
        # Step 1: Call LLM
        llm_response = call_llm_for_info(text_source)
        
        if not llm_response:
            # Fallback: Create basic transaction
            print("⚠️  LLM extraction failed, creating fallback transaction")
            txn_dict = {
                'txn_id': f"TXN_FALLBACK_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                'description': text_source[:500],
                'clean_description': text_source[:200],
                'merchant_name': 'Unknown',
                'payment_channel': 'Unknown',
                'amount': 0.0,
                'type': 'unknown',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'weekday': datetime.now().strftime('%A'),
                'time_of_day': datetime.now().strftime('%H:%M'),
                'balance_after_txn': None,
                'category': 'Uncategorized',
                'subcategory': '',
                'is_recurring': False,
                'recurrence_interval': None,
                'confidence_score': 0.0,
                'is_suspicious': False,
                'embedding_version': 1,
                'raw_email_snippet': raw_snippet or text_source[:500]
            }
        else:
            # Step 2: Parse LLM response
            txn_dict = parse_llm_response(llm_response)
            
            if not txn_dict:
                return False, "Failed to parse LLM response", None
            
            # Add raw snippet
            txn_dict['raw_email_snippet'] = raw_snippet or text_source[:500]
        
        # Step 3: Save to database
        success, message = TransactionDB.add_transaction(txn_dict)
        
        txn_id = txn_dict.get('txn_id')
        
        if success:
            print(f"✅ Transaction saved successfully: {txn_id}")
        else:
            print(f"❌ Failed to save transaction: {message}")
        
        print(f"{'='*80}\n")
        
        return success, message, txn_id
        
    except Exception as e:
        error_msg = f"Error in save_llm_transaction: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg, None


# ==================== GMAIL INTEGRATION HOOK ====================

def process_gmail_snippet(snippet, message_id=None):
    """
    Gmail ingestion hook for processing email snippets.
    
    This function can be called from Gmail extraction flow to
    automatically process and store transactions.
    
    Args:
        snippet: Gmail email snippet text
        message_id: Optional Gmail message ID for reference
        
    Returns:
        tuple: (success: bool, message: str, txn_id: str or None)
    """
    print(f"\n📧 Processing Gmail snippet (message_id: {message_id})")
    
    # Add message ID to the raw snippet for reference
    raw_snippet = f"[Gmail Message ID: {message_id}]\n{snippet}" if message_id else snippet
    
    return save_llm_transaction(snippet, raw_snippet=raw_snippet)


def process_attachment_text(attachment_text, filename=None):
    """
    Process text extracted from receipt/invoice attachments.
    
    Args:
        attachment_text: Text extracted from PDF/image attachment
        filename: Optional filename for reference
        
    Returns:
        tuple: (success: bool, message: str, txn_id: str or None)
    """
    print(f"\n📎 Processing attachment text (filename: {filename})")
    
    raw_snippet = f"[Attachment: {filename}]\n{attachment_text}" if filename else attachment_text
    
    return save_llm_transaction(attachment_text, raw_snippet=raw_snippet)
