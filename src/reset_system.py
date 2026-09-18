import os
import logging
from dotenv import load_dotenv

load_dotenv('.env')

try:
    import s3fs
    from confluent_kafka.admin import AdminClient
    from pyiceberg.catalog import load_catalog
except ImportError as e:
    print(f"Missing required library: {e}. Please ensure s3fs, confluent-kafka, and pyiceberg are installed.")
    exit(1)

from src.config import (
    R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME,
    NEON_POSTGRES_URI,
    KAFKA_BOOTSTRAP_SERVERS, KAFKA_SECURITY_PROTOCOL,
    KAFKA_SSL_CA_LOCATION, KAFKA_SSL_CERT_LOCATION, KAFKA_SSL_KEY_LOCATION
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("ResetSystem")


def reset_iceberg():
    """Drop all tables and namespaces in the Iceberg catalog."""
    logger.info("--- 1. Resetting Iceberg Catalog ---")
    try:
        catalog = load_catalog(
            "default",
            **{
                "uri": NEON_POSTGRES_URI,
                "s3.endpoint": R2_ENDPOINT,
                "s3.access-key-id": R2_ACCESS_KEY_ID,
                "s3.secret-access-key": R2_SECRET_ACCESS_KEY,
            }
        )
        namespaces = catalog.list_namespaces()
        for ns in namespaces:
            tables = catalog.list_tables(ns)
            for table_identifier in tables:
                logger.info(f"Dropping Iceberg table: {table_identifier}")
                catalog.drop_table(table_identifier)
                
            logger.info(f"Dropping Iceberg namespace: {ns}")
            catalog.drop_namespace(ns)
            
        logger.info("Iceberg catalog cleared.")
    except Exception as e:
        logger.error(f"Failed to clear Iceberg catalog: {e}")


def reset_r2():
    """Delete all files under the data/ directory in the R2 bucket."""
    logger.info("--- 2. Resetting R2 Storage ---")
    try:
        fs = s3fs.S3FileSystem(
            client_kwargs={
                "endpoint_url": R2_ENDPOINT,
                "aws_access_key_id": R2_ACCESS_KEY_ID,
                "aws_secret_access_key": R2_SECRET_ACCESS_KEY
            }
        )
        bucket_path = f"{R2_BUCKET_NAME}/data"
        if fs.exists(bucket_path):
            logger.info(f"Deleting everything in {bucket_path}...")
            fs.rm(bucket_path, recursive=True)
            logger.info("R2 data cleared.")
        else:
            logger.info(f"R2 path {bucket_path} does not exist. Skipping.")
    except Exception as e:
        logger.error(f"Failed to clear R2 storage: {e}")


def reset_kafka():
    """Delete all user topics in Kafka."""
    logger.info("--- 3. Resetting Kafka Topics ---")
    try:
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
        metadata = admin.list_topics(timeout=10)
        
        # Filter out internal Kafka topics (e.g. __consumer_offsets)
        topics_to_delete = [t for t in metadata.topics.keys() if not t.startswith("__")]
        
        if topics_to_delete:
            logger.info(f"Found topics to delete: {topics_to_delete}")
            fs_results = admin.delete_topics(topics_to_delete, operation_timeout=30)
            for topic, future in fs_results.items():
                try:
                    future.result()  # Wait for the topic deletion to finish
                    logger.info(f"Topic '{topic}' deleted successfully.")
                except Exception as e:
                    logger.error(f"Failed to delete topic '{topic}': {e}")
        else:
            logger.info("No user topics found. Skipping.")
            
    except Exception as e:
        logger.error(f"Failed to clear Kafka topics: {e}")


if __name__ == "__main__":
    print("="*60)
    print(" DANGER ZONE: SYSTEM RESET")
    print("="*60)
    print("This script will DESTROY ALL DATA in:")
    print(" 1. Iceberg Catalog (Postgres)")
    print(" 2. Cloudflare R2 Bucket (/data directory)")
    print(" 3. Kafka (All non-internal topics)")
    print("="*60)
    
    confirm = input("Are you absolutely sure? Type 'yes' to proceed: ")
    if confirm.strip().lower() == 'yes':
        print("\\nStarting reset sequence...\\n")
        reset_iceberg()
        reset_r2()
        reset_kafka()
        print("\\n✅ System reset complete. You can now test on a clean slate.")
    else:
        print("Reset cancelled. Phew! That was close.")
