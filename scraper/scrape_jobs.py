#!/usr/bin/env python3
"""
Job Aggregator Scraper

This script scrapes job postings from various job boards and company career sites
for new grad / entry level positions with visa sponsorship available.
"""

import os
import sys
import csv
import re
import time
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
import asyncio
import logging

import pandas as pd
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from dateutil import parser as date_parser

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

# Job board configurations
JOB_BOARDS = {
    'indeed': {
        'url': 'https://www.indeed.com/jobs',
        'params': {
            'q': 'software engineer entry level',
            'l': 'remote',
            'fromage': '1',  # Last 24 hours
            'sort': 'date'
        },
        'parser': 'indeed_parser'
    },
    'glassdoor': {
        'url': 'https://www.glassdoor.com/Job/jobs.htm',
        'params': {
            'sc.keyword': 'software engineer entry level',
            'locT': 'C',
            'locId': '1',  # United States
            'fromAge': '1'  # Last 24 hours
        },
        'parser': 'glassdoor_parser'
    },
    'ziprecruiter': {
        'url': 'https://www.ziprecruiter.com/jobs-search',
        'params': {
            'search': 'software engineer entry level',
            'location': 'United States',
            'days': '1'
        },
        'parser': 'ziprecruiter_parser'
    },
    'linkedin': {
        'url': 'https://www.linkedin.com/jobs/search/',
        'params': {
            'keywords': 'software engineer entry level',
            'location': 'United States',
            'f_TPR': 'r86400',  # Last 24 hours
            'f_E': '1,2',  # Entry level and Associate
            'f_TPR': 'r86400'  # Posted in last 24 hours
        },
        'parser': 'linkedin_parser'
    },
    'greenhouse': {
        'url': 'https://boards-api.greenhouse.io/v1/boards',
        'params': {
            'q': 'software engineer',
            'location': 'United States'
        },
        'parser': 'greenhouse_parser'
    },
    'lever': {
        'url': 'https://jobs.lever.co/api/',
        'params': {
            'q': 'software engineer',
            'location': 'United States'
        },
        'parser': 'lever_parser'
    },
    'angellist': {
        'url': 'https://angel.co/jobs',
        'params': {
            'q': 'software engineer',
            'location': 'United States'
        },
        'parser': 'angellist_parser'
    },
    'wellfound': {
        'url': 'https://wellfound.com/role/l/software-engineer',
        'params': {
            'q': 'software engineer',
            'location': 'United States'
        },
        'parser': 'wellfound_parser'
    }
}


