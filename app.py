import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import base64
from flask import Flask, redirect, url_for, session, render_template, request, send_file, flash, jsonify
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
from io import BytesIO
import re
import json

# Import ONE database instance
from modules.database.db import db
from modules.database.models import Transaction, Receipt, Wishlist
from modules.database.repository import TransactionRepository
from modules.database.transaction_repo import ReceiptRepository
from modules.database.wishlist_repo import WishlistRepository
from modules.gmail_sync import sync_all_gmail_data

# Import analytics module
from modules.analytics.analyzer import generate_analytics_report
from modules.analytics.cache import analytics_cache

# Import NVIDIA OCR module
from modules.nvidia_ocr import process_uploaded_file, parse_json_safely

# Import LLM extraction functions
from modules.llm_extraction.extractor import extract_transaction_from_text, extract_receipt_from_text

# Import MCP server for secure LLM-backend communication
from modules.mcp.server import mcp_server

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Configure SQLite database with ABSOLUTE PATH
# This prevents Flask from creating it in the instance/ folder
project_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(project_dir, 'lumen_transactions.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize ONE database instance
db.init_app(app)

# Auto-initialize database on startup
print("\n" + "="*80)
print("🚀 INITIALIZING DATABASE")
print("="*80)
print(f">>>> USING DB: {app.config['SQLALCHEMY_DATABASE_URI']}")
print(f">>>> ABSOLUTE PATH: {db_path}")
print("="*80)

with app.app_context():
    # Create tables if they don't exist (PRESERVES existing data)
    db.create_all()
    print("✅ Database initialized: lumen_transactions.db")
    print("📊 Table: transactions")
    print("📊 Table: receipts")
    print("📊 Table: wishlist")
    
    # Verify database file exists
    if os.path.exists(db_path):
        size_kb = os.path.getsize(db_path) / 1024
        print(f"✅ Database file verified: {size_kb:.2f} KB")
    else:
        print("❌ WARNING: Database file not found at expected location!")

print("="*80 + "\n")

# Register custom Jinja2 filter for JSON parsing
@app.template_filter('from_json')
def from_json_filter(s):
    return json.loads(s)


# ---------------------- ERROR HANDLERS ----------------------
@app.errorhandler(400)
def bad_request_error(error):
    print(f"❌ 400 Bad Request: {error}")
    print(f"Request URL: {request.url}")
    print(f"Request method: {request.method}")
    if request.is_json:
        print(f"Request JSON: {request.get_json()}")
    return jsonify({
        "success": False,
        "error": "Bad Request",
        "message": str(error)
    }), 400


@app.errorhandler(500)
def internal_error(error):
    print(f"❌ 500 Internal Server Error: {error}")
    print(f"Request URL: {request.url}")
    print(f"Request method: {request.method}")
    import traceback
    traceback.print_exc()
    db.session.rollback()
    return jsonify({
        "success": False,
        "error": "Internal Server Error",
        "message": "An unexpected error occurred"
    }), 500

CLIENT_SECRET_FILE = os.getenv("GOOGLE_CLIENT_SECRET_FILE")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid"
]

# Initialize repository
repo = TransactionRepository()


# ---------------------- HOME ----------------------
@app.route("/")
def index():
    # Show landing page for unauthenticated users
    if "credentials" in session:
        return redirect(url_for("dashboard_analytics"))
    else:
        return render_template("landing.html")


# ---------------------- LOGIN PAGE ----------------------
@app.route("/login")
def login_page():
    """Alternative login page route"""
    if "credentials" in session:
        return redirect(url_for("dashboard_analytics"))
    else:
        return render_template("login.html")

@app.route("/login-with-google")
def login_with_google():
    """Route for the Google login button"""
    return redirect(url_for("auth_google"))


# ---------------------- GOOGLE LOGIN ----------------------
@app.route("/auth/google")
def auth_google():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=url_for("oauth2callback", _external=True)
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent"
    )

    session["state"] = state
    return redirect(auth_url)


