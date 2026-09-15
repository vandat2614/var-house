import os
import logging
from pyiceberg.catalog.sql import SqlCatalog
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

load_dotenv()

postgres_uri = os.getenv('POSTGRES_URI')
endpoint = os.getenv('ENDPOINT')
access_key = os.getenv('ACCESS_KEY_ID')
secret_key = os.getenv('SECRET_ACCESS_KEY')

catalog = SqlCatalog(
    "default",
    **{
        "uri": postgres_uri,
        "s3.endpoint": endpoint,
        "s3.access-key-id": access_key,
        "s3.secret-access-key": secret_key,
    }
)

namespace = "football_2026_2027"

try:
    tables = catalog.list_tables(namespace)
    for table_identifier in tables:
        print(f"Dropping table {table_identifier}")
        try:
            catalog.drop_table(table_identifier)
        except Exception as e:
            print(f"Error dropping {table_identifier}: {e}")
            
    try:
        catalog.drop_namespace(namespace)
        print(f"Dropped namespace {namespace}")
    except Exception as e:
        print(f"Namespace {namespace} drop err (or not empty): {e}")
except Exception as e:
    print(f"Could not list/drop tables: {e}")
