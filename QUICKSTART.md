# LinkedIn Data Scraper - Quick Start Guide

## 🚀 Quick Start

### 1. Setup (First Time Only)

Run the setup script:
```bash
setup.bat
```

This will:
- Create a virtual environment
- Install all dependencies
- Create a config.json file

### 2. Configure

Edit `config.json` to customize your settings:

```json
{
  "scraping": {
    "max_profiles": 50,
    "delay_min": 2,
    "delay_max": 5,
    "headless": true
  },
  "data": {
    "output_dir": "./data",
    "save_csv": true,
    "save_json": true,
    "save_excel": true
  }
}
```

### 3. Run

Activate the virtual environment:
```bash
venv\Scripts\activate
```

Run the scraper:
```bash
python main.py --niche "software development" --max-profiles 50
```

## 📋 Command Line Options

```bash
python main.py --help
```

### Required Arguments:
- `--niche`: The niche or keyword to search for
  - Example: `--niche "digital marketing"`

### Optional Arguments:
- `--max-profiles`: Maximum number of profiles to scrape (default: 50)
- `--config`: Path to config file (default: config.json)
- `--output`: Output directory (default: ./data)
- `--no-websites`: Skip website scraping
- `--headless`: Run browser in headless mode

## 💡 Usage Examples

### Basic Usage
```bash
# Search for software developers
python main.py --niche "software developer"

# Search for digital marketers with custom limit
python main.py --niche "digital marketing" --max-profiles 100
```

### Advanced Usage
```bash
# Custom output directory
python main.py --niche "web design" --output ./my_data

# Skip website scraping (LinkedIn only)
python main.py --niche "sales" --no-websites

# Run in headless mode (no browser window)
python main.py --niche "consulting" --headless
```

### Multiple Niches
```bash
# Run for different niches
python main.py --niche "python developer"
python main.py --niche "react developer"
python main.py --niche "data scientist"
```

## 📊 Output Files

The scraper creates three types of files in the output directory:

### 1. CSV Files
- `{niche}_linkedin_{timestamp}.csv` - LinkedIn profile data
- `{niche}_website_{timestamp}.csv` - Website data
- `{niche}_combined_{timestamp}.csv` - Combined data

### 2. JSON File
- `{niche}_{timestamp}.json` - All data in JSON format with metadata

### 3. Excel File
- `{niche}_{timestamp}.xlsx` - Multi-sheet Excel workbook

## 📁 Data Fields

### LinkedIn Data
- Name
- Headline
- Location
- Profile URL
- Company
- Website
- Email (if available)
- Phone (if available)
- About section

### Website Data
- Contact Email
- Contact Phone
- Facebook URL
- Twitter URL
- Instagram URL
- LinkedIn URL
- Physical Address

## ⚙️ Configuration Options

### Scraping Settings
```json
"scraping": {
  "max_profiles": 50,        // Maximum profiles to scrape
  "delay_min": 2,            // Minimum delay between requests (seconds)
  "delay_max": 5,            // Maximum delay between requests (seconds)
  "timeout": 30,             // Request timeout (seconds)
  "max_retries": 3,          // Maximum retry attempts
  "headless": true,          // Run browser in headless mode
  "user_agent": "..."        // Custom user agent
}
```

### Website Scraping
```json
"website_scraping": {
  "enabled": true,           // Enable/disable website scraping
  "timeout": 15,             // Request timeout (seconds)
  "max_depth": 2,            // Maximum pages to visit per website
  "follow_links": [          // Page types to visit
    "contact",
    "about",
    "team"
  ]
}
```

### Data Output
```json
"data": {
  "output_dir": "./data",    // Output directory
  "save_csv": true,          // Save as CSV
  "save_json": true,         // Save as JSON
  "save_excel": true         // Save as Excel
}
```

## 🔧 Troubleshooting

### Chrome Driver Issues
If you get ChromeDriver errors:
1. The script auto-downloads ChromeDriver
2. Make sure Chrome browser is installed
3. Try updating Chrome to the latest version

### Rate Limiting
If you're getting blocked:
1. Increase `delay_min` and `delay_max` in config
2. Reduce `max_profiles`
3. Use `--headless` mode less frequently
4. Consider using LinkedIn API for production

### No Data Found
If no profiles are found:
1. Try a different niche/keyword
2. Make the search term more specific
3. Check if LinkedIn is accessible
4. Try without `--headless` to see what's happening

### Import Errors
If you get import errors:
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

## ⚠️ Important Notes

### Legal Compliance
- This tool is for **educational purposes only**
- LinkedIn's Terms of Service prohibit automated scraping
- For production use, use LinkedIn's official API
- Ensure GDPR compliance when collecting personal data
- Always respect robots.txt and rate limits

### Best Practices
1. **Start Small**: Test with `--max-profiles 10` first
2. **Use Delays**: Don't set delays too low
3. **Respect Limits**: Don't scrape thousands of profiles
4. **Check Data**: Review output files for quality
5. **Save Progress**: The tool auto-saves on interruption (Ctrl+C)

### Rate Limiting
- Default delays: 2-5 seconds between requests
- Recommended: Don't scrape more than 50-100 profiles per session
- Take breaks between scraping sessions
- Use random delays to appear more human-like

## 📝 Logs

Logs are saved in the `logs/` directory:
- Console output shows INFO level and above
- Log files contain DEBUG level for troubleshooting
- Each run creates a new log file with timestamp

## 🛑 Stopping the Scraper

To stop the scraper gracefully:
1. Press `Ctrl+C`
2. The scraper will save collected data
3. Files will be saved with `_partial` suffix

## 📞 Support

For issues or questions:
1. Check the logs in `logs/` directory
2. Review the configuration in `config.json`
3. Try running with fewer profiles first
4. Check that all dependencies are installed

## 🔄 Updates

To update the scraper:
```bash
# Activate virtual environment
venv\Scripts\activate

# Update dependencies
pip install -r requirements.txt --upgrade
```

## 🎯 Tips for Better Results

1. **Use Specific Niches**: "Python Developer" vs "Developer"
2. **Target Locations**: Add location filters in LinkedIn search
3. **Check Profiles**: Review a few profiles manually first
4. **Verify Data**: Always verify extracted data before using
5. **Combine Sources**: Use multiple data sources for accuracy

Happy Scraping! 🚀

📈 Performance
⏱️ Speed: ~8-15 seconds per profile
📊 Capacity: 50-100 profiles per session (recommended)
💾 Memory: ~200-500 MB
🌐 Network: Moderate bandwidth usage

🔧 Technologies Used
Selenium - Browser automation
BeautifulSoup4 - HTML parsing
Requests - HTTP requests
Pandas - Data processing
openpyxl - Excel export
colorlog - Colored logging
tqdm - Progress bars