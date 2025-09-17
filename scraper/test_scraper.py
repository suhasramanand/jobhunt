#!/usr/bin/env python3
"""
Simple test scraper to debug browser issues
"""

import asyncio
from playwright.async_api import async_playwright

async def test_browser():
    """Test basic browser functionality"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        try:
            page = await browser.new_page()
            page.set_default_timeout(30000)
            
            print("Testing Indeed...")
            await page.goto('https://www.indeed.com/jobs?q=software+engineer+entry+level&l=remote&fromage=1&sort=date', 
                           wait_until='domcontentloaded', timeout=30000)
            
            await page.wait_for_timeout(3000)
            
            # Try to find job elements
            job_elements = await page.query_selector_all('[data-jk]')
            print(f"Found {len(job_elements)} job elements")
            
            if job_elements:
                # Try to get the first job
                first_job = job_elements[0]
                title_elem = await first_job.query_selector('h2 a')
                if title_elem:
                    title = await title_elem.inner_text()
                    print(f"First job title: {title}")
                    
                    # Get job URL
                    job_id = await first_job.get_attribute('data-jk')
                    if job_id:
                        job_url = f"https://www.indeed.com/viewjob?jk={job_id}"
                        print(f"Job URL: {job_url}")
            
            await page.close()
            print("Test completed successfully!")
            
        except Exception as e:
            print(f"Error during test: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_browser())