# ---------------------- GOOGLE CALLBACK ----------------------
@app.route("/oauth2callback")
def oauth2callback():
    try:
        state = session["state"]

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            state=state,
            redirect_uri=url_for("oauth2callback", _external=True)
        )

        flow.fetch_token(authorization_response=request.url)
    
    except Exception as e:
        print(f"❌ OAuth Error: {str(e)}")
        # Check if it's a scope warning that we can handle
        if "Scope has changed" in str(e):
            print("⚠️  Gmail scope was not granted. App will work with limited functionality.")
            # Still try to get basic credentials if possible
            try:
                flow = Flow.from_client_secrets_file(
                    CLIENT_SECRET_FILE,
                    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
                    state=state,
                    redirect_uri=url_for("oauth2callback", _external=True)
                )
                flow.fetch_token(authorization_response=request.url)
            except:
                flash("Authentication failed. Please check your Google Cloud Console setup.", "error")
                return redirect(url_for("landing"))
        else:
            flash(f"Authentication failed: {str(e)}", "error")
            return redirect(url_for("landing"))

    creds = flow.credentials

    session["credentials"] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }
    
    # Fetch user profile info from Google
    try:
        from googleapiclient.discovery import build
        credentials = Credentials(
            token=creds.token,
            refresh_token=creds.refresh_token,
            token_uri=creds.token_uri,
            client_id=creds.client_id,
            client_secret=creds.client_secret
        )
        
        # Get user info from People API or userinfo endpoint
        oauth2_service = build('oauth2', 'v2', credentials=credentials)
        user_info = oauth2_service.userinfo().get().execute()
        
        # Store user info in session
        session['user_name'] = user_info.get('name', 'LUMEN User')
        session['user_email'] = user_info.get('email', '')
        session['user_picture'] = user_info.get('picture', '')
        
        print(f"✅ User logged in: {session['user_name']} ({session['user_email']})")
    except Exception as e:
        print(f"⚠️ Could not fetch user profile: {e}")
        session['user_name'] = 'LUMEN User'
        session['user_email'] = ''

    return redirect(url_for("dashboard_analytics"))


# ---------------------- EXTRACT TRANSACTION INFO ----------------------
def extract_transaction(snippet):
    text = snippet.lower()

    # Enhanced amount pattern to match various formats: Rs 100, Rs. 100, ₹100, INR 100
    amount_pattern = r"(?:rs\.?|₹|inr)\s?([0-9,]+(?:\.[0-9]{1,2})?)"
    amount_match = re.search(amount_pattern, text)
    if amount_match:
        # Remove commas from amount
        amount = amount_match.group(1).replace(",", "")
    else:
        amount = None

    # Enhanced action detection with more keywords
    if any(word in text for word in ["credited", "received", "deposit", "credit to", "money received", "added to"]):
        action = "credited"
    elif any(word in text for word in ["debited", "spent", "withdrawn", "purchased", "paid", "debit from", "payment to", "transferred to", "sent to"]):
        action = "debited"
    else:
        action = None

    # Enhanced name pattern to capture merchant/person names
    name_pattern = r"(?:to|from|at|via)\s+([A-Za-z0-9][A-Za-z0-9\s\.\-]{2,30}?)(?:\s+(?:on|for|is|was|a\/c|account)|$)"
    name_match = re.search(name_pattern, text)
    name = name_match.group(1).strip() if name_match else None

    return {
        "amount": amount,
        "action": action,
        "name": name
    }


# ---------------------- OLD DASHBOARD (REMOVED) ----------------------
# This dashboard page has been replaced by dashboard_analytics
# Kept as commented code in case needed for reference
# @app.route("/dashboard")
# def dashboard():
#     if "credentials" not in session:
#         return redirect(url_for("index"))
#     # ... (rest of old dashboard code removed)


# ---------------------- RECEIPTS PAGE ----------------------
@app.route("/receipts")
def receipts_page():
    if "credentials" not in session:
        return redirect(url_for("index"))

    # Load receipts from SQLite
    receipts_data = ReceiptRepository.get_recent(limit=40)

    receipts = []
    for receipt in receipts_data:
        # Determine receipt type: Gmail or OCR
        is_gmail = receipt.attachment_message_id is not None and receipt.attachment_id is not None
        
        receipt_dict = {
            "receipt_id": receipt.receipt_id,
            "vendor": receipt.merchant_name,
            "date": receipt.issue_date,
            "total": receipt.total_amount,
            "snippet": receipt.raw_snippet or f"{receipt.merchant_name} - ₹{receipt.total_amount}",
            "type": "gmail" if is_gmail else "ocr",
            "filename": receipt.attachment_filename,
            "attachmentId": receipt.attachment_id if is_gmail else None,
            "messageId": receipt.attachment_message_id if is_gmail else None
        }
        
        receipts.append(receipt_dict)

    return render_template("receipts.html", receipts=receipts)


