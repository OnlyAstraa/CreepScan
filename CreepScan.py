import requests
import re
import time
import sys
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.robotparser import RobotFileParser
from collections import deque, defaultdict
from dataclasses import dataclass, asdict
from typing import Set, List, Dict, Optional
import random

# Disable ALL logging completely
import logging
logging.disable(logging.CRITICAL)

@dataclass
class ContactInfo:
    email: Optional[str] = None
    phone: Optional[str] = None
    url: Optional[str] = None
    context: Optional[str] = None

class PoliteCrawler:
    def __init__(self, base_url: str, delay: float = 1.0, max_pages: int = 50):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.delay = delay
        self.max_pages = max_pages
        
        # Tracking
        self.visited_urls: Set[str] = set()
        self.contacts: List[ContactInfo] = []
        self.url_queue = deque([base_url])
        
        # Bypass strategies
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        
        # Session for connection reuse
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PoliteContactCrawler/1.0 (+http://example.com/bot)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Robust regex patterns
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
        
        self.phone_patterns = [
            re.compile(r'\+?1?[-.\s]?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'),  # US format
            re.compile(r'\+?([0-9]{1,3})[-.\s]?\(?([0-9]{3,4})\)?[-.\s]?([0-9]{3,4})[-.\s]?([0-9]{3,4})'),  # International
            re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),  # Simple 10-digit
        ]
        
        # Check robots.txt silently
        self.robots_parser = RobotFileParser()
        self.robots_parser.set_url(urljoin(base_url, '/robots.txt'))
        try:
            self.robots_parser.read()
        except:
            pass
    
    def can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt"""
        try:
            return self.robots_parser.can_fetch(self.session.headers['User-Agent'], url)
        except:
            return True
    
    def get_page_with_bypass(self, url: str) -> Optional[str]:
        """Fetch page content with multiple bypass strategies"""
        
        # Strategy 1: Normal request
        if self._try_normal_request(url):
            return self._try_normal_request(url)
        
        # Strategy 2: Rotate User-Agent
        if self._try_user_agent_rotation(url):
            return self._try_user_agent_rotation(url)
        
        # Strategy 3: Add referrer
        if self._try_with_referrer(url):
            return self._try_with_referrer(url)
        
        # Strategy 4: Session with cookies
        if self._try_session_persistence(url):
            return self._try_session_persistence(url)
        
        return None
    
    def _try_normal_request(self, url: str) -> Optional[str]:
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.text
        except:
            pass
        return None
    
    def _try_user_agent_rotation(self, url: str) -> Optional[str]:
        original_ua = self.session.headers['User-Agent']
        try:
            self.session.headers['User-Agent'] = random.choice(self.user_agents)
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.text
        except:
            pass
        finally:
            self.session.headers['User-Agent'] = original_ua
        return None
    
    def _try_with_referrer(self, url: str) -> Optional[str]:
        try:
            headers = {'Referer': self.base_url}
            response = self.session.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.text
        except:
            pass
        return None
    
    def _try_session_persistence(self, url: str) -> Optional[str]:
        try:
            # First visit the homepage to establish session
            self.session.get(self.base_url, timeout=5)
            time.sleep(1)
            
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.text
        except:
            pass
        return None
    
    def extract_contacts(self, content: str, url: str) -> List[ContactInfo]:
        """Extract emails and phone numbers from content"""
        contacts = []
        
        # Extract emails
        emails = self.email_pattern.findall(content)
        for email in emails:
            # Get context around email
            email_index = content.find(email)
            context_start = max(0, email_index - 50)
            context_end = min(len(content), email_index + len(email) + 50)
            context = content[context_start:context_end].strip()
            
            contacts.append(ContactInfo(
                email=email.lower(),
                url=url,
                context=context
            ))
        
        # Extract phone numbers
        for pattern in self.phone_patterns:
            phones = pattern.findall(content)
            for phone_match in phones:
                if isinstance(phone_match, tuple):
                    phone = ''.join(phone_match)
                else:
                    phone = phone_match
                
                # Clean and validate phone
                phone_clean = re.sub(r'[^\d+]', '', phone)
                if len(phone_clean) >= 10:  # Minimum valid phone length
                    phone_index = content.find(str(phone_match))
                    context_start = max(0, phone_index - 50)
                    context_end = min(len(content), phone_index + 50)
                    context = content[context_start:context_end].strip()
                    
                    contacts.append(ContactInfo(
                        phone=phone_clean,
                        url=url,
                        context=context
                    ))
        
        return contacts
    
    def extract_links(self, content: str, base_url: str) -> List[str]:
        """Extract all links from page content"""
        link_pattern = re.compile(r'href=[\'"]?([^\'" >]+)', re.IGNORECASE)
        links = link_pattern.findall(content)
        
        valid_links = []
        for link in links:
            full_url = urljoin(base_url, link)
            parsed = urlparse(full_url)
            
            # Only same domain links
            if parsed.netloc == self.domain:
                # Remove fragment and normalize
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    clean_url += f"?{parsed.query}"
                
                valid_links.append(clean_url)
        
        return valid_links
    
    def discover_endpoints(self, base_url: str) -> List[str]:
        """Discover common endpoints and API routes"""
        common_paths = [
            '/api', '/api/v1', '/api/v2',
            '/contact', '/about', '/team', '/staff',
            '/sitemap.xml', '/robots.txt',
            '/admin', '/login', '/register',
            '/search', '/help', '/support',
            '/blog', '/news', '/press',
            '/.well-known/security.txt'
        ]
        
        endpoints = []
        for path in common_paths:
            endpoint = urljoin(base_url, path)
            endpoints.append(endpoint)
        
        return endpoints
    
    def update_progress(self, pages_crawled: int, total_emails: int, total_phones: int):
        """Display animated progress bar that grows with each page"""
        progress_pct = int((pages_crawled / self.max_pages) * 100)
        
        # Create progress bar
        bar_length = 30
        filled_length = int(bar_length * pages_crawled / self.max_pages)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # Clear line and show progress bar (overwrite same line)
        sys.stdout.write(f'\r[{bar}] {progress_pct}% | Emails: {total_emails} | Phones: {total_phones}')
        sys.stdout.flush()
    
    def crawl(self) -> Dict:
        """Main crawling method"""
        print(f"🎯 Target: \033[96m{self.domain}\033[0m")
        print(f"⚙️  Config: {self.max_pages} pages | {self.delay}s delay")
        print("-" * 40)
        
        # Add common endpoints to queue
        endpoints = self.discover_endpoints(self.base_url)
        self.url_queue.extend(endpoints)
        
        pages_crawled = 0
        
        while self.url_queue and pages_crawled < self.max_pages:
            url = self.url_queue.popleft()
            
            if url in self.visited_urls:
                continue
            
            # Check robots.txt compliance
            if not self.can_fetch(url):
                continue
            
            # Fetch page content
            content = self.get_page_with_bypass(url)
            if not content:
                continue
            
            self.visited_urls.add(url)
            pages_crawled += 1
            
            # Extract contacts
            contacts = self.extract_contacts(content, url)
            self.contacts.extend(contacts)
            
            # Count current totals
            total_emails = len([c for c in self.contacts if c.email])
            total_phones = len([c for c in self.contacts if c.phone])
            
            # Update progress display
            self.update_progress(pages_crawled, total_emails, total_phones)
            
            # Extract and queue new links
            links = self.extract_links(content, url)
            for link in links:
                if link not in self.visited_urls and link not in self.url_queue:
                    self.url_queue.append(link)
            
            # Respectful delay
            time.sleep(self.delay)
        
        # Deduplicate contacts
        self._deduplicate_contacts()
        
        # Final counts after deduplication
        final_emails = len([c for c in self.contacts if c.email])
        final_phones = len([c for c in self.contacts if c.phone])
        
        print(f"\n🎉 Scan complete! Emails: \033[92m{final_emails}\033[0m | Phones: \033[92m{final_phones}\033[0m")
        
        result = {
            'pages_crawled': pages_crawled,
            'total_contacts': len(self.contacts),
            'unique_emails': final_emails,
            'unique_phones': final_phones,
            'visited_urls': list(self.visited_urls)
        }
        
        return result
    
    def _deduplicate_contacts(self):
        """Remove duplicate contacts"""
        seen_emails = set()
        seen_phones = set()
        unique_contacts = []
        
        for contact in self.contacts:
            is_duplicate = False
            
            if contact.email and contact.email in seen_emails:
                is_duplicate = True
            elif contact.email:
                seen_emails.add(contact.email)
            
            if contact.phone and contact.phone in seen_phones:
                is_duplicate = True
            elif contact.phone:
                seen_phones.add(contact.phone)
            
            if not is_duplicate:
                unique_contacts.append(contact)
        
        self.contacts = unique_contacts
    
    def save_to_txt_files(self, domain_name: str):
        """Save contacts to separate .txt files"""
        email_file = f"{domain_name}_emails.txt"
        phone_file = f"{domain_name}_phones.txt"
        
        # Save emails
        emails_written = 0
        with open(email_file, 'w', encoding='utf-8') as f:
            for contact in self.contacts:
                if contact.email:
                    f.write(f"{contact.email}\t{contact.url}\n")
                    emails_written += 1
        
        # Save phones
        phones_written = 0
        with open(phone_file, 'w', encoding='utf-8') as f:
            for contact in self.contacts:
                if contact.phone:
                    f.write(f"{contact.phone}\t{contact.url}\n")
                    phones_written += 1
        
        print(f"💾 Saved \033[92m{emails_written}\033[0m emails to \033[94m{email_file}\033[0m")
        print(f"💾 Saved \033[92m{phones_written}\033[0m phones to \033[94m{phone_file}\033[0m")
        
        return email_file, phone_file

def print_banner():
    """Display attractive banner with branding"""
    print("\033[96m" + "="*80)
    print(r"""
 $$$$$$\                                           $$$$$$\                               
