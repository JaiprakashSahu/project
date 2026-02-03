"""
Analytics module for transaction analysis and anomaly detection.
"""
from .analyzer import (
    load_transactions_from_db,
    compute_category_pie,
    compute_top4_categories,
    compute_daily_spending,
    compute_monthly_spending,
    compute_money_flow,
    detect_suspicious_patterns,
    call_llm_for_patterns,
    generate_analytics_report
)

__all__ = [
    'load_transactions_from_db',
    'compute_category_pie',
    'compute_top4_categories',
    'compute_daily_spending',
    'compute_monthly_spending',
    'compute_money_flow',
    'detect_suspicious_patterns',
    'call_llm_for_patterns',
    'generate_analytics_report'
]
