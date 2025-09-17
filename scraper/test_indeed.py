#!/usr/bin/env python3
"""
Test Indeed scraping specifically
"""

import asyncio
from playwright.async_api import async_playwright

async def test_indeed():
    """Test Indeed scraping"""
    print("Testing Indeed scraping...")
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                page = await browser.new_page()
                page.set_default_timeout(60000)
                
                print("Setting user agent...")
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                })
                
                print("Navigating to Indeed...")
                await page.goto('https://www.indeed.com/jobs?q=software+engineer+entry+level&l=remote&fromage=1&sort=date', 
                               wait_until='domcontentloaded', timeout=60000)
                
                print("Waiting for page to load...")
                await page.wait_for_timeout(5000)
                
                print("Looking for job elements...")
                job_elements = await page.query_selector_all('[data-jk]')
                print(f"Found {len(job_elements)} job elements")
                
                if job_elements:
                    print("Processing first few jobs...")
                    for i, element in enumerate(job_elements[:3]):
                        try:
                            title_elem = await element.query_selector('h2 a')
                            if title_elem:
                                title = await title_elem.inner_text()
                                print(f"Job {i+1}: {title}")
                        except Exception as e:
                            print(f"Error processing job {i+1}: {e}")
                
                await page.close()
                print("Test completed successfully!")
                
            except Exception as e:
                print(f"Error during Indeed test: {e}")
                import traceback
                traceback.print_exc()
            finally:
                await browser.close()
                
    except Exception as e:
        print(f"Error with browser: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_indeed())
