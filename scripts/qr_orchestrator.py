"""
Agent 2: QR Code & Barcode Orchestrator
=======================================
This agent scans product folders for .jpg images, detects QR codes and barcodes, and saves
consolidated results in a single Excel file.

Features:
- Processes all product folders from image scraper
- Detects QR codes and barcodes in .jpg images
- For QR codes: Extracts URLs and follows redirects using Selenium
- For barcodes: Extracts decoded data (no redirect checking)
- Creates code snapshots with appropriate naming
- Saves consolidated results in Excel format with detailed columns
- No external server dependencies - runs standalone
"""

import time
import os
import sys
import pandas as pd
import glob
import cv2
from pyzbar import pyzbar
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from datetime import datetime

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
    print("Usage: python qr_orchestrator.py <output_folder>")
    sys.exit(1)

HOTFOLDER_PATH = sys.argv[1]

# Legacy inputs/paths and PDF helpers removed (processing .jpg only)

def detect_codes_and_decode(image):
    """Detect both QR codes and barcodes using pyzbar"""
    try:
        # Convert BGR to RGB for pyzbar
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Detect all codes (QR codes and barcodes)
        codes = pyzbar.decode(rgb_image)
        
        results = []
        for code in codes:
            if not code.data:
                continue
                
            # Decode the data
            data = code.data.decode('utf-8')
            
            # Determine if it's a QR code or barcode based on content and type
            code_type = code.type
            is_qr_code = (code_type == 'QRCODE') or is_url_like(data)
            
            # Get bounding box and crop the code area
            rect = code.rect
            x_min, y_min = rect.left, rect.top
            x_max, y_max = rect.left + rect.width, rect.top + rect.height
            
            # Crop the code from the image
            code_crop = rgb_image[y_min:y_max, x_min:x_max]
            
            # Convert back to BGR for saving
            code_crop_bgr = cv2.cvtColor(code_crop, cv2.COLOR_RGB2BGR)
            
            results.append((data, code_crop_bgr, code_type, is_qr_code))
            
        return results
        
    except Exception as e:
        print(f"❌ Error in code detection: {str(e)}")
        return []

def is_url_like(data):
    """Check if the decoded data looks like a URL"""
    url_indicators = ['http://', 'https://', 'www.', '.com', '.org', '.net', '.in', '.co']
    data_lower = data.lower()
    return any(indicator in data_lower for indicator in url_indicators)

def get_redirected_url(url, driver):
    """Get redirected URL using Selenium with 10-second loading wait"""
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        print(f"🌐 Loading URL: {url[:50]}...")
        driver.get(url)
        
        # Wait for 10 seconds to allow the page to fully load
        print("⏳ Waiting 10 seconds for URL to load...")
        time.sleep(10)
        
        # Check if URL has changed (redirected)
        final_url = driver.current_url
        if final_url != url:
            print(f"🔄 Redirected to: {final_url[:50]}...")
        else:
            print("✅ No redirect detected")
            
        return final_url
    except Exception as e:
        print(f"❌ Error loading URL: {str(e)}")
        return f"Redirect Error: {str(e)}"