# ---------------------- VIEW OCR RECEIPT ----------------------
@app.route("/receipt/<receipt_id>")
def view_receipt(receipt_id):
    """View detailed information for an OCR-uploaded receipt."""
    if "credentials" not in session:
        return redirect(url_for("index"))
    
    # Get receipt from database
    receipt = Receipt.query.filter_by(receipt_id=receipt_id).first()
    
    if not receipt:
        return "Receipt not found", 404
    
    # Parse raw_snippet if it contains JSON
    extracted_json = None
    if receipt.raw_snippet:
        try:
            # Try to extract JSON from raw_snippet
            cleaned = receipt.raw_snippet.strip()
            if cleaned.startswith('{') and cleaned.endswith('}'):
                extracted_json = json.loads(cleaned)
        except:
            pass
    
    return render_template("receipt_view.html", receipt=receipt, extracted_json=extracted_json)


# ---------------------- TRANSACTIONS PAGE ----------------------
@app.route("/transactions")
def transactions_page():
    if "credentials" not in session:
        return redirect(url_for("index"))

    # Load transactions from SQLite
    transactions = repo.get_all()[:40]  # Get first 40

    tx_list = []
    for tx in transactions:
        tx_list.append({
            "txn_id": tx.txn_id,
            "amount": tx.amount,
            "type": tx.type,  # credit or debit
            "merchant": tx.merchant_name,
            "date": tx.date,
            "category": tx.category
        })

    return render_template("transactions.html", txns=tx_list)


@app.route("/transaction/<txn_id>")
def transaction_detail(txn_id):
    """View detailed transaction information"""
    if "credentials" not in session:
        return redirect(url_for("index"))
    
    # Get transaction from database
    transaction = Transaction.query.filter_by(txn_id=txn_id).first()
    
    if not transaction:
        return "Transaction not found", 404
    
    return render_template("transaction_detail.html", txn=transaction)


# ---------------------- DOWNLOAD ATTACHMENT ----------------------
@app.route("/download/<message_id>/<attachment_id>/<filename>")
def download(message_id, attachment_id, filename):
    creds = Credentials(**session["credentials"])
    gmail = build("gmail", "v1", credentials=creds)

    attachment = gmail.users().messages().attachments().get(
        userId="me",
        messageId=message_id,
        id=attachment_id
    ).execute()

    file_data = base64.urlsafe_b64decode(attachment["data"])

    return send_file(
        BytesIO(file_data),
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )


# ---------------------- SYNC GMAIL DATA ----------------------
@app.route("/sync")
def sync_gmail():
    if "credentials" not in session:
        return redirect(url_for("index"))
    
    try:
        # Run Gmail sync with LLM extraction
        result = sync_all_gmail_data(session["credentials"])
        
        # Format success message
        tx_result = result.get('transactions', {})
        receipt_result = result.get('receipts', {})
        
        message = f"Sync completed! "
        message += f"Transactions: {tx_result.get('new_transactions', 0)} new, {tx_result.get('skipped', 0)} skipped. "
        message += f"Receipts: {receipt_result.get('new_receipts', 0)} new, {receipt_result.get('skipped', 0)} skipped."
        
        flash(message, 'success')
    except Exception as e:
        flash(f"Sync error: {str(e)}", 'error')
    
    return redirect(url_for("dashboard_analytics"))


@app.route("/sync/api")
def sync_gmail_api():
    """API endpoint for AJAX sync requests"""
    if "credentials" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    
    try:
        result = sync_all_gmail_data(session["credentials"])
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------- DEBUG/ADMIN ROUTES ----------------------
@app.route("/api/debug/transactions")
def debug_transactions():
    """View all transactions in database (JSON)"""
    transactions = repo.get_all()
    return jsonify({
        "count": len(transactions),
        "transactions": [t.to_dict() for t in transactions]
    })


