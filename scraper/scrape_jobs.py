#!/usr/bin/env python3
"""
Robust job scraper using multiple approaches
"""

import os
import sys
import csv
import re
import time
import json
import hashlib
import requests
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
import asyncio
import logging
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
CSV_FILE_PATH = '../data/jobs.csv'
SCRAPE_WITHIN_HOURS = 2
MAX_EXPERIENCE_YEARS = 2
TARGET_ROLES = ['SDE', 'SWE', 'DevOps', 'Cloud', 'AI/ML']

# Visa sponsorship keywords
VISA_SPONSORSHIP_KEYWORDS = [
    'visa sponsorship', 'will sponsor', 'h1b', 'h1-b', 'sponsorship available',
    'work authorization', 'green card', 'permanent resident', 'citizenship not required',
    'international candidates', 'visa support', 'immigration support'
]

VISA_NO_SPONSORSHIP_KEYWORDS = [
    'no sponsorship', 'no visa sponsorship', 'citizenship required', 'us citizen required',
    'green card required', 'permanent resident required', 'no h1b', 'no h1-b'
]

class RobustJobScraper:
    """Robust job scraper using multiple approaches with human behavior simulation"""
    
    def __init__(self):
        self.existing_jobs = []
        self.new_jobs = []
        self.scraped_jobs = set()
        
        # User agents to rotate through
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        # Session for connection reuse
        self.session = requests.Session()
        
        # Set up session with realistic headers
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
    
    def get_random_user_agent(self):
        """Get a random user agent"""
        return random.choice(self.user_agents)
    
    def human_delay(self, min_seconds=1, max_seconds=3):
        """Simulate human delay between requests"""
        delay = random.uniform(min_seconds, max_seconds)
        logger.info(f"Waiting {delay:.2f} seconds (human simulation)...")
        time.sleep(delay)
    
    def get_realistic_headers(self, referer=None):
        """Get realistic headers that mimic human browsing"""
        headers = {
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': random.choice([
                'en-US,en;q=0.9',
                'en-US,en;q=0.9,es;q=0.8',
                'en-GB,en;q=0.9,en-US;q=0.8'
            ]),
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site' if referer else 'none',
            'Cache-Control': 'max-age=0',
            'DNT': '1'
        }
        
        if referer:
            headers['Referer'] = referer
            
        return headers
    
    def load_existing_jobs(self) -> None:
        """Load existing jobs from CSV"""
        try:
            if os.path.exists(CSV_FILE_PATH):
                with open(CSV_FILE_PATH, 'r', newline='', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    self.existing_jobs = list(reader)
                    logger.info(f"Loaded {len(self.existing_jobs)} existing jobs")
            else:
                logger.info("No existing jobs file found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading existing jobs: {e}")
            self.existing_jobs = []
    
    def generate_job_id(self, title: str, company: str, url: str) -> str:
        """Generate unique job ID"""
        content = f"{title}_{company}_{url}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def check_experience_requirement(self, job_text: str) -> bool:
        """Check if job is entry level (≤ 2 years experience)"""
        job_text_lower = job_text.lower()
        
        # Look for entry level indicators
        entry_level_indicators = [
            'entry level', 'new grad', 'new graduate', 'junior', 'associate',
            '0-2 years', '0 to 2 years', '1-2 years', '1 to 2 years',
            'recent graduate', 'college graduate', 'university graduate'
        ]
        
        # Look for senior level indicators (exclude these)
        senior_indicators = [
            'senior', 'sr.', 'lead', 'principal', 'architect', 'manager',
            '5+ years', '5 years', '6+ years', '7+ years', '8+ years',
            '10+ years', '10 years', 'experienced', 'expert'
        ]
        
        # Check for senior indicators first
        for indicator in senior_indicators:
            if indicator in job_text_lower:
                return False
        
        # Check for entry level indicators
        for indicator in entry_level_indicators:
            if indicator in job_text_lower:
                return True
        
        # If no clear indicators, assume it might be entry level
        return True
    
    def check_visa_sponsorship(self, job_text: str) -> bool:
        """Check if job offers visa sponsorship"""
        job_text_lower = job_text.lower()
        
        # Check for negative indicators first
        for keyword in VISA_NO_SPONSORSHIP_KEYWORDS:
            if keyword in job_text_lower:
                return False
        
        # Check for positive indicators
        for keyword in VISA_SPONSORSHIP_KEYWORDS:
            if keyword in job_text_lower:
                return True
        
        # If no clear indicators, assume sponsorship might be available
        return True
    
    def categorize_role(self, title: str, description: str = '') -> str:
        """Categorize job role"""
        text = f"{title} {description}".lower()
        
        if any(keyword in text for keyword in ['devops', 'dev ops', 'site reliability', 'sre']):
            return 'DevOps'
        elif any(keyword in text for keyword in ['cloud', 'aws', 'azure', 'gcp', 'google cloud']):
            return 'Cloud'
        elif any(keyword in text for keyword in ['ai', 'ml', 'machine learning', 'artificial intelligence', 'data scientist']):
            return 'AI/ML'
        elif any(keyword in text for keyword in ['software engineer', 'swe', 'software developer']):
            return 'SWE'
        else:
            return 'SDE'
    
    def scrape_indeed_simple(self) -> List[Dict]:
        """Indeed scraper with human behavior simulation"""
        jobs = []
        try:
            # First, visit the main Indeed page to establish session
            logger.info("Establishing session with Indeed...")
            main_page = self.session.get('https://www.indeed.com', 
                                       headers=self.get_realistic_headers(), 
                                       timeout=30)
            main_page.raise_for_status()
            self.human_delay(2, 4)
            
            # Now search for jobs with realistic behavior
            search_url = "https://www.indeed.com/jobs?q=software+engineer+entry+level&l=remote&fromage=1&sort=date"
            logger.info("Searching for jobs on Indeed...")
            
            response = self.session.get(search_url, 
                                      headers=self.get_realistic_headers('https://www.indeed.com'), 
                                      timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find job cards
            job_cards = soup.find_all('div', {'data-jk': True})
            
            for card in job_cards[:10]:  # Limit to first 10
                try:
                    title_elem = card.find('h2', class_='jobTitle')
                    if not title_elem:
                        continue
                    
                    title_link = title_elem.find('a')
                    if not title_link:
                        continue
                    
                    title = title_link.get_text(strip=True)
                    company_elem = card.find('span', {'data-testid': 'company-name'})
                    company = company_elem.get_text(strip=True) if company_elem else 'Unknown'
                    
                    location_elem = card.find('div', {'data-testid': 'job-location'})
                    location = location_elem.get_text(strip=True) if location_elem else 'Remote'
                    
                    # Get job URL
                    job_id = card.get('data-jk')
                    job_url = f"https://www.indeed.com/viewjob?jk={job_id}" if job_id else ''
                    
                    # Check filters
                    job_text = f"{title} {company}".lower()
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    if not self.check_visa_sponsorship(job_text):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title,
                        'company': company,
                        'location': location,
                        'role': self.categorize_role(title, ''),
                        'post_url': job_url,
                        'posted_at': 'Recently',
                        'experience_text': 'Entry level software engineering position',
                        'visa_sponsorship': True,
                        'snippet': f'Software engineering position at {company}',
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing Indeed job: {e}")
                    continue
            
            logger.info(f"Scraped {len(jobs)} jobs from Indeed")
            
        except Exception as e:
            logger.error(f"Error scraping Indeed: {e}")
        
        return jobs
    
    def scrape_remote_ok(self) -> List[Dict]:
        """Scrape jobs from RemoteOK with human behavior simulation"""
        jobs = []
        try:
            logger.info("Accessing RemoteOK...")
            self.human_delay(1, 2)
            
            url = "https://remoteok.io/remote-dev-jobs"
            
            response = self.session.get(url, 
                                      headers=self.get_realistic_headers(), 
                                      timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find job listings
            job_listings = soup.find_all('tr', class_='job')
            
            for listing in job_listings[:10]:  # Limit to first 10
                try:
                    company_elem = listing.find('td', class_='company')
                    if not company_elem:
                        continue
                    
                    company = company_elem.get_text(strip=True)
                    
                    position_elem = listing.find('td', class_='position')
                    if not position_elem:
                        continue
                    
                    title_link = position_elem.find('a')
                    if not title_link:
                        continue
                    
                    title = title_link.get_text(strip=True)
                    job_url = title_link.get('href', '')
                    if job_url and not job_url.startswith('http'):
                        job_url = urljoin('https://remoteok.com', job_url)
                    
                    # Check if it's software engineering related
                    job_text = f"{title} {company}".lower()
                    if not any(keyword in job_text for keyword in ['software', 'engineer', 'developer', 'programmer', 'devops', 'cloud', 'ai', 'ml']):
                        continue
                    
                    # Check if it's entry level
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    # Check visa sponsorship
                    if not self.check_visa_sponsorship(job_text):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title,
                        'company': company,
                        'location': 'Remote',
                        'role': self.categorize_role(title, ''),
                        'post_url': job_url,
                        'posted_at': 'Recently',
                        'experience_text': 'Remote software engineering position',
                        'visa_sponsorship': True,
                        'snippet': f'Remote software engineering position at {company}',
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing RemoteOK job: {e}")
                    continue
            
            logger.info(f"Scraped {len(jobs)} jobs from RemoteOK")
            
        except Exception as e:
            logger.error(f"Error scraping RemoteOK: {e}")
        
        return jobs
    
    def scrape_stackoverflow_jobs(self) -> List[Dict]:
        """Scrape jobs from Stack Overflow Jobs with human behavior simulation"""
        jobs = []
        try:
            logger.info("Accessing StackOverflow Jobs...")
            self.human_delay(1, 3)
            
            url = "https://stackoverflow.com/jobs"
            
            response = self.session.get(url, 
                                      headers=self.get_realistic_headers(), 
                                      timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find job listings
            job_listings = soup.find_all('div', class_='-job')
            
            for listing in job_listings[:10]:  # Limit to first 10
                try:
                    title_elem = listing.find('h2', class_='mb4')
                    if not title_elem:
                        continue
                    
                    title_link = title_elem.find('a')
                    if not title_link:
                        continue
                    
                    title = title_link.get_text(strip=True)
                    job_url = title_link.get('href', '')
                    if job_url and not job_url.startswith('http'):
                        job_url = urljoin('https://stackoverflow.com', job_url)
                    
                    company_elem = listing.find('h3', class_='mb4')
                    company = company_elem.get_text(strip=True) if company_elem else 'Unknown'
                    
                    location_elem = listing.find('span', class_='fc-black-500')
                    location = location_elem.get_text(strip=True) if location_elem else 'Remote'
                    
                    # Check if it's entry level
                    job_text = f"{title} {company}".lower()
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    # Check visa sponsorship
                    if not self.check_visa_sponsorship(job_text):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title,
                        'company': company,
                        'location': location,
                        'role': self.categorize_role(title, ''),
                        'post_url': job_url,
                        'posted_at': 'Recently',
                        'experience_text': 'Software engineering position',
                        'visa_sponsorship': True,
                        'snippet': f'Software engineering position at {company}',
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing StackOverflow job: {e}")
                    continue
            
            logger.info(f"Scraped {len(jobs)} jobs from StackOverflow")
            
        except Exception as e:
            logger.error(f"Error scraping StackOverflow: {e}")
        
        return jobs
    
    def scrape_we_work_remotely(self) -> List[Dict]:
        """Scrape jobs from We Work Remotely with human behavior simulation"""
        jobs = []
        try:
            logger.info("Accessing We Work Remotely...")
            self.human_delay(1, 2)
            
            url = "https://weworkremotely.com/categories/remote-programming-jobs"
            
            response = self.session.get(url, 
                                      headers=self.get_realistic_headers(), 
                                      timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find job listings
            job_listings = soup.find_all('li', class_='feature')
            
            for listing in job_listings[:10]:  # Limit to first 10
                try:
                    title_elem = listing.find('span', class_='title')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    company_elem = listing.find('span', class_='company')
                    company = company_elem.get_text(strip=True) if company_elem else 'Unknown'
                    
                    # Get job URL
                    job_link = listing.find('a')
                    job_url = ''
                    if job_link:
                        job_url = job_link.get('href', '')
                        if job_url and not job_url.startswith('http'):
                            job_url = urljoin('https://weworkremotely.com', job_url)
                    
                    # Check if it's software engineering related
                    job_text = f"{title} {company}".lower()
                    if not any(keyword in job_text for keyword in ['software', 'engineer', 'developer', 'programmer', 'devops', 'cloud', 'ai', 'ml']):
                        continue
                    
                    # Check if it's entry level
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    # Check visa sponsorship
                    if not self.check_visa_sponsorship(job_text):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title,
                        'company': company,
                        'location': 'Remote',
                        'role': self.categorize_role(title, ''),
                        'post_url': job_url,
                        'posted_at': 'Recently',
                        'experience_text': 'Remote software engineering position',
                        'visa_sponsorship': True,
                        'snippet': f'Remote software engineering position at {company}',
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing We Work Remotely job: {e}")
                    continue
            
            logger.info(f"Scraped {len(jobs)} jobs from We Work Remotely")
            
        except Exception as e:
            logger.error(f"Error scraping We Work Remotely: {e}")
        
        return jobs
    
    def scrape_jobspresso(self) -> List[Dict]:
        """Scrape jobs from Jobspresso with human behavior simulation"""
        jobs = []
        try:
            logger.info("Accessing Jobspresso...")
            self.human_delay(1, 2)
            
            url = "https://jobspresso.co/remote-jobs/development/"
            
            response = self.session.get(url, 
                                      headers=self.get_realistic_headers(), 
                                      timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find job listings
            job_listings = soup.find_all('div', class_='job-list-item')
            
            for listing in job_listings[:10]:  # Limit to first 10
                try:
                    title_elem = listing.find('h4', class_='job-title')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    company_elem = listing.find('span', class_='job-company')
                    company = company_elem.get_text(strip=True) if company_elem else 'Unknown'
                    
                    location_elem = listing.find('span', class_='job-location')
                    location = location_elem.get_text(strip=True) if location_elem else 'Remote'
                    
                    # Get job URL
                    job_link = listing.find('a', class_='job-title')
                    job_url = ''
                    if job_link:
                        job_url = job_link.get('href', '')
                        if job_url and not job_url.startswith('http'):
                            job_url = urljoin('https://jobspresso.co', job_url)
                    
                    # Check if it's software engineering related
                    job_text = f"{title} {company}".lower()
                    if not any(keyword in job_text for keyword in ['software', 'engineer', 'developer', 'programmer', 'devops', 'cloud', 'ai', 'ml']):
                        continue
                    
                    # Check if it's entry level
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    # Check visa sponsorship
                    if not self.check_visa_sponsorship(job_text):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title,
                        'company': company,
                        'location': location,
                        'role': self.categorize_role(title, ''),
                        'post_url': job_url,
                        'posted_at': 'Recently',
                        'experience_text': 'Remote software engineering position',
                        'visa_sponsorship': True,
                        'snippet': f'Remote software engineering position at {company}',
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing Jobspresso job: {e}")
                    continue
            
            logger.info(f"Scraped {len(jobs)} jobs from Jobspresso")
            
        except Exception as e:
            logger.error(f"Error scraping Jobspresso: {e}")
        
        return jobs
    
    def scrape_github_jobs_api(self) -> List[Dict]:
        """Scrape jobs using GitHub Jobs API (if available)"""
        jobs = []
        try:
            logger.info("Trying GitHub Jobs API...")
            self.human_delay(1, 2)
            
            # Try to access GitHub Jobs API or similar
            api_url = "https://jobs.github.com/positions.json?description=software+engineer&location=remote"
            
            response = self.session.get(api_url, 
                                      headers=self.get_realistic_headers(), 
                                      timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            for job in data[:10]:  # Limit to first 10
                try:
                    title = job.get('title', '')
                    company = job.get('company', 'Unknown')
                    location = job.get('location', 'Remote')
                    job_url = job.get('url', '')
                    description = job.get('description', '')
                    
                    # Check if it's entry level
                    job_text = f"{title} {description}".lower()
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    # Check visa sponsorship
                    if not self.check_visa_sponsorship(job_text):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title,
                        'company': company,
                        'location': location,
                        'role': self.categorize_role(title, description),
                        'post_url': job_url,
                        'posted_at': job.get('created_at', 'Recently'),
                        'experience_text': description[:200] + '...' if len(description) > 200 else description,
                        'visa_sponsorship': True,
                        'snippet': description[:300] + '...' if len(description) > 300 else description,
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing GitHub Jobs API job: {e}")
                    continue
            
            logger.info(f"Scraped {len(jobs)} jobs from GitHub Jobs API")
            
        except Exception as e:
            logger.error(f"Error scraping GitHub Jobs API: {e}")
        
        return jobs
    
    def scrape_remote_co(self) -> List[Dict]:
        """Scrape jobs from Remote.co"""
        jobs = []
        try:
            logger.info("Accessing Remote.co...")
            self.human_delay(1, 2)
            
            url = "https://remote.co/remote-jobs/developer/"
            
            response = self.session.get(url, 
                                      headers=self.get_realistic_headers(), 
                                      timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find job listings
            job_listings = soup.find_all('div', class_='job_listing')
            
            for listing in job_listings[:10]:  # Limit to first 10
                try:
                    title_elem = listing.find('h3', class_='job_title')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    company_elem = listing.find('div', class_='job_company')
                    company = company_elem.get_text(strip=True) if company_elem else 'Unknown'
                    
                    location_elem = listing.find('div', class_='job_location')
                    location = location_elem.get_text(strip=True) if location_elem else 'Remote'
                    
                    # Get job URL
                    job_link = listing.find('a')
                    job_url = ''
                    if job_link:
                        job_url = job_link.get('href', '')
                        if job_url and not job_url.startswith('http'):
                            job_url = urljoin('https://remote.co', job_url)
                    
                    # Check if it's software engineering related
                    job_text = f"{title} {company}".lower()
                    if not any(keyword in job_text for keyword in ['software', 'engineer', 'developer', 'programmer', 'devops', 'cloud', 'ai', 'ml']):
                        continue
                    
                    # Check if it's entry level
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    # Check visa sponsorship
                    if not self.check_visa_sponsorship(job_text):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title,
                        'company': company,
                        'location': location,
                        'role': self.categorize_role(title, ''),
                        'post_url': job_url,
                        'posted_at': 'Recently',
                        'experience_text': 'Remote software engineering position',
                        'visa_sponsorship': True,
                        'snippet': f'Remote software engineering position at {company}',
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing Remote.co job: {e}")
                    continue
            
            logger.info(f"Scraped {len(jobs)} jobs from Remote.co")
            
        except Exception as e:
            logger.error(f"Error scraping Remote.co: {e}")
        
        return jobs
    
    def create_realistic_sample_jobs(self) -> List[Dict]:
        """Create realistic sample jobs when scraping fails"""
        jobs = []
        try:
            # Realistic job data based on actual job postings
            realistic_jobs = [
                {
                    'title': 'Software Engineer - Entry Level',
                    'company': 'TechCorp Solutions',
                    'location': 'San Francisco, CA',
                    'role': 'SWE',
                    'post_url': 'https://example.com/techcorp-software-engineer',
                    'posted_at': '2 hours ago',
                    'experience_text': 'Entry level software engineering position for recent graduates',
                    'visa_sponsorship': True,
                    'snippet': 'Join our engineering team as an entry-level software engineer. Work on cutting-edge projects with mentorship from senior developers.',
                },
                {
                    'title': 'Junior DevOps Engineer',
                    'company': 'CloudStart Inc',
                    'location': 'Remote',
                    'role': 'DevOps',
                    'post_url': 'https://example.com/cloudstart-devops',
                    'posted_at': '1 hour ago',
                    'experience_text': 'Entry level DevOps position with focus on AWS and containerization',
                    'visa_sponsorship': True,
                    'snippet': 'Help us build and maintain our cloud infrastructure. Great opportunity for new graduates interested in DevOps.',
                },
                {
                    'title': 'AI/ML Engineer - New Grad',
                    'company': 'DataTech Innovations',
                    'location': 'Seattle, WA',
                    'role': 'AI/ML',
                    'post_url': 'https://example.com/datatech-ai-ml',
                    'posted_at': '3 hours ago',
                    'experience_text': 'New graduate AI/ML engineering position with machine learning focus',
                    'visa_sponsorship': True,
                    'snippet': 'Work on cutting-edge machine learning projects. Perfect for recent CS graduates with ML coursework.',
                },
                {
                    'title': 'Software Developer - Entry Level',
                    'company': 'StartupXYZ',
                    'location': 'Austin, TX',
                    'role': 'SDE',
                    'post_url': 'https://example.com/startupxyz-developer',
                    'posted_at': '4 hours ago',
                    'experience_text': 'Entry level software development role with modern tech stack',
                    'visa_sponsorship': True,
                    'snippet': 'Join our fast-growing startup as a software developer. Work with React, Node.js, and cloud technologies.',
                },
                {
                    'title': 'Cloud Engineer - New Graduate',
                    'company': 'CloudScale Technologies',
                    'location': 'Denver, CO',
                    'role': 'Cloud',
                    'post_url': 'https://example.com/cloudscale-engineer',
                    'posted_at': '5 hours ago',
                    'experience_text': 'New graduate cloud engineering position with AWS/GCP focus',
                    'visa_sponsorship': True,
                    'snippet': 'Build scalable cloud solutions for enterprise clients. Great learning opportunity for cloud technologies.',
                }
            ]
            
            for job_data in realistic_jobs:
                job_data['id'] = self.generate_job_id(job_data['title'], job_data['company'], job_data['post_url'])
                job_data['scraped_at'] = datetime.now().isoformat()
                jobs.append(job_data)
            
            logger.info(f"Created {len(jobs)} realistic sample jobs")
            
        except Exception as e:
            logger.error(f"Error creating realistic sample jobs: {e}")
        
        return jobs
    
    def deduplicate_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """Remove duplicate jobs based on ID/URL"""
        unique_jobs = []
        seen_ids = set()
        
        for job in jobs:
            job_id = job.get('id', '')
            job_url = job.get('post_url', '')
            
            # Check if we've already seen this job
            if job_id in seen_ids or job_url in self.scraped_jobs:
                continue
            
            seen_ids.add(job_id)
            self.scraped_jobs.add(job_url)
            unique_jobs.append(job)
        
        return unique_jobs
    
    def save_jobs_to_csv(self) -> None:
        """Save all jobs (existing + new) to CSV file"""
        try:
            # Combine existing and new jobs
            all_jobs = self.existing_jobs + self.new_jobs
            
            # Create DataFrame and save to CSV
            if all_jobs:
                # Ensure directory exists
                os.makedirs(os.path.dirname(CSV_FILE_PATH), exist_ok=True)
                
                # Save to CSV
                with open(CSV_FILE_PATH, 'w', newline='', encoding='utf-8') as file:
                    fieldnames = ['id', 'title', 'company', 'location', 'role', 'post_url', 
                                 'posted_at', 'experience_text', 'visa_sponsorship', 'snippet', 'scraped_at']
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(all_jobs)
                
                logger.info(f"Saved {len(all_jobs)} jobs to {CSV_FILE_PATH}")
            else:
                logger.info("No jobs to save")
            
        except Exception as e:
            logger.error(f"Error saving jobs to CSV: {e}")
            raise
    
    def run_scraper(self) -> None:
        """Main scraper execution"""
        logger.info("Starting robust job scraper...")
        
        try:
            # Load existing jobs
            self.load_existing_jobs()
            
            # Scrape jobs using different methods
            all_jobs = []
            
            # Try Indeed with human behavior simulation
            logger.info("Scraping Indeed with human behavior simulation...")
            indeed_jobs = self.scrape_indeed_simple()
            all_jobs.extend(indeed_jobs)
            self.human_delay(3, 5)  # Longer delay between sites
            
            # Try RemoteOK
            logger.info("Scraping RemoteOK...")
            remoteok_jobs = self.scrape_remote_ok()
            all_jobs.extend(remoteok_jobs)
            self.human_delay(2, 4)
            
            # Try StackOverflow Jobs
            logger.info("Scraping StackOverflow Jobs...")
            stackoverflow_jobs = self.scrape_stackoverflow_jobs()
            all_jobs.extend(stackoverflow_jobs)
            self.human_delay(2, 4)
            
            # Try We Work Remotely
            logger.info("Scraping We Work Remotely...")
            wwr_jobs = self.scrape_we_work_remotely()
            all_jobs.extend(wwr_jobs)
            self.human_delay(2, 4)
            
            # Try Jobspresso
            logger.info("Scraping Jobspresso...")
            jobspresso_jobs = self.scrape_jobspresso()
            all_jobs.extend(jobspresso_jobs)
            self.human_delay(2, 4)
            
            # Try GitHub Jobs API
            logger.info("Scraping GitHub Jobs API...")
            github_jobs = self.scrape_github_jobs_api()
            all_jobs.extend(github_jobs)
            self.human_delay(2, 4)
            
            # Try Remote.co
            logger.info("Scraping Remote.co...")
            remote_co_jobs = self.scrape_remote_co()
            all_jobs.extend(remote_co_jobs)
            
            # Add delays between different job site requests to simulate human behavior
            if len(all_jobs) > 0:
                logger.info(f"Successfully scraped {len(all_jobs)} jobs from all sources")
            else:
                logger.warning("No jobs found from any source - sites may be blocking automated requests")
            
            # Deduplicate
            unique_new_jobs = self.deduplicate_jobs(all_jobs)
            self.new_jobs = unique_new_jobs
            
            logger.info(f"Found {len(self.new_jobs)} new unique jobs")
            
            # Save to CSV
            self.save_jobs_to_csv()
            
            logger.info("Scraping completed successfully!")
            
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            raise

def main():
    """Main function"""
    scraper = RobustJobScraper()
    scraper.run_scraper()

if __name__ == "__main__":
    main()
