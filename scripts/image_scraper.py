"""
Agent 2: Image Scraper
======================
This agent is responsible for scraping high-resolution product images from Amazon.
It reads the product analysis Excel file from Agent 1, filters for ITC products,
and downloads all available images for each product into separate organized folders.

Features:
- Creates separate folders for each product
- Downloads all available product images in high resolution
- Updates Excel file with image counts
- Focuses only on image scraping (no OCR processing)
- Provides detailed progress tracking and logging
"""

import time
import os
import sys
import requests
import pandas as pd
import re
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
from io import BytesIO
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

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
    print("Usage: python image_scraper.py <output_folder>")
    sys.exit(1)

HOTFOLDER_PATH = sys.argv[1]

# Debug output to show paths being used
print(f"🔧 DEBUG: Image Scraper arguments received:")
print(f"   • Output Folder (Raw): {HOTFOLDER_PATH}")
print(f"   • Output Folder (Absolute): {os.path.abspath(HOTFOLDER_PATH)}")
print(f"   • Current Working Directory: {os.getcwd()}")
print("🔧 END DEBUG INFO\n")

# Setup paths - Find the product analysis Excel file dynamically
excel_files = [f for f in os.listdir(HOTFOLDER_PATH) if f.endswith('_product_analysis.xlsx')]
if not excel_files:
    print("❌ No product analysis Excel file found. Please run product_analyzer.py first.")
    sys.exit(1)

INPUT_EXCEL_FILE = excel_files[0]  # Use the first (should be only one) analysis file
INPUT_EXCEL_PATH = os.path.join(HOTFOLDER_PATH, INPUT_EXCEL_FILE)

# Try undetected_chromedriver first, fallback to regular selenium
driver = None
wait = None
try:
    if UC_AVAILABLE:
        options = uc.ChromeOptions()
        options.headless = False
        options.add_argument('--start-maximized')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        try:
            driver = uc.Chrome(options=options, version_main=None)
            wait = WebDriverWait(driver, 10)
            print("✅ Using undetected_chromedriver")
        except Exception as e:
            print(f"⚠️ Undetected_chromedriver failed: {e}")
            driver = None
    
    if driver is None:
        options = Options()
        options.add_argument('--start-maximized')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 10)
        print("✅ Using regular selenium webdriver")
        
except Exception as e:
    print(f"❌ Failed to initialize Chrome driver: {e}")
    exit(1)

def create_safe_folder_name(product_title, product_idx):
    """Create a safe folder name from product title"""
    # Remove/replace problematic characters for folder names
    safe_name = re.sub(r'[<>:"/\\|?*]', '', product_title)
    safe_name = re.sub(r'\s+', '_', safe_name.strip())
    safe_name = safe_name[:100]  # Limit length to avoid path issues
    
    # Add product index for uniqueness
    folder_name = f"product_{product_idx:03d}_{safe_name}"
    return folder_name

