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
    'google_careers': {
        'url': 'https://careers.google.com/jobs/results/',
        'params': {
            'q': 'software engineer',
            'location': 'United States',
            'sort_by': 'date'
        },
        'parser': 'google_careers_parser'
    },
    'linkedin': {
        'url': 'https://www.linkedin.com/jobs/search/',
        'params': {
            'keywords': 'software engineer entry level',
            'location': 'United States',
            'f_TPR': 'r86400',  # Last 24 hours
            'sortBy': 'DD'
        },
        'parser': 'linkedin_parser'
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
            await page.goto(JOB_BOARDS['indeed']['url'], wait_until='networkidle')
            
            # Search for jobs
            await page.fill('#text-input-what', 'software engineer entry level')
            await page.fill('#text-input-where', 'remote')
            await page.click('button[type="submit"]')
            await page.wait_for_load_state('networkidle')
            
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
                    
                    # Get job URL
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
                    
                    # Generate job data
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url or ''),
                        'title': title.strip(),
                        'company': company.strip(),
                        'location': location.strip(),
                        'role': self.categorize_role(title, snippet),
                        'post_url': job_url or '',
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
        
        return jobs
    
    async def scrape_google_careers(self, browser) -> List[Dict]:
        """Scrape jobs from Google Careers"""
        jobs = []
        try:
            page = await browser.new_page()
            await page.goto(JOB_BOARDS['google_careers']['url'], wait_until='networkidle')
            
            # Search for entry level software positions
            search_input = await page.query_selector('input[type="search"]')
            if search_input:
                await search_input.fill('software engineer entry level')
                await page.keyboard.press('Enter')
                await page.wait_for_load_state('networkidle')
            
            # Extract job listings
            job_elements = await page.query_selector_all('[data-test-id="job-card"]')
            
            for element in job_elements[:15]:  # Limit results
                try:
                    title_elem = await element.query_selector('h3 a')
                    company_elem = await element.query_selector('[data-test-id="job-card-company"]')
                    location_elem = await element.query_selector('[data-test-id="job-card-location"]')
                    
                    if not title_elem:
                        continue
                    
                    title = await title_elem.inner_text()
                    company = await company_elem.inner_text() if company_elem else 'Google'
                    location = await location_elem.inner_text() if location_elem else 'Various'
                    
                    # Get job URL
                    job_url = await title_elem.get_attribute('href')
                    if job_url and not job_url.startswith('http'):
                        job_url = urljoin('https://careers.google.com', job_url)
                    
                    # For Google, assume visa sponsorship is available
                    job_text = f"{title} {company}".lower()
                    
                    if not self.check_experience_requirement(job_text):
                        continue
                    
                    job_data = {
                        'id': self.generate_job_id(title, company, job_url or ''),
                        'title': title.strip(),
                        'company': company.strip(),
                        'location': location.strip(),
                        'role': self.categorize_role(title, ''),
                        'post_url': job_url or '',
                        'posted_at': 'Recently',  # Google doesn't show specific dates
                        'experience_text': 'Entry level software engineering position',
                        'visa_sponsorship': True,  # Google typically sponsors
                        'snippet': f'Software engineering position at {company}',
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing Google job: {e}")
                    continue
            
            await page.close()
            
        except Exception as e:
            logger.error(f"Error scraping Google Careers: {e}")
        
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
                
                # Scrape Google Careers
                logger.info("Scraping Google Careers...")
                google_jobs = await self.scrape_google_careers(browser)
                all_jobs.extend(google_jobs)
                logger.info(f"Found {len(google_jobs)} jobs from Google Careers")
                
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
