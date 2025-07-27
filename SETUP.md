# Agentic AI Setup Guide

## Overview

This application provides an automated product scraping workflow with 6 AI agents that work together to analyze products, extract images, process text, detect QR codes, merge data, and send email reports.

## Prerequisites

### 1. Node.js and npm

- Install Node.js (v18 or later)
- Ensure npm is available

### 2. Python Environment

- Python 3.8 or later
- Install required Python packages:

```bash
pip install pandas selenium requests textblob nltk undetected-chromedriver opencv-python pyzbar pillow pymupdf fitz
```

### 3. Chrome Browser

- Install Google Chrome browser
- Download ChromeDriver and ensure it's in your PATH

### 4. Additional Setup

#### For text extraction (Gemini API):

- Get a Google Gemini API key
- Update the API key in `scripts/text_extractor.py`:

```python
API_KEY = "your_gemini_api_key_here"
```

#### For email functionality:

- Update email credentials in `scripts/exception_reporter.py`:

```python
SENDER_EMAIL = 'your_email@gmail.com'
SENDER_PASS = 'your_app_password'  # Use App Password for Gmail
```

## Installation

1. **Clone and setup the project:**

```bash
cd agenticai
npm install
```

2. **Install Python dependencies:**

```bash
pip install -r requirements.txt  # Create this file with the packages listed above
```

3. **Download NLTK data:**

```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"
```

## Running the Application

1. **Start the development server:**

```bash
npm run dev
```

2. **Open your browser:**
   Navigate to `http://localhost:3000`

3. **Fill in the form:**

   - **Site to scrape:** Currently only Amazon is supported
   - **Product name:** Enter the product you want to analyze (e.g., "aashirvaad")
   - **Output folder:** Choose where to save results (e.g., `C:\Users\YourName\Downloads\products`)
   - **Recipient email:** Email address to receive the final report

4. **Click "Start Scraping"**
   The application will show real-time progress as it runs through all 6 agents.

## Workflow Steps

### Agent 1: Product Analyzer (`product_analyzer.py`)

- Scrapes Amazon product listings
- Extracts product details, ratings, and specifications
- Determines if products are ITC brand
- Outputs: `{product_name}_product_analysis.xlsx`

### Agent 2: Image Scraper (`image_scraper.py`)

- Creates individual folders for each product
- Downloads all product images in high resolution
- Outputs: Organized folders with product images

### Agent 3: Text Extractor (`text_extractor.py`)

- Uses Google Gemini Vision API to extract text from images
- Creates local Excel files for each product folder
- Outputs: `extracted_text.xlsx` in each product folder

### Agent 4: QR Code Detector (`qr_orchestrator.py`)

- Detects QR codes and barcodes in all images
- Follows QR code redirects using Selenium
- Outputs: `qr_barcode_results_{timestamp}.xlsx`

### Agent 5: Data Merger (`credential_check.py`)

- Merges all extracted text data
- Detects contact information (phone, FSSAI, email)
- Outputs: `{product_name}_merged_analysis.xlsx`

### Agent 6: Email Reporter (`exception_reporter.py`)

- Sends email with all Excel files as attachments
- Provides comprehensive analysis summary

## Troubleshooting

### Common Issues:

1. **ChromeDriver not found:**

   - Download ChromeDriver from https://chromedriver.chromium.org/
   - Add to your system PATH

2. **Python module not found:**

   - Ensure all required packages are installed
   - Use virtual environment if needed

3. **Email sending fails:**

   - Use Gmail App Passwords instead of regular password
   - Enable 2-factor authentication on Gmail

4. **Permission denied on folder creation:**

   - Ensure the output folder path exists and is writable
   - Run with appropriate permissions

5. **Gemini API errors:**
   - Verify your API key is correct
   - Check API quota and usage limits

### Performance Tips:

- Use SSD storage for faster image processing
- Ensure stable internet connection for API calls
- Close unnecessary applications during scraping

## File Structure After Processing

```
output_folder/
├── {product_name}_product_analysis.xlsx
├── {product_name}_merged_analysis.xlsx
├── qr_barcode_results_{timestamp}.xlsx
├── product_001_ProductName1/
│   ├── image_01.jpg
│   ├── image_02.jpg
│   ├── extracted_text.xlsx
│   └── product_info.txt
├── product_002_ProductName2/
│   └── ...
└── ...
```

## Security Notes

- Keep your API keys secure and don't commit them to version control
- Use environment variables for sensitive credentials
- Be mindful of rate limits on APIs
- Respect website terms of service when scraping

## Support

For issues or questions:

1. Check the console output for detailed error messages
2. Verify all prerequisites are installed
3. Ensure network connectivity for API calls
4. Check file permissions in the output directory