@app.route("/api/debug/receipts")
def debug_receipts():
    """View all receipts in database (JSON)"""
    receipts = ReceiptRepository.get_all() if hasattr(ReceiptRepository, 'get_all') else []
    return jsonify({
        "count": len(receipts),
        "receipts": [r.to_dict() for r in receipts]
    })


@app.route("/api/debug/stats")
def debug_stats():
    """View database statistics"""
    transactions = repo.get_all()
    receipts = ReceiptRepository.get_all() if hasattr(ReceiptRepository, 'get_all') else []
    
    credit_txns = [t for t in transactions if t.type == 'credit']
    debit_txns = [t for t in transactions if t.type == 'debit']
    
    return jsonify({
        "database_file": "lumen_transactions.db",
        "transactions": {
            "total": len(transactions),
            "credit": len(credit_txns),
            "debit": len(debit_txns),
            "total_credit_amount": sum(t.amount or 0 for t in credit_txns),
            "total_debit_amount": sum(t.amount or 0 for t in debit_txns)
        },
        "receipts": {
            "total": len(receipts),
            "total_amount": sum(r.total_amount or 0 for r in receipts) if receipts else 0
        }
    })


# ---------------------- NEW TRANSACTION DB ROUTES ----------------------
@app.route("/init-db")
def init_db_route():
    """
    Initialize/reinitialize the transaction database.
    Creates tables if they don't exist.
    """
    try:
        print("\n" + "="*80)
        print("🔧 Manual database initialization requested")
        print("="*80)
        
        with app.app_context():
            db.create_all()
            
            db_file_path = os.path.join(os.getcwd(), 'lumen_transactions.db')
            if os.path.exists(db_file_path):
                print("✅ Database tables created/verified: lumen_transactions.db")
                print("📊 Table: transactions")
                
                return "✔ Database initialized"
            else:
                return jsonify({
                    "success": False,
                    "message": "Database file was not created"
                }), 500
                
    except Exception as e:
        error_msg = f"Database initialization error: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({
            "success": False,
            "error": error_msg
        }), 500


@app.route("/save-transaction", methods=['POST'])
def save_transaction():
    """
    Save a transaction to the database via JSON POST.
    
    Expected JSON fields (matching schema):
    {
        "txn_id": "TXN_...",
        "description": "...",
        "clean_description": "...",
        "merchant_name": "...",
        "payment_channel": "...",
        "amount": 100.0,
        "type": "debit",
        "date": "2025-11-15",
        "weekday": "Friday",
        "time_of_day": "14:30",
        "balance_after_txn": 5000.0,
        "category": "Food",
        "subcategory": "Restaurant",
        "is_recurring": false,
        "recurrence_interval": null,
        "confidence_score": 0.95,
        "is_suspicious": false,
        "embedding_version": 1,
        "raw_email_snippet": "..."
    }
    """
    data = request.json

    if not data:
        return jsonify({"success": False, "error": "No JSON received"}), 400

    if repo.exists(data["txn_id"]):
        return jsonify({"success": False, "duplicate": True})

    repo.add(data)
    return jsonify({"success": True})


