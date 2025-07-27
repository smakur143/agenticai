"""
Agent 4: Text Merger & Contact Extractor
========================================
This agent merges extracted text Excel files from product folders with the main input file,
creates image columns for each extracted text, and performs phone number and FSSAI detection.

Features:
- Merges extracted text from all product folders
- Creates image 1, image 2, etc. columns in main Excel
- Detects phone numbers, emails, and FSSAI numbers
- Provides contact detection summary
- Saves enhanced Excel with all information
"""

import os
import sys
import pandas as pd
import glob
import re
from pathlib import Path

# Configure UTF-8 encoding for console output (fixes Windows Unicode issues)
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    # Python < 3.7 doesn't have reconfigure, try setting environment variable
    import locale
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

# Get parameters from command line
if len(sys.argv) < 2:
    print("Usage: python credential_check.py <output_folder>")
    sys.exit(1)

HOTFOLDER_PATH = sys.argv[1]

# Find the product analysis Excel file dynamically
excel_files = [f for f in os.listdir(HOTFOLDER_PATH) if f.endswith('_product_analysis.xlsx')]
if not excel_files:
    print("❌ No product analysis Excel file found. Please run previous agents first.")
    sys.exit(1)

INPUT_EXCEL_FILE = excel_files[0]
INPUT_EXCEL_PATH = os.path.join(HOTFOLDER_PATH, INPUT_EXCEL_FILE)

# Extract product name from the Excel file name to create output file name
product_name = INPUT_EXCEL_FILE.replace('_product_analysis.xlsx', '')
OUTPUT_EXCEL_FILE = f"{product_name}_merged_analysis.xlsx"
OUTPUT_EXCEL_PATH = os.path.join(HOTFOLDER_PATH, OUTPUT_EXCEL_FILE)

def classify_text(text):
    """Extract phone numbers, emails, and FSSAI numbers from text"""
    if not text or pd.isna(text):
        return {
            "Toll-free/Mobile Numbers": [],
            "Emails": [],
            "FSSAI Numbers": [],
            "Other Numbers": []
        }
    
    # Convert to string and clean
    text = str(text).strip()
    
    # Patterns
    mobile_pattern = r"\b1[89]00(?:\s\d{3}){3}\b"   # Matches 1800 425 444 444 or 1860 123 456 789
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    fssai_pattern = r"\b\d{14}\b"
    other_number_pattern = r"\b\d{10,}\b"  # Catch any long numbers that are NOT FSSAI or toll-free format

    # Extract main categories
    mobiles = re.findall(mobile_pattern, text)
    emails = re.findall(email_pattern, text)
    fssai_numbers = re.findall(fssai_pattern, text)

    # Extract all long numbers
    all_numbers = re.findall(other_number_pattern, text)

    # Remove already matched FSSAI numbers and toll-free from "others"
    others = list(set(all_numbers) - set(fssai_numbers) - set(["".join(re.findall(r"\d", m)) for m in mobiles]))

    return {
        "Toll-free/Mobile Numbers": mobiles,
        "Emails": emails,
        "FSSAI Numbers": fssai_numbers,
        "Other Numbers": others
    }

def create_contact_summary(classified_data):
    """Create a summary of what contact information was found"""
    mobiles = classified_data.get("Toll-free/Mobile Numbers", [])
    emails = classified_data.get("Emails", [])
    fssai = classified_data.get("FSSAI Numbers", [])
    others = classified_data.get("Other Numbers", [])
    
    summary_parts = []
    
    if fssai:
        summary_parts.append(f"FSSAI Found: {', '.join(fssai)}")
    
    if mobiles:
        summary_parts.append(f"Phone Found: {', '.join(mobiles)}")
    
    if emails:
        summary_parts.append(f"Email Found: {', '.join(emails)}")
    
    if others:
        summary_parts.append(f"Other Numbers: {', '.join(others)}")
    
    if not summary_parts:
        return "No contact info found"
    
    return " | ".join(summary_parts)

def create_safe_folder_name(product_title, product_idx):
    """Create a safe folder name from product title"""
    safe_name = re.sub(r'[<>:"/\\|?*]', '', product_title)
    safe_name = re.sub(r'\s+', '_', safe_name.strip())
    safe_name = safe_name[:100]  # Limit length
    folder_name = f"product_{product_idx:03d}_{safe_name}"
    return folder_name

def find_matching_folder(product_title, product_folders):
    """Find the matching product folder for a given product title"""
    # Try exact matches first
    for folder_path in product_folders:
        folder_name = os.path.basename(folder_path)
        if product_title.lower().replace(' ', '_') in folder_name.lower():
            return folder_path
    
    # Try partial matches with first few words
    title_words = product_title.split()[:3]  # First 3 words
    for folder_path in product_folders:
        folder_name = os.path.basename(folder_path).lower()
        if any(word.lower() in folder_name for word in title_words if len(word) > 3):
            return folder_path
    
    return None

def load_extracted_text_from_folder(folder_path):
    """Load extracted text data from a product folder"""
    extracted_text_file = os.path.join(folder_path, "extracted_text.xlsx")
    
    if not os.path.exists(extracted_text_file):
        print(f"⚠️ No extracted_text.xlsx found in {os.path.basename(folder_path)}")
        return {}
    
    try:
        df = pd.read_excel(extracted_text_file)
        
        # Create dictionary mapping image number to extracted text
        image_texts = {}
        for _, row in df.iterrows():
            image_num = row.get('Image_Number', 0)
            extracted_text = row.get('Extracted_Text', '')
            if image_num and extracted_text:
                image_texts[f"image {image_num}"] = extracted_text
        
        return image_texts
        
    except Exception as e:
        print(f"❌ Error reading extracted text from {folder_path}: {str(e)}")
        return {}

