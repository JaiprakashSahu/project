"""
Transaction Analytics and Anomaly Detection Module
Generates insights, charts, and AI-powered pattern detection
"""
import os
import io
import base64
import time
import json
import requests
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
LLM_API_URL = os.getenv("LLM_API_URL", "http://172.16.122.48:1234/v1/chat/completions")
LLM_MODEL = "qwen2.5-coder-3b-instruct-mlx"

# Set style for charts
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)
plt.rcParams['font.size'] = 10


def load_transactions_from_db(app):
    """
    Load all transactions from SQLite database into pandas DataFrame.
    
    Args:
        app: Flask app instance (for app context)
        
    Returns:
        pd.DataFrame: Transaction data
    """
    print(">> Loading transactions from database...")
    
    from modules.database.db import db
    from modules.database.models import Transaction
    
    with app.app_context():
        transactions = Transaction.query.all()
        
        if not transactions:
            print(">> No transactions found in database")
            return pd.DataFrame()
        
        # Convert to DataFrame
        data = []
        for t in transactions:
            data.append({
                'txn_id': t.txn_id,
                'description': t.description,
                'clean_description': t.clean_description,
                'merchant_name': t.merchant_name,
                'payment_channel': t.payment_channel,
                'amount': t.amount or 0,
                'type': t.type,
                'date': t.date,
                'weekday': t.weekday,
                'time_of_day': t.time_of_day,
                'balance_after_txn': t.balance_after_txn,
                'category': t.category or 'Other',
                'subcategory': t.subcategory,
                'is_recurring': t.is_recurring,
                'recurrence_interval': t.recurrence_interval,
                'confidence_score': t.confidence_score,
                'is_suspicious': t.is_suspicious,
                'embedding_version': t.embedding_version,
                'raw_email_snippet': t.raw_email_snippet,
                'created_at': t.created_at
            })
        
        df = pd.DataFrame(data)
        
        # Convert date column to datetime
        if 'date' in df.columns and not df.empty:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        print(f">> Loaded {len(df)} transactions")
        return df


def fig_to_base64(fig):
    """
    Convert matplotlib figure to base64 string for embedding in HTML.
    
    Args:
        fig: matplotlib figure
        
    Returns:
        str: base64 encoded PNG
    """
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close(fig)
    return f"data:image/png;base64,{image_base64}"


def compute_category_pie(df):
    """
    Generate pie chart of spending by category.
    
    Args:
        df: Transaction DataFrame
        
    Returns:
        str: base64 encoded PNG
    """
    if df.empty:
        return None
    
    # Filter debit transactions only
    debits = df[df['type'] == 'debit'].copy()
    
    if debits.empty:
        return None
    
    # Group by category
    category_spending = debits.groupby('category')['amount'].sum().sort_values(ascending=False)
    
    # Create pie chart
    fig, ax = plt.subplots(figsize=(8, 8))
    colors = sns.color_palette("pastel", len(category_spending))
    
    ax.pie(
        category_spending.values,
        labels=category_spending.index,
        autopct='%1.1f%%',
        colors=colors,
        startangle=90
    )
    ax.set_title('Spending by Category', fontsize=16, fontweight='bold')
    
    return fig_to_base64(fig)


def compute_top4_categories(df):
    """
    Generate bar chart of top 4 spending categories.
    
    Args:
        df: Transaction DataFrame
        
    Returns:
        str: base64 encoded PNG
    """
    if df.empty:
        return None
    
    # Filter debit transactions
    debits = df[df['type'] == 'debit'].copy()
    
    if debits.empty:
        return None
    
    # Get top 4 categories
    top4 = debits.groupby('category')['amount'].sum().sort_values(ascending=False).head(4)
    
    # Create bar chart
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = sns.color_palette("viridis", len(top4))
    
    ax.bar(top4.index, top4.values, color=colors)
    ax.set_title('Top 4 Spending Categories', fontsize=16, fontweight='bold')
    ax.set_xlabel('Category', fontsize=12)
    ax.set_ylabel('Amount (₹)', fontsize=12)
    ax.tick_params(axis='x', rotation=45)
    
    # Add value labels on bars
    for i, (cat, val) in enumerate(top4.items()):
        ax.text(i, val, f'₹{val:.0f}', ha='center', va='bottom', fontsize=10)
    
    plt.tight_layout()
    return fig_to_base64(fig)