def process_product_folders_for_qr(driver):
    """Process all product folders for QR detection"""
    print("🔍 Starting QR detection in product folders...")
    
    # Find all product folders
    product_folders = []
    for item in os.listdir(HOTFOLDER_PATH):
        item_path = os.path.join(HOTFOLDER_PATH, item)
        if os.path.isdir(item_path) and item.startswith('product_'):
            product_folders.append(item_path)
    
    product_folders.sort()
    print(f"🗂️ Found {len(product_folders)} product folders to scan")
    
    if len(product_folders) == 0:
        print("❌ No product folders found. Please run Agent 2 (Image Scraper) first.")
        return []
    
    all_results = []
    total_images = 0
    total_qr_codes = 0
    
    for i, folder_path in enumerate(product_folders, 1):
        folder_name = os.path.basename(folder_path)
        print(f"\n📁 Processing folder {i}/{len(product_folders)}: {folder_name}")
        
        # Find all supported files in this folder (images and PDFs)
        file_extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp', '*.pdf']
        all_files = []
        for ext in file_extensions:
            all_files.extend(glob.glob(os.path.join(folder_path, ext)))
        
        # Filter and sort files
        all_files = [f for f in all_files if not f.endswith('product_info.txt') and 'qr_snapshot' not in f]
        all_files.sort()
        
        print(f"🖼️ Found {len(all_files)} .jpg images to scan for QR codes and barcodes")
        
        folder_code_count = 0
        for file_path in all_files:
            file_name = os.path.basename(file_path)
            print(f"🔍 Scanning: {file_name}")
            
            try:
                # Read .jpg image
                print(f"🖼️ Processing image: {file_name}")
                image = cv2.imread(file_path)
                if image is None:
                    raise Exception(f"Could not read image file: {file_name}")
                
                # Detect QR codes and barcodes
                code_results = detect_codes_and_decode(image)
                
                if code_results:
                    folder_code_count += 1
                    total_qr_codes += 1
                    
                    for code_idx, (data, code_image, code_type, is_qr_code) in enumerate(code_results):
                        # Save code snapshot
                        base_name = file_name.rsplit('.', 1)[0]
                        if is_qr_code:
                            snap_name = f"{base_name}_qr_{code_idx+1}.jpg"
                            print(f"✅ QR code found: {data[:50]}...")
                        else:
                            snap_name = f"{base_name}_barcode_{code_idx+1}.jpg"
                            print(f"✅ Barcode found ({code_type}): {data}")
                        
                        snap_path = os.path.join(folder_path, snap_name)
                        cv2.imwrite(snap_path, code_image)
                        
                        # Get redirected URL only for QR codes/URLs
                        if is_qr_code:
                            redirected_url = get_redirected_url(data, driver)
                        else:
                            redirected_url = 'N/A (Barcode)'
                        
                        all_results.append({
                            'folder_name': folder_name,
                            'image_name': file_name,
                            'code_detected': 'Yes',
                            'code_type': code_type,
                            'is_qr_code': 'Yes' if is_qr_code else 'No',
                            'data': data,
                            'redirected_url': redirected_url,
                            'code_snapshot': snap_name
                        })
                        
                        break  # Only process first code per file
                else:
                    all_results.append({
                        'folder_name': folder_name,
                        'image_name': file_name,
                        'code_detected': 'No',
                        'code_type': '',
                        'is_qr_code': '',
                        'data': 'No code detected',
                        'redirected_url': '',
                        'code_snapshot': ''
                    })
                    print(f"❌ No codes found")
                    
            except Exception as e:
                print(f"❌ Error processing {file_name}: {str(e)}")
                all_results.append({
                    'folder_name': folder_name,
                    'image_name': file_name,
                    'code_detected': 'No',
                    'code_type': '',
                    'is_qr_code': '',
                    'data': f'Error: {str(e)}',
                    'redirected_url': '',
                    'code_snapshot': ''
                })
            
            total_images += 1
        
        print(f"✅ Folder complete: {folder_code_count} codes found in {len(all_files)} files")
    
    print(f"\n📊 Code Detection Summary:")
    print(f"   • Product folders processed: {len(product_folders)}")
    print(f"   • Total files scanned: {total_images}")
    print(f"   • Codes detected (QR + Barcodes): {total_qr_codes}")
    print(f"   • Code detection rate: {(total_qr_codes/total_images*100):.1f}%" if total_images > 0 else "   • No files processed")
    
    return all_results

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
                return False
        except Exception as e:
            print(f"❌ Error saving {file_path}: {e}")
            return False
    return False

def main():
    """Main execution function for QR code and barcode detection"""
    print("🔍 QR Code & Barcode Detection Agent Starting...")
    print("📋 Standalone detection - supports QR codes and barcodes - no external servers required")
    
    # Check if product folders exist
    if not os.path.exists(HOTFOLDER_PATH):
        print(f"❌ Hotfolder not found: {HOTFOLDER_PATH}")
        print("Please run Agent 2 (Image Scraper) first.")
        return
    
    # Setup browser for redirect checking
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-web-security')
    
    print('🌐 Launching browser for URL redirect checking...')
    try:
        driver = webdriver.Chrome(options=chrome_options)
        print('✅ Browser launched successfully')
    except Exception as e:
        print(f'❌ Failed to launch browser: {e}')
        return
    
    try:
        # Process all product folders for QR detection
        all_results = process_product_folders_for_qr(driver)
        
        if all_results:
            # Create consolidated Excel file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            code_results_file = f"qr_barcode_results_{timestamp}.xlsx"
            code_results_path = os.path.join(HOTFOLDER_PATH, code_results_file)
            
            df = pd.DataFrame(all_results)
            
            if save_excel_with_retry(df, code_results_path):
                print(f"\n💾 Saved consolidated code detection results to: {code_results_file}")
                print(f"📊 Excel file location: {code_results_path}")
            else:
                print(f"\n❌ Failed to save code detection results Excel file")
        else:
            print("\n⚠️ No results to save - no product folders found or processed")

        print('\n🎉 QR code and barcode detection completed successfully!')
        print('📋 Excel Results include:')
        print('   • folder_name: Product folder name')
        print('   • image_name: File name (image)')
        print('   • code_detected: Yes/No if any code found')
        print('   • code_type: Type of code (QRCODE, CODE128, EAN13, etc.)')
        print('   • is_qr_code: Yes if QR code, No if barcode')
        print('   • data: Decoded data (URL for QR, number for barcode)')
        print('   • redirected_url: Final URL (only for QR codes)')
        print('   • code_snapshot: Code image snapshot filename')

    except Exception as e:
        print(f'❌ Failed during QR detection process: {e}')
        import traceback
        traceback.print_exc()
    finally:
        # Close browser
        if 'driver' in locals():
            driver.quit()
        print('🔄 Browser closed - QR detection complete.')

if __name__ == '__main__':
    main() 