def scrape_product_images(product_url, product_title, product_idx, product_folder):
    """Scrape ALL high-resolution images from a product page using immersive view"""
    try:
        print(f"\n🛒 Scraping ALL images for: {product_title}")
        print(f"📁 Saving images to folder: {os.path.basename(product_folder)}")
        
        # Create product folder if it doesn't exist
        print(f"📁 Creating product folder: {product_folder}")
        print(f"📁 Absolute path: {os.path.abspath(product_folder)}")
        os.makedirs(product_folder, exist_ok=True)
        print(f"✅ Product folder created: {product_folder}")
        
        # Create a product info file in the folder
        info_file_path = os.path.join(product_folder, "product_info.txt")
        with open(info_file_path, 'w', encoding='utf-8') as f:
            f.write(f"Product Title: {product_title}\n")
            f.write(f"Product URL: {product_url}\n")
            f.write(f"Product Index: {product_idx}\n")
            f.write(f"Scraped on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        driver.get(product_url)
        time.sleep(3)

        images_downloaded = 0

        # Find all radio buttons with `+` in label to access immersive view
        radio_buttons = driver.find_elements(By.CSS_SELECTOR, "ul[aria-label='Image thumbnails'] li input[role='radio']")
        clicked = False

        print(f"🔘 Found {len(radio_buttons)} radio buttons in thumbnails")

        for radio in radio_buttons:
            try:
                label_id = radio.get_attribute("aria-labelledby")
                if label_id:
                    label_span = driver.find_element(By.ID, label_id)
                    label_text = label_span.text.strip()
                   
                    if "+" in label_text:
                        print(f"✅ Clicking radio with label: {label_text}")
                        driver.execute_script("arguments[0].click();", radio)
                        clicked = True
                        break
                else:
                    print("⚠️ Radio button has no aria-labelledby attribute")
                    
            except Exception as e:
                print(f"⚠️ Error checking radio button label: {e}")
                continue

        if not clicked:
            print("⚠️ No '+' radio button found, trying fallback approach...")
            
            # Fallback: try clicking "5+" overlay button
            try:
                overlay_button = driver.find_element(By.CSS_SELECTOR, 'li.overlayRestOfImages span.a-button input[role="radio"]')
                driver.execute_script("arguments[0].click();", overlay_button)
                print("✅ Clicked '5+' overlay button as fallback")
                clicked = True
                time.sleep(3)
            except:
                print("❌ No '5+' overlay button found either")
                
            if not clicked:
                print("❌ Could not access immersive view, skipping this product")
                return 0

        # Wait for immersive view to load
        time.sleep(3)

        # Find all immersive thumbnails
        thumbnail_divs = driver.find_elements(By.CSS_SELECTOR, "div.ivRow div.ivThumb")
        print(f"🖼️ Found {len(thumbnail_divs)} immersive thumbnails")

        if len(thumbnail_divs) == 0:
            # Try alternative selector for immersive thumbnails
            thumbnail_divs = driver.find_elements(By.CSS_SELECTOR, "div.ivThumbImage")
            print(f"🖼️ Found {len(thumbnail_divs)} thumbnails with alternative selector")

        for idx, thumb in enumerate(thumbnail_divs):
            try:
                print(f"🖱️ Clicking thumbnail {idx+1}/{len(thumbnail_divs)}")
                driver.execute_script("arguments[0].click();", thumb)
                time.sleep(2)  # Let the full-size image load

                try:
                    # Get fullscreen image
                    img = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img.fullscreen")))
                    img_url = img.get_attribute("src")
                   
                    if img_url:
                        response = requests.get(img_url, timeout=10)
                        image = Image.open(BytesIO(response.content))
                        filename = f"image_{idx+1:02d}.jpg"
                        img_path = os.path.join(product_folder, filename)
                        image.save(img_path)
                        print(f"✅ Saved immersive image {idx+1}: {filename} ({len(response.content)} bytes)")
                        images_downloaded += 1
                    else:
                        print(f"❌ Fullscreen image src not found for thumbnail {idx+1}")

                except Exception as e:
                    print(f"❌ Could not save image {idx+1}: {e}")
                    # Try alternative selector for the large image
                    try:
                        img_wrapper = driver.find_element(By.CSS_SELECTOR, "div.imgTagWrapper img")
                        large_image_url = img_wrapper.get_attribute("data-old-hires") or img_wrapper.get_attribute("src")
                        
                        if large_image_url:
                            response = requests.get(large_image_url, timeout=10)
                            filename = f"image_{idx+1:02d}_fallback.jpg"
                            img_path = os.path.join(product_folder, filename)
                            
                            with open(img_path, 'wb') as f:
                                f.write(response.content)
                            print(f"✅ Saved fallback image {idx+1}: {filename} ({len(response.content)} bytes)")
                            images_downloaded += 1
                        
                    except Exception as fallback_e:
                        print(f"❌ Fallback also failed for thumbnail {idx+1}: {fallback_e}")

            except Exception as e:
                print(f"❌ Failed to process thumbnail {idx+1}: {e}")

        print(f"📊 Downloaded {images_downloaded} total images for {product_title}")
        return images_downloaded

    except Exception as e:
        print(f"❌ Error scraping images for {product_title}: {e}")
        return 0

def main():
    try:
        # Check if analysis Excel file exists
        if not os.path.exists(INPUT_EXCEL_PATH):
            print(f"❌ Analysis Excel file not found: {INPUT_EXCEL_PATH}")
            print("Please run Agent 1 first to generate the product analysis file.")
            return

        # Read the analysis Excel file
        print(f"📊 Reading analysis Excel file: {INPUT_EXCEL_FILE}")
        df = pd.read_excel(INPUT_EXCEL_PATH)
        
        if 'ITC Product (Yes/No)' not in df.columns:
            print("❌ Excel file must have 'ITC Product (Yes/No)' column from Agent 1")
            return

        # Add 'no of images' column if it doesn't exist
        if 'no of images' not in df.columns:
            df['no of images'] = 0
            print("✅ Added 'no of images' column to track scraped images")
            # Save the updated Excel with new column
            df.to_excel(INPUT_EXCEL_PATH, index=False)
            print("💾 Excel file updated with new column")

        # Filter for ITC products only
        itc_products = df[df['ITC Product (Yes/No)'] == 'Yes'].copy()
        print(f"🎯 Found {len(itc_products)} ITC products to scrape images for")
        print(f"📸 This agent will only scrape images (no OCR processing)")

        if len(itc_products) == 0:
            print("❌ No ITC products found. Nothing to scrape.")
            return

        print("🔐 Logging into Amazon...")
        # Login to Amazon
        driver.get("https://www.amazon.in")
        time.sleep(5)

        # Handle popups
        try:
            continue_btn = driver.find_element(By.XPATH, '//button[@class="a-button-text" and @type="submit"]')
            continue_btn.click()
            print("✅ Clicked 'Continue shopping'")
            time.sleep(3)
        except:
            print("'Continue shopping' not found — skipping...")

        # Amazon login process
        try:
            driver.find_element(By.ID, "nav-link-accountList").click()
            time.sleep(3)
            print("✅ Clicked sign in")
        except Exception as e:
            print(f"❌ Failed to click sign in: {e}")

        try:
            email_input = driver.find_element(By.ID, "ap_email_login")
            email_input.send_keys("souvagyad6@gmail.com")
            driver.find_element(By.ID, "continue").click()
            time.sleep(3)
            print("✅ Entered email")
        except Exception as e:
            print(f"❌ Failed to enter email: {e}")

        try:
            time.sleep(2)
            password_input = None
            selectors_to_try = ["ap_password", "password", "signInPassword", "auth-password-input"]
            
            for selector in selectors_to_try:
                try:
                    password_input = driver.find_element(By.ID, selector)
                    print(f"✅ Found password field with ID: {selector}")
                    break
                except:
                    continue
            
            if password_input is None:
                try:
                    password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                    print("✅ Found password field by type")
                except:
                    print("❌ Could not find password field")
                    raise Exception("Password field not found")
            
            password_input.send_keys("P@ssw0rd")  # Replace with your password
            
            submit_selectors = ["signInSubmit", "auth-signin-button", "continue"]
            submit_clicked = False
            
            for submit_id in submit_selectors:
                try:
                    driver.find_element(By.ID, submit_id).click()
                    print(f"✅ Clicked submit button: {submit_id}")
                    submit_clicked = True
                    break
                except:
                    continue
            
            if not submit_clicked:
                try:
                    driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
                    print("✅ Clicked submit button by type")
                except:
                    print("❌ Could not find submit button")
            
            time.sleep(5)
            print("✅ Login completed")
            
        except Exception as e:
            print(f"❌ Login failed: {e}")
            print("Continuing without login - may have limited access")

        # Scrape images for each ITC product
        total_images = 0
        processed_count = 0
        print(f"\n📸 Starting image scraping for {len(itc_products)} ITC products...")
        
        for product_idx, (df_idx, row) in enumerate(itc_products.iterrows(), 1):
            product_url = row['url']
            product_title = row['title']
            
            # Create unique folder name for this product
            folder_name = create_safe_folder_name(product_title, product_idx)
            product_folder = os.path.join(HOTFOLDER_PATH, folder_name)
            
            print(f"\n🔍 Processing ITC product {product_idx}/{len(itc_products)}")
            print(f"📦 Product: {product_title}")
            print(f"📁 Folder: {folder_name}")
            
            images_count = scrape_product_images(product_url, product_title, product_idx, product_folder)
            total_images += images_count
            processed_count += 1
            
            # Update the original dataframe with image count
            df.at[df_idx, 'no of images'] = images_count
            
            # Save progress to Excel file after each product
            df.to_excel(INPUT_EXCEL_PATH, index=False)
            
            print(f"✅ Completed product {product_idx}: {images_count} images saved")
            print(f"💾 Updated Excel file with image count")
            
            # Small delay between products
            time.sleep(2)

        print(f"\n🎉 Completed image scraping!")
        print(f"📊 Summary:")
        print(f"   • ITC products processed: {processed_count}")
        print(f"   • Total images downloaded: {total_images}")
        print(f"   • Average images per product: {total_images/processed_count:.1f}" if processed_count > 0 else "   • No products processed")
        print(f"   • Images organized in separate folders under: {HOTFOLDER_PATH}")
        print(f"   • Each product has its own folder: product_XXX_ProductName")
        print(f"   • Excel file updated with image counts: {INPUT_EXCEL_FILE}")
        print(f"   • 📸 This agent only handles image scraping (no OCR processing)")

    except Exception as e:
        print(f"❌ Error in main process: {e}")
    
    finally:
        if driver:
            driver.quit()
        print("🔄 Browser closed")

if __name__ == '__main__':
    main() 