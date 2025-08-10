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
    print("❌ ERROR: Missing required output folder argument")
    sys.exit(1)

HOTFOLDER_PATH = sys.argv[1]

# Debug output to show paths being used
print(f"🔧 DEBUG: Image Scraper arguments received:")
print(f"   • Output Folder (Raw): {HOTFOLDER_PATH}")
print(f"   • Output Folder (Absolute): {os.path.abspath(HOTFOLDER_PATH)}")
print(f"   • Current Working Directory: {os.getcwd()}")
print("🔧 END DEBUG INFO\n")

# Setup paths - Find the filtered products Excel file dynamically
excel_files = [f for f in os.listdir(HOTFOLDER_PATH) if f.endswith('_filtered_products.xlsx')]
if not excel_files:
    print("❌ No filtered products Excel file found. Please run product_analyzer.py first.")
    sys.exit(1)

INPUT_EXCEL_FILE = excel_files[0]  # Use the first (should be only one) filtered file
INPUT_EXCEL_PATH = os.path.join(HOTFOLDER_PATH, INPUT_EXCEL_FILE)

# Try undetected_chromedriver first, fallback to regular selenium
driver = None
wait = None
try:
    if UC_AVAILABLE:
        print("🔧 Attempting to use undetected_chromedriver...")
        options = uc.ChromeOptions()
        options.add_argument('--headless')  # Run in headless mode for server environments
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--window-size=1920,1080')
        try:
            driver = uc.Chrome(options=options, version_main=None)
            wait = WebDriverWait(driver, 15)
            print("✅ Using undetected_chromedriver")
        except Exception as e:
            print(f"⚠️ Undetected_chromedriver failed: {e}")
            driver = None
    
    if driver is None:
        print("🔧 Attempting to use regular selenium webdriver...")
        options = Options()
        options.add_argument('--headless')  # Run in headless mode for server environments
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        try:
            driver = webdriver.Chrome(options=options)
            wait = WebDriverWait(driver, 15)
            print("✅ Using regular selenium webdriver")
        except Exception as e:
            print(f"❌ Failed to initialize regular Chrome driver: {e}")
            print("💡 Make sure Chrome/Chromium is installed and chromedriver is in PATH")
            print("💡 You may need to install: apt-get install -y chromium-browser chromium-chromedriver")
            sys.exit(1)
        
