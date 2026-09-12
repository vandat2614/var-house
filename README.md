# ⚽ VAR-house: Football Data Lakehouse & Streaming Pipeline

VAR-house is an end-to-end data engineering pipeline designed to ingest, transform, and store football (soccer) match data in near real-time. Built around the **Medallion Architecture**, this system utilizes modern data engineering tools to process match facts, player statistics, and live fixtures into a robust Data Lakehouse.

## 🌟 Key Features

- **Event-Driven Streaming:** Uses **Apache Kafka** to handle real-time data queues for raw and transformed match details.
- **Lakehouse Storage:** Stores curated data in **Apache Iceberg**, providing analytical capabilities with ACID compliance.
- **Orchestrated Workflows:** Uses **Apache Airflow** to dynamically track schedules, orchestrate daily batch crawling, and trigger real-time ingestion right after matches conclude.
- **Medallion Architecture:** Follows a strict Bronze (Raw JSON) -> Silver (Transformed Data) -> Gold (Iceberg Tables) data modeling pattern.

## 🏗️ Architecture Flow

```text
[Airflow / Historical Script] --(Raw JSON)--> [Kafka: raw-match-details] 
                                                        |
                                              [Terminal 1: Transformer]
                                                        |
                                        [Kafka: transformed-match-details]
                                                        |
                                              [Terminal 2: Loader]
                                                        |
                                              [Apache Iceberg Lakehouse]
```

---

## 🚀 Setup & Execution Guide

Follow this step-by-step guide to get the data pipeline up and running on your local machine.

### Step 1: Prepare the Environment

1. Ensure **Docker Desktop** is running.
2. Open a terminal in the project root directory and set up a Python virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 2: Spin Up Infrastructure

We need Kafka (as our message broker) and Airflow (for scheduling and orchestration). Start the services using Docker Compose:

```bash
docker compose up -d
```
*Note: Airflow might take about 30 seconds to initialize its database on the first run. The Airflow UI will be available at `http://localhost:8080` (Username/Password: `airflow` / `airflow`).*

### Step 3: Fetch Foundational Data (Fixtures)

Before the system knows which matches to monitor, it needs the season's fixtures. In your terminal (with the `.venv` activated), run:

```bash
python src/crawl_fixtures.py
```
> **What this does:** The script fetches the match calendar, transforms it, and saves it to `data/transformed/fixtures/{CURRENT_SEASON}/`. Airflow and other scripts will use this to look up matches.

### Step 4: Start the Streaming Pipeline (Consumers)

The system requires two background workers to process data continuously from Kafka and load it into Iceberg. **Open 2 NEW terminal windows** (remember to activate the virtual environment in both using `.\.venv\Scripts\Activate.ps1`):

**Terminal 1 (Stream Transformer):** 
Listens for raw data from the crawler, cleans it, and publishes it back to Kafka.
```bash
python -m src.stream_pipeline.stream_transformer
```

**Terminal 2 (Iceberg Loader):**
Listens for the cleaned data and writes it directly into the Apache Iceberg Data Lake.
```bash
python -m src.stream_pipeline.stream_loader
```

*(Keep both of these terminals running in the background).*

### Step 5: Historical Catchup

With the infrastructure and workers ready, you can fetch historical matches (e.g., from the last 30 days) to populate your data lake.

Open a **3rd Terminal** (activate `.venv`) and run:
```bash
python src/crawl_historical_matches.py --days 30
```
> **What this does:** This script finds all completed matches within the specified timeframe, fetches their details, and sends them to Kafka. You will see the two worker terminals (from Step 4) immediately begin processing and saving the records to Iceberg.

### Step 6: Enable Real-time Tracking (Airflow)

To automate the ingestion of upcoming and live matches daily:
1. Open your browser and go to `http://localhost:8080`.
2. Log in using `airflow` / `airflow`.
3. Locate the DAG named **`match_details_crawler`** and toggle it **On (Unpause)**.
4. This DAG scans for matches within a ±3 day window and uses a `DateTimeSensor` to automatically trigger the crawler exactly **2 hours after kickoff**. From here on, the data ingestion runs completely on autopilot!
