#!/usr/bin/env python3
"""
Very simple test to check if Playwright works at all
"""

import asyncio
from playwright.async_api import async_playwright

async def simple_test():
    """Very simple browser test"""
    print("Starting simple test...")
    
    try:
        async with async_playwright() as p:
            print("Playwright context created")
            
            browser = await p.chromium.launch(headless=True)
            print("Browser launched")
            
            page = await browser.new_page()
            print("Page created")
            
            await page.goto('https://example.com')
            print("Page loaded")
            
            title = await page.title()
            print(f"Page title: {title}")
            
            await page.close()
            print("Page closed")
            
            await browser.close()
            print("Browser closed")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(simple_test())