except Exception as e:
    print(f"❌ Failed to initialize Chrome driver: {e}")
    print("💡 This could be due to:")
    print("   • Chrome/Chromium not installed")
    print("   • ChromeDriver not found in PATH")
    print("   • Missing dependencies")
    print("   • Permission issues")
    sys.exit(1)

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
    """Scrape ALL high-resolution images from a product page using immersive view or fallback method"""
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
        used_immersive_view = False

        # Method 1: Try to find and click radio buttons with `+` in label to access immersive view
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
                        used_immersive_view = True
                        break
                else:
                    print("⚠️ Radio button has no aria-labelledby attribute")
                    
            except Exception as e:
                print(f"⚠️ Error checking radio button label: {e}")
                continue

        if not clicked:
            print("⚠️ No '+' radio button found, trying fallback approach...")
            
            # Fallback: try clicking "5+" or similar overlay button
            try:
                overlay_button = driver.find_element(By.CSS_SELECTOR, 'li.overlayRestOfImages span.a-button input[role="radio"]')
                driver.execute_script("arguments[0].click();", overlay_button)
                print("✅ Clicked overlay button as fallback")
                clicked = True
                used_immersive_view = True
                time.sleep(3)
            except:
                print("❌ No overlay button found either")

        # Method 2: If immersive view failed, try the new fallback method
        if not clicked:
            print("🔄 Trying alternative method: clicking on textMoreImages buttons...")
            
            # Look for radio buttons with textMoreImages span (like "9+")
            try:
                text_more_buttons = driver.find_elements(By.CSS_SELECTOR, "span.a-button-inner input[role='radio']")
                print(f"🔘 Found {len(text_more_buttons)} potential textMoreImages buttons")
                
                for button in text_more_buttons:
                    try:
                        # Check if this button has a textMoreImages span
                        parent_span = button.find_element(By.XPATH, "..")
                        text_more_span = parent_span.find_element(By.CSS_SELECTOR, "span.textMoreImages")
                        text_more_text = text_more_span.text.strip()
                        
                        if "+" in text_more_text:
                            print(f"✅ Found textMoreImages button with text: {text_more_text}")
                            driver.execute_script("arguments[0].click();", button)
                            clicked = True
                            time.sleep(3)
                            
                            # Now scrape the large image from imgTagWrapper
                            print("🖼️ Extracting large image from imgTagWrapper...")
                            try:
                                img_wrapper = driver.find_element(By.ID, "imgTagWrapperId")
                                large_img = img_wrapper.find_element(By.CSS_SELECTOR, "img")
                                
                                # Try to get the highest resolution image
                                img_url = large_img.get_attribute("data-old-hires") or large_img.get_attribute("src")
                                
                                if img_url:
                                    response = requests.get(img_url, timeout=10)
                                    if response.status_code == 200:
                                        filename = f"main_image.jpg"
                                        img_path = os.path.join(product_folder, filename)
                                        
                                        with open(img_path, 'wb') as f:
                                            f.write(response.content)
                                        print(f"✅ Saved main image: {filename} ({len(response.content)} bytes)")
                                        images_downloaded += 1
                                    else:
                                        print(f"❌ Failed to download image: HTTP {response.status_code}")
                                else:
                                    print("❌ No image URL found in imgTagWrapper")
                                    
                            except Exception as img_error:
                                print(f"❌ Error extracting image from imgTagWrapper: {img_error}")
                            
                            break
                            
                    except Exception as e:
                        # This button doesn't have textMoreImages, continue to next
                        continue
                
                if not clicked:
                    print("❌ No textMoreImages buttons found")
                    
            except Exception as e:
                print(f"❌ Error in textMoreImages fallback: {e}")

        # If we successfully accessed immersive view, scrape all images from it
        if used_immersive_view:
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
                            if response.status_code == 200:
                                image = Image.open(BytesIO(response.content))
                                filename = f"image_{idx+1:02d}.jpg"
                                img_path = os.path.join(product_folder, filename)
                                image.save(img_path)
                                print(f"✅ Saved immersive image {idx+1}: {filename} ({len(response.content)} bytes)")
                                images_downloaded += 1
                            else:
                                print(f"❌ Failed to download image {idx+1}: HTTP {response.status_code}")
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
                                if response.status_code == 200:
                                    filename = f"image_{idx+1:02d}_fallback.jpg"
                                    img_path = os.path.join(product_folder, filename)
                                    
                                    with open(img_path, 'wb') as f:
                                        f.write(response.content)
                                    print(f"✅ Saved fallback image {idx+1}: {filename} ({len(response.content)} bytes)")
                                    images_downloaded += 1
                                else:
                                    print(f"❌ Failed to download fallback image {idx+1}: HTTP {response.status_code}")
                            
                        except Exception as fallback_e:
                            print(f"❌ Fallback also failed for thumbnail {idx+1}: {fallback_e}")

                except Exception as e:
                    print(f"❌ Failed to process thumbnail {idx+1}: {e}")

        # If no images were downloaded, try to get at least the main product image
        if images_downloaded == 0:
            print("🔄 No images downloaded yet, trying to get main product image...")
            try:
                main_img = driver.find_element(By.CSS_SELECTOR, "img[data-a-image-name='landingImage']")
                img_url = main_img.get_attribute("data-old-hires") or main_img.get_attribute("src")
                
                if img_url:
                    response = requests.get(img_url, timeout=10)
                    if response.status_code == 200:
                        filename = "main_product_image.jpg"
                        img_path = os.path.join(product_folder, filename)
                        
                        with open(img_path, 'wb') as f:
                            f.write(response.content)
                        print(f"✅ Saved main product image: {filename} ({len(response.content)} bytes)")
                        images_downloaded += 1
                    else:
                        print(f"❌ Failed to download main image: HTTP {response.status_code}")
                else:
                    print("❌ No main product image URL found")
                    
            except Exception as e:
                print(f"❌ Failed to get main product image: {e}")

        print(f"📊 Downloaded {images_downloaded} total images for {product_title}")
        return images_downloaded

    except Exception as e:
        print(f"❌ Error scraping images for {product_title}: {e}")
        return 0

