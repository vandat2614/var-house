import os
import logging
from dotenv import load_dotenv

load_dotenv('.env')

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("InitSystem")

from src.config import (
    R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME,
    KAFKA_BOOTSTRAP_SERVERS, KAFKA_SECURITY_PROTOCOL,
    KAFKA_SSL_CA_LOCATION, KAFKA_SSL_CERT_LOCATION, KAFKA_SSL_KEY_LOCATION
)


def init_r2():
    logger.info("--- 1. Checking R2 Storage ---")
    try:
        import s3fs
        fs = s3fs.S3FileSystem(
            client_kwargs={
                "endpoint_url": R2_ENDPOINT,
                "aws_access_key_id": R2_ACCESS_KEY_ID,
                "aws_secret_access_key": R2_SECRET_ACCESS_KEY
            }
        )
        
        # Check if bucket exists
        if not fs.exists(R2_BUCKET_NAME):
            logger.info(f"Bucket {R2_BUCKET_NAME} not found. Attempting to create...")
            fs.mkdir(R2_BUCKET_NAME)
            logger.info(f"Bucket {R2_BUCKET_NAME} created successfully.")
        else:
            logger.info(f"Bucket {R2_BUCKET_NAME} already exists.")
            
        # Ensure directories exist
        for d in ["data/raw", "data/silver", "data/gold"]:
            path = f"{R2_BUCKET_NAME}/{d}"
            if not fs.exists(path):
                fs.makedirs(path)
                logger.info(f"Created directory: {path}")
            else:
                logger.info(f"Directory {path} already exists.")
                
        logger.info("R2 storage check complete.")
        
    except Exception as e:
        logger.error(f"Failed to initialize R2 storage: {e}")


def init_iceberg():
    logger.info("--- 2. Initializing Iceberg Catalog & Namespaces ---")
    try:
        from src.etl.load.iceberg_catalog import get_catalog
        # get_catalog() automatically connects to DB and creates DEFAULT_NAMESPACE ('football')
        catalog = get_catalog()
        namespaces = catalog.list_namespaces()
        logger.info(f"Iceberg connection successful. Existing namespaces: {namespaces}")
        
    except Exception as e:
        logger.error(f"Failed to initialize Iceberg catalog: {e}")


def init_kafka():
    logger.info("--- 3. Initializing Kafka Topics ---")
    try:
        from confluent_kafka.admin import AdminClient, NewTopic
        
        conf = {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "security.protocol": KAFKA_SECURITY_PROTOCOL,
        }
        if KAFKA_SECURITY_PROTOCOL == "SSL":
            conf.update({
                "ssl.ca.location": KAFKA_SSL_CA_LOCATION,
                "ssl.certificate.location": KAFKA_SSL_CERT_LOCATION,
                "ssl.key.location": KAFKA_SSL_KEY_LOCATION,
            })
            
        admin = AdminClient(conf)
        
        required_topics = ["raw-match-details", "transformed-match-details"]
        existing_topics = admin.list_topics(timeout=10).topics.keys()
        
        topics_to_create = []
        for t in required_topics:
            if t not in existing_topics:
                # 3 partitions, replication factor 1 (adjust if needed for prod)
                topics_to_create.append(NewTopic(t, num_partitions=3, replication_factor=1))
                
        if topics_to_create:
            fs_results = admin.create_topics(topics_to_create)
            for topic, future in fs_results.items():
                try:
                    future.result()
                    logger.info(f"Topic '{topic}' created successfully.")
                except Exception as e:
                    logger.error(f"Failed to create topic '{topic}': {e}")
        else:
            logger.info("All required topics already exist.")
            
    except Exception as e:
        logger.error(f"Failed to initialize Kafka topics: {e}")


if __name__ == "__main__":
    print("="*60)
    print(" PROJECT INITIALIZATION ")
    print("="*60)
    print("This script will ensure all external dependencies are ready:")
    print(" 1. Cloudflare R2 (Buckets & Folders)")
    print(" 2. Iceberg Catalog (Postgres & Namespaces)")
    print(" 3. Kafka (Topics)")
    print("="*60)
    print("\nStarting initialization sequence...\n")
    
    init_r2()
    init_iceberg()
    init_kafka()
    
    print("\n[OK] System initialization complete. Ready to run ETL pipelines.")
