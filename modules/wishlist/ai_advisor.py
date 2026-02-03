"""
Wishlist AI Advisor
Provides intelligent purchase recommendations based on spending analytics
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def get_purchase_advice(item_name, expected_price, category, user_analytics):
    """
    Get AI-powered purchase advice for a wishlist item
    
    Args:
        item_name: Name of the item
        expected_price: Expected price
        category: Item category
        user_analytics: User's spending analytics data
        
    Returns:
        dict: AI advice with should_buy_now, reasons, risk, confidence, summary
    """
    try:
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = os.getenv("OPENAI_MODEL", "gpt-4")
        
        if not api_key:
            return {
                "should_buy_now": False,
                "reasons": ["AI service not configured. Please set OPENAI_API_KEY or GROQ_API_KEY."],
                "risk": "unknown",
                "confidence": 0.0,
                "summary": "Unable to provide advice without AI service."
            }
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        # Build comprehensive prompt
        prompt = f"""You are a financial advisor. Based on user's last 90 days transactions and category spending trends, evaluate whether they should buy the wishlist item:

Item: {item_name}
Expected Price: ₹{expected_price}
Category: {category}

User Spending Summary:
{user_analytics}

Analyze:
1. Is this a good time to purchase based on their spending patterns?
2. Is the price reasonable compared to similar transactions?
3. What are the financial risks?
4. What's your confidence in this recommendation?

Provide:
- should_buy_now (true/false)
- reasons (array of detailed reasons)
- risk (high/medium/low)
- confidence (0.0-1.0)
- summary (one sentence recommendation)

Return ONLY valid JSON with these exact fields. No markdown, no explanation."""

        # Call AI
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a financial advisor providing purchase recommendations in JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        # Parse response
        content = response.choices[0].message.content.strip()
        
        # Clean JSON if wrapped in markdown
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()
        
        # Parse JSON
        import json
        advice = json.loads(content)
        
        # Validate required fields
        required_fields = ["should_buy_now", "reasons", "risk", "confidence", "summary"]
        for field in required_fields:
            if field not in advice:
                raise ValueError(f"Missing required field: {field}")
        
        # Ensure types are correct
        advice["should_buy_now"] = bool(advice["should_buy_now"])
        advice["confidence"] = float(advice["confidence"])
        
        if not isinstance(advice["reasons"], list):
            advice["reasons"] = [str(advice["reasons"])]
        
        print(f"✅ AI advice generated for {item_name}")
        return advice
        
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse AI response as JSON: {e}")
        print(f"Raw response: {content[:200]}...")
        return {
            "should_buy_now": False,
            "reasons": ["Unable to analyze. AI returned invalid format."],
            "risk": "unknown",
            "confidence": 0.0,
            "summary": "Analysis failed. Please try again."
        }
        
    except Exception as e:
        print(f"❌ Error getting purchase advice: {str(e)}")
        return {
            "should_buy_now": False,
            "reasons": [f"Error: {str(e)}"],
            "risk": "unknown",
            "confidence": 0.0,
            "summary": "Unable to provide advice due to an error."
        }


def build_analytics_summary(transactions, category):
    """
    Build a summary of user's spending analytics
    
    Args:
        transactions: List of transaction objects
        category: Category to focus on
        
    Returns:
        str: Formatted analytics summary
    """
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    # Filter last 90 days
    ninety_days_ago = datetime.now() - timedelta(days=90)
    recent_txns = []
    
    for txn in transactions:
        try:
            txn_date = datetime.strptime(txn.date, '%Y-%m-%d')
            if txn_date >= ninety_days_ago:
                recent_txns.append(txn)
        except:
            continue
    
    # Calculate statistics
    total_spending = sum(t.amount for t in recent_txns if t.type == 'debit')
    category_spending = sum(t.amount for t in recent_txns if t.category == category and t.type == 'debit')
    category_count = len([t for t in recent_txns if t.category == category and t.type == 'debit'])
    
    # Average per category
    avg_category_transaction = category_spending / category_count if category_count > 0 else 0
    
    # Monthly breakdown
    monthly_spending = defaultdict(float)
    for txn in recent_txns:
        if txn.type == 'debit':
            try:
                month = txn.date[:7]  # YYYY-MM
                monthly_spending[month] += txn.amount
            except:
                continue
    
    # Build summary
    summary = f"""
Last 90 Days Spending Analytics:
- Total Spending: ₹{total_spending:,.2f}
- Category '{category}' Spending: ₹{category_spending:,.2f} ({category_count} transactions)
- Average per '{category}' transaction: ₹{avg_category_transaction:,.2f}
- Monthly spending trend: {dict(sorted(monthly_spending.items()))}
- Transaction count: {len(recent_txns)} total, {category_count} in {category}
"""
    
    return summary
