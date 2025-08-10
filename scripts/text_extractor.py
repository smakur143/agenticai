"""
Agent 3: Text Extractor
=======================
This agent processes image folders created by Agent 2, extracts text from each image
using Google's Gemini Vision API, and saves the results both locally and in the main Excel file.

Features:
- Processes all product folders created by Agent 2
- Extracts text from each image using Gemini 2.5 Flash
- Saves extracted text in local Excel files per folder
- Updates main Excel file with image text columns
- Handles API rate limiting and error recovery
- Provides detailed progress tracking
"""

import time
import os
import sys
import requests
import base64
import pandas as pd
import glob
from pathlib import Path

# CONFIGURATION
API_KEY = "AIzaSyBp_t3Qo6E1W6nzm6ryNGGIlfrdAdXl8tY"

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
    print("Usage: python text_extractor.py <output_folder>")
    sys.exit(1)

HOTFOLDER_PATH = sys.argv[1]

# Find the filtered products Excel file dynamically
excel_files = [f for f in os.listdir(HOTFOLDER_PATH) if f.endswith('_filtered_products.xlsx')]
if not excel_files:
    print("❌ No filtered products Excel file found. Please run product_analyzer.py first.")
    sys.exit(1)

INPUT_EXCEL_FILE = excel_files[0]  # Use the first (should be only one) filtered file
INPUT_EXCEL_PATH = os.path.join(HOTFOLDER_PATH, INPUT_EXCEL_FILE)

# PROMPT for text extraction

PROMPT = """
Extract all visible text from the provided image as accurately as possible. Carefully review the
extracted results before generating the response to ensure no text is missed or misinterpreted.
Do not hallucinate or assume any text that is not clearly visible.
Focus on product information, ingredients, nutritional facts, brand names, and any other text content.
"""

def encode_image_to_base64(image_path):
    """Convert image to base64 for API call"""
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        return base64.b64encode(image_bytes).decode("utf-8")
    except Exception as e:
        print(f"❌ Error encoding image {image_path}: {e}")
        return None