@app.route("/api/transactions/all", methods=['GET'])
def get_all_transactions():
    """Get all transactions from the database"""
    try:
        transactions = repo.get_all()
        return jsonify({
            "success": True,
            "count": len(transactions),
            "transactions": [t.to_dict() for t in transactions]
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------- DASHBOARD (ANALYTICS) PAGE ----------------------
@app.route("/dashboard-analytics")
def dashboard_analytics():
    """Dashboard - Anomalies and Analytics page"""
    if "credentials" not in session:
        return redirect(url_for("index"))
    
    return render_template("anomalies.html")


@app.route("/api/dashboard-data")
def dashboard_data():
    """
    API endpoint for dashboard data (charts.js compatibility).
    Returns basic chart data for dashboard.
    """
    try:
        print("📊 Dashboard data requested")
        
        # Get transactions for basic analytics
        transactions = repo.get_all()
        
        # Calculate totals
        debit_total = sum(t.amount or 0 for t in transactions if t.type == 'debit')
        credit_total = sum(t.amount or 0 for t in transactions if t.type == 'credit')
        net_flow = credit_total - debit_total
        
        # Get category breakdown for donut chart
        categories = {}
        for t in transactions:
            if t.category and t.type == 'debit':  # Only debit transactions for spending
                categories[t.category] = categories.get(t.category, 0) + (t.amount or 0)
        
        # Sort categories by amount
        sorted_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
        
        donut_labels = [cat[0] for cat in sorted_categories] or ['No Data']
        donut_values = [cat[1] for cat in sorted_categories] or [0]
        
        # Basic line chart data (last 7 days spending)
        from datetime import datetime, timedelta
        today = datetime.now()
        daily_spending = {}
        
        for i in range(7):
            date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            daily_spending[date] = 0
        
        for t in transactions:
            if t.date and t.type == 'debit':
                if t.date in daily_spending:
                    daily_spending[t.date] += t.amount or 0
        
        line_labels = list(daily_spending.keys())
        line_values = list(daily_spending.values())
        
        return jsonify({
            "success": True,
            "debit_total": debit_total,
            "credit_total": credit_total,
            "net_flow": net_flow,
            "donut_labels": donut_labels,
            "donut_values": donut_values,
            "mini_labels": donut_labels[:3],
            "mini_values": donut_values[:3],
            "line_labels": line_labels,
            "line_values": line_values
        })
        
    except Exception as e:
        print(f"❌ Dashboard data error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": str(e),
            "debit_total": 0,
            "credit_total": 0,
            "net_flow": 0,
            "donut_labels": ['No Data'],
            "donut_values": [0],
            "mini_labels": ['No Data'],
            "mini_values": [0],
            "line_labels": ['No Data'],
            "line_values": [0]
        }), 500


@app.route("/api/anomalies-data")
def anomalies_data():
    """
    API endpoint for analytics data with caching.
    Returns charts, insights, and anomalies.
    """
    try:
        # Check cache first
        cached_data = analytics_cache.get('analytics_report')
        
        if cached_data:
            return jsonify({
                "success": True,
                "cached": True,
                **cached_data
            })
        
        # Generate fresh analytics report
        report = generate_analytics_report(app)
        
        # Cache the result
        analytics_cache.set('analytics_report', report)
        
        return jsonify({
            "success": True,
            "cached": False,
            **report
        })
        
    except Exception as e:
        print(f"❌ Analytics error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": str(e),
            "ai_summary": "Unable to load AI insights. Showing basic analytics.",
            "pie_chart": None,
            "top4_chart": None,
            "daily_chart": None,
            "monthly_chart": None,
            "debit_total": 0,
            "credit_total": 0,
            "net_flow": 0,
            "patterns": [],
            "suspicious": [],
            "recommendations": ["Please check system logs for errors"]
        }), 500