def save_excel_with_retry(df, file_path, max_retries=5):
    """Save Excel file with retry logic for permission errors"""
    for attempt in range(max_retries):
        try:
            df.to_excel(file_path, index=False)
            return True
        except PermissionError:
            if attempt < max_retries - 1:
                print(f"⚠️ Permission denied saving {file_path}. Retrying in {attempt + 1} seconds...")
                print("💡 Please close the Excel file if it's open and wait...")
                import time
                time.sleep(attempt + 1)
            else:
                print(f"❌ Failed to save {file_path} after {max_retries} attempts")
                return False
        except Exception as e:
            print(f"❌ Error saving {file_path}: {e}")
            return False
    return False

def main():
    """Main execution function for text merging and contact extraction"""
    print("📋 Text Merger & Contact Extractor Agent Starting...")
    
    # Check if main Excel file exists
    if not os.path.exists(INPUT_EXCEL_PATH):
        print(f"❌ Main Excel file not found: {INPUT_EXCEL_PATH}")
        print("Please run previous agents first.")
        return
    
    # Read the main Excel file
    print(f"📊 Reading main Excel file: {INPUT_EXCEL_FILE}")
    try:
        main_df = pd.read_excel(INPUT_EXCEL_PATH)
        print(f"✅ Loaded {len(main_df)} products from main Excel")
    except Exception as e:
        print(f"❌ Error reading main Excel file: {e}")
        return
    
    # Find all product folders
    product_folders = []
    for item in os.listdir(HOTFOLDER_PATH):
        item_path = os.path.join(HOTFOLDER_PATH, item)
        if os.path.isdir(item_path) and item.startswith('product_'):
            product_folders.append(item_path)
    
    product_folders.sort()
    print(f"🗂️ Found {len(product_folders)} product folders")
    
    if len(product_folders) == 0:
        print("❌ No product folders found. Please run Agent 2 (Image Scraper) and Agent 3 (Text Extractor) first.")
        return
    
    # Determine maximum number of images across all folders
    max_images = 0
    for folder_path in product_folders:
        image_texts = load_extracted_text_from_folder(folder_path)
        if image_texts:
            folder_max = max([int(key.split()[1]) for key in image_texts.keys()])
            max_images = max(max_images, folder_max)
    
    print(f"📸 Maximum images found in any folder: {max_images}")
    
    # Add image columns to main dataframe if they don't exist
    for i in range(1, max_images + 1):
        col_name = f"image {i}"
        if col_name not in main_df.columns:
            main_df[col_name] = ""
    
    # Add contact detection columns
    if 'phone_fssai_check' not in main_df.columns:
        main_df['phone_fssai_check'] = ""
    
    # Process each product
    processed_count = 0
    matched_count = 0
    
    for idx, row in main_df.iterrows():
        product_title = str(row.get('title', ''))
        print(f"\n🔍 Processing product {idx+1}/{len(main_df)}: {product_title[:50]}...")
        
        # Find matching folder
        matching_folder = find_matching_folder(product_title, product_folders)
        
        if matching_folder:
            matched_count += 1
            folder_name = os.path.basename(matching_folder)
            print(f"✅ Found matching folder: {folder_name}")
            
            # Load extracted text from folder
            image_texts = load_extracted_text_from_folder(matching_folder)
            
            if image_texts:
                print(f"📝 Found extracted text for {len(image_texts)} images")
                
                # Update image columns
                all_extracted_text = []
                for image_col, text in image_texts.items():
                    if image_col in main_df.columns:
                        main_df.at[idx, image_col] = text
                        all_extracted_text.append(text)
                
                # Analyze all extracted text for contact information
                combined_text = " ".join(all_extracted_text)
                classified_data = classify_text(combined_text)
                contact_summary = create_contact_summary(classified_data)
                main_df.at[idx, 'phone_fssai_check'] = contact_summary
                
                print(f"📞 Contact detection: {contact_summary}")
            else:
                print("⚠️ No extracted text data found in folder")
                main_df.at[idx, 'phone_fssai_check'] = "No text data available"
        else:
            print("❌ No matching folder found")
            main_df.at[idx, 'phone_fssai_check'] = "No folder match"
        
        processed_count += 1
    
    # Save the merged Excel file
    if save_excel_with_retry(main_df, OUTPUT_EXCEL_PATH):
        print(f"\n💾 Saved merged analysis to: {OUTPUT_EXCEL_FILE}")
        print(f"📊 Excel file location: {OUTPUT_EXCEL_PATH}")
    else:
        print(f"\n❌ Failed to save merged Excel file")
        return
    
    # Final summary
    print(f"\n🎉 Text merging and contact extraction completed!")
    print(f"📊 Summary:")
    print(f"   • Products processed: {processed_count}")
    print(f"   • Products with matching folders: {matched_count}")
    print(f"   • Image columns added: {max_images}")
    print(f"   • Contact detection performed for all products")
    print(f"   • Output file: {OUTPUT_EXCEL_FILE}")
    print(f"\n📋 New columns added:")
    print(f"   • image 1, image 2, ... image {max_images}: Extracted text from images")
    print(f"   • phone_fssai_check: Contact information summary")

if __name__ == '__main__':
    main() 