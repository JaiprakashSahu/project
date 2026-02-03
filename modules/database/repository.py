"""
Transaction Repository - Isolates all database operations.
"""
from modules.database.db import db
from modules.database.models import Transaction


class TransactionRepository:
    """Repository class for Transaction CRUD operations"""
    
    def add(self, data: dict):
        """
        Add a transaction to the database.
        
        Args:
            data: Dictionary with transaction fields
            
        Returns:
            bool: True if added, False if already exists
        """
        if self.exists(data["txn_id"]):
            print(f"⚠️  Transaction already exists: {data['txn_id']}")
            return False

        txn = Transaction(**data)
        db.session.add(txn)
        db.session.commit()
        print(f"✅ Transaction inserted: {data['txn_id']} | {data.get('merchant_name', 'Unknown')} | ₹{data.get('amount', 0)}")
        return True

    def exists(self, txn_id):
        """
        Check if a transaction exists by txn_id.
        
        Args:
            txn_id: Transaction ID to check
            
        Returns:
            bool: True if exists, False otherwise
        """
        return db.session.query(Transaction).filter_by(txn_id=txn_id).first() is not None

    def get_all(self):
        """
        Get all transactions from the database.
        
        Returns:
            list: List of Transaction objects
        """
        return Transaction.query.all()
    
    def get_by_id(self, txn_id):
        """
        Get a transaction by its ID.
        
        Args:
            txn_id: Transaction ID
            
        Returns:
            Transaction or None
        """
        return Transaction.query.filter_by(txn_id=txn_id).first()

    def delete_all(self):
        """
        Delete all transactions from the database.
        WARNING: This is destructive!
        """
        count = db.session.query(Transaction).count()
        db.session.query(Transaction).delete()
        db.session.commit()
        print(f"🗑️  Deleted all transactions (count: {count})")
    
    def save_from_llm_dict(self, d: dict):
        """
        Save transaction from LLM extraction output.
        Cleans null/empty values before saving.
        
        Args:
            d: Dictionary from LLM extraction
            
        Returns:
            bool: True if saved, False if duplicate
        """
        # Clean null/empty values
        clean = {k: (v if v not in ["", "null", None] else None) for k, v in d.items()}
        return self.add(clean)