def call_gemini_flash(image_base64, prompt, max_retries=3):
    """Call Gemini API with retry logic"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    },
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": image_base64
                        }
                    }
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.RequestException as e:
            print(f"⚠️ API call failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return f"Error: API call failed after {max_retries} attempts"
        except Exception as e:
            print(f"❌ Unexpected error in API call: {e}")
            return f"Error: {str(e)}"

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
                time.sleep(attempt + 1)
            else:
                print(f"❌ Failed to save {file_path} after {max_retries} attempts")
                print("📝 Please close the Excel file and try again")
                return False
        except Exception as e:
            print(f"❌ Error saving {file_path}: {e}")
            return False
    return False

def process_product_folder(folder_path, product_name):
    """Process all images in a product folder and extract text"""
    print(f"\n📁 Processing folder: {product_name}")
    
    # Find all image files in the folder
    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp']
    image_files = []
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(folder_path, ext)))
    
    # Filter out any non-image files and sort
    image_files = [f for f in image_files if not f.endswith('product_info.txt')]
    image_files.sort()
    
    print(f"🖼️ Found {len(image_files)} images to process")
    
    if len(image_files) == 0:
        print("⚠️ No images found in folder")
        return []
    
    extracted_texts = []
    successful_extractions = 0
    
    for i, image_path in enumerate(image_files, 1):
        image_name = os.path.basename(image_path)
        print(f"🔍 Processing image {i}/{len(image_files)}: {image_name}")
        
        # Encode image to base64
        image_base64 = encode_image_to_base64(image_path)
        if not image_base64:
            extracted_texts.append(f"Error: Could not encode {image_name}")
            continue
        
        # Extract text using Gemini API
        extracted_text = call_gemini_flash(image_base64, PROMPT)
        extracted_texts.append(extracted_text)
        
        if not extracted_text.startswith("Error:"):
            successful_extractions += 1
            print(f"✅ Extracted text from {image_name} ({len(extracted_text)} characters)")
        else:
            print(f"❌ Failed to extract text from {image_name}")
        
        # Small delay to respect API rate limits
        time.sleep(1)
    
    # Save extracted texts to local Excel file
    local_excel_data = []
    for i, (image_file, text) in enumerate(zip(image_files, extracted_texts), 1):
        local_excel_data.append({
            'Image_Number': i,
            'Image_Name': os.path.basename(image_file),
            'Extracted_Text': text,
            'Character_Count': len(text) if not text.startswith("Error:") else 0
        })
    
    local_df = pd.DataFrame(local_excel_data)
    local_excel_path = os.path.join(folder_path, "extracted_text.xlsx")
    
    if save_excel_with_retry(local_df, local_excel_path):
        print(f"💾 Saved local Excel file: extracted_text.xlsx")
    else:
        print(f"❌ Failed to save local Excel file")
    
    print(f"📊 Successfully extracted text from {successful_extractions}/{len(image_files)} images")
    
    return extracted_texts

def update_main_excel(main_df, product_folders_data):
    """Update main Excel file with extracted text columns"""
    print(f"\n📊 Updating main Excel file with extracted text...")
    
    # Find the maximum number of images across all products
    max_images = max([len(texts) for texts in product_folders_data.values()]) if product_folders_data else 0
    
    # Add image text columns if they don't exist
    for i in range(1, max_images + 1):
        col_name = f"image {i}"
        if col_name not in main_df.columns:
            main_df[col_name] = ""
    
    # Update rows with extracted text using proper folder matching
    for folder_name, texts in product_folders_data.items():
        # Extract product index from folder name (e.g., "product_003_Name" -> 3)
        try:
            # Folder format: product_XXX_ProductName
            if folder_name.startswith('product_'):
                parts = folder_name.split('_')
                if len(parts) >= 2:
                    product_idx = int(parts[1])  # Extract the numeric index
                    
                    # Use 1-based indexing to match DataFrame rows (product_001 -> row 0)
                    df_row_idx = product_idx - 1
                    
                    if 0 <= df_row_idx < len(main_df):
                        # Update image columns for this product
                        for i, text in enumerate(texts, 1):
                            col_name = f"image {i}"
                            if col_name in main_df.columns:
                                # Limit text length for Excel and clean it
                                clean_text = str(text).replace('\n', ' ').replace('\r', ' ')[:1000]
                                main_df.at[df_row_idx, col_name] = clean_text
                        
                        product_title = main_df.at[df_row_idx, 'title'] if 'title' in main_df.columns else 'Unknown'
                        print(f"✅ Updated text for product {product_idx}: {product_title[:50]}...")
                    else:
                        print(f"⚠️ Product index {product_idx} out of range for folder: {folder_name}")
                else:
                    print(f"⚠️ Unexpected folder name format: {folder_name}")
            else:
                print(f"⚠️ Folder doesn't start with 'product_': {folder_name}")
                
        except (ValueError, IndexError) as e:
            print(f"❌ Error processing folder {folder_name}: {e}")
            # Fallback: try to match by title similarity (last resort)
            best_match_idx = None
            best_similarity = 0
            
            # Extract cleaned product name from folder
            folder_clean = folder_name.replace('product_', '').replace('_', ' ')
            folder_words = set(folder_clean.lower().split())
            
            for idx, row in main_df.iterrows():
                title = str(row.get('title', '')).lower()
                title_words = set(title.split())
                
                # Calculate word overlap similarity
                common_words = folder_words.intersection(title_words)
                similarity = len(common_words) / max(len(folder_words), len(title_words), 1)
                
                if similarity > best_similarity and similarity > 0.3:  # At least 30% similarity
                    best_similarity = similarity
                    best_match_idx = idx
            
            if best_match_idx is not None:
                # Update image columns for matched product
                for i, text in enumerate(texts, 1):
                    col_name = f"image {i}"
                    if col_name in main_df.columns:
                        clean_text = str(text).replace('\n', ' ').replace('\r', ' ')[:1000]
                        main_df.at[best_match_idx, col_name] = clean_text
                
                product_title = main_df.at[best_match_idx, 'title'] if 'title' in main_df.columns else 'Unknown'
                print(f"✅ Fallback match for {folder_name}: {product_title[:50]} (similarity: {best_similarity:.2f})")
            else:
                print(f"❌ No suitable match found for folder: {folder_name}")
    
    return main_df

def main():
    try:
        # Check if main Excel file exists
        if not os.path.exists(INPUT_EXCEL_PATH):
            print(f"❌ Main Excel file not found: {INPUT_EXCEL_PATH}")
            print("Please run Agent 2 first to generate the image scraping results.")
            return

        # Read the main Excel file
        print(f"📊 Reading main Excel file: {INPUT_EXCEL_FILE}")
        main_df = pd.read_excel(INPUT_EXCEL_PATH)
        
        # Find all product folders
        product_folders = []
        for item in os.listdir(HOTFOLDER_PATH):
            item_path = os.path.join(HOTFOLDER_PATH, item)
            if os.path.isdir(item_path) and item.startswith('product_'):
                product_folders.append(item_path)
        
        product_folders.sort()
        print(f"🗂️ Found {len(product_folders)} product folders to process")
        
        if len(product_folders) == 0:
            print("❌ No product folders found. Please run Agent 2 first.")
            return
        
        # Process each product folder
        product_folders_data = {}
        total_images_processed = 0
        
        for i, folder_path in enumerate(product_folders, 1):
            folder_name = os.path.basename(folder_path)
            print(f"\n🔄 Processing folder {i}/{len(product_folders)}")
            
            extracted_texts = process_product_folder(folder_path, folder_name)
            product_folders_data[folder_name] = extracted_texts
            total_images_processed += len(extracted_texts)
            
            # Small delay between folders
            time.sleep(2)
        
        # Update main Excel file with extracted text
        updated_df = update_main_excel(main_df, product_folders_data)
        
        # Save updated main Excel file
        if save_excel_with_retry(updated_df, INPUT_EXCEL_PATH):
            print(f"✅ Updated main Excel file: {INPUT_EXCEL_FILE}")
        else:
            print(f"❌ Failed to update main Excel file")
            # Save backup copy
            backup_path = INPUT_EXCEL_PATH.replace('.xlsx', '_backup.xlsx')
            if save_excel_with_retry(updated_df, backup_path):
                print(f"💾 Saved backup file: {os.path.basename(backup_path)}")
        
        # Final summary
        print(f"\n🎉 Completed text extraction!")
        print(f"📊 Summary:")
        print(f"   • Product folders processed: {len(product_folders)}")
        print(f"   • Total images processed: {total_images_processed}")
        print(f"   • Local Excel files created in each folder")
        print(f"   • Main Excel file updated with image text columns")
        print(f"   • 🤖 Used Gemini 2.5 Flash for text extraction")

    except Exception as e:
        print(f"❌ Error in main process: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main() 