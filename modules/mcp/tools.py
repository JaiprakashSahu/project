"""
MCP Tools for Project LUMEN
===========================
READ-ONLY tools that wrap existing analytics/database functions.
The LLM can only call these tools - it cannot access DB or tokens directly.

Each tool:
- Has a clear purpose
- Returns clean JSON
- Internally calls existing functions
- Is completely read-only
"""

from datetime import datetime, timedelta
from modules.database.db import db
from modules.database.models import Transaction


# =============================================================================
# TOOL 1: get_monthly_spending_summary
# =============================================================================
def get_monthly_spending_summary(month: str = None, year: int = None) -> dict:
    """
    Get spending summary for a specific month.
    
    Args:
        month: Month name (e.g., "January") or number (1-12). Defaults to current month.
        year: Year (e.g., 2025). Defaults to current year.
    
    Returns:
        {
            "month": "January 2025",
            "total_spent": 15000.00,
            "total_income": 50000.00,
            "net_flow": 35000.00,
            "transaction_count": 45,
            "avg_transaction": 333.33
        }
    """
    # Default to current month/year
    now = datetime.now()
    
    if year is None:
        year = now.year
    
    if month is None:
        target_month = now.month
    elif isinstance(month, str):
        # Convert month name to number
        month_names = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        target_month = month_names.get(month.lower(), now.month)
    else:
        target_month = int(month)
    
    # Build date prefix for filtering (e.g., "2025-01")
    date_prefix = f"{year}-{target_month:02d}"
    
    # Query transactions for this month
    transactions = Transaction.query.filter(
        Transaction.date.like(f"{date_prefix}%")
    ).all()
    
    # Calculate totals
    total_spent = sum(t.amount or 0 for t in transactions if t.type == 'debit')
    total_income = sum(t.amount or 0 for t in transactions if t.type == 'credit')
    net_flow = total_income - total_spent
    tx_count = len(transactions)
    avg_tx = total_spent / tx_count if tx_count > 0 else 0
    
    # Format month name
    month_name = datetime(year, target_month, 1).strftime("%B %Y")
    
    return {
        "month": month_name,
        "total_spent": round(total_spent, 2),
        "total_income": round(total_income, 2),
        "net_flow": round(net_flow, 2),
        "transaction_count": tx_count,
        "avg_transaction": round(avg_tx, 2)
    }


# =============================================================================
# TOOL 2: get_top_spending_categories
# =============================================================================
def get_top_spending_categories(limit: int = 5, days: int = 30) -> dict:
    """
    Get top spending categories for a time period.
    
    Args:
        limit: Number of categories to return (default: 5)
        days: Number of days to look back (default: 30)
    
    Returns:
        {
            "period": "Last 30 days",
            "total_analyzed": 15000.00,
            "categories": [
                {"category": "Dining", "amount": 5000.00, "percentage": 33.3, "count": 12},
                {"category": "Shopping", "amount": 3000.00, "percentage": 20.0, "count": 8},
                ...
            ]
        }
    """
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    start_str = start_date.strftime("%Y-%m-%d")
    
    # Query debit transactions in date range
    transactions = Transaction.query.filter(
        Transaction.type == 'debit',
        Transaction.date >= start_str
    ).all()
    
    # Group by category
    category_totals = {}
    category_counts = {}
    
    for t in transactions:
        cat = t.category or 'Other'
        category_totals[cat] = category_totals.get(cat, 0) + (t.amount or 0)
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    # Calculate total for percentages
    total = sum(category_totals.values())
    
    # Sort and limit
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    # Build result
    categories = []
    for cat, amount in sorted_categories:
        categories.append({
            "category": cat,
            "amount": round(amount, 2),
            "percentage": round((amount / total * 100) if total > 0 else 0, 1),
            "count": category_counts[cat]
        })
    
    return {
        "period": f"Last {days} days",
        "total_analyzed": round(total, 2),
        "categories": categories
    }


