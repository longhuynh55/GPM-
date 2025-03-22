import pandas as pd
import os
import numpy as np
from typing import Dict, List, Union, Optional, Tuple

class FinancialDataLoader:
    """
    Utility class for loading and processing financial data from CSV files
    """
    
    def __init__(self, data_dir: str):
        """
        Initialize the data loader with the directory containing the CSV files
        
        Args:
            data_dir (str): Path to the directory containing the CSV files
        """
        self.data_dir = data_dir
        self.data_cache = {}
        self.file_mapping = {
            'avg_by_code': 'Average_by_Code.csv',
            'avg_by_sector': 'Average_by_Sector.csv',
            'balance_sheet': 'BCDKT.csv',
            'fin_statements': 'BCTC.csv',
            'income_statement': 'KQKD.csv',
            'cash_flow': 'LCTT.csv',
            'disclosures': 'TM.csv'
        }
        # Kiểm tra thư mục dữ liệu có tồn tại không
        if not os.path.isdir(data_dir):
            raise ValueError(f"Directory does not exist: {data_dir}")
        
        # Kiểm tra các file dữ liệu
        self._validate_data_files()
    
    def _validate_data_files(self) -> None:
        """
        Validate the existence of data files
        
        Raises:
            FileNotFoundError: If any required data file is missing
        """
        missing_files = []
        for key, filename in self.file_mapping.items():
            file_path = os.path.join(self.data_dir, filename)
            if not os.path.isfile(file_path):
                missing_files.append(filename)
        
        if missing_files:
            raise FileNotFoundError(f"Missing data files: {', '.join(missing_files)}")
        
    def load_all_data(self) -> Dict[str, pd.DataFrame]:
        """
        Load all financial data CSV files
        
        Returns:
            Dict[str, pd.DataFrame]: Dictionary containing all loaded dataframes
            
        Raises:
            Exception: If there are errors loading any file, with details about which files failed
        """
        result = {}
        errors = {}
        
        for key, filename in self.file_mapping.items():
            file_path = os.path.join(self.data_dir, filename)
            try:
                df = self._load_and_clean_csv(file_path)
                # Cache the data for future use
                self.data_cache[key] = df
                result[key] = df
            except Exception as e:
                errors[filename] = str(e)
                # Still create an empty DataFrame for consistency
                result[key] = pd.DataFrame()
        
        if errors:
            error_msg = "; ".join([f"{file}: {err}" for file, err in errors.items()])
            print(f"WARNING: Some files could not be loaded properly: {error_msg}")
        
        return result
    
    def _load_and_clean_csv(self, file_path: str) -> pd.DataFrame:
        """
        Load a CSV file and perform basic cleaning operations
        
        Args:
            file_path (str): Path to the CSV file
            
        Returns:
            pd.DataFrame: Cleaned dataframe
        
        Raises:
            FileNotFoundError: If the file does not exist
            Exception: For other errors during loading
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Thử với nhiều encoding khác nhau nếu cần
        encodings = ['utf-8', 'latin1', 'cp1252']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            raise Exception(f"Could not decode file with any of the attempted encodings")
            
        # Chuẩn hóa tên cột
        df.columns = [col.strip() for col in df.columns]
        
        # Xử lý giá trị thiếu
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        df[numeric_cols] = df[numeric_cols].fillna(0)
        
        # Xử lý các cột ngày tháng nếu có
        if 'Năm' in df.columns:
            df['Năm'] = pd.to_numeric(df['Năm'], errors='coerce').fillna(0).astype(int)
        
        if 'Quý' in df.columns:
            df['Quý'] = pd.to_numeric(df['Quý'], errors='coerce').fillna(0).astype(int)
            
        return df
    
    def get_sectors(self) -> List[str]:
        """
        Get list of all available sectors
        
        Returns:
            List[str]: List of sector names
        """
        if 'avg_by_sector' not in self.data_cache:
            self.load_dataset('avg_by_sector')
            
        if 'avg_by_sector' in self.data_cache and 'Sector' in self.data_cache['avg_by_sector'].columns:
            return self.data_cache['avg_by_sector']['Sector'].dropna().unique().tolist()
        return []
    
    def get_companies(self) -> List[str]:
        """
        Get list of all available company codes
        
        Returns:
            List[str]: List of company codes
        """
        if 'avg_by_code' not in self.data_cache:
            self.load_dataset('avg_by_code')
            
        if 'avg_by_code' in self.data_cache and 'Mã' in self.data_cache['avg_by_code'].columns:
            return self.data_cache['avg_by_code']['Mã'].dropna().unique().tolist()
        return []
    
    def load_dataset(self, dataset_name: str) -> pd.DataFrame:
        """
        Load a specific dataset by name
        
        Args:
            dataset_name (str): Name of the dataset to load
                (avg_by_code, avg_by_sector, balance_sheet, fin_statements, 
                income_statement, cash_flow, disclosures)
        
        Returns:
            pd.DataFrame: The loaded dataframe
            
        Raises:
            ValueError: If the dataset name is unknown
            FileNotFoundError: If the file does not exist
        """
        # Return from cache if available
        if dataset_name in self.data_cache:
            return self.data_cache[dataset_name]
        
        if dataset_name not in self.file_mapping:
            raise ValueError(f"Unknown dataset: {dataset_name}. Available datasets: {', '.join(self.file_mapping.keys())}")
        
        file_path = os.path.join(self.data_dir, self.file_mapping[dataset_name])
        df = self._load_and_clean_csv(file_path)
        self.data_cache[dataset_name] = df
        
        return df
    
    def _validate_company_code(self, company_code: str) -> bool:
        """
        Validate if a company code exists in the data
        
        Args:
            company_code (str): Company code to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        companies = self.get_companies()
        return company_code in companies
    
    def _validate_sector_name(self, sector_name: str) -> bool:
        """
        Validate if a sector name exists in the data
        
        Args:
            sector_name (str): Sector name to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        sectors = self.get_sectors()
        return sector_name in sectors
    
    def get_company_data(self, company_code: str) -> Dict[str, Union[pd.DataFrame, Dict]]:
        """
        Get all data for a specific company
        
        Args:
            company_code (str): Company code to look up
        
        Returns:
            Dict containing company data from different datasets
            
        Raises:
            ValueError: If the company code is invalid
        """
        # Validate company code
        if not self._validate_company_code(company_code):
            raise ValueError(f"Invalid company code: {company_code}")
            
        result = {}
        
        # Get company metrics from avg_by_code
        if 'avg_by_code' not in self.data_cache:
            self.load_dataset('avg_by_code')
        
        if 'avg_by_code' in self.data_cache:
            company_metrics = self.data_cache['avg_by_code'][
                self.data_cache['avg_by_code']['Mã'] == company_code
            ]
            if not company_metrics.empty:
                result['metrics'] = company_metrics.iloc[0].to_dict()
            else:
                result['metrics'] = {}
                print(f"WARNING: No metrics found for company {company_code}")
            
        # Get financial statements
        for dataset in ['balance_sheet', 'income_statement', 'cash_flow']:
            if dataset not in self.data_cache:
                try:
                    self.load_dataset(dataset)
                except Exception as e:
                    print(f"WARNING: Could not load {dataset}: {e}")
                    continue
            
            if dataset in self.data_cache:
                if 'Mã' not in self.data_cache[dataset].columns:
                    print(f"WARNING: 'Mã' column not found in {dataset}")
                    result[dataset] = pd.DataFrame()
                    continue
                    
                company_data = self.data_cache[dataset][
                    self.data_cache[dataset]['Mã'] == company_code
                ]
                
                if not company_data.empty:
                    # Sort by year and quarter if available
                    if all(col in company_data.columns for col in ['Năm', 'Quý']):
                        company_data = company_data.sort_values(by=['Năm', 'Quý'])
                    
                    result[dataset] = company_data
                else:
                    result[dataset] = pd.DataFrame()
                    print(f"WARNING: No {dataset} data found for company {company_code}")
        
        return result
    
    def get_sector_data(self, sector_name: str) -> Dict[str, Union[pd.DataFrame, Dict]]:
        """
        Get all data for a specific sector
        
        Args:
            sector_name (str): Sector name to look up
        
        Returns:
            Dict containing sector data from different datasets
            
        Raises:
            ValueError: If the sector name is invalid
        """
        # Validate sector name
        if not self._validate_sector_name(sector_name):
            raise ValueError(f"Invalid sector name: {sector_name}")
            
        result = {}
        
        # Get sector metrics from avg_by_sector
        if 'avg_by_sector' not in self.data_cache:
            self.load_dataset('avg_by_sector')
        
        if 'avg_by_sector' in self.data_cache:
            sector_metrics = self.data_cache['avg_by_sector'][
                self.data_cache['avg_by_sector']['Sector'] == sector_name
            ]
            if not sector_metrics.empty:
                result['metrics'] = sector_metrics.iloc[0].to_dict()
            else:
                result['metrics'] = {}
                print(f"WARNING: No metrics found for sector {sector_name}")
        
        # Get companies in this sector - use more consistent approach
        companies_in_sector = set()
        sector_columns = ['Ngành ICB - cấp 1', 'Sector', 'Ngành']  # Possible column names
        
        for dataset in ['balance_sheet', 'income_statement', 'cash_flow']:
            if dataset not in self.data_cache:
                try:
                    self.load_dataset(dataset)
                except Exception as e:
                    print(f"WARNING: Could not load {dataset}: {e}")
                    continue
            
            if dataset in self.data_cache:
                df = self.data_cache[dataset]
                
                # Find the correct sector column
                sector_col = None
                for col in sector_columns:
                    if col in df.columns:
                        sector_col = col
                        break
                
                if sector_col is None:
                    print(f"WARNING: No sector column found in {dataset}")
                    continue
                    
                # Filter by sector
                sector_filter = df[sector_col] == sector_name
                if 'Mã' in df.columns:
                    companies = df[sector_filter]['Mã'].dropna().unique().tolist()
                    companies_in_sector.update(companies)
        
        result['companies'] = list(companies_in_sector)
        
        if not result['companies']:
            print(f"WARNING: No companies found for sector {sector_name}")
        
        return result
    
    def get_financial_time_series(self, company_code: str, 
                                 metrics: List[str], 
                                 years: Optional[List[int]] = None) -> pd.DataFrame:
        """
        Get time series data for specific financial metrics for a company
        
        Args:
            company_code (str): Company code
            metrics (List[str]): List of metric names to retrieve
            years (List[int], optional): Specific years to include (default: all available)
        
        Returns:
            pd.DataFrame: Time series data for the requested metrics
            
        Raises:
            ValueError: If the company code is invalid or metrics are not specified
        """
        # Validate company code
        if not self._validate_company_code(company_code):
            raise ValueError(f"Invalid company code: {company_code}")
            
        if not metrics:
            raise ValueError("At least one metric must be specified")
        
        # Map metrics to datasets
        metric_to_dataset = {
            # Balance sheet metrics
            'TÀI SẢN NGẮN HẠN': 'balance_sheet',
            'Tiền và tương đương tiền': 'balance_sheet',
            'TỔNG CỘNG TÀI SẢN': 'balance_sheet',
            'NỢ PHẢI TRẢ': 'balance_sheet',
            'VỐN CHỦ SỞ HỮU': 'balance_sheet',
            
            # Income statement metrics
            'Doanh thu thuần': 'income_statement',
            'Lợi nhuận gộp về bán hàng và cung cấp dịch vụ': 'income_statement',
            'Lợi nhuận thuần từ hoạt động kinh doanh': 'income_statement',
            'Tổng lợi nhuận kế toán trước thuế': 'income_statement',
            'Lợi nhuận sau thuế thu nhập doanh nghiệp': 'income_statement',
            
            # Cash flow metrics
            'Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh (TT)': 'cash_flow',
            'Lưu chuyển tiền tệ ròng từ hoạt động đầu tư (TT)': 'cash_flow',
            'Lưu chuyển tiền tệ từ hoạt động tài chính (TT)': 'cash_flow'
        }
        
        # Validate metrics
        unknown_metrics = [m for m in metrics if m not in metric_to_dataset]
        if unknown_metrics:
            print(f"WARNING: Unknown metrics will be ignored: {', '.join(unknown_metrics)}")
        
        # Identify needed datasets
        needed_datasets = set()
        for metric in metrics:
            if metric in metric_to_dataset:
                needed_datasets.add(metric_to_dataset[metric])
        
        # Nothing to do if no valid metrics
        if not needed_datasets:
            print("WARNING: No valid metrics specified")
            return pd.DataFrame()
        
        # Load datasets if needed
        dataset_data = {}
        for dataset in needed_datasets:
            try:
                if dataset not in self.data_cache:
                    self.load_dataset(dataset)
                    
                if dataset in self.data_cache:
                    # Filter by company
                    if 'Mã' not in self.data_cache[dataset].columns:
                        print(f"WARNING: 'Mã' column not found in {dataset}")
                        continue
                        
                    company_data = self.data_cache[dataset][
                        self.data_cache[dataset]['Mã'] == company_code
                    ]
                    
                    # Filter by years if specified
                    if years and 'Năm' in company_data.columns:
                        company_data = company_data[company_data['Năm'].isin(years)]
                    
                    # Sort by year and quarter if available
                    if all(col in company_data.columns for col in ['Năm', 'Quý']):
                        company_data = company_data.sort_values(by=['Năm', 'Quý'])
                    
                    dataset_data[dataset] = company_data
            except Exception as e:
                print(f"WARNING: Error processing {dataset}: {e}")
        
        # Create a unified time series with all period identifiers
        periods = set()
        for dataset, df in dataset_data.items():
            if not df.empty and all(col in df.columns for col in ['Năm', 'Quý']):
                for _, row in df.iterrows():
                    periods.add((row['Năm'], row['Quý']))
        
        if not periods:
            print(f"WARNING: No time periods found for company {company_code}")
            return pd.DataFrame()
            
        # Create base dataframe with time periods
        periods = sorted(periods)
        result_df = pd.DataFrame({
            'Mã': company_code,
            'Năm': [p[0] for p in periods],
            'Quý': [p[1] for p in periods]
        })
        
        # Add metrics from each dataset
        for metric in metrics:
            if metric in metric_to_dataset:
                dataset = metric_to_dataset[metric]
                if dataset in dataset_data and not dataset_data[dataset].empty and metric in dataset_data[dataset].columns:
                    # Create a reference df for this metric
                    metric_df = dataset_data[dataset][['Năm', 'Quý', metric]].copy()
                    
                    # Merge with result
                    result_df = pd.merge(
                        result_df, 
                        metric_df,
                        on=['Năm', 'Quý'],
                        how='left'
                    )
                else:
                    # Add empty column if metric not found
                    result_df[metric] = np.nan
        
        return result_df