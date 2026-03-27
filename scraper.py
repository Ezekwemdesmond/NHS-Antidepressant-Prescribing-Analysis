import requests
import pandas as pd
import time
import os
import csv
from datetime import datetime
from bs4 import BeautifulSoup
import re
import logging
from urllib.parse import urljoin


# LOGGING CONFIGURATION
# Logs to both the console and a persistent log file for auditability.

os.makedirs('pca_data/raw', exist_ok=True)
os.makedirs('pca_data/logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pca_data/logs/scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Constants

BASE_URL          = "https://opendata.nhsbsa.net"
DATASET_URL       = f"{BASE_URL}/dataset/prescription-cost-analysis-pca-monthly-data"
RAW_DATA_DIR      = "pca_data/raw"           # Raw CSVs
COMBINED_DATA_DIR = "pca_data"               # Combined/processed output
LOG_DIR           = "pca_data/logs"
DOWNLOAD_LOG_PATH = f"{LOG_DIR}/download_log.csv"

# Columns to retain from each monthly file.
# Defined here so any upstream schema change is caught in one place.
REQUIRED_COLUMNS  = ['YEAR_MONTH', 'REGION_NAME', 'BNF_CHEMICAL_SUBSTANCE', 'ITEMS', 'NIC']

# HTTP request headers — identifies the scraper politely to the server.
REQUEST_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/91.0.4472.124 Safari/537.36'
    )
}



# DOWNLOAD LOG UTILITIES

# The download log is a CSV file that records every file downloaded:
# what was downloaded, when, from where, and whether it succeeded.
#
# This serves two purposes in industry:
#   1. AUDITABILITY  — In regulated sectors like healthcare, you must be able
#                      to prove exactly what raw data you received and when.
#   2. INCREMENTAL   — The log lets the scraper skip files already downloaded
#      LOADING          on a re-run, rather than hammering the NHS BSA server
#                      again unnecessarily.


def _initialise_download_log():
    """
    Create the download log CSV with headers if it does not already exist.
    Called once at scraper startup.
    """
    if not os.path.exists(DOWNLOAD_LOG_PATH):
        with open(DOWNLOAD_LOG_PATH, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'downloaded_at', 'year_month', 'filename',
                'source_url', 'file_size_bytes', 'status', 'error_message'
            ])
            writer.writeheader()
        logger.info(f"Download log initialised at {DOWNLOAD_LOG_PATH}")


def _log_download(year_month, filename, source_url,
                  file_size_bytes=None, status='success', error_message=''):
    """
    Append a single record to the download log.

    Parameters
    
    year_month      : str   — e.g. '202101'
    filename        : str   — local filename saved to RAW_DATA_DIR
    source_url      : str   — the URL the file was downloaded from
    file_size_bytes : int   — size of the downloaded file in bytes
    status          : str   — 'success' or 'failed'
    error_message   : str   — populated only when status is 'failed'
    """
    with open(DOWNLOAD_LOG_PATH, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'downloaded_at', 'year_month', 'filename',
            'source_url', 'file_size_bytes', 'status', 'error_message'
        ])
        writer.writerow({
            'downloaded_at' : datetime.now().isoformat(),
            'year_month'    : year_month,
            'filename'      : filename,
            'source_url'    : source_url,
            'file_size_bytes': file_size_bytes,
            'status'        : status,
            'error_message' : error_message
        })


