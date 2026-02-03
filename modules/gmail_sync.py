from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from modules.llm_extraction.extractor import extract_transaction_from_text, extract_receipt_from_text
from modules.database.transaction_repo import TransactionRepository, ReceiptRepository


def sync_gmail_transactions(session_credentials):
    """
    Fetch transaction emails from Gmail, extract with LLM, and store in SQLite.
    Only processes new transactions that aren't already in the database.
    """
    creds = Credentials(**session_credentials)
    gmail = build("gmail", "v1", credentials=creds)
    
    # Query for banking and payment transactions
    tx_query = '(from:(bank OR paytm OR phonepe OR gpay OR googlepay OR amazonpay OR paypal OR bhim OR upi OR alerts) OR subject:(transaction OR credited OR debited OR payment OR "account statement" OR "debit card" OR "credit card" OR "net banking" OR UPI OR NEFT OR RTGS OR IMPS)) AND (credited OR debited OR paid OR received OR sent OR withdrawn OR deposited OR transferred OR Rs OR INR OR ₹)'
    
    try:
        result = gmail.users().messages().list(userId="me", q=tx_query, maxResults=50).execute()
        messages = result.get("messages", [])
        
        new_count = 0
        skipped_count = 0
        error_count = 0
        
        for msg in messages:
            try:
                full_msg = gmail.users().messages().get(userId="me", id=msg["id"], format="full").execute()
                snippet = full_msg.get("snippet", "")
                
                # Extract transaction info using LLM
                transaction_dict = extract_transaction_from_text(snippet)
                
                # Store ALL transactions, even if extraction partially fails
                if transaction_dict:
                    # Check for duplicates
                    if not TransactionRepository.exists(transaction_dict['txn_id']):
                        # Also check by date/amount/merchant to avoid duplicates (if amount exists)
                        amount = transaction_dict.get('amount', 0)
                        if amount > 0:
                            duplicate_check = TransactionRepository.check_duplicate(
                                transaction_dict['date'],
                                transaction_dict['amount'],
                                transaction_dict['merchant_name']
                            )
                        else:
                            duplicate_check = False
                        
                        if not duplicate_check:
                            success, message = TransactionRepository.add_transaction(transaction_dict)
                            if success:
                                new_count += 1
                            else:
                                error_count += 1
                                print(f"Error storing transaction: {message}")
                        else:
                            skipped_count += 1
                    else:
                        skipped_count += 1
                else:
                    # LLM extraction completely failed
                    error_count += 1
                    print(f"LLM extraction failed for message {msg['id']}")
            except Exception as e:
                error_count += 1
                print(f"Error processing transaction message {msg['id']}: {str(e)}")
        
        return {
            'success': True,
            'new_transactions': new_count,
            'skipped': skipped_count,
            'errors': error_count
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def sync_gmail_receipts(session_credentials):
    """
    Fetch receipt/invoice emails from Gmail, extract with LLM, and store in SQLite.
    Only processes new receipts that aren't already in the database.
    """
    creds = Credentials(**session_credentials)
    gmail = build("gmail", "v1", credentials=creds)
    
    # Query for payment-related invoices and bills
    invoice_query = '(subject:(invoice OR receipt OR bill OR payment OR "order confirmation" OR "tax invoice") OR from:(payment OR billing OR invoice OR noreply)) has:attachment filename:pdf'
    
    try:
        result = gmail.users().messages().list(userId="me", q=invoice_query, maxResults=50).execute()
        messages = result.get("messages", [])
        
        new_count = 0
        skipped_count = 0
        error_count = 0
        
        for msg in messages:
            try:
                # Check if this message was already processed
                if ReceiptRepository.check_duplicate_by_message(msg["id"]):
                    skipped_count += 1
                    continue
                
                full_msg = gmail.users().messages().get(userId="me", id=msg["id"], format="full").execute()
                snippet = full_msg.get("snippet", "")
                
                # Extract receipt info using LLM
                receipt_dict = extract_receipt_from_text(snippet)
                
                if receipt_dict:
                    # Add attachment information
                    parts = full_msg["payload"].get("parts", [])
                    for part in parts:
                        if part.get("filename") and part.get("body", {}).get("attachmentId"):
                            receipt_dict['attachment_filename'] = part["filename"]
                            receipt_dict['attachment_message_id'] = msg["id"]
                            receipt_dict['attachment_id'] = part["body"]["attachmentId"]
                            break  # Take first attachment
                    
                    # Store raw snippet
                    receipt_dict['raw_snippet'] = snippet
                    
                    # Save to database
                    success, message = ReceiptRepository.add_receipt(receipt_dict)
                    if success:
                        new_count += 1
                    else:
                        error_count += 1
                        print(f"Error storing receipt: {message}")
                else:
                    # LLM extraction failed for receipt
                    error_count += 1
                    print(f"LLM extraction failed for receipt message {msg['id']}")
            except Exception as e:
                error_count += 1
                print(f"Error processing receipt message {msg['id']}: {str(e)}")
        
        return {
            'success': True,
            'new_receipts': new_count,
            'skipped': skipped_count,
            'errors': error_count
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def sync_all_gmail_data(session_credentials):
    """
    Sync both transactions and receipts from Gmail.
    """
    tx_result = sync_gmail_transactions(session_credentials)
    receipt_result = sync_gmail_receipts(session_credentials)
    
    return {
        'transactions': tx_result,
        'receipts': receipt_result
    }
