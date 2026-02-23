# LinkedIn Data Scraper Tool

A Python-based tool for collecting business information from LinkedIn profiles and their associated websites.

## ⚠️ Legal Disclaimer

This tool is for **educational purposes only**. LinkedIn's Terms of Service prohibit automated scraping. For production use:
- Use LinkedIn's official API
- Ensure compliance with GDPR and data protection laws
- Obtain proper consent before collecting personal data
- Respect robots.txt and rate limits

## Features

- 🔍 Search LinkedIn for profiles in specific niches
- 📊 Extract LinkedIn profile data (contact, email, website, location)
- 🌐 Visit associated websites and extract additional data
- 💾 Store data in CSV and JSON formats
- 🔄 Rate limiting and error handling
- 📝 Comprehensive logging

## Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. Copy `config.example.json` to `config.json`
2. Update the configuration with your settings:
   - LinkedIn credentials (if using authenticated scraping)
   - Search parameters
   - Rate limits
   - Output preferences

## Usage

### Basic Usage

```bash
python main.py --niche "software development" --max-profiles 50
```

### Advanced Usage

```bash
# Specify output directory
python main.py --niche "digital marketing" --output ./data --max-profiles 100

# Use custom config file
python main.py --config custom_config.json

# Resume from previous session
python main.py --resume
```

## Project Structure

```
Scrapper/
├── main.py                 # Main entry point
├── config.json            # Configuration file
├── requirements.txt       # Python dependencies
├── scrapers/
│   ├── __init__.py
│   ├── linkedin_scraper.py    # LinkedIn scraping logic
│   └── website_scraper.py     # Website scraping logic
├── utils/
│   ├── __init__.py
│   ├── data_storage.py        # Data storage utilities
│   ├── logger.py              # Logging configuration
│   └── validators.py          # Data validation
└── data/                      # Output directory
    ├── linkedin_data.csv
    ├── website_data.csv
    └── combined_data.json
```

## Data Fields Collected

### LinkedIn Data
- Name
- Headline
- Location
- Profile URL
- Company
- Website
- Email (if available)
- Phone (if available)

### Website Data
- Contact Email
- Contact Phone
- Facebook URL
- Twitter URL
- LinkedIn URL
- Instagram URL
- Address

## Rate Limiting

The tool implements intelligent rate limiting to avoid detection:
- Random delays between requests (2-5 seconds)
- Exponential backoff on errors
- Maximum requests per hour limit

## Error Handling

- Automatic retry on failed requests
- Session persistence
- Detailed error logging
- Graceful degradation

## Contributing

This is an educational project. Feel free to fork and modify for learning purposes.

## License

MIT License - See LICENSE file for details
