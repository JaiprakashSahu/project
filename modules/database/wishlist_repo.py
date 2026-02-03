"""
Wishlist Repository
Handles all database operations for wishlist items
"""

from modules.database.db import db
from modules.database.models import Wishlist
from datetime import datetime


class WishlistRepository:
    """Repository for wishlist CRUD operations"""
    
    @staticmethod
    def add_item(user_email, item_name, expected_price, category, notes=None):
        """Add a new item to wishlist"""
        try:
            wishlist_id = f"WISH_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            
            item = Wishlist(
                wishlist_id=wishlist_id,
                user_email=user_email,
                item_name=item_name,
                expected_price=expected_price,
                category=category,
                notes=notes
            )
            
            db.session.add(item)
            db.session.commit()
            
            print(f"✅ Wishlist item added: {wishlist_id} - {item_name}")
            return True, wishlist_id
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding wishlist item: {str(e)}")
            return False, None
    
    @staticmethod
    def get_by_user(user_email, limit=100):
        """Get all wishlist items for a user, sorted by newest first"""
        try:
            items = Wishlist.query.filter_by(user_email=user_email)\
                                  .order_by(Wishlist.created_at.desc())\
                                  .limit(limit)\
                                  .all()
            return items
        except Exception as e:
            print(f"❌ Error fetching wishlist: {str(e)}")
            return []
    
    @staticmethod
    def get_by_id(wishlist_id):
        """Get a specific wishlist item by ID"""
        try:
            return Wishlist.query.filter_by(wishlist_id=wishlist_id).first()
        except Exception as e:
            print(f"❌ Error fetching wishlist item: {str(e)}")
            return None
    
    @staticmethod
    def delete_item(wishlist_id):
        """Delete a wishlist item"""
        try:
            item = Wishlist.query.filter_by(wishlist_id=wishlist_id).first()
            
            if not item:
                return False, "Item not found"
            
            db.session.delete(item)
            db.session.commit()
            
            print(f"✅ Wishlist item deleted: {wishlist_id}")
            return True, "Item deleted successfully"
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error deleting wishlist item: {str(e)}")
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def count_by_user(user_email):
        """Count wishlist items for a user"""
        try:
            return Wishlist.query.filter_by(user_email=user_email).count()
        except Exception as e:
            print(f"❌ Error counting wishlist items: {str(e)}")
            return 0
    
    @staticmethod
    def get_all():
        """Get all wishlist items (for debugging)"""
        try:
            return Wishlist.query.all()
        except Exception as e:
            print(f"❌ Error fetching all wishlist items: {str(e)}")
            return []
