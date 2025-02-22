from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
from requests.auth import HTTPBasicAuth
import base64
from datetime import datetime
import sqlite3

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Daraja API Constants
DARAJA_API_URL = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
CONSUMER_KEY = "77bgGpmlOxlgJu6oEXhEgUgnu0j2WYxA"
CONSUMER_SECRET = "viM8ejHgtEmtPTHd"
BUSINESS_SHORTCODE = "174379"
PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
CALLBACK_URL = "https://yourwebsite.com/callback"
OAUTH_URL = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
QUERY_URL = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"

# Database setup
def init_db():
    conn = sqlite3.connect('mpesa.db')
    c = conn.cursor()
    
    # Create transactions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            mpesa_receipt TEXT UNIQUE,
            transaction_date TEXT,
            phone_number TEXT,
            status TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

def generate_access_token():
    try:
        response = requests.get(
            OAUTH_URL,
            auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET)
        )
        return response.json()['access_token']
    except Exception as e:
        print(f"Token generation error: {e}")
        return None

def generate_password():
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    data_to_encode = f"{BUSINESS_SHORTCODE}{PASSKEY}{timestamp}"
    encoded = base64.b64encode(data_to_encode.encode())
    return encoded.decode('utf-8'), timestamp

@app.route('/')
def payment():
    """Render payment page"""
    return render_template('payment.html')

@app.route('/stk_push', methods=['POST'])
def stk_push():
    try:
        data = request.json
        phone_number = data.get("phone_number")
        amount = data.get("amount")
        account_reference = data.get("account_reference", "AdminAccess")
        transaction_desc = data.get("transaction_desc", "Admin Access Payment")
        
        access_token = generate_access_token()
        if not access_token:
            return jsonify({"error": "Could not generate access token"}), 500

        password, timestamp = generate_password()

        payload = {
            "BusinessShortCode": BUSINESS_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(float(amount)),
            "PartyA": phone_number,
            "PartyB": BUSINESS_SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": CALLBACK_URL,
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(DARAJA_API_URL, json=payload, headers=headers)
        
        checkout_data = response.json()
        if 'CheckoutRequestID' in checkout_data:
            session['checkout_request_id'] = checkout_data['CheckoutRequestID']
            session['phone_number'] = phone_number
        
        return jsonify(response.json())

    except Exception as e:
        print(f"STK push error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/check_payment_status', methods=['POST'])
def check_payment_status():
    try:
        data = request.json
        checkout_request_id = data.get('checkout_request_id')
        
        access_token = generate_access_token()
        if not access_token:
            return jsonify({"ResultCode": "1", "ResultDesc": "Please try again"})

        password, timestamp = generate_password()

        payload = {
            "BusinessShortCode": BUSINESS_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(QUERY_URL, json=payload, headers=headers)

        if response.ok:
            result = response.json()
            if str(result.get('ResultCode')) == "0":
                # Payment successful, set admin session
                session['is_admin'] = True
                session['payment_verified'] = True
                
            return jsonify({
                "ResultCode": str(result.get('ResultCode')),
                "ResultDesc": "Success" if result.get('ResultCode') == "0" else "Please try again"
            })

    except Exception as e:
        print(f"Status check error: {e}")
        return jsonify({
            "ResultCode": "1",
            "ResultDesc": "Please try again"
        })

@app.route('/callback', methods=['POST'])
def callback():
    """Handle M-Pesa callback"""
    try:
        data = request.json
        print("M-Pesa Callback Data:", data)
        
        callback_data = data.get('Body', {}).get('stkCallback', {})
        result_code = callback_data.get('ResultCode')
        
        if result_code == 0:
            items = callback_data.get('CallbackMetadata', {}).get('Item', [])
            transaction_data = {
                'amount': next((i['Value'] for i in items if i['Name'] == 'Amount'), None),
                'mpesa_receipt': next((i['Value'] for i in items if i['Name'] == 'MpesaReceiptNumber'), None),
                'transaction_date': next((i['Value'] for i in items if i['Name'] == 'TransactionDate'), None),
                'phone_number': next((i['Value'] for i in items if i['Name'] == 'PhoneNumber'), None)
            }
            
            # Store transaction in database
            conn = sqlite3.connect('mpesa.db')
            c = conn.cursor()
            c.execute('''
                INSERT INTO transactions 
                (amount, mpesa_receipt, transaction_date, phone_number, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                transaction_data['amount'],
                transaction_data['mpesa_receipt'],
                transaction_data['transaction_date'],
                transaction_data['phone_number'],
                'success'
            ))
            conn.commit()
            conn.close()
            
            # Set admin session
            session['is_admin'] = True
            session['payment_verified'] = True
            session['phone_number'] = transaction_data['phone_number']
            
            return jsonify({"ResultCode": 0, "ResultDesc": "Success"})
        else:
            return jsonify({"ResultCode": 1, "ResultDesc": "Failed"})
            
    except Exception as e:
        print(f"Callback error: {e}")
        return jsonify({"ResultCode": 1, "ResultDesc": "Error processing callback"})

@app.route('/admin_dashboard')
def admin_dashboard():
    """Admin dashboard with transaction history"""
    if not session.get('payment_verified'):
        return redirect(url_for('payment'))
        
    conn = sqlite3.connect('mpesa.db')
    c = conn.cursor()
    
    # Get all transactions
    transactions = c.execute('SELECT * FROM transactions ORDER BY transaction_date DESC').fetchall()
    
    # Calculate statistics
    total_amount = sum(t[1] for t in transactions)
    success_count = len([t for t in transactions if t[5] == 'success'])
    success_rate = (success_count / len(transactions) * 100) if transactions else 0
    
    conn.close()
    
    return render_template(
        'admin_dashboard.html',
        transactions=transactions,
        total_amount=total_amount,
        success_rate=success_rate,
        phone_number=session.get('phone_number')
    )

if __name__ == '__main__':
    app.run(debug=True)