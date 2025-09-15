# 📡 Web Crawler for Emails & Phone Numbers

A Python-based crawling tool that scans a given target domain and automatically collects **emails** and **phone numbers** from all publicly accessible pages.  

This project is built for **ethical use cases** like OSINT, bug bounty recon, and penetration testing.

---

## ✅ Features

- Crawl entire domain starting from a given URL  
- Extract **emails** and **phone numbers** using regex  
- Detect and follow **internal links**  
- Ignore external domains and subdomains  
- Parse `sitemap.xml` if available  
- Add your own **custom URLs** for scanning  
- Limit maximum pages with `max_pages`  

---

## 🕷️ How It Works

### What It WILL Crawl:
- `https://example.com` (starting point)  
- `https://example.com/about`  
- `https://example.com/contact`  
- `https://example.com/blog/post1`  
- `https://example.com/sub/dir` (if linked internally)  

### What It WON’T Crawl:
- `https://subdomain.example.com` (different subdomain)  
- `https://other-site.com` (different domain)  
- `https://example.com/hidden-page` (unless linked internally)  

### Crawling Process:
1. Start from target domain (e.g., `https://example.com`)  
2. Extract all links (`<a href="...">`)  
3. Add **same-domain** links to the crawl queue  
4. Visit each page and repeat process  
5. Extract emails and phone numbers using regex  
6. Save results  

---

## 💻 Installation

Clone the repo and install requirements:

```bash
git clone https://github.com/OnlyAstraa/CreepScan.git
cd CreepScan