# ---------------------- UPLOAD RECEIPT (OCR) ----------------------
@app.route("/upload-receipt", methods=["POST"])
def upload_receipt():
    """
    Handle receipt file upload with OCR processing.
    
    Flow:
    1. Save uploaded file to ./uploads/receipts/
    2. Extract TEXT using NVIDIA Vision LLM
    3. Validate and parse JSON from text
    4. Map to database schema
    5. Insert into receipts table
    """
    try:
        print(f"\n🔍 Upload receipt request received")
        
        # Check if file was uploaded
        if 'file' not in request.files:
            print("❌ No file in request")
            return jsonify({
                "success": False,
                "error": "No file uploaded"
            }), 400
        
        file = request.files['file']
        print(f"📄 File received: {file.filename}")
        
        if file.filename == '':
            print("❌ Empty filename")
            return jsonify({
                "success": False,
                "error": "Empty filename"
            }), 400
        
        # Validate file extension
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.pdf'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        print(f"📋 File extension: {file_ext}")
        
        if file_ext not in allowed_extensions:
            print(f"❌ Invalid file type: {file_ext}")
            return jsonify({
                "success": False,
                "error": f"Invalid file type '{file_ext}'. Allowed: {', '.join(allowed_extensions)}"
            }), 400
        
        # Check file size (not empty)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        print(f"📏 File size: {file_size} bytes")
        
        if file_size == 0:
            print("❌ Empty file")
            return jsonify({
                "success": False,
                "error": "Uploaded file is empty"
            }), 400
        
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join(project_dir, 'uploads', 'receipts')
        os.makedirs(upload_dir, exist_ok=True)
        print(f"📁 Upload directory: {upload_dir}")
        
        # Save file with timestamp to avoid conflicts
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(upload_dir, safe_filename)
        
        file.save(file_path)
        print(f"✅ File saved: {file_path}")
        
        # Verify file was saved correctly
        if not os.path.exists(file_path):
            print(f"❌ File not found after save: {file_path}")
            return jsonify({
                "success": False,
                "error": "Failed to save uploaded file"
            }), 500
        
        # Step 2: Extract TEXT using NVIDIA Vision LLM
        print("🔍 Running OCR extraction...")
        raw_text_response = process_uploaded_file(file_path)
        print(f"📝 OCR raw response type: {type(raw_text_response)}")
        print(f"📝 OCR response length: {len(raw_text_response) if raw_text_response else 0}")
        
        if not raw_text_response:
            print("❌ OCR extraction failed - no response")
            return jsonify({
                "success": False,
                "error": "Failed to extract data from file - OCR returned no response"
            }), 400
        
        if len(raw_text_response.strip()) < 10:
            print(f"❌ OCR extraction failed - response too short: '{raw_text_response}'")
            return jsonify({
                "success": False,
                "error": "OCR extraction failed - response too short or empty"
            }), 400
        
        print(f"✅ OCR text response received: {len(raw_text_response)} characters")
        print(f"📄 Raw OCR output preview: {raw_text_response[:200]}...")
        
        # Step 3: Parse and validate JSON from text
        print("🔍 Parsing JSON from OCR text...")
        receipt_json = parse_json_safely(raw_text_response)
        print(f"📊 JSON parsing result: {receipt_json is not None}")
        
        if not receipt_json:
            print(f"❌ JSON parsing failed")
            print(f"Raw response: {raw_text_response[:300]}...")
            return jsonify({
                "success": False,
                "error": "OCR returned invalid JSON. Please try with a clearer image.",
                "raw_output": raw_text_response[:500]
            }), 400
        
        print(f"✅ Valid JSON parsed: {receipt_json}")
        
        # Step 4: Validate required JSON fields
        required_fields = ['vendor', 'date', 'total']
        missing_fields = []
        
        for field in required_fields:
            if field not in receipt_json or not receipt_json[field]:
                missing_fields.append(field)
        
        if missing_fields:
            print(f"❌ Missing required fields: {missing_fields}")
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}",
                "extracted_json": receipt_json
            }), 422
        
        # Validate total is a number
        try:
            total_amount = float(receipt_json.get('total', 0))
            if total_amount <= 0:
                print(f"❌ Invalid total amount: {total_amount}")
                return jsonify({
                    "success": False,
                    "error": "Total amount must be greater than 0"
                }), 422
        except (ValueError, TypeError) as e:
            print(f"❌ Invalid total format: {receipt_json.get('total')} - {e}")
            return jsonify({
                "success": False,
                "error": f"Invalid total amount format: {receipt_json.get('total')}"
            }), 422
        
        # Step 5: Map JSON to database schema
        from datetime import datetime
        
        receipt_data = {
            'receipt_id': f"RCP_OCR_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'receipt_type': 'uploaded',
            'issue_date': receipt_json.get('date', datetime.now().strftime('%Y-%m-%d')),
            'issue_time': '',
            'merchant_name': receipt_json.get('vendor', 'Unknown'),
            'merchant_address': '',
            'merchant_gst': '',
            'subtotal_amount': float(receipt_json.get('subtotal', 0)),
            'tax_amount': float(receipt_json.get('tax', 0)),
            'total_amount': total_amount,
            'payment_method': receipt_json.get('payment_method', 'Unknown'),
            'extracted_confidence_score': float(receipt_json.get('confidence_score', 0)),
            'is_suspicious': float(receipt_json.get('confidence_score', 100)) < 50,
            'embedding_version': 1,
            'attachment_filename': safe_filename,
            'raw_snippet': raw_text_response[:500]
        }
        
        print(f"📊 Receipt data prepared: {receipt_data['receipt_id']}")
        
        # Step 6: Insert into receipts table
        print("💾 Inserting into database...")
        success, message = ReceiptRepository.add_receipt(receipt_data)
        
        if success:
            print(f"✅ Receipt inserted successfully: {receipt_data['receipt_id']}")
            return jsonify({
                "success": True,
                "message": f"Receipt processed successfully! Vendor: {receipt_data['merchant_name']}, Total: ₹{receipt_data['total_amount']}",
                "type": "receipt",
                "data": receipt_data,
                "json_extracted": receipt_json
            })
        else:
            print(f"❌ Database insertion failed: {message}")
            return jsonify({
                "success": False,
                "error": f"Failed to save receipt to database: {message}"
            }), 500
        
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


