"""
Agent 3: Excel Results Email Sender
===================================
This agent finds and sends all generated Excel files from the product analysis pipeline.

Features:
- Finds all three main Excel files:
  1. sunfeast_product_analysis.xlsx (from Agent 1)
  2. sunfeast_merged_analysis.xlsx (from Agent 4)  
  3. qr_barcode_results_*.xlsx (from Agent 2 QR Orchestrator)
- Sends comprehensive email with all attachments
- Provides detailed file descriptions in email body
- Handles missing files gracefully
"""

import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import sys
import glob

# Configure UTF-8 encoding for console output (fixes Windows Unicode issues)
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    # Python < 3.7 doesn't have reconfigure, try setting environment variable
    import locale
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

# Get parameters from command line
if len(sys.argv) < 3:
    print("Usage: python exception_reporter.py <output_folder> <recipient_email>")
    sys.exit(1)

HOTFOLDER_PATH = sys.argv[1]
RECIPIENT_EMAIL = sys.argv[2]

# Find the Excel files dynamically based on what's available
excel_files = [f for f in os.listdir(HOTFOLDER_PATH) if f.endswith('.xlsx')]
filtered_files = [f for f in excel_files if f.endswith('_filtered_products.xlsx')]
merged_files = [f for f in excel_files if f.endswith('_merged_analysis.xlsx')]

# Define the specific Excel files to attach
REQUIRED_FILES = []
if filtered_files:
    REQUIRED_FILES.append(filtered_files[0])  # Product analysis file
if merged_files:
    REQUIRED_FILES.append(merged_files[0])    # Merged analysis file

# Pattern for QR/Barcode results (timestamped files)
QR_BARCODE_PATTERN = "qr_barcode_results_*.xlsx"

# Set the sender email
SENDER_EMAIL = 'souvikmakur2003@gmail.com'
SENDER_PASS = 'feuz htpc mfha ayhn'

# Gmail SMTP settings
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 465

def send_email_with_attachments(subject, body, to, attachment_paths):
    """Send email with multiple attachments"""
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = to
        msg.attach(MIMEText(body, 'plain'))

        attached_count = 0
        
        # Attach all Excel files
        for attachment_path in attachment_paths:
            if os.path.exists(attachment_path):
                with open(attachment_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(attachment_path)}"')
                    msg.attach(part)
                    print(f"✅ Attached: {os.path.basename(attachment_path)}")
                    attached_count += 1
            else:
                print(f"⚠️ Attachment not found: {os.path.basename(attachment_path)}")

        if attached_count == 0:
            print("❌ No attachments found to send")
            return False

        # Send email via Gmail SMTP
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.send_message(msg)
        
        print(f"📧 Email sent successfully with {attached_count} attachments!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

def find_excel_files():
    """Find all required Excel files in the hotfolder"""
    attachment_paths = []
    
    # Find specific required files
    for filename in REQUIRED_FILES:
        file_path = os.path.join(HOTFOLDER_PATH, filename)
        if os.path.exists(file_path):
            attachment_paths.append(file_path)
            print(f"✅ Found: {filename}")
        else:
            print(f"⚠️ Missing: {filename}")
    
    # Find latest QR/Barcode results file
    qr_files = glob.glob(os.path.join(HOTFOLDER_PATH, QR_BARCODE_PATTERN))
    if qr_files:
        latest_qr_file = max(qr_files, key=os.path.getctime)
        attachment_paths.append(latest_qr_file)
        print(f"✅ Found latest QR/Barcode results: {os.path.basename(latest_qr_file)}")
    else:
        print(f"⚠️ No QR/Barcode results files found matching pattern: {QR_BARCODE_PATTERN}")
    
    return attachment_paths

def main():
    try:
        print("📧 Agent 3: Excel Results Email Sender Starting...")
        
        # Find all Excel files to attach
        print("\n🔍 Searching for Excel files to attach...")
        attachment_paths = find_excel_files()
        
        if not attachment_paths:
            print("❌ No Excel files found to send!")
            print("Please ensure all agents have run successfully:")
            print("   • Agent 1: Product Analysis")
            print("   • Agent 2: QR/Barcode Detection") 
            print("   • Agent 4: Text Merger")
            return
        
        # Extract product name from the first analysis file for dynamic subject
        product_name = "Products"
        if filtered_files:
            product_name = filtered_files[0].replace('_filtered_products.xlsx', '').title()

        # Enhanced email content
        email_subject = f"Complete Product Analysis Results - {product_name}"
        
        file_list = "\n".join([f"   • {os.path.basename(path)}" for path in attachment_paths])
        
        email_body = f"""
Complete Product Analysis Results

Please find the attached comprehensive analysis files for {product_name} products:

{file_list}

File Descriptions:
• *_filtered_products.xlsx: Filtered product list with relevant products containing the search term
• *_merged_analysis.xlsx: Complete analysis with extracted text from images and contact information
• qr_barcode_results_[timestamp].xlsx: QR code and barcode detection results with URL redirects

Total files attached: {len(attachment_paths)}

Best regards,
Automated Product Analysis System
        """
        
        print(f"\n📧 Preparing to send email with {len(attachment_paths)} attachments...")
        
        # Send email with all Excel files
        success = send_email_with_attachments(
            subject=email_subject,
            body=email_body,
            to=RECIPIENT_EMAIL,
            attachment_paths=attachment_paths
        )
        
        if success:
            print("\n✅ Email sent successfully!")
            print(f"📧 Sent to: {RECIPIENT_EMAIL}")
            print(f"📎 Total attachments: {len(attachment_paths)}")
            print("📋 Attached files:")
            for path in attachment_paths:
                print(f"   • {os.path.basename(path)}")
        else:
            print("\n❌ Failed to send email")
            
    except Exception as e:
        print(f"❌ Error in Agent 3: {e}")

if __name__ == '__main__':
    main() 