import urllib.parse

class B2BPurifier:
    """
    Utility to filter out non-business websites (blogs, SaaS, news, directories, etc.)
    Keeps only real B2B companies, service providers, agencies, and e-commerce brands.
    """
    BLOCKLIST = {
        # Major Marketing/SEO Platforms & Tools
        'hubspot.com', 'semrush.com', 'moz.com', 'ahrefs.com', 'mailchimp.com', 'hootsuite.com', 'buffer.com', 
        'sproutsocial.com', 'constantcontact.com', 'activecampaign.com', 'sendinblue.com', 'getresponse.com',
        'convertkit.com', 'drip.com', 'klaviyo.com', 'omnisend.com', 'aweber.com',
        
        # Content Publishers / News / Media
        'forbes.com', 'entrepreneur.com', 'inc.com', 'fastcompany.com', 'techcrunch.com', 'mashable.com', 
        'wired.com', 'theguardian.com', 'nytimes.com', 'wsj.com', 'bbc.com', 'cnn.com', 'reuters.com', 
        'bloomberg.com', 'huffpost.com', 'businessinsider.com', 'theverge.com', 'engadget.com', 'gizmodo.com',
        'lifehacker.com', 'vice.com', 'buzzfeed.com', 'vox.com', 'slate.com', 'salon.com', 'thedailybeast.com',
        'politico.com', 'theatlantic.com', 'time.com', 'newsweek.com', 'usatoday.com', 'washingtonpost.com',
        'latimes.com', 'nypost.com', 'cnbc.com', 'axios.com', 'propublica.org',
        
        # Marketing Blogs/Resources/Publications
        'neilpatel.com', 'backlinko.com', 'searchenginejournal.com', 'searchengineland.com', 'marketingland.com', 
        'socialmediaexaminer.com', 'contentmarketinginstitute.com', 'copyblogger.com', 'wordstream.com', 
        'convinceandconvert.com', 'ducttapemarketing.com', 'marketingprofs.com', 'adweek.com', 'adage.com',
        'martechtoday.com', 'chiefmarketer.com', 'clickz.com', 'practicalecommerce.com', 'smartinsights.com',
        'socialmediatoday.com', 'contentmarketingworld.com', 'blog.kissmetrics.com', 'groovehq.com',
        
        # SaaS/Tools/Software Platforms
        'salesforce.com', 'monday.com', 'asana.com', 'trello.com', 'slack.com', 'canva.com', 'figma.com', 
        'adobe.com', 'shopify.com', 'wix.com', 'squarespace.com', 'zoom.us', 'intercom.com', 'zendesk.com',
        'typeform.com', 'calendly.com', 'notion.so', 'airtable.com', 'clickup.com', 'basecamp.com', 'jira.com',
        'confluence.com', 'dropbox.com', 'box.com', 'evernote.com', 'grammarly.com', 'loom.com', 'miro.com',
        'zapier.com', 'ifttt.com', 'integromat.com', 'make.com', 'pipedrive.com', 'hubspot.com', 'freshworks.com',
        'zoho.com', 'microsoft.com', 'google.com', 'apple.com', 'atlassian.com', 'oracle.com', 'sap.com',
        'stripe.com', 'paypal.com', 'square.com', 'quickbooks.com', 'xero.com', 'freshbooks.com',
        
        # Website Builders / Hosting / Domain Services
        'wordpress.com', 'blogspot.com', 'blogger.com', 'tumblr.com', 'weebly.com', 'webflow.com', 'carrd.co',
        'bluehost.com', 'siteground.com', 'hostgator.com', 'godaddy.com', 'namecheap.com', 'domain.com',
        'digitalocean.com', 'cloudflare.com', 'hostinger.com', 'dreamhost.com', 'a2hosting.com', 'inmotionhosting.com',
        'medium.com', 'substack.com', 'ghost.org', 'wordpress.org',
        
        # Directories/Reviews/Comparison Sites
        'yelp.com', 'trustpilot.com', 'g2.com', 'capterra.com', 'clutch.co', 'goodfirms.co', 'designrush.com', 
        'tripadvisor.com', 'glassdoor.com', 'yellowpages.com', 'angieslist.com', 'bbb.org', 'crunchbase.com',
        'thumbtack.com', 'houzz.com', 'bark.com', 'porch.com', 'homeadvisor.com', 'angi.com', 'trustradius.com',
        'gartner.com', 'forrester.com', 'softwareadvice.com', 'getapp.com', 'saasworthy.com', 'producthunt.com',
        'alternativeto.net', 'similarweb.com', 'builtwith.com', 'manta.com', 'superpages.com',
        
        # Freelance/Gig Marketplaces
        'upwork.com', 'fiverr.com', 'freelancer.com', 'toptal.com', 'guru.com', '99designs.com', 'designcrowd.com',
        'peopleperhour.com', 'flexjobs.com', 'contently.com', 'cloudpeeps.com', 'workana.com',
        
        # Forums/Communities/Q&A
        'reddit.com', 'quora.com', 'stackoverflow.com', 'stackexchange.com', 'discord.com', 'discord.gg',
        'askubuntu.com', 'superuser.com', 'serverfault.com', 'warriorforum.com', 'blackhatworld.com',
        'digitalpoint.com', 'wickedfire.com', 'seomastering.com', 'webmasterworld.com',
        
        # Wiki / Educational / Reference
        'wikipedia.org', 'wikihow.com', 'fandom.com', 'wikia.com', 'investopedia.com', 'dictionary.com',
        'britannica.com', 'encyclopedia.com', 'reference.com', 'answers.com',
        
        # Job Boards / HR Platforms
        'indeed.com', 'linkedin.com', 'monster.com', 'careerbuilder.com', 'ziprecruiter.com', 'dice.com',
        'simplyhired.com', 'workable.com', 'greenhouse.io', 'lever.co', 'bamboohr.com', 'gusto.com',
        
        # Affiliate / Coupon / Deal Sites
        'slickdeals.net', 'retailmenot.com', 'groupon.com', 'coupons.com', 'dealnews.com', 'offers.com',
        'rakuten.com', 'honey.com', 'wikibuy.com', 'pcpartpicker.com', 'camelcamelcamel.com',
        
        # Social Media Platforms
        'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com', 'tiktok.com', 'snapchat.com',
        'pinterest.com', 'tumblr.com', 'vimeo.com', 'dailymotion.com', 'twitch.tv',
        
        # Developer / Code Platforms
        'github.com', 'gitlab.com', 'bitbucket.org', 'codepen.io', 'jsfiddle.net', 'replit.com',
        'codesandbox.io', 'glitch.com', 'stackblitz.com', 'npmjs.com', 'pypi.org',
        
        # Design Resources / Stock Sites
        'dribbble.com', 'behance.net', 'unsplash.com', 'pexels.com', 'pixabay.com', 'freepik.com',
        'shutterstock.com', 'istockphoto.com', 'gettyimages.com', 'depositphotos.com', 'envato.com',
        'themeforest.net', 'creativemarket.com', 'graphicriver.net',
        
        # E-learning / Course Platforms
        'udemy.com', 'coursera.org', 'edx.org', 'skillshare.com', 'lynda.com', 'linkedin.com/learning',
        'pluralsight.com', 'codecademy.com', 'treehouse.com', 'udacity.com', 'masterclass.com',
        'brilliant.org', 'khanacademy.org',
        
        # Analytics / Data Platforms
        'analytics.google.com', 'mixpanel.com', 'amplitude.com', 'heap.io', 'segment.com', 'kissmetrics.com',
        'crazyegg.com', 'hotjar.com', 'fullstory.com', 'logrocket.com',
    }
    
    BAD_KEYWORDS = [
        # URL path indicators
        '/blog/', '/blog', '/news/', '/article/', '/post/', '/posts/', '/guide/', '/guides/', 
        '/resources/', '/learn/', '/tutorial/', '/tutorials/', '/tips/', '/how-to/', '/magazine/',
        '/press/', '/media/', '/wiki/', '/forum/', '/community/', '/review/', '/reviews/',
        '/directory/', '/listing/', '/compare/', '/vs/', '/best-of/', '/top-10/', '/affiliate/',
        
        # Subdomain indicators
        'blog.', 'news.', 'magazine.', 'portal.', 'forum.', 'community.', 'help.', 'support.',
        'learn.', 'resources.', 'kb.', 'wiki.', 'docs.', 'developer.', 'dev.',
        
        # Content site patterns
        '/price-comparison', '/deals/', '/coupons/', '/offers/', '/promotions/',
        '/rankings/', '/ratings/', '/testimonial/', '/case-study/', '/whitepaper/',
        '/ebook/', '/download/', '/free-', '/template/', '/tool/',
    ]
    
    # Additional patterns to exclude
    EXCLUDED_PATTERNS = [
        '.blogspot.', '.wordpress.', '.medium.', '.substack.', '.ghost.', '.tumblr.',
        '.wixsite.', '.weebly.', '.webflow.', '.carrd.', '.notion.site',
    ]

    @classmethod
    def is_safe_b2b(cls, url: str) -> bool:
        """
        Returns True if the URL likely belongs to a real B2B company/service.
        Returns False if it's a blog, news site, SaaS platform, or directory.
        """
        if not url:
            return False
            
        url_lower = url.lower()
        
        # 1. Clean URL to get base domain
        try:
            parsed = urllib.parse.urlparse(url_lower)
            domain = parsed.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
        except:
            return False
            
        # 2. Check hardcoded blocklist
        if domain in cls.BLOCKLIST:
            return False
            
        # 3. Check for excluded patterns (subdomain providers)
        if any(pattern in url_lower for pattern in cls.EXCLUDED_PATTERNS):
            return False

        # 4. Check for major subdomains or paths
        if any(keyword in url_lower for keyword in cls.BAD_KEYWORDS):
            return False
            
        # 5. Check for common social/search noise
        noise = ['google.', 'facebook.', 'twitter.', 'instagram.', 'youtube.', 'linkedin.', 'pinterest.', 'github.']
        if any(n in domain for n in noise):
            return False
            
        return True