# ---------------------- WISHLIST SYSTEM ----------------------
@app.route("/wishlist")
def wishlist_page():
    """Wishlist & Smart Advisor page"""
    if "credentials" not in session:
        return redirect(url_for("index"))
    
    # Get user email from credentials
    creds = Credentials(**session["credentials"])
    gmail = build("gmail", "v1", credentials=creds)
    profile = gmail.users().getProfile(userId="me").execute()
    user_email = profile.get("emailAddress")
    
    # Get wishlist items for user
    wishlist_items = WishlistRepository.get_by_user(user_email)
    
    # Format for template
    items = []
    for item in wishlist_items:
        items.append({
            "wishlist_id": item.wishlist_id,
            "item_name": item.item_name,
            "expected_price": item.expected_price,
            "category": item.category or "uncategorized",
            "notes": item.notes,
            "created_at": item.created_at.strftime('%B %d, %Y at %I:%M %p') if item.created_at else ""
        })
    
    # Count for navbar badge
    wishlist_count = len(items)
    
    return render_template("wishlist.html", wishlist_items=items, wishlist_count=wishlist_count)


@app.route("/wishlist/add", methods=["POST"])
def add_wishlist_item():
    """Add item to wishlist with auto-categorization"""
    if "credentials" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    
    try:
        # Get user email
        creds = Credentials(**session["credentials"])
        gmail = build("gmail", "v1", credentials=creds)
        profile = gmail.users().getProfile(userId="me").execute()
        user_email = profile.get("emailAddress")
        
        # Get form data
        data = request.get_json() if request.is_json else request.form
        item_name = data.get("item_name", "").strip()
        expected_price = float(data.get("expected_price", 0))
        notes = data.get("notes", "").strip()
        
        if not item_name or expected_price <= 0:
            return jsonify({"success": False, "error": "Invalid item name or price"}), 400
        
        # Auto-categorize using AI (simple keyword matching for now)
        category = categorize_item(item_name)
        
        # Add to database
        success, wishlist_id = WishlistRepository.add_item(
            user_email=user_email,
            item_name=item_name,
            expected_price=expected_price,
            category=category,
            notes=notes
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Added {item_name} to wishlist",
                "wishlist_id": wishlist_id,
                "category": category
            })
        else:
            return jsonify({"success": False, "error": "Failed to add item"}), 500
            
    except ValueError:
        return jsonify({"success": False, "error": "Invalid price format"}), 400
    except Exception as e:
        print(f"❌ Error adding wishlist item: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/wishlist/delete/<wishlist_id>", methods=["POST"])
def delete_wishlist_item(wishlist_id):
    """Delete wishlist item"""
    if "credentials" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    
    try:
        success, message = WishlistRepository.delete_item(wishlist_id)
        
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 404
            
    except Exception as e:
        print(f"❌ Error deleting wishlist item: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/wishlist/advice/<wishlist_id>")