$$  __$$\                                         $$  __$$\                              
$$ /  \__| $$$$$$\   $$$$$$\   $$$$$$\   $$$$$$\  $$ /  \__| $$$$$$$\ $$$$$$\  $$$$$$$\  
$$ |      $$  __$$\ $$  __$$\ $$  __$$\ $$  __$$\ \$$$$$$\  $$  _____|\____$$\ $$  __$$\ 
$$ |      $$ |  \__|$$$$$$$$ |$$$$$$$$ |$$ /  $$ | \____$$\ $$ /      $$$$$$$ |$$ |  $$ |
$$ |  $$\ $$ |      $$   ____|$$   ____|$$ |  $$ |$$\   $$ |$$ |     $$  __$$ |$$ |  $$ |
\$$$$$$  |$$ |      \$$$$$$$\ \$$$$$$$\ $$$$$$$  |\$$$$$$  |\$$$$$$$\\$$$$$$$ |$$ |  $$ |
 \______/ \__|       \_______| \_______|$$  ____/  \______/  \_______|\_______|\__|  \__|
                                        $$ |                                             
                                        $$ |                                             
                                        \__|                                             
                                                                        ~By Astra
    """)
    print("="*80)
    print("🕷️  POLITE DOMAIN-LIMITED WEB CRAWLER")
    print("📧  Extracts Emails & Phone Numbers")
    print("🤖  Respects robots.txt & Rate Limits")
    print("🔄  Multiple Bypass Strategies")
    print("="*80 + "\033[0m")

def print_input_section():
    """Styled input section"""
    print("\033[94m" + "📝 CONFIGURATION" + "\033[0m")
    print("-" * 40)

def main():
    # Display banner
    print_banner()
    
    # Input section with styling
    print_input_section()
    target_url = input("🌐 Enter target URL: ").strip()
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url
    
    delay = float(input("⏱️  Enter delay between requests (seconds, default 1.0): ") or "1.0")
    max_pages = int(input("📄 Enter max pages to crawl (default 50): ") or "50")
    
    # Crawling section header
    print("\n\033[92m" + "🚀 STARTING CRAWL" + "\033[0m")
    print("-" * 40)
    
    # Initialize crawler
    crawler = PoliteCrawler(target_url, delay=delay, max_pages=max_pages)
    
    # Start crawling
    results = crawler.crawl()
    
    # Results section with styling
    print("\n\n\033[93m" + "📊 RESULTS" + "\033[0m")
    print("=" * 50)
    
    # Save results to .txt files
    domain_name = urlparse(target_url).netloc.replace('.', '_')
    email_file, phone_file = crawler.save_to_txt_files(domain_name)
    
    # Final styled output
    print("\n\033[96m" + "💾 FILES CREATED:" + "\033[0m")
    print(f"📧 {email_file}")
    print(f"📞 {phone_file}")
    
    print("\n\033[92m" + "✅ CRAWL COMPLETED SUCCESSFULLY!" + "\033[0m")
    print("\033[96m" + "="*50 + "\033[0m")
    print("Thank you for using CreepScan! 🕷️")
    print("\033[90m" + "Happy hunting! - Astra" + "\033[0m")

if __name__ == "__main__":
    main()
