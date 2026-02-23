# LinkedIn Data Scraper - Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                  LINKEDIN DATA SCRAPER WORKFLOW                  │
└─────────────────────────────────────────────────────────────────┘

                            ┌──────────┐
                            │  START   │
                            └────┬─────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Initialize Scrapers    │
                    │  • Chrome WebDriver     │
                    │  • Load Configuration   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Search LinkedIn       │
                    │   • Enter niche         │
                    │   • Find profiles       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Extract Profile URLs   │
                    │  • Collect URLs         │
                    │  • Max: 50 profiles     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ Scrape LinkedIn Data    │
                    │ ┌─────────────────────┐ │
                    │ │ • Name              │ │
                    │ │ • Headline          │ │
                    │ │ • Location          │ │
                    │ │ • Company           │ │
                    │ │ • Website URL       │ │
                    │ │ • Email             │ │
                    │ │ • Phone             │ │
                    │ └─────────────────────┘ │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Has Website URL?       │
                    └────┬────────────────┬───┘
                         │ Yes            │ No
                         │                │
              ┌──────────▼──────────┐     │
              │  Visit Website      │     │
              │  • Find contact     │     │
              │  • Parse pages      │     │
              └──────────┬──────────┘     │
                         │                │
              ┌──────────▼──────────┐     │
              │ Extract Website Data│     │
              │ ┌─────────────────┐ │     │
              │ │ • Email         │ │     │
              │ │ • Phone         │ │     │
              │ │ • Facebook      │ │     │
              │ │ • Twitter       │ │     │
              │ │ • Instagram     │ │     │
              │ │ • Address       │ │     │
              │ └─────────────────┘ │     │
              └──────────┬──────────┘     │
                         │                │
                         └────────┬───────┘
                                  │
                     ┌────────────▼────────────┐
                     │   Combine All Data      │
                     │   • Merge LinkedIn +    │
                     │     Website data        │
                     └────────────┬────────────┘
                                  │
                     ┌────────────▼────────────┐
                     │   Save to Files         │
                     │   ┌──────────────────┐  │
                     │   │ • CSV files      │  │
                     │   │ • JSON file      │  │
                     │   │ • Excel file     │  │
                     │   └──────────────────┘  │
                     └────────────┬────────────┘
                                  │
                            ┌─────▼─────┐
                            │    END    │
                            └───────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         OUTPUT FILES                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📄 {niche}_linkedin_{timestamp}.csv                            │
│     → LinkedIn profile data only                                │
│                                                                  │
│  📄 {niche}_website_{timestamp}.csv                             │
│     → Website data only                                         │
│                                                                  │
│  📄 {niche}_combined_{timestamp}.csv                            │
│     → Combined LinkedIn + Website data                          │
│                                                                  │
│  📄 {niche}_{timestamp}.json                                    │
│     → All data in JSON format with metadata                     │
│                                                                  │
│  📄 {niche}_{timestamp}.xlsx                                    │
│     → Multi-sheet Excel workbook                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      KEY FEATURES                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✓ Automated LinkedIn profile search                            │
│  ✓ Extract contact information                                  │
│  ✓ Visit and scrape associated websites                         │
│  ✓ Intelligent rate limiting                                    │
│  ✓ Multiple output formats (CSV, JSON, Excel)                   │
│  ✓ Error handling and retry logic                               │
│  ✓ Detailed logging                                             │
│  ✓ Configurable settings                                        │
│  ✓ Resume on interruption                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Example

```
LinkedIn Profile
├── Name: "John Doe"
├── Headline: "Software Engineer at Tech Corp"
├── Location: "San Francisco, CA"
├── Company: "Tech Corp"
├── Website: "https://techcorp.com"
└── Profile URL: "https://linkedin.com/in/johndoe"
         │
         │ (Visit Website)
         ▼
Website Data
├── Email: "contact@techcorp.com"
├── Phone: "+1-555-0123"
├── Facebook: "https://facebook.com/techcorp"
├── Twitter: "https://twitter.com/techcorp"
└── Address: "123 Tech St, San Francisco, CA"
         │
         │ (Combine)
         ▼
Combined Entry
├── Name: "John Doe"
├── Headline: "Software Engineer at Tech Corp"
├── Location: "San Francisco, CA"
├── Company: "Tech Corp"
├── LinkedIn URL: "https://linkedin.com/in/johndoe"
├── Website: "https://techcorp.com"
├── Website Email: "contact@techcorp.com"
├── Website Phone: "+1-555-0123"
├── Facebook: "https://facebook.com/techcorp"
├── Twitter: "https://twitter.com/techcorp"
└── Address: "123 Tech St, San Francisco, CA"
```

## Rate Limiting Strategy

```
Request 1 → [2-5s delay] → Request 2 → [2-5s delay] → Request 3
     │                           │                         │
     └─ Random delay             └─ Random delay          └─ Random delay
        Appears human-like          Avoids detection         Prevents blocking
```

## Error Handling

```
Try Scrape Profile
     │
     ├─ Success → Save Data
     │
     └─ Failure → Retry (max 3 times)
              │
              ├─ Success → Save Data
              │
              └─ Final Failure → Log Error & Continue
```