def get_wishlist_advice(wishlist_id):
    """Get AI-powered purchase advice for a wishlist item"""
    if "credentials" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    
    try:
        # Get wishlist item
        item = WishlistRepository.get_by_id(wishlist_id)
        
        if not item:
            return jsonify({"success": False, "error": "Item not found"}), 404
        
        # Get user's transactions for analytics
        transactions = repo.get_all()
        
        # Import AI advisor
        from modules.wishlist.ai_advisor import get_purchase_advice, build_analytics_summary
        
        # Build analytics summary
        analytics_summary = build_analytics_summary(transactions, item.category or "uncategorized")
        
        # Get AI advice
        advice = get_purchase_advice(
            item_name=item.item_name,
            expected_price=item.expected_price,
            category=item.category or "uncategorized",
            user_analytics=analytics_summary
        )
        
        return jsonify({
            "success": True,
            "item": {
                "name": item.item_name,
                "price": item.expected_price,
                "category": item.category
            },
            "advice": advice
        })
        
    except Exception as e:
        print(f"❌ Error getting wishlist advice: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def categorize_item(item_name):
    """Simple keyword-based categorization for wishlist items"""
    item_lower = item_name.lower()
    
    # Category keywords mapping (same as transaction categories)
    categories = {
        "groceries": ["grocery", "vegetable", "fruit", "food", "supermarket", "mart", "store"],
        "dining": ["restaurant", "cafe", "coffee", "pizza", "burger", "meal", "dine"],
        "transportation": ["uber", "ola", "taxi", "metro", "bus", "train", "fuel", "petrol"],
        "utilities": ["electricity", "water", "gas", "internet", "mobile", "recharge", "bill"],
        "entertainment": ["movie", "cinema", "game", "music", "spotify", "netflix", "prime"],
        "shopping": ["clothes", "shoes", "dress", "shirt", "jeans", "fashion", "amazon", "flipkart"],
        "healthcare": ["medicine", "doctor", "hospital", "pharmacy", "health", "medical"],
        "education": ["book", "course", "class", "tuition", "study", "school", "college"],
        "electronics": ["phone", "laptop", "computer", "tablet", "camera", "headphone", "speaker"],
        "home": ["furniture", "decor", "appliance", "kitchen", "bedroom", "cleaning"]
    }
    
    for category, keywords in categories.items():
        if any(keyword in item_lower for keyword in keywords):
            return category
    
    return "other"


# ---------------------- MCP API ENDPOINTS ----------------------
# Model Context Protocol - Secure control layer between LLM and backend

@app.route("/api/mcp/tools")
def mcp_tools():
    """
    MCP Tool Discovery Endpoint.
    Returns list of available tools and their schemas.
    The LLM uses this to know what actions it can take.
    """
    try:
        tools = mcp_server.get_available_tools()
        return jsonify({
            "success": True,
            "tool_count": len(tools),
            "tools": tools,
            "info": {
                "description": "MCP tools for Project LUMEN financial assistant",
                "security": "All tools are read-only. LLM cannot access database or tokens directly."
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/mcp/execute", methods=["POST"])
def mcp_execute():
    """
    MCP Tool Execution Endpoint.
    Executes a specific tool with given arguments.
    Useful for testing tools without LLM.
    """
    try:
        data = request.get_json()
        
        if not data or "tool" not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'tool' in request body"
            }), 400
        
        tool_name = data["tool"]
        arguments = data.get("arguments", {})
        
        result = mcp_server.execute_tool(tool_name, arguments)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/mcp/chat", methods=["POST"])
def mcp_chat():
    """
    MCP Chat Endpoint.
    Handles natural language questions via MCP → LLM flow.
    
    Request:
        {"message": "Why did I overspend this month?"}
    
    Response:
        {
            "success": true,
            "response": "Looking at your spending data...",
            "tools_used": ["get_monthly_spending_summary", "get_top_spending_categories"]
        }
    """
    if "credentials" not in session:
        return jsonify({
            "success": False,
            "error": "Not authenticated"
        }), 401
    
    try:
        data = request.get_json()
        
        if not data or "message" not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'message' in request body"
            }), 400
        
        user_message = data["message"]
        
        # Route through MCP server
        result = mcp_server.chat(user_message)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ MCP Chat error: {str(e)}")
        return jsonify({
            "success": False,
            "response": "An error occurred while processing your request.",
            "tools_used": [],
            "error": str(e)
        }), 500


@app.route("/api/llm/status")
def llm_status():
    """
    LLM Status Endpoint.
    Returns current LLM provider configuration and availability.
    
    Response:
        {
            "provider": "auto",
            "local": {"available": true, "model": "..."},
            "groq": {"available": true, "model": "..."}
        }
    """
    try:
        status = mcp_server.get_llm_status()
        return jsonify({
            "success": True,
            **status
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------- LOGOUT ----------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------- RUN ----------------------
if __name__ == "__main__":
    app.run(port=5000, debug=True)