def compute_daily_spending(df):
    """
    Generate line chart of daily spending trends.
    
    Args:
        df: Transaction DataFrame
        
    Returns:
        str: base64 encoded PNG
    """
    if df.empty:
        return None
    
    # Filter debit transactions with valid dates
    debits = df[df['type'] == 'debit'].copy()
    debits = debits[debits['date'].notna()]
    
    if debits.empty:
        return None
    
    # Group by date
    daily = debits.groupby(debits['date'].dt.date)['amount'].sum().sort_index()
    
    if daily.empty:
        return None
    
    # Create line chart
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(daily.index, daily.values, marker='o', linewidth=2, markersize=6, color='#FF6B6B')
    ax.fill_between(daily.index, daily.values, alpha=0.3, color='#FF6B6B')
    
    ax.set_title('Daily Spending Trend', fontsize=16, fontweight='bold')
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Amount (₹)', fontsize=12)
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig_to_base64(fig)


def compute_monthly_spending(df):
    """
    Generate bar chart of monthly spending.
    
    Args:
        df: Transaction DataFrame
        
    Returns:
        str: base64 encoded PNG
    """
    if df.empty:
        return None
    
    # Filter debit transactions with valid dates
    debits = df[df['type'] == 'debit'].copy()
    debits = debits[debits['date'].notna()]
    
    if debits.empty:
        return None
    
    # Extract month-year
    debits['month'] = debits['date'].dt.to_period('M')
    monthly = debits.groupby('month')['amount'].sum().sort_index()
    
    if monthly.empty:
        return None
    
    # Create bar chart
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = sns.color_palette("coolwarm", len(monthly))
    
    ax.bar(range(len(monthly)), monthly.values, color=colors)
    ax.set_xticks(range(len(monthly)))
    ax.set_xticklabels([str(m) for m in monthly.index], rotation=45)
    
    ax.set_title('Monthly Spending Trend', fontsize=16, fontweight='bold')
    ax.set_xlabel('Month', fontsize=12)
    ax.set_ylabel('Amount (₹)', fontsize=12)
    
    # Add value labels
    for i, val in enumerate(monthly.values):
        ax.text(i, val, f'₹{val:.0f}', ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    return fig_to_base64(fig)


def compute_money_flow(df):
    """
    Calculate total debit and credit amounts.
    
    Args:
        df: Transaction DataFrame
        
    Returns:
        dict: {'debit_total', 'credit_total', 'net_flow'}
    """
    if df.empty:
        return {'debit_total': 0, 'credit_total': 0, 'net_flow': 0}
    
    debit_total = df[df['type'] == 'debit']['amount'].sum()
    credit_total = df[df['type'] == 'credit']['amount'].sum()
    net_flow = credit_total - debit_total
    
    return {
        'debit_total': round(debit_total, 2),
        'credit_total': round(credit_total, 2),
        'net_flow': round(net_flow, 2)
    }


def detect_suspicious_patterns(df):
    """
    Detect suspicious transactions and patterns.
    
    Args:
        df: Transaction DataFrame
        
    Returns:
        dict: Suspicious transactions and patterns
    """
    suspicious = []
    patterns = []
    
    if df.empty:
        return {'suspicious': suspicious, 'patterns': patterns}
    
    # 1. High-value transactions (top 5%)
    if len(df) > 0:
        threshold = df['amount'].quantile(0.95)
        high_value = df[df['amount'] > threshold]
        
        for _, txn in high_value.iterrows():
            suspicious.append({
                'txn_id': txn['txn_id'],
                'merchant': txn['merchant_name'],
                'amount': txn['amount'],
                'date': str(txn['date']),
                'reason': 'High-value transaction'
            })
    
    # 2. Flagged as suspicious
    flagged = df[df['is_suspicious'] == True]
    for _, txn in flagged.iterrows():
        suspicious.append({
            'txn_id': txn['txn_id'],
            'merchant': txn['merchant_name'],
            'amount': txn['amount'],
            'date': str(txn['date']),
            'reason': 'Flagged by system'
        })
    
    # 3. Detect patterns
    if not df.empty:
        # Recurring transactions
        recurring = df[df['is_recurring'] == True]
        if len(recurring) > 0:
            patterns.append(f"Found {len(recurring)} recurring transactions")
        
        # Most common merchant
        if 'merchant_name' in df.columns:
            top_merchant = df['merchant_name'].value_counts().head(1)
            if not top_merchant.empty:
                patterns.append(f"Most frequent: {top_merchant.index[0]} ({top_merchant.values[0]} transactions)")
        
        # Peak spending day
        if 'weekday' in df.columns:
            peak_day = df.groupby('weekday')['amount'].sum().idxmax()
            patterns.append(f"Peak spending day: {peak_day}")
    
    return {'suspicious': suspicious[:10], 'patterns': patterns}  # Limit to top 10


def call_llm_for_patterns(df):
    """
    Call LLM to analyze transaction patterns and generate insights.
    
    Args:
        df: Transaction DataFrame
        
    Returns:
        dict: AI-generated insights
    """
    print(">> Calling LLM for pattern analysis...")
    
    if df.empty:
        return {
            'summary': "No transactions available for analysis.",
            'patterns': [],
            'risky_behaviors': [],
            'suspicious': [],
            'savings_tips': []
        }
    
    try:
        # Prepare summary data
        money_flow = compute_money_flow(df)
        category_spending = df[df['type'] == 'debit'].groupby('category')['amount'].sum().sort_values(ascending=False).head(5)
        
        # Get monthly spending trend
        if 'date' in df.columns:
            df_copy = df[df['date'].notna()].copy()
            df_copy['month'] = pd.to_datetime(df_copy['date']).dt.to_period('M')
            monthly = df_copy.groupby('month')['amount'].sum().to_dict()
            monthly_str = ', '.join([f"{k}: ₹{v:.0f}" for k, v in list(monthly.items())[-3:]])
        else:
            monthly_str = "No date data available"
        
        # High-value transactions
        high_value = df[df['amount'] > df['amount'].quantile(0.90)]
        
        # Build prompt
        prompt = f"""
Analyze these financial transactions and provide insights in JSON format.

TRANSACTION SUMMARY:
- Total Debit: ₹{money_flow['debit_total']:.2f}
- Total Credit: ₹{money_flow['credit_total']:.2f}
- Net Flow: ₹{money_flow['net_flow']:.2f}
- Total Transactions: {len(df)}

TOP SPENDING CATEGORIES:
{category_spending.to_string()}

RECENT MONTHLY SPENDING:
{monthly_str}

HIGH-VALUE TRANSACTIONS:
{high_value[['merchant_name', 'amount', 'category']].head(5).to_string() if not high_value.empty else 'None'}

Return ONLY valid JSON with this structure (no markdown, no code blocks):
{{
  "summary": "2-3 sentence overview of spending habits",
  "patterns": ["pattern 1", "pattern 2", "pattern 3"],
  "risky_behaviors": ["risk 1", "risk 2"],
  "suspicious": ["suspicious item 1", "suspicious item 2"],
  "savings_tips": ["tip 1", "tip 2", "tip 3"]
}}
"""
        
        # Call LLM API
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": "You are a financial analyst. Provide insights in valid JSON format only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            
            # Clean response (remove markdown code blocks if present)
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            content = content.strip()
            
            # Parse JSON
            insights = json.loads(content)
            print(">> LLM OK")
            return insights
        else:
            print(f">> LLM FAILED: Status {response.status_code}")
            return _fallback_insights(df, money_flow)
            
    except requests.exceptions.Timeout:
        print(">> LLM FAILED: Timeout")
        return _fallback_insights(df, money_flow)
    except json.JSONDecodeError as e:
        print(f">> LLM FAILED: JSON parse error - {e}")
        return _fallback_insights(df, money_flow)
    except Exception as e:
        print(f">> LLM FAILED: {str(e)}")
        return _fallback_insights(df, money_flow)


def _fallback_insights(df, money_flow):
    """Generate basic insights when LLM fails"""
    category_spending = df[df['type'] == 'debit'].groupby('category')['amount'].sum().sort_values(ascending=False)
    
    return {
        'summary': f"Analyzed {len(df)} transactions. Total spending: ₹{money_flow['debit_total']:.2f}. Net flow: ₹{money_flow['net_flow']:.2f}.",
        'patterns': [
            f"Top category: {category_spending.index[0] if not category_spending.empty else 'N/A'}",
            f"Total categories: {len(category_spending)}",
            f"Average transaction: ₹{df['amount'].mean():.2f}"
        ],
        'risky_behaviors': ["Unable to detect without AI analysis"],
        'suspicious': ["Run LLM analysis for detailed detection"],
        'savings_tips': [
            "Track your daily expenses",
            "Set category-wise budgets",
            "Review recurring subscriptions"
        ]
    }


def generate_analytics_report(app):
    """
    Generate complete analytics report with charts and insights.
    
    Args:
        app: Flask app instance
        
    Returns:
        dict: Complete analytics data
    """
    start_time = time.time()
    print("\n" + "="*80)
    print(">> Analytics started")
    print("="*80)
    
    # Load data
    df = load_transactions_from_db(app)
    
    if df.empty:
        print(">> No transactions to analyze")
        print("="*80)
        return {
            'pie_chart': None,
            'top4_chart': None,
            'daily_chart': None,
            'monthly_chart': None,
            'debit_total': 0,
            'credit_total': 0,
            'net_flow': 0,
            'ai_summary': "No transactions available for analysis.",
            'patterns': [],
            'suspicious': [],
            'recommendations': []
        }
    
    # Generate charts
    print(">> Generating charts...")
    pie_chart = compute_category_pie(df)
    print("   ✅ Pie chart")
    
    top4_chart = compute_top4_categories(df)
    print("   ✅ Top 4 chart")
    
    daily_chart = compute_daily_spending(df)
    print("   ✅ Daily chart")
    
    monthly_chart = compute_monthly_spending(df)
    print("   ✅ Monthly chart")
    
    print(">> Generated charts OK")
    
    # Calculate money flow
    money_flow = compute_money_flow(df)
    
    # Detect suspicious patterns
    suspicious_data = detect_suspicious_patterns(df)
    
    # Call LLM for insights
    ai_insights = call_llm_for_patterns(df)
    
    # Calculate elapsed time
    elapsed = time.time() - start_time
    print(f">> Completed in {elapsed:.2f} seconds")
    print("="*80 + "\n")
    
    return {
        'pie_chart': pie_chart,
        'top4_chart': top4_chart,
        'daily_chart': daily_chart,
        'monthly_chart': monthly_chart,
        'debit_total': money_flow['debit_total'],
        'credit_total': money_flow['credit_total'],
        'net_flow': money_flow['net_flow'],
        'ai_summary': ai_insights.get('summary', 'No summary available'),
        'patterns': ai_insights.get('patterns', []) + suspicious_data['patterns'],
        'suspicious': suspicious_data['suspicious'],
        'recommendations': ai_insights.get('savings_tips', [])
    }
