import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from bs4 import BeautifulSoup
import re
import logging
from urllib.parse import urljoin

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NHSPCADataScraper:
    def __init__(self, base_url="https://opendata.nhsbsa.net"):
        self.base_url = base_url
        self.dataset_url = f"{base_url}/dataset/prescription-cost-analysis-pca-monthly-data"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        # Define the columns we want to keep
        self.required_columns = ['YEAR', 'YEAR_MONTH', 'REGION_NAME', 'BNF_CHEMICAL_SUBSTANCE', 'ITEMS', 'COST']
        
    def get_available_datasets(self):
        """
        Scrape the main dataset page to get all available monthly datasets
        """
        try:
            response = self.session.get(self.dataset_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all dataset links
            dataset_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/resource/' in href and 'PCA' in link.text:
                    # Extract the date from the link text
                    text = link.text.strip()
                    if 'PCA' in text and ('202' in text):  # Filter for years 2021+
                        dataset_links.append({
                            'title': text,
                            'url': urljoin(self.base_url, href),
                            'resource_id': href.split('/')[-1]
                        })
            
            return dataset_links
            
        except Exception as e:
            logger.error(f"Error getting available datasets: {e}")
            return []
    
    def extract_date_from_title(self, title):
        """
        Extract date from dataset title (e.g., "Prescription Cost Analysis (PCA) - Jan 2021")
        """
        try:
            # Extract month and year from title
            match = re.search(r'(\w{3})\s+(\d{4})', title)
            if match:
                month_str, year_str = match.groups()
                
                # Convert month abbreviation to number
                month_map = {
                    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                }
                
                month_num = month_map.get(month_str)
                if month_num:
                    return f"{year_str}{month_num}"
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting date from title '{title}': {e}")
            return None
    
    def get_download_url(self, resource_url):
        """
        Get the actual CSV download URL from the resource page
        """
        try:
            response = self.session.get(resource_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for download links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.endswith('.csv') or 'download' in href.lower():
                    return urljoin(self.base_url, href)
            
            # Alternative: look for resource URLs in the page
            for link in soup.find_all('a', href=True):
                if '/dataset/' in link['href'] and '/resource/' in link['href'] and '/download/' in link['href']:
                    return urljoin(self.base_url, link['href'])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting download URL from {resource_url}: {e}")
            return None
    
    def filter_columns(self, df):
        """
        Filter dataframe to include only required columns
        """
        available_columns = df.columns.tolist()
        logger.info(f"Available columns: {available_columns}")
        
        # Find which required columns are actually present
        present_columns = [col for col in self.required_columns if col in available_columns]
        missing_columns = [col for col in self.required_columns if col not in available_columns]
        
        if missing_columns:
            logger.warning(f"Missing columns: {missing_columns}")
        
        if present_columns:
            logger.info(f"Filtering to columns: {present_columns}")
            return df[present_columns].copy()
        else:
            logger.error("None of the required columns found in dataset!")
            return None
    
    def download_dataset(self, download_url, filename, max_retries=3):
        """
        Download a single dataset with retry logic
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"Downloading {filename} (attempt {attempt + 1}/{max_retries})")
                
                response = self.session.get(download_url, stream=True)
                response.raise_for_status()
                
                os.makedirs('pca_data', exist_ok=True)
                filepath = os.path.join('pca_data', filename)
                
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logger.info(f"Successfully downloaded {filename}")
                return filepath
                
            except Exception as e:
                logger.error(f"Error downloading {filename} (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)  # Wait before retry
                else:
                    return None
        
        return None
    
    def filter_datasets_by_date_range(self, datasets, start_date="202101"):
        """
        Filter datasets to only include those from start_date onwards
        """
        filtered_datasets = []
        
        for dataset in datasets:
            date_str = self.extract_date_from_title(dataset['title'])
            if date_str and date_str >= start_date:
                dataset['date'] = date_str
                filtered_datasets.append(dataset)
        
        # Sort by date
        filtered_datasets.sort(key=lambda x: x['date'])
        
        return filtered_datasets
    
    def scrape_all_data(self, start_date="202101", delay_between_downloads=2):
        """
        Main method to scrape all PCA data from start_date to latest
        """
        logger.info("Starting NHS PCA data scraping...")
        
        # Get all available datasets
        logger.info("Getting list of available datasets...")
        datasets = self.get_available_datasets()
        
        if not datasets:
            logger.error("No datasets found!")
            return []
        
        logger.info(f"Found {len(datasets)} total datasets")
        
        # Filter by date range
        filtered_datasets = self.filter_datasets_by_date_range(datasets, start_date)
        logger.info(f"Found {len(filtered_datasets)} datasets from {start_date} onwards")
        
        downloaded_files = []
        
        for i, dataset in enumerate(filtered_datasets):
            try:
                logger.info(f"Processing dataset {i+1}/{len(filtered_datasets)}: {dataset['title']}")
                
                # Get download URL
                download_url = self.get_download_url(dataset['url'])
                
                if not download_url:
                    # Try direct construction of download URL
                    download_url = f"{self.base_url}/dataset/prescription-cost-analysis-pca-monthly-data/resource/{dataset['resource_id']}/download"
                
                if download_url:
                    filename = f"PCA_{dataset['date']}.csv"
                    filepath = self.download_dataset(download_url, filename)
                    
                    if filepath:
                        downloaded_files.append({
                            'date': dataset['date'],
                            'title': dataset['title'],
                            'filepath': filepath,
                            'download_url': download_url
                        })
                    else:
                        logger.warning(f"Failed to download {dataset['title']}")
                else:
                    logger.warning(f"Could not find download URL for {dataset['title']}")
                
                # Add delay between downloads to be polite
                if i < len(filtered_datasets) - 1:
                    time.sleep(delay_between_downloads)
                    
            except Exception as e:
                logger.error(f"Error processing dataset {dataset['title']}: {e}")
                continue
        
        logger.info(f"Scraping completed. Downloaded {len(downloaded_files)} files")
        return downloaded_files
    
    def combine_datasets(self, downloaded_files, output_filename="combined_pca_data.csv"):
        """
        Combine all downloaded datasets into a single CSV file with filtered columns
        """
        if not downloaded_files:
            logger.warning("No files to combine")
            return None
        
        logger.info(f"Combining {len(downloaded_files)} datasets...")
        
        combined_data = []
        
        for file_info in downloaded_files:
            try:
                logger.info(f"Reading {file_info['filepath']}")
                df = pd.read_csv(file_info['filepath'])
                
                # Filter to required columns
                filtered_df = self.filter_columns(df)
                
                if filtered_df is not None:
                    # Add metadata columns
                    filtered_df['data_source_date'] = file_info['date']
                    filtered_df['data_source_title'] = file_info['title']
                    
                    combined_data.append(filtered_df)
                    logger.info(f"Added {len(filtered_df):,} records from {file_info['date']}")
                else:
                    logger.warning(f"Skipping {file_info['filepath']} - no required columns found")
                
            except Exception as e:
                logger.error(f"Error reading {file_info['filepath']}: {e}")
                continue
        
        if combined_data:
            logger.info("Concatenating all datasets...")
            final_df = pd.concat(combined_data, ignore_index=True)
            
            # Save as CSV
            output_path = os.path.join('pca_data', output_filename)
            final_df.to_csv(output_path, index=False)
            
            logger.info(f"Combined dataset saved to {output_path}")
            logger.info(f"Total records: {len(final_df):,}")
            logger.info(f"Columns: {list(final_df.columns)}")
            logger.info(f"Date range: {final_df['data_source_date'].min()} to {final_df['data_source_date'].max()}")
            
            # Show sample of data
            logger.info("\nSample of combined data:")
            print(final_df.head())
            
            return output_path
        
        return None

def main():
    # Initialize scraper
    scraper = NHSPCADataScraper()
    
    # Scrape all data from January 2021 onwards
    downloaded_files = scraper.scrape_all_data(start_date="202101", delay_between_downloads=3)
    
    if downloaded_files:
        # Print summary
        print("\n" + "="*60)
        print("DOWNLOAD SUMMARY")
        print("="*60)
        for file_info in downloaded_files:
            print(f"{file_info['date']}: {file_info['title']}")
        
        # Combine all datasets
        combined_file = scraper.combine_datasets(downloaded_files)
        
        if combined_file:
            print(f"\nAll data combined into: {combined_file}")
            
            # Load and show basic info about combined dataset
            df = pd.read_csv(combined_file)
            print(f"\nDataset Info:")
            print(f"- Total records: {len(df):,}")
            print(f"- Columns: {list(df.columns)}")
            print(f"- Date range: {df['data_source_date'].min()} to {df['data_source_date'].max()}")
            print(f"- File size: {os.path.getsize(combined_file) / 1024**2:.1f} MB")
            
            # Show summary statistics for numeric columns
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                print(f"\nSummary statistics for numeric columns:")
                print(df[numeric_cols].describe())
    else:
        print("No files were downloaded successfully")

if __name__ == "__main__":
    main()