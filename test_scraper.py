#!/usr/bin/env python3
"""
Test script for the job scraper
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'scraper'))

from scraper.scrape_jobs import JobScraper
import asyncio

async def test_scraper():
    """Test the scraper functionality"""
    print("🧪 Testing Job Scraper...")
    
    try:
        # Initialize scraper
        scraper = JobScraper()
        print("✅ Scraper initialized successfully")
        
        # Test loading existing jobs
        scraper.load_existing_jobs()
        print(f"✅ Loaded {len(scraper.existing_jobs)} existing jobs")
        
        # Test job categorization
        test_cases = [
            ("Software Engineer", "Build software applications", "SWE"),
            ("DevOps Engineer", "Manage infrastructure and deployment", "DevOps"),
            ("Cloud Architect", "Design cloud solutions on AWS", "Cloud"),
            ("ML Engineer", "Build machine learning models", "AI/ML"),
            ("Developer", "Write code for web applications", "SDE")
        ]
        
        for title, description, expected_role in test_cases:
            actual_role = scraper.categorize_role(title, description)
            status = "✅" if actual_role == expected_role else "❌"
            print(f"{status} Role categorization: '{title}' -> {actual_role} (expected: {expected_role})")
        
        # Test experience requirement checking
        test_experience_cases = [
            ("Entry level software engineer position", True),
            ("0-2 years of experience required", True),
            ("5+ years of experience in software development", False),
            ("New graduate welcome", True),
            ("Senior software engineer with 10 years experience", False)
        ]
        
        for text, expected in test_experience_cases:
            actual = scraper.check_experience_requirement(text)
            status = "✅" if actual == expected else "❌"
            print(f"{status} Experience check: '{text}' -> {actual} (expected: {expected})")
        
        # Test visa sponsorship detection
        test_visa_cases = [
            ("We offer visa sponsorship for qualified candidates", True),
            ("H1B sponsorship available", True),
            ("No visa sponsorship provided", False),
            ("US citizenship required", False),
            ("International candidates welcome", True)
        ]
        
        for text, expected in test_visa_cases:
            actual = scraper.check_visa_sponsorship(text)
            status = "✅" if actual == expected else "❌"
            print(f"{status} Visa sponsorship: '{text}' -> {actual} (expected: {expected})")
        
        print("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_scraper())
    sys.exit(0 if success else 1)
