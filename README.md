# Agentic AI - Automated Product Scraping Workflow

A comprehensive web application that orchestrates 6 AI agents to automate product analysis, image extraction, text processing, QR code detection, and reporting.

## 🚀 Features

- **Multi-Agent Workflow**: 6 specialized agents working in sequence
- **Real-time Progress Tracking**: Live updates with Server-Sent Events
- **Amazon Product Scraping**: Automated product data extraction
- **Image Processing**: High-resolution image downloading and text extraction
- **QR Code Detection**: Automated QR/barcode scanning with redirect following
- **Contact Information Extraction**: Phone, email, and FSSAI number detection
- **Automated Reporting**: Email delivery of comprehensive Excel reports

## 🏗️ Architecture

### Frontend (Next.js)

- Modern React-based web interface
- Real-time progress tracking
- Responsive design with Tailwind CSS

### Backend (Python Scripts)

1. **Product Analyzer** - Scrapes Amazon product listings
2. **Image Scraper** - Downloads product images
3. **Text Extractor** - Uses Google Gemini Vision API for OCR
4. **QR Orchestrator** - Detects and processes QR codes/barcodes
5. **Credential Checker** - Merges data and extracts contact info
6. **Email Reporter** - Sends comprehensive reports

## 🛠️ Quick Start

### Prerequisites

- Node.js 18+
- Python 3.8+
- Google Chrome
- ChromeDriver

### Installation

1. **Clone and setup:**

```bash
git clone <repository>
cd agenticai
npm install
```

2. **Install Python dependencies:**

```bash
pip install -r requirements.txt
```

3. **Configure API keys:**

   - Update Gemini API key in `scripts/text_extractor.py`
   - Update email credentials in `scripts/exception_reporter.py`

4. **Start the application:**

```bash
npm run dev
```

5. **Open browser:**
   Navigate to `http://localhost:3000`

## 📋 Usage

1. **Select scraping site** (Currently Amazon only)
2. **Enter product name** (e.g., "aashirvaad")
3. **Choose output folder** for results
4. **Enter recipient email** for reports
5. **Click "Start Scraping"** and watch real-time progress

## 📊 Output Files

- `{product}_product_analysis.xlsx` - Product details and ITC classification
- `{product}_merged_analysis.xlsx` - Complete analysis with extracted text
- `qr_barcode_results_{timestamp}.xlsx` - QR/barcode detection results
- Individual product folders with images and text extraction results

## 🔧 Configuration

### Environment Variables

Create `.env.local` for sensitive data:

```
GEMINI_API_KEY=your_api_key
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
```

### Supported Platforms

- Currently: Amazon India
- Planned: Flipkart, BigBasket

## 📚 Documentation

See [SETUP.md](SETUP.md) for detailed setup instructions and troubleshooting.

## 🔒 Security

- Use environment variables for API keys
- Enable 2FA for email accounts
- Respect website terms of service
- Monitor API usage and rate limits

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues or questions:

- Check console output for errors
- Verify all dependencies are installed
- Ensure API keys are configured
- Review file permissions
