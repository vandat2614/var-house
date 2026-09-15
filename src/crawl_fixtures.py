import os
import sys
import logging
from dotenv import load_dotenv

# Ensure project root is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("FixtureCrawlerScript")

def main():
    from src.extract.fixture_crawler import crawl_all_fixtures
        
    
    logger.info("Starting Fixture Crawl...")
    # force_refresh=True forces fetching from the web rather than using cached JSON
    crawl_all_fixtures()
    
    logger.info("Fixture Crawl Complete! Data loaded directly to Iceberg Dimensions.")

if __name__ == "__main__":
    main()