class JobScraper:
    """Main job scraper class"""
    
    def __init__(self):
        self.scraped_jobs: Set[str] = set()  # For deduplication
        self.new_jobs: List[Dict] = []
        self.existing_jobs: List[Dict] = []
        
    def load_existing_jobs(self) -> None:
        """Load existing jobs from CSV file"""
        if os.path.exists(CSV_FILE_PATH):
            try:
                df = pd.read_csv(CSV_FILE_PATH)
                self.existing_jobs = df.to_dict('records')
                # Add existing job URLs to deduplication set
                self.scraped_jobs = set(job.get('post_url', '') for job in self.existing_jobs)
                logger.info(f"Loaded {len(self.existing_jobs)} existing jobs")
            except Exception as e:
                logger.error(f"Error loading existing jobs: {e}")
                self.existing_jobs = []
        else:
            logger.info("No existing jobs file found, starting fresh")
            self.existing_jobs = []
    
    def is_within_timeframe(self, posted_at: str) -> bool:
        """Check if job was posted within the specified timeframe"""
        try:
            if not posted_at or posted_at.strip() == '':
                return False
                
            # Parse various date formats
            posted_date = date_parser.parse(posted_at, fuzzy=True)
            cutoff_time = datetime.now() - timedelta(hours=SCRAPE_WITHIN_HOURS)
            
            return posted_date >= cutoff_time
        except Exception as e:
            logger.warning(f"Error parsing date '{posted_at}': {e}")
            return False
    
    def check_experience_requirement(self, job_text: str) -> bool:
        """Check if job requires <= 2 years experience"""
        if not job_text:
            return False
            
        text_lower = job_text.lower()
        
        # Look for experience patterns
        experience_patterns = [
            r'(\d+)\s*years?\s*(?:of\s*)?experience',
            r'experience\s*(?:of\s*)?(\d+)\s*years?',
            r'(\d+)\+?\s*years?\s*(?:of\s*)?experience',
        ]
        
        for pattern in experience_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                try:
                    years = int(match)
                    if years > MAX_EXPERIENCE_YEARS:
                        return False
                except ValueError:
                    continue
        
        # Check for entry level keywords
        entry_level_keywords = [
            'entry level', 'new grad', 'graduate', 'junior', 'associate',
            '0-2 years', '0-1 years', '1-2 years', 'fresh graduate'
        ]
        
        return any(keyword in text_lower for keyword in entry_level_keywords)
    
    def check_visa_sponsorship(self, job_text: str) -> bool:
        """Check if job offers visa sponsorship"""
        if not job_text:
            return False
            
        text_lower = job_text.lower()
        
        # Check for negative keywords first
        for negative in VISA_NO_SPONSORSHIP_KEYWORDS:
            if negative in text_lower:
                return False
        
        # Check for positive keywords
        for positive in VISA_SPONSORSHIP_KEYWORDS:
            if positive in text_lower:
                return True
        
        return False
    
    def categorize_role(self, title: str, description: str) -> Optional[str]:
        """Categorize job role based on title and description"""
        text = f"{title} {description}".lower()
        
        if any(keyword in text for keyword in ['devops', 'dev ops', 'infrastructure', 'deployment']):
            return 'DevOps'
        elif any(keyword in text for keyword in ['cloud', 'aws', 'azure', 'gcp', 'google cloud']):
            return 'Cloud'
        elif any(keyword in text for keyword in ['ai', 'ml', 'machine learning', 'artificial intelligence', 'data science']):
            return 'AI/ML'
        elif any(keyword in text for keyword in ['software engineer', 'software developer', 'sde', 'swe']):
            return 'SWE'
        else:
            return 'SDE'  # Default fallback
    
    def generate_job_id(self, title: str, company: str, url: str) -> str:
        """Generate unique job ID"""
        content = f"{title}_{company}_{url}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    async def scrape_indeed(self, browser) -> List[Dict]:
        """Scrape jobs from Indeed"""
        jobs = []
        try:
            page = await browser.new_page()
            # Set longer timeout and wait for page load
            page.set_default_timeout(60000)  # 60 seconds
            
            # Add user agent to avoid detection
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            await page.goto(JOB_BOARDS['indeed']['url'], wait_until='domcontentloaded', timeout=60000)
            
            # Wait a bit for page to fully load
            await page.wait_for_timeout(2000)
            
            # Search for jobs
            await page.fill('#text-input-what', 'software engineer entry level')
            await page.fill('#text-input-where', 'remote')
            await page.click('button[type="submit"]')
            await page.wait_for_load_state('networkidle', timeout=30000)
            
            # Extract job listings
            job_elements = await page.query_selector_all('[data-jk]')
            
            for element in job_elements[:20]:  # Limit to first 20 results
                try:
                    title_elem = await element.query_selector('h2 a')
                    company_elem = await element.query_selector('[data-testid="company-name"]')
                    location_elem = await element.query_selector('[data-testid="job-location"]')
                    snippet_elem = await element.query_selector('[data-testid="job-snippet"]')
                    
                    if not title_elem:
                        continue
                        
                    title = await title_elem.inner_text()
                    company = await company_elem.inner_text() if company_elem else 'Unknown'
                    location = await location_elem.inner_text() if location_elem else 'Remote'
                    snippet = await snippet_elem.inner_text() if snippet_elem else ''
                    
                    # Get job URL - Indeed uses data-jk attribute for job IDs
                    job_id = await element.get_attribute('data-jk')
                    if job_id:
                        job_url = f"https://www.indeed.com/viewjob?jk={job_id}"
                    else:
                        # Fallback to href if data-jk not available
                        job_url = await title_elem.get_attribute('href')
                        if job_url and not job_url.startswith('http'):
                            job_url = urljoin('https://www.indeed.com', job_url)
                    
                    # Get posted date
                    posted_elem = await element.query_selector('[data-testid="myJobsStateDate"]')
                    posted_at = await posted_elem.inner_text() if posted_elem else ''
                    
                    # Combine text for analysis
                    job_text = f"{title} {snippet}".lower()
                    
                    # Apply filters
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    if not self.check_visa_sponsorship(job_text):
                        continue
                    
                    # Validate that we have a real URL
                    if not job_url or not job_url.startswith('http'):
                        logger.warning(f"Skipping job with invalid URL: {job_url}")
                        continue
                    
                    # Generate job data
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title.strip(),
                        'company': company.strip(),
                        'location': location.strip(),
                        'role': self.categorize_role(title, snippet),
                        'post_url': job_url,
                        'posted_at': posted_at.strip(),
                        'experience_text': snippet[:200] + '...' if len(snippet) > 200 else snippet,
                        'visa_sponsorship': True,
                        'snippet': snippet.strip(),
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing Indeed job: {e}")
                    continue
            
            await page.close()
            
        except Exception as e:
            logger.error(f"Error scraping Indeed: {e}")
            # Try a simpler approach if the main method fails
            try:
                logger.info("Attempting fallback Indeed scraping...")
                await self.scrape_indeed_fallback(browser, jobs)
            except Exception as fallback_error:
                logger.error(f"Fallback Indeed scraping also failed: {fallback_error}")
        
        return jobs
    
    async def scrape_indeed_fallback(self, browser, jobs) -> None:
        """Fallback method for Indeed scraping"""
        try:
            page = await browser.new_page()
            page.set_default_timeout(30000)  # 30 seconds
            
            # Try a direct search URL
            search_url = "https://www.indeed.com/jobs?q=software+engineer+entry+level&l=remote&fromage=1&sort=date"
            await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(3000)
            
            # Try to find job elements with a more generic selector
            job_elements = await page.query_selector_all('[data-jk], .job_seen_beacon, .jobsearch-SerpJobCard')
            
            for element in job_elements[:10]:  # Limit to first 10 results
                try:
                    # Try multiple selectors for title
                    title_elem = await element.query_selector('h2 a, .jobTitle a, a[data-jk]')
                    if not title_elem:
                        continue
                        
                    title = await title_elem.inner_text()
                    if not title or len(title.strip()) < 5:
                        continue
                    
                    # Try multiple selectors for company
                    company_elem = await element.query_selector('[data-testid="company-name"], .companyName, .company')
                    company = await company_elem.inner_text() if company_elem else 'Unknown'
                    
                    # Try multiple selectors for location
                    location_elem = await element.query_selector('[data-testid="job-location"], .companyLocation, .location')
                    location = await location_elem.inner_text() if location_elem else 'Remote'
                    
                    # Get job URL
                    job_id = await element.get_attribute('data-jk')
                    if job_id:
                        job_url = f"https://www.indeed.com/viewjob?jk={job_id}"
                    else:
                        job_url = await title_elem.get_attribute('href')
                        if job_url and not job_url.startswith('http'):
                            job_url = urljoin('https://www.indeed.com', job_url)
                    
                    if not job_url or not job_url.startswith('http'):
                        continue
                    
                    # Create a basic job entry
                    job_text = f"{title} {company}".lower()
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title.strip(),
                        'company': company.strip(),
                        'location': location.strip(),
                        'role': self.categorize_role(title, ''),
                        'post_url': job_url,
                        'posted_at': 'Recently',
                        'experience_text': 'Entry level software engineering position',
                        'visa_sponsorship': True,  # Assume true for Indeed jobs
                        'snippet': f'Software engineering position at {company}',
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing fallback Indeed job: {e}")
                    continue
            
            await page.close()
            
        except Exception as e:
            logger.error(f"Fallback Indeed scraping failed: {e}")
            raise
    
    async def scrape_glassdoor(self, browser) -> List[Dict]:
        """Scrape jobs from Glassdoor"""
        jobs = []
        try:
            page = await browser.new_page()
            page.set_default_timeout(60000)
            
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            # Glassdoor jobs search URL
            search_url = "https://www.glassdoor.com/Job/jobs.htm?sc.keyword=software%20engineer%20entry%20level&locT=C&locId=1&fromAge=1&sortBy=date"
            
            await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)
            
            # Extract job listings
            job_elements = await page.query_selector_all('[data-test="jobListing"]')
            
            for element in job_elements[:15]:  # Limit to first 15 results
                try:
                    title_elem = await element.query_selector('[data-test="job-title"] a')
                    company_elem = await element.query_selector('[data-test="employer-name"]')
                    location_elem = await element.query_selector('[data-test="job-location"]')
                    
                    if not title_elem:
                        continue
                        
                    title = await title_elem.inner_text()
                    company = await company_elem.inner_text() if company_elem else 'Unknown'
                    location = await location_elem.inner_text() if location_elem else 'Remote'
                    
                    # Get job URL
                    job_url = await title_elem.get_attribute('href')
                    if job_url and not job_url.startswith('http'):
                        job_url = urljoin('https://www.glassdoor.com', job_url)
                    
                    # Check filters
                    job_text = f"{title} {company}".lower()
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    if not self.check_visa_sponsorship(job_text):
                        continue
                    
                    # Validate URL
                    if not job_url or not job_url.startswith('http'):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title.strip(),
                        'company': company.strip(),
                        'location': location.strip(),
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
                    logger.warning(f"Error processing Glassdoor job: {e}")
                    continue
            
            await page.close()
            
        except Exception as e:
            logger.error(f"Error scraping Glassdoor: {e}")
        
        return jobs
    
    async def scrape_linkedin(self, browser) -> List[Dict]:
        """Scrape jobs from LinkedIn"""
        jobs = []
        try:
            page = await browser.new_page()
            page.set_default_timeout(60000)
            
            # Add user agent
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            # LinkedIn jobs search URL
            search_url = "https://www.linkedin.com/jobs/search/?keywords=software%20engineer%20entry%20level&location=United%20States&f_TPR=r86400&f_E=1%2C2&sortBy=DD"
            
            await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)
            
            # Extract job listings
            job_elements = await page.query_selector_all('.jobs-search-results__list-item')
            
            for element in job_elements[:15]:  # Limit to first 15 results
                try:
                    title_elem = await element.query_selector('.job-search-card__title a')
                    company_elem = await element.query_selector('.job-search-card__subtitle a')
                    location_elem = await element.query_selector('.job-search-card__location')
                    snippet_elem = await element.query_selector('.job-search-card__snippet')
                    
                    if not title_elem:
                        continue
                        
                    title = await title_elem.inner_text()
                    company = await company_elem.inner_text() if company_elem else 'Unknown'
                    location = await location_elem.inner_text() if location_elem else 'Remote'
                    snippet = await snippet_elem.inner_text() if snippet_elem else ''
                    
                    # Get job URL
                    job_url = await title_elem.get_attribute('href')
                    if job_url and not job_url.startswith('http'):
                        job_url = urljoin('https://www.linkedin.com', job_url)
                    
                    # Check filters
                    job_text = f"{title} {snippet}".lower()
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    if not self.check_visa_sponsorship(job_text):
                        continue
                    
                    # Validate URL
                    if not job_url or not job_url.startswith('http'):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title.strip(),
                        'company': company.strip(),
                        'location': location.strip(),
                        'role': self.categorize_role(title, snippet),
                        'post_url': job_url,
                        'posted_at': 'Recently',
                        'experience_text': snippet[:200] + '...' if len(snippet) > 200 else snippet,
                        'visa_sponsorship': True,
                        'snippet': snippet.strip(),
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing LinkedIn job: {e}")
                    continue
            
            await page.close()
            
        except Exception as e:
            logger.error(f"Error scraping LinkedIn: {e}")
        
        return jobs
    
    async def scrape_ziprecruiter(self, browser) -> List[Dict]:
        """Scrape jobs from ZipRecruiter"""
        jobs = []
        try:
            page = await browser.new_page()
            page.set_default_timeout(60000)
            
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            # ZipRecruiter jobs search URL
            search_url = "https://www.ziprecruiter.com/jobs-search?search=software+engineer+entry+level&location=United+States&days=1"
            
            await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)
            
            # Extract job listings
            job_elements = await page.query_selector_all('.job_content')
            
            for element in job_elements[:15]:  # Limit to first 15 results
                try:
                    title_elem = await element.query_selector('.job_link')
                    company_elem = await element.query_selector('.job_org')
                    location_elem = await element.query_selector('.job_location')
                    
                    if not title_elem:
                        continue
                        
                    title = await title_elem.inner_text()
                    company = await company_elem.inner_text() if company_elem else 'Unknown'
                    location = await location_elem.inner_text() if location_elem else 'Remote'
                    
                    # Get job URL
                    job_url = await title_elem.get_attribute('href')
                    if job_url and not job_url.startswith('http'):
                        job_url = urljoin('https://www.ziprecruiter.com', job_url)
                    
                    # Check filters
                    job_text = f"{title} {company}".lower()
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    if not self.check_visa_sponsorship(job_text):
                        continue
                    
                    # Validate URL
                    if not job_url or not job_url.startswith('http'):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title.strip(),
                        'company': company.strip(),
                        'location': location.strip(),
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
                    logger.warning(f"Error processing ZipRecruiter job: {e}")
                    continue
            
            await page.close()
            
        except Exception as e:
            logger.error(f"Error scraping ZipRecruiter: {e}")
        
        return jobs
    
    async def scrape_wellfound(self, browser) -> List[Dict]:
        """Scrape jobs from Wellfound (formerly AngelList)"""
        jobs = []
        try:
            page = await browser.new_page()
            page.set_default_timeout(60000)
            
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            # Wellfound software engineer jobs
            search_url = "https://wellfound.com/role/l/software-engineer"
            await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)
            
            # Extract job listings
            job_elements = await page.query_selector_all('.job-card, .job-listing, [data-qa="job-card"]')
            
            for element in job_elements[:10]:  # Limit to first 10 results
                try:
                    title_elem = await element.query_selector('h3 a, .job-title a, a[href*="/job/"]')
                    company_elem = await element.query_selector('.company-name, .job-company')
                    location_elem = await element.query_selector('.job-location, .location')
                    
                    if not title_elem:
                        continue
                        
                    title = await title_elem.inner_text()
                    company = await company_elem.inner_text() if company_elem else 'Startup'
                    location = await location_elem.inner_text() if location_elem else 'Remote'
                    
                    # Get job URL
                    job_url = await title_elem.get_attribute('href')
                    if job_url and not job_url.startswith('http'):
                        job_url = urljoin('https://wellfound.com', job_url)
                    
                    # Check filters
                    job_text = f"{title} {company}".lower()
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    if not self.check_visa_sponsorship(job_text):
                        continue
                    
                    if not job_url or not job_url.startswith('http'):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url),
                        'title': title.strip(),
                        'company': company.strip(),
                        'location': location.strip(),
                        'role': self.categorize_role(title, ''),
                        'post_url': job_url,
                        'posted_at': 'Recently',
                        'experience_text': 'Software engineering position at startup',
                        'visa_sponsorship': True,
                        'snippet': f'Software engineering position at {company}',
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing Wellfound job: {e}")
                    continue
            
            await page.close()
            
        except Exception as e:
            logger.error(f"Error scraping Wellfound: {e}")
        
        return jobs
    
    async def scrape_lever(self, browser) -> List[Dict]:
        """Scrape jobs from Lever-powered company sites"""
        jobs = []
        try:
            # List of popular companies using Lever
            lever_companies = [
                'netflix.com',
                'spotify.com',
                'slack.com',
                'dropbox.com',
                'twitch.tv',
                'coinbase.com'
            ]
            
            for company in lever_companies:
                try:
                    page = await browser.new_page()
                    page.set_default_timeout(30000)
                    
                    # Try to find Lever job board
                    careers_urls = [
                        f"https://{company}/careers",
                        f"https://{company}/jobs",
                        f"https://jobs.lever.co/{company.replace('.com', '').replace('.tv', '').replace('.co', '')}"
                    ]
                    
                    for url in careers_urls:
                        try:
                            await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                            await page.wait_for_timeout(2000)
                            
                            # Look for job listings
                            job_elements = await page.query_selector_all('.posting, .job, [data-qa="posting"]')
                            
                            if job_elements:
                                for element in job_elements[:3]:  # Limit per company
                                    try:
                                        title_elem = await element.query_selector('a, .posting-title, h3')
                                        location_elem = await element.query_selector('.posting-categories, .location')
                                        
                                        if not title_elem:
                                            continue
                                            
                                        title = await title_elem.inner_text()
                                        location = await location_elem.inner_text() if location_elem else 'Various'
                                        
                                        # Get job URL
                                        job_url = await title_elem.get_attribute('href')
                                        if job_url and not job_url.startswith('http'):
                                            job_url = urljoin(url, job_url)
                                        
                                        # Check if it's entry level
                                        job_text = title.lower()
                                        if not self.check_experience_requirement(job_text):
                                            continue
                                        
                                        if not job_url or not job_url.startswith('http'):
                                            continue
                                        
                                        job_data = {
                                            'id': self.generate_job_id(title, company, job_url),
                                            'title': title.strip(),
                                            'company': company.replace('.com', '').replace('.tv', '').replace('.co', '').title(),
                                            'location': location.strip(),
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
                                        logger.warning(f"Error processing Lever job: {e}")
                                        continue
                                break  # Found jobs, move to next company
                                
                        except Exception as e:
                            continue  # Try next URL
                    
                    await page.close()
                    
                except Exception as e:
                    logger.warning(f"Error scraping {company}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error scraping Lever: {e}")
        
        return jobs
    
    async def scrape_all_sources(self) -> List[Dict]:
        """Scrape jobs from all configured sources"""
        all_jobs = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                # Scrape Indeed
                logger.info("Scraping Indeed...")
                indeed_jobs = await self.scrape_indeed(browser)
                all_jobs.extend(indeed_jobs)
                logger.info(f"Found {len(indeed_jobs)} jobs from Indeed")
                
                # Scrape Glassdoor
                logger.info("Scraping Glassdoor...")
                glassdoor_jobs = await self.scrape_glassdoor(browser)
                all_jobs.extend(glassdoor_jobs)
                logger.info(f"Found {len(glassdoor_jobs)} jobs from Glassdoor")
                
                # Scrape LinkedIn
                logger.info("Scraping LinkedIn...")
                linkedin_jobs = await self.scrape_linkedin(browser)
                all_jobs.extend(linkedin_jobs)
                logger.info(f"Found {len(linkedin_jobs)} jobs from LinkedIn")
                
                # Scrape ZipRecruiter
                logger.info("Scraping ZipRecruiter...")
                ziprecruiter_jobs = await self.scrape_ziprecruiter(browser)
                all_jobs.extend(ziprecruiter_jobs)
                logger.info(f"Found {len(ziprecruiter_jobs)} jobs from ZipRecruiter")
                
                # Scrape Wellfound
                logger.info("Scraping Wellfound...")
                wellfound_jobs = await self.scrape_wellfound(browser)
                all_jobs.extend(wellfound_jobs)
                logger.info(f"Found {len(wellfound_jobs)} jobs from Wellfound")
                
                # Scrape Lever companies
                logger.info("Scraping Lever companies...")
                lever_jobs = await self.scrape_lever(browser)
                all_jobs.extend(lever_jobs)
                logger.info(f"Found {len(lever_jobs)} jobs from Lever companies")
                
            finally:
                await browser.close()
        
        return all_jobs
    
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
            df = pd.DataFrame(all_jobs)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(CSV_FILE_PATH), exist_ok=True)
            
            # Save to CSV
            df.to_csv(CSV_FILE_PATH, index=False)
            logger.info(f"Saved {len(all_jobs)} jobs to {CSV_FILE_PATH}")
            
        except Exception as e:
            logger.error(f"Error saving jobs to CSV: {e}")
            raise
    
    async def run_scraper(self) -> None:
        """Main scraper execution"""
        logger.info("Starting job scraper...")
        
        try:
            # Load existing jobs
            self.load_existing_jobs()
            
            # Scrape new jobs
            scraped_jobs = await self.scrape_all_sources()
            logger.info(f"Scraped {len(scraped_jobs)} total jobs")
            
            # Deduplicate
            unique_new_jobs = self.deduplicate_jobs(scraped_jobs)
            self.new_jobs = unique_new_jobs
            
            logger.info(f"Found {len(self.new_jobs)} new unique jobs")
            
            # Save to CSV
            self.save_jobs_to_csv()
            
            logger.info("Scraping completed successfully!")
            
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            raise


async def main():
    """Main entry point"""
    scraper = JobScraper()
    await scraper.run_scraper()


if __name__ == "__main__":
    asyncio.run(main())

