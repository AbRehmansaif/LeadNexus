from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Setup Chrome options (optional, headless mode)
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")  # comment out if you want to see the browser
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Setup ChromeDriver using webdriver-manager
service = Service(ChromeDriverManager().install())

# Launch browser
driver = webdriver.Chrome(service=service, options=chrome_options)

# Test
driver.get("https://www.google.com")
print("Title:", driver.title)

driver.quit()