def main():
    try:
        # Validate output folder exists
        if not os.path.exists(HOTFOLDER_PATH):
            print(f"❌ Output folder does not exist: {HOTFOLDER_PATH}")
            print("Please ensure the output folder path is correct.")
            sys.exit(1)
        
        # Check if filtered products Excel file exists
        if not os.path.exists(INPUT_EXCEL_PATH):
            print(f"❌ Filtered products Excel file not found: {INPUT_EXCEL_PATH}")
            print("Please run product_analyzer.py first to generate the filtered products file.")
            sys.exit(1)

        # Read the filtered products Excel file
        print(f"📊 Reading filtered products Excel file: {INPUT_EXCEL_FILE}")
        try:
            df = pd.read_excel(INPUT_EXCEL_PATH)
            print(f"✅ Successfully loaded Excel file with {len(df)} rows")
        except Exception as e:
            print(f"❌ Failed to read Excel file: {e}")
            print("🔧 Make sure the Excel file is not open in another application")
            sys.exit(1)
        
        # Add 'no of images' column if it doesn't exist
        if 'no of images' not in df.columns:
            df['no of images'] = 0
            print("✅ Added 'no of images' column to track scraped images")
            # Save the updated Excel with new column
            df.to_excel(INPUT_EXCEL_PATH, index=False)
            print("💾 Excel file updated with new column")

        # Use all products from filtered file (no need to filter further)
        products_to_scrape = df.copy()
        print(f"🎯 Found {len(products_to_scrape)} filtered products to scrape images for")
        print(f"📸 This agent will scrape images from all products in the filtered list")

        if len(products_to_scrape) == 0:
            print("❌ No products found in filtered file. Nothing to scrape.")
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

        # Skip Amazon login for now - proceed without authentication
        # Note: This limits access to some features but avoids login issues
        print("⚠️ Skipping Amazon login - proceeding without authentication")
        print("💡 To enable login, configure proper credentials via environment variables")
        
        # Optional: Check if we can access the site without login
        try:
            # Test basic Amazon access
            current_url = driver.current_url
            print(f"✅ Successfully accessed Amazon: {current_url}")
        except Exception as e:
            print(f"⚠️ Warning: Basic Amazon access test failed: {e}")

        # Scrape images for each filtered product
        total_images = 0
        processed_count = 0
        print(f"\n📸 Starting image scraping for {len(products_to_scrape)} filtered products...")
        
        for product_idx, (df_idx, row) in enumerate(products_to_scrape.iterrows(), 1):
            product_url = row['url']
            product_title = row['title']
            
            # Create unique folder name for this product
            folder_name = create_safe_folder_name(product_title, product_idx)
            product_folder = os.path.join(HOTFOLDER_PATH, folder_name)
            
            print(f"\n🔍 Processing filtered product {product_idx}/{len(products_to_scrape)}")
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
        print(f"   • Filtered products processed: {processed_count}")
        print(f"   • Total images downloaded: {total_images}")
        print(f"   • Average images per product: {total_images/processed_count:.1f}" if processed_count > 0 else "   • No products processed")
        print(f"   • Images organized in separate folders under: {HOTFOLDER_PATH}")
        print(f"   • Each product has its own folder: product_XXX_ProductName")
        print(f"   • Excel file updated with image counts: {INPUT_EXCEL_FILE}")
        print(f"   • 📸 Scraped images from all products in filtered list")

    except Exception as e:
        print(f"❌ Error in main process: {e}")
    
    finally:
        if driver:
            driver.quit()
        print("🔄 Browser closed")

if __name__ == '__main__':
    main() 