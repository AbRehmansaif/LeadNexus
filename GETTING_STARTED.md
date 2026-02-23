# 🚀 Getting Started with LinkedIn Data Scraper

Welcome! This guide will help you get up and running with the LinkedIn Data Scraper in just a few minutes.

## 📋 Prerequisites

Before you begin, make sure you have:

- ✅ **Python 3.8 or higher** installed ([Download here](https://www.python.org/downloads/))
- ✅ **Google Chrome** browser installed
- ✅ **Internet connection**
- ✅ Basic command line knowledge

## 🎯 Quick Start (3 Steps)

### Step 1: Run Setup

Double-click `setup.bat` or run in command prompt:

```bash
setup.bat
```

This will:
- Create a virtual environment
- Install all dependencies
- Create your config file

**Expected output:**
```
[1/4] Creating virtual environment...
[2/4] Activating virtual environment...
[3/4] Installing dependencies...
[4/4] Creating configuration file...
Setup Complete!
```

### Step 2: Configure (Optional)

Edit `config.json` to customize settings:

```json
{
  "scraping": {
    "max_profiles": 50,
    "headless": true
  }
}
```

**Most users can skip this step and use defaults!**

### Step 3: Run the Scraper

**Option A: Interactive Mode (Recommended for beginners)**

Double-click `run.bat` and select from preset niches:

```
1. Software Developers (50 profiles)
2. Digital Marketers (50 profiles)
3. Sales Professionals (50 profiles)
4. Data Scientists (50 profiles)
5. Custom niche
```

**Option B: Command Line (For advanced users)**

```bash
# Activate virtual environment
venv\Scripts\activate

# Run scraper
python main.py --niche "your niche here" --max-profiles 50
```

## 📊 What Happens Next?

1. **Browser Opens**: Chrome will open and navigate to LinkedIn
2. **Search**: The tool searches for profiles matching your niche
3. **Scraping**: Profiles are scraped one by one (with delays)
4. **Website Visits**: Associated websites are visited and scraped
5. **Data Saved**: Results are saved in the `data/` folder

**Progress indicators will show:**
```
Scraping LinkedIn profiles: 100%|████████| 50/50 [04:30<00:00]
Scraping websites: 100%|████████| 35/35 [02:15<00:00]
```

## 📁 Finding Your Results

After scraping completes, check the `data/` folder:

```
data/
├── software_developer_linkedin_20260208_015530.csv
├── software_developer_website_20260208_015530.csv
├── software_developer_combined_20260208_015530.csv
├── software_developer_20260208_015530.json
└── software_developer_20260208_015530.xlsx
```

**Open the `combined` CSV file to see all data in one place!**

## 💡 Example Use Cases

### Use Case 1: Finding Software Developers

```bash
python main.py --niche "python developer" --max-profiles 50
```

**Result:** 50 Python developer profiles with contact info

### Use Case 2: Digital Marketing Agencies

```bash
python main.py --niche "digital marketing agency" --max-profiles 100
```

**Result:** 100 agency profiles with websites and social media

### Use Case 3: Sales Leads in Specific Location

```bash
python main.py --niche "sales manager new york" --max-profiles 75
```

**Result:** 75 sales managers in New York with contact details

## ⚙️ Common Configurations

### Scrape More Profiles

```bash
python main.py --niche "your niche" --max-profiles 100
```

### Skip Website Scraping (Faster)

```bash
python main.py --niche "your niche" --no-websites
```

### Custom Output Directory

```bash
python main.py --niche "your niche" --output ./my_data
```

### Run in Visible Browser Mode (See What's Happening)

Edit `config.json`:
```json
{
  "scraping": {
    "headless": false
  }
}
```

## 🔧 Troubleshooting

### Problem: "Python not found"

**Solution:** Install Python from [python.org](https://www.python.org/downloads/)

Make sure to check "Add Python to PATH" during installation!

### Problem: "ChromeDriver error"

**Solution:** 
1. Make sure Chrome browser is installed
2. Update Chrome to the latest version
3. The script will auto-download the correct ChromeDriver

### Problem: "No profiles found"

**Solution:**
1. Try a different, more specific niche
2. Check your internet connection
3. Try running without `--headless` to see what's happening

### Problem: "Import errors"

**Solution:**
```bash
# Reinstall dependencies
venv\Scripts\activate
pip install -r requirements.txt --force-reinstall
```

### Problem: Getting blocked by LinkedIn

**Solution:**
1. Increase delays in `config.json`:
   ```json
   {
     "scraping": {
       "delay_min": 5,
       "delay_max": 10
     }
   }
   ```
2. Reduce number of profiles
3. Take breaks between scraping sessions

## 📖 Understanding the Output

### CSV Files

**LinkedIn Data:**
- Name, Headline, Location
- Company, Profile URL
- Website, Email, Phone

**Website Data:**
- Contact Email, Phone
- Social Media Links
- Physical Address

**Combined Data:**
- All LinkedIn + Website data merged

### JSON File

Contains all data plus metadata:
```json
{
  "metadata": {
    "total_linkedin_profiles": 50,
    "total_websites_scraped": 35
  },
  "linkedin_data": [...],
  "website_data": [...],
  "combined_data": [...]
}
```

### Excel File

Multi-sheet workbook:
- Sheet 1: LinkedIn Data
- Sheet 2: Website Data
- Sheet 3: Combined Data

## 🎓 Best Practices

### 1. Start Small
```bash
# Test with 10 profiles first
python main.py --niche "test" --max-profiles 10
```

### 2. Use Specific Niches
- ✅ Good: "python developer san francisco"
- ❌ Bad: "developer"

### 3. Respect Rate Limits
- Don't scrape thousands of profiles at once
- Take breaks between sessions
- Use appropriate delays

### 4. Verify Data
- Always review the output files
- Check for data quality
- Validate contact information

### 5. Legal Compliance
- Use for legitimate business purposes only
- Respect privacy laws (GDPR, etc.)
- Consider using LinkedIn's official API for production

## 📞 Need Help?

### Check the Documentation
- `README.md` - Project overview
- `QUICKSTART.md` - Detailed usage guide
- `WORKFLOW.md` - How it works
- `PROJECT_STRUCTURE.md` - Technical details

### Check the Logs
- Logs are saved in `logs/` folder
- Look for error messages
- Check timestamps to find relevant logs

### Common Questions

**Q: How long does it take?**
A: About 8-15 seconds per profile. 50 profiles = ~10-15 minutes

**Q: Can I run multiple instances?**
A: Not recommended. LinkedIn may detect and block you.

**Q: Is this legal?**
A: This is for educational purposes. For production, use LinkedIn's API.

**Q: Can I scrape my own connections?**
A: Yes, but still respect rate limits and terms of service.

**Q: What if I get interrupted?**
A: Press Ctrl+C to stop. Data collected so far will be saved.

## 🎉 Next Steps

Now that you're set up:

1. ✅ Run your first scrape with a small niche
2. ✅ Review the output files
3. ✅ Adjust configuration as needed
4. ✅ Scale up to your target number of profiles
5. ✅ Use the data for your business needs

## ⚠️ Important Reminders

- 🔒 **Privacy**: Handle collected data responsibly
- ⚖️ **Legal**: Ensure compliance with applicable laws
- 🤝 **Ethics**: Use for legitimate business purposes
- 🚦 **Rate Limits**: Don't abuse the system
- 📝 **Terms**: LinkedIn's ToS prohibits automated scraping

---

**Ready to start?** Run `setup.bat` now! 🚀

For detailed documentation, see `QUICKSTART.md` and `README.md`.