# =============================================================================
# TOOL 3: detect_anomalies
# =============================================================================
def detect_anomalies(threshold_percentile: float = 95) -> dict:
    """
    Detect suspicious or unusual transactions.
    
    Args:
        threshold_percentile: Transactions above this percentile are flagged (default: 95)
    
    Returns:
        {
            "anomaly_count": 3,
            "threshold_amount": 5000.00,
            "anomalies": [
                {
                    "txn_id": "TXN_123",
                    "merchant": "Unknown Merchant",
                    "amount": 10000.00,
                    "date": "2025-01-15",
                    "category": "Other",
                    "reason": "High-value transaction (above 95th percentile)"
                },
                ...
            ],
            "patterns": [
                "3 transactions flagged as suspicious by system",
                "Most frequent merchant: Swiggy (12 transactions)"
            ]
        }
    """
    transactions = Transaction.query.all()
    
    if not transactions:
        return {
            "anomaly_count": 0,
            "threshold_amount": 0,
            "anomalies": [],
            "patterns": ["No transactions to analyze"]
        }
    
    # Calculate threshold amount (e.g., 95th percentile)
    amounts = sorted([t.amount or 0 for t in transactions])
    threshold_idx = int(len(amounts) * threshold_percentile / 100)
    threshold_amount = amounts[min(threshold_idx, len(amounts) - 1)]
    
    anomalies = []
    patterns = []
    
    # Find high-value transactions
    for t in transactions:
        if (t.amount or 0) > threshold_amount:
            anomalies.append({
                "txn_id": t.txn_id,
                "merchant": t.merchant_name or "Unknown",
                "amount": round(t.amount, 2),
                "date": t.date,
                "category": t.category or "Other",
                "reason": f"High-value transaction (above {int(threshold_percentile)}th percentile)"
            })
    
    # Find system-flagged suspicious transactions
    suspicious = [t for t in transactions if t.is_suspicious]
    if suspicious:
        patterns.append(f"{len(suspicious)} transaction(s) flagged as suspicious by system")
        for t in suspicious:
            if not any(a['txn_id'] == t.txn_id for a in anomalies):
                anomalies.append({
                    "txn_id": t.txn_id,
                    "merchant": t.merchant_name or "Unknown",
                    "amount": round(t.amount or 0, 2),
                    "date": t.date,
                    "category": t.category or "Other",
                    "reason": "Flagged as suspicious by system"
                })
    
    # Find recurring patterns
    recurring = [t for t in transactions if t.is_recurring]
    if recurring:
        patterns.append(f"{len(recurring)} recurring transaction(s) detected")
    
    # Find most frequent merchant
    merchant_counts = {}
    for t in transactions:
        m = t.merchant_name or "Unknown"
        merchant_counts[m] = merchant_counts.get(m, 0) + 1
    
    if merchant_counts:
        top_merchant = max(merchant_counts.items(), key=lambda x: x[1])
        patterns.append(f"Most frequent: {top_merchant[0]} ({top_merchant[1]} transactions)")
    
    # Limit anomalies to top 10
    anomalies = sorted(anomalies, key=lambda x: x['amount'], reverse=True)[:10]
    
    return {
        "anomaly_count": len(anomalies),
        "threshold_amount": round(threshold_amount, 2),
        "anomalies": anomalies,
        "patterns": patterns
    }


# =============================================================================
# TOOL 4: get_recent_transactions
# =============================================================================
def get_recent_transactions(limit: int = 10, category: str = None) -> dict:
    """
    Get most recent transactions, optionally filtered by category.
    
    Args:
        limit: Number of transactions to return (default: 10, max: 50)
        category: Optional category filter (e.g., "Dining", "Shopping")
    
    Returns:
        {
            "count": 10,
            "filter": "All categories",
            "transactions": [
                {
                    "txn_id": "TXN_123",
                    "merchant": "Swiggy",
                    "amount": 500.00,
                    "type": "debit",
                    "date": "2025-01-15",
                    "category": "Dining"
                },
                ...
            ]
        }
    """
    # Enforce max limit for safety
    limit = min(limit, 50)
    
    # Build query
    query = Transaction.query
    
    if category:
        query = query.filter(Transaction.category.ilike(f"%{category}%"))
        filter_text = f"Category: {category}"
    else:
        filter_text = "All categories"
    
    # Order by date descending and limit
    transactions = query.order_by(Transaction.date.desc()).limit(limit).all()
    
    # Build result
    tx_list = []
    for t in transactions:
        tx_list.append({
            "txn_id": t.txn_id,
            "merchant": t.merchant_name or "Unknown",
            "amount": round(t.amount or 0, 2),
            "type": t.type,
            "date": t.date,
            "category": t.category or "Other"
        })
    
    return {
        "count": len(tx_list),
        "filter": filter_text,
        "transactions": tx_list
    }


# =============================================================================
# TOOL REGISTRY
# =============================================================================
# This is the ONLY way the LLM can interact with our data.
# Each tool has a schema that describes what it does and what parameters it accepts.

MCP_TOOLS = {
    "get_monthly_spending_summary": {
        "function": get_monthly_spending_summary,
        "description": "Get spending summary for a specific month including total spent, income, and net flow.",
        "parameters": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month name (e.g., 'January') or number (1-12). Defaults to current month."
                },
                "year": {
                    "type": "integer",
                    "description": "Year (e.g., 2025). Defaults to current year."
                }
            },
            "required": []
        }
    },
    "get_top_spending_categories": {
        "function": get_top_spending_categories,
        "description": "Get top spending categories with amounts and percentages for a time period.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of categories to return (default: 5)"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default: 30)"
                }
            },
            "required": []
        }
    },
    "detect_anomalies": {
        "function": detect_anomalies,
        "description": "Detect suspicious or unusual transactions based on amount thresholds and system flags.",
        "parameters": {
            "type": "object",
            "properties": {
                "threshold_percentile": {
                    "type": "number",
                    "description": "Transactions above this percentile are flagged (default: 95)"
                }
            },
            "required": []
        }
    },
    "get_recent_transactions": {
        "function": get_recent_transactions,
        "description": "Get most recent transactions, optionally filtered by category.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of transactions to return (default: 10, max: 50)"
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter (e.g., 'Dining', 'Shopping')"
                }
            },
            "required": []
        }
    }
}