def _get_already_downloaded():
    """
    Read the download log and return a set of year_month values
    that were previously downloaded successfully.

    This enables incremental loading — if PCA_202101.csv already exists
    and was logged as successful, we skip it on the next run rather than
    re-downloading it from the NHS BSA server.

    Returns

    set of str — e.g. {'202101', '202102', '202103'}
    """
    if not os.path.exists(DOWNLOAD_LOG_PATH):
        return set()

    already_downloaded = set()
    with open(DOWNLOAD_LOG_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['status'] == 'success':
                already_downloaded.add(row['year_month'])

    return already_downloaded


# Scraper Class


class NHSPCADataScraper:
    """
    Scraper for NHS Business Services Authority (NHS BSA)
    Prescription Cost Analysis (PCA) monthly datasets.

    Follows the raw landing zone pattern:
      1. Downloads raw monthly CSV files to pca_data/raw/ — untouched source data.
      2. Logs every download attempt to pca_data/logs/download_log.csv.
      3. Supports incremental loading — skips files already downloaded.
      4. Combines raw files into a single combined CSV for downstream processing.

    The scraper does NOT perform any data transformation or database loading.
    Those responsibilities belong to separate scripts (processor.py, loader.py)
    in line with the separation of concerns principle.

    Usage

        scraper = NHSPCADataScraper()
        downloaded_files = scraper.scrape_all_data(start_date='202101')
        scraper.combine_datasets(downloaded_files)
    """

    def __init__(self):
        """Initialise the scraper, set up the HTTP session, and prepare the log."""
        self.base_url    = BASE_URL
        self.dataset_url = DATASET_URL
        self.session     = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

        # Ensure all required directories exist before any downloads begin
        os.makedirs(RAW_DATA_DIR, exist_ok=True)
        os.makedirs(COMBINED_DATA_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)

        # Initialise the download log (creates the file if it does not exist)
        _initialise_download_log()

        logger.info("NHSPCADataScraper initialised.")
        logger.info(f"Raw data directory  : {RAW_DATA_DIR}")
        logger.info(f"Download log        : {DOWNLOAD_LOG_PATH}")

 
    # Data discovery
   

    def get_available_datasets(self):
        """
        Scrape the NHS BSA dataset page to discover all available
        monthly PCA dataset links.

        Returns
       
        list of dict — each dict contains 'title', 'url', 'resource_id'
        """
        logger.info(f"Fetching dataset index from: {self.dataset_url}")

        try:
            response = self.session.get(self.dataset_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            dataset_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.text.strip()

                if '/resource/' in href and 'PCA' in text and '202' in text:
                    dataset_links.append({
                        'title'      : text,
                        'url'        : urljoin(self.base_url, href),
                        'resource_id': href.split('/')[-1]
                    })

            logger.info(f"Found {len(dataset_links)} datasets on the index page.")
            return dataset_links

        except requests.exceptions.Timeout:
            logger.error("Request timed out fetching the dataset index page.")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error fetching dataset index: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching dataset index: {e}")
            return []

    def _extract_date_from_title(self, title):
        """
        Parse a dataset title and extract the year-month as a 6-digit string.

        Example
        
        'Prescription Cost Analysis (PCA) - Jan 2021' → '202101'

        Parameters
        
        title : str

        Returns
     
        str or None — '202101' format, or None if parsing fails
        """
        month_map = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }

        try:
            match = re.search(r'(\w{3})\s+(\d{4})', title)
            if match:
                month_str, year_str = match.groups()
                month_num = month_map.get(month_str)
                if month_num:
                    return f"{year_str}{month_num}"

            logger.warning(f"Could not parse date from title: '{title}'")
            return None

        except Exception as e:
            logger.error(f"Error parsing date from title '{title}': {e}")
            return None

    def _filter_by_date_range(self, datasets, start_date):
        """
        Filter the list of discovered datasets to only include those
        from start_date onwards, and sort them chronologically.

        Parameters
       
        datasets   : list of dict
        start_date : str — '202101' format

        Returns
    
        list of dict — filtered and sorted
        """
        filtered = []
        for dataset in datasets:
            date_str = self._extract_date_from_title(dataset['title'])
            if date_str and date_str >= start_date:
                dataset['date'] = date_str
                filtered.append(dataset)

        filtered.sort(key=lambda x: x['date'])
        logger.info(
            f"After filtering from {start_date}: {len(filtered)} datasets to process."
        )
        return filtered

 
    # Download


    def _get_download_url(self, resource_url):
        """
        Visit a resource page and extract the direct CSV download URL.

        Parameters
       
        resource_url : str — the resource detail page URL

        Returns
   
        str or None — direct download URL, or None if not found
        """
        try:
            response = self.session.get(resource_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Strategy 1: look for a direct .csv link
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.endswith('.csv') or 'download' in href.lower():
                    return urljoin(self.base_url, href)

            # Strategy 2: look for the standard CKAN download path pattern
            for link in soup.find_all('a', href=True):
                href = link['href']
                if (
                    '/dataset/' in href
                    and '/resource/' in href
                    and '/download/' in href
                ):
                    return urljoin(self.base_url, href)

            logger.warning(f"No download URL found on resource page: {resource_url}")
            return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching resource page: {resource_url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching resource page {resource_url}: {e}")
            return None

    def _download_single_file(self, download_url, filename, year_month):
        """
        Download a single CSV file and save it to the raw data directory.

        Files are saved to pca_data/raw/ and never modified after download.
        This directory is the raw landing zone — the source of truth for
        all downstream processing.

        Parameters
      
        download_url : str  — direct URL to the CSV file
        filename     : str  — local filename to save as (e.g. 'PCA_202101.csv')
        year_month   : str  — '202101' format, used for logging

        Returns
       
        str or None — full local filepath if successful, None if failed
        """
        filepath = os.path.join(RAW_DATA_DIR, filename)

        # Skip if already downloaded and logged as successful
        # This is the incremental loading check — avoids redundant downloads
        already_done = _get_already_downloaded()
        if year_month in already_done and os.path.exists(filepath):
            logger.info(
                f"Skipping {filename} — already downloaded (found in log)."
            )
            return filepath

        logger.info(f"Downloading: {filename}")

        try:
            response = self.session.get(download_url, stream=True, timeout=60)
            response.raise_for_status()

            file_size = 0
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        file_size += len(chunk)

            logger.info(
                f"Saved: {filename} "
                f"({file_size / 1024:.1f} KB) → {RAW_DATA_DIR}/"
            )

            # Log the successful download for auditability and incremental loading
            _log_download(
                year_month      = year_month,
                filename        = filename,
                source_url      = download_url,
                file_size_bytes = file_size,
                status          = 'success'
            )

            return filepath

        except requests.exceptions.Timeout:
            error_msg = f"Download timed out for {filename}"
            logger.error(error_msg)
            _log_download(
                year_month    = year_month,
                filename      = filename,
                source_url    = download_url,
                status        = 'failed',
                error_message = error_msg
            )
            return None

        except requests.exceptions.RequestException as e:
            error_msg = f"HTTP error downloading {filename}: {e}"
            logger.error(error_msg)
            _log_download(
                year_month    = year_month,
                filename      = filename,
                source_url    = download_url,
                status        = 'failed',
                error_message = error_msg
            )
            return None

        except Exception as e:
            error_msg = f"Unexpected error downloading {filename}: {e}"
            logger.error(error_msg)
            _log_download(
                year_month    = year_month,
                filename      = filename,
                source_url    = download_url,
                status        = 'failed',
                error_message = error_msg
            )
            # Remove partial file if the download was incomplete
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Removed partial file: {filepath}")
            return None

    
    # Orchestration


    def scrape_all_data(self, start_date="202101", delay_between_requests=2):
        """
        Main orchestration method. Discovers, filters, and downloads all
        PCA monthly datasets from start_date to the latest available.

        A polite delay between requests (delay_between_requests seconds) is
        applied to avoid overloading the NHS BSA server — this is standard
        practice when scraping public sector websites.

        Parameters
        
        start_date              : str — '202101' format, inclusive lower bound
        delay_between_requests  : int — seconds to wait between downloads

        Returns
       
        list of dict — metadata for each successfully downloaded file,
                       including 'date', 'title', 'filepath', 'download_url'
        """
        logger.info("=" * 60)
        logger.info("NHS PCA DATA SCRAPER — STARTING")
        logger.info(f"Start date          : {start_date}")
        logger.info(f"Request delay       : {delay_between_requests}s")
        logger.info(f"Raw output dir      : {RAW_DATA_DIR}/")
        logger.info("=" * 60)

        # Step 1 — Discover all available datasets on the NHS BSA portal
        all_datasets = self.get_available_datasets()
        if not all_datasets:
            logger.error("No datasets discovered. Exiting.")
            return []

        # Step 2 — Filter to the requested date range, sorted chronologically
        datasets_to_process = self._filter_by_date_range(all_datasets, start_date)
        if not datasets_to_process:
            logger.error(f"No datasets found from {start_date} onwards. Exiting.")
            return []

        # Step 3 — Download each dataset
        downloaded_files = []
        total = len(datasets_to_process)

        for i, dataset in enumerate(datasets_to_process, start=1):
            logger.info(f"[{i}/{total}] Processing: {dataset['title']}")

            try:
                # Resolve the direct download URL from the resource page
                download_url = self._get_download_url(dataset['url'])

                # Fallback: construct the standard CKAN download URL directly
                if not download_url:
                    download_url = (
                        f"{self.base_url}/dataset/"
                        f"prescription-cost-analysis-pca-monthly-data"
                        f"/resource/{dataset['resource_id']}/download"
                    )
                    logger.info(f"Using fallback download URL for {dataset['title']}")

                filename = f"PCA_{dataset['date']}.csv"
                filepath = self._download_single_file(
                    download_url = download_url,
                    filename     = filename,
                    year_month   = dataset['date']
                )

                if filepath:
                    downloaded_files.append({
                        'date'        : dataset['date'],
                        'title'       : dataset['title'],
                        'filepath'    : filepath,
                        'download_url': download_url
                    })

            except Exception as e:
                logger.error(
                    f"Unexpected error processing {dataset['title']}: {e}"
                )
                continue

            # Polite delay between requests — skip delay after the last file
            if i < total:
                logger.info(f"Waiting {delay_between_requests}s before next request...")
                time.sleep(delay_between_requests)

        # Step 4 — Summary
        failed_count = total - len(downloaded_files)
        logger.info("=" * 60)
        logger.info(f"SCRAPING COMPLETE")
        logger.info(f"  Total datasets found : {total}")
        logger.info(f"  Successfully saved   : {len(downloaded_files)}")
        logger.info(f"  Failed / skipped     : {failed_count}")
        logger.info(f"  Raw files saved to   : {RAW_DATA_DIR}/")
        logger.info(f"  Download log         : {DOWNLOAD_LOG_PATH}")
        logger.info("=" * 60)

        return downloaded_files

    # Combining

    def combine_datasets(self, downloaded_files=None, output_filename="combined_pca_data.csv"):
        """
        Combine all raw monthly CSV files in pca_data/raw/ into a single
        combined CSV file saved to pca_data/.

        This combined file is the input to the next stage of the pipeline
        (processor.py → loader.py). It is NOT the same as the raw files —
        it is a convenience file for downstream use.

        If downloaded_files is not provided, the method reads all CSV files
        directly from the RAW_DATA_DIR. This means you can run combine_datasets()
        independently without re-running the scraper.

        Parameters
        ----------
        downloaded_files : list of dict or None
            If None, reads all CSVs from RAW_DATA_DIR automatically.
        output_filename  : str — name of the combined output file

        Returns
        -------
        str or None — path to the combined CSV file, or None if failed
        """
        # If no files passed in, read everything from the raw directory
        if downloaded_files is None:
            raw_files = sorted([
                f for f in os.listdir(RAW_DATA_DIR)
                if f.endswith('.csv')
            ])
            if not raw_files:
                logger.warning(f"No CSV files found in {RAW_DATA_DIR}/")
                return None

            downloaded_files = [
                {
                    'date'    : f.replace('PCA_', '').replace('.csv', ''),
                    'filepath': os.path.join(RAW_DATA_DIR, f)
                }
                for f in raw_files
            ]
            logger.info(
                f"combine_datasets() called standalone — "
                f"found {len(downloaded_files)} raw files in {RAW_DATA_DIR}/"
            )

        if not downloaded_files:
            logger.warning("No files to combine.")
            return None

        logger.info(f"Combining {len(downloaded_files)} monthly files...")

        combined_chunks = []
        files_read      = 0
        files_failed    = 0

        for file_info in downloaded_files:
            filepath = file_info['filepath']
            try:
                df = pd.read_csv(filepath)

                # Retain only the required columns that are present
                # (guards against upstream schema changes in NHS BSA files)
                present_cols = [
                    col for col in REQUIRED_COLUMNS
                    if col in df.columns
                ]

                if not present_cols:
                    logger.warning(
                        f"No required columns found in {filepath} — skipping."
                    )
                    files_failed += 1
                    continue

                missing_cols = set(REQUIRED_COLUMNS) - set(present_cols)
                if missing_cols:
                    logger.warning(
                        f"{filepath}: missing columns {missing_cols} — "
                        f"proceeding with available columns."
                    )

                combined_chunks.append(df[present_cols].copy())
                files_read += 1
                logger.info(
                    f"  Read {len(df):,} rows from "
                    f"{os.path.basename(filepath)}"
                )

            except pd.errors.EmptyDataError:
                logger.warning(f"{filepath} is empty — skipping.")
                files_failed += 1
            except Exception as e:
                logger.error(f"Error reading {filepath}: {e}")
                files_failed += 1
                continue

        if not combined_chunks:
            logger.error("No data to combine after reading all files.")
            return None

        # Concatenate all monthly DataFrames into one
        logger.info("Concatenating all monthly files...")
        combined_df = pd.concat(combined_chunks, ignore_index=True)

        # Save combined file to the main pca_data/ directory
        output_path = os.path.join(COMBINED_DATA_DIR, output_filename)
        combined_df.to_csv(output_path, index=False)

        logger.info("=" * 60)
        logger.info("COMBINING COMPLETE")
        logger.info(f"  Files read          : {files_read}")
        logger.info(f"  Files failed        : {files_failed}")
        logger.info(f"  Total rows combined : {len(combined_df):,}")
        logger.info(f"  Output saved to     : {output_path}")
        logger.info("=" * 60)

        return output_path



# Entry point

def main():
    """
    Run the full scraping pipeline:
      1. Scrape all PCA monthly data from January 2021 onwards.
      2. Combine all raw monthly files into a single combined CSV.

    The combined CSV is then ready for the next pipeline stage:
      → processor.py  (data cleaning and validation)
      → loader.py     (load into MySQL staging table)
    """
    scraper = NHSPCADataScraper()

    # Stage 1 — Download all monthly raw CSV files
    downloaded_files = scraper.scrape_all_data(
        start_date             = "202101",
        delay_between_requests = 2
    )

    # Stage 2 — Combine raw files into a single combined CSV
    if downloaded_files:
        combined_path = scraper.combine_datasets(downloaded_files)
        if combined_path:
            print(f"\nPipeline complete.")
            print(f"Raw files     : {RAW_DATA_DIR}/")
            print(f"Combined file : {combined_path}")
            print(f"Download log  : {DOWNLOAD_LOG_PATH}")
            print(f"\nNext step: run processor.py to clean and validate the data.")
        else:
            print("Scraping succeeded but combining failed. Check the log.")
    else:
        print("No files were downloaded. Check pca_data/logs/scraper.log for details.")


if __name__ == "__main__":
    main()
