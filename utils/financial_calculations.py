import pandas as pd
import numpy as np
from typing import Dict, List, Union, Optional

class FinancialCalculator:
    """
    Utility class for calculating financial ratios and metrics
    """
    
    @staticmethod
    def calculate_ratios(balance_sheet: pd.DataFrame, 
                         income_statement: pd.DataFrame, 
                         cash_flow: Optional[pd.DataFrame] = None) -> Dict[str, float]:
        """
        Calculate key financial ratios from financial statements
        
        Args:
            balance_sheet (pd.DataFrame): Balance sheet data
            income_statement (pd.DataFrame): Income statement data
            cash_flow (pd.DataFrame, optional): Cash flow statement data
            
        Returns:
            Dict[str, float]: Dictionary of calculated financial ratios
        """
        ratios = {}
        
        # Ensure we have data with the same period
        if balance_sheet.empty or income_statement.empty:
            return ratios
        
        # Extract the most recent financial data
        try:
            bs = balance_sheet.iloc[-1]  # Most recent balance sheet
            is_data = income_statement.iloc[-1]  # Most recent income statement
            
            # Profitability Ratios
            # ROA (Return on Assets)
            if 'TỔNG CỘNG TÀI SẢN' in bs and bs['TỔNG CỘNG TÀI SẢN'] != 0 and 'Lợi nhuận sau thuế thu nhập doanh nghiệp' in is_data:
                ratios['ROA'] = (is_data['Lợi nhuận sau thuế thu nhập doanh nghiệp'] / bs['TỔNG CỘNG TÀI SẢN']) * 100
            
            # ROE (Return on Equity)
            if 'VỐN CHỦ SỞ HỮU' in bs and bs['VỐN CHỦ SỞ HỮU'] != 0 and 'Lợi nhuận sau thuế thu nhập doanh nghiệp' in is_data:
                ratios['ROE'] = (is_data['Lợi nhuận sau thuế thu nhập doanh nghiệp'] / bs['VỐN CHỦ SỞ HỮU']) * 100
            
            # ROS (Return on Sales)
            if 'Doanh thu thuần' in is_data and is_data['Doanh thu thuần'] != 0 and 'Lợi nhuận sau thuế thu nhập doanh nghiệp' in is_data:
                ratios['ROS'] = (is_data['Lợi nhuận sau thuế thu nhập doanh nghiệp'] / is_data['Doanh thu thuần']) * 100
            
            # Gross Profit Margin
            if 'Doanh thu thuần' in is_data and is_data['Doanh thu thuần'] != 0 and 'Lợi nhuận gộp về bán hàng và cung cấp dịch vụ' in is_data:
                ratios['Gross_Profit_Margin'] = (is_data['Lợi nhuận gộp về bán hàng và cung cấp dịch vụ'] / is_data['Doanh thu thuần']) * 100
            
            # Liquidity Ratios
            # Current Ratio
            if 'Nợ ngắn hạn' in bs and bs['Nợ ngắn hạn'] != 0 and 'TÀI SẢN NGẮN HẠN' in bs:
                ratios['Current_Ratio'] = bs['TÀI SẢN NGẮN HẠN'] / bs['Nợ ngắn hạn']
            
            # Quick Ratio
            if 'Nợ ngắn hạn' in bs and bs['Nợ ngắn hạn'] != 0 and 'TÀI SẢN NGẮN HẠN' in bs and 'Hàng tồn kho, ròng' in bs:
                ratios['Quick_Ratio'] = (bs['TÀI SẢN NGẮN HẠN'] - bs['Hàng tồn kho, ròng']) / bs['Nợ ngắn hạn']
            
            # Leverage Ratios
            # Debt to Assets Ratio
            if 'TỔNG CỘNG TÀI SẢN' in bs and bs['TỔNG CỘNG TÀI SẢN'] != 0 and 'NỢ PHẢI TRẢ' in bs:
                ratios['Debt_to_Assets'] = (bs['NỢ PHẢI TRẢ'] / bs['TỔNG CỘNG TÀI SẢN']) * 100
            
            # Debt to Equity Ratio
            if 'VỐN CHỦ SỞ HỮU' in bs and bs['VỐN CHỦ SỞ HỮU'] != 0 and 'NỢ PHẢI TRẢ' in bs:
                ratios['Debt_to_Equity'] = (bs['NỢ PHẢI TRẢ'] / bs['VỐN CHỦ SỞ HỮU']) * 100
            
            # Interest Coverage Ratio
            if 'Trong đó: Chi phí lãi vay' in is_data and is_data['Trong đó: Chi phí lãi vay'] != 0 and 'Lợi nhuận thuần từ hoạt động kinh doanh' in is_data:
                ratios['Interest_Coverage'] = is_data['Lợi nhuận thuần từ hoạt động kinh doanh'] / is_data['Trong đó: Chi phí lãi vay']
            
            # Efficiency Ratios
            # Asset Turnover Ratio
            if 'TỔNG CỘNG TÀI SẢN' in bs and bs['TỔNG CỘNG TÀI SẢN'] != 0 and 'Doanh thu thuần' in is_data:
                ratios['Asset_Turnover'] = is_data['Doanh thu thuần'] / bs['TỔNG CỘNG TÀI SẢN']
            
            # Add Cash Flow Ratios if cash flow data is available
            if cash_flow is not None and not cash_flow.empty:
                cf = cash_flow.iloc[-1]  # Most recent cash flow statement
                
                # Operating Cash Flow Ratio
                if 'Nợ ngắn hạn' in bs and bs['Nợ ngắn hạn'] != 0 and 'Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh (TT)' in cf:
                    ratios['Operating_Cash_Flow_Ratio'] = cf['Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh (TT)'] / bs['Nợ ngắn hạn']
                
                # Cash Flow to Debt Ratio
                if 'NỢ PHẢI TRẢ' in bs and bs['NỢ PHẢI TRẢ'] != 0 and 'Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh (TT)' in cf:
                    ratios['Cash_Flow_to_Debt'] = cf['Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh (TT)'] / bs['NỢ PHẢI TRẢ']
            
        except Exception as e:
            print(f"Error calculating financial ratios: {e}")
        
        return ratios
    
    @staticmethod
    def calculate_growth_rates(financial_data: pd.DataFrame, 
                              metrics: List[str], 
                              periods: Optional[int] = 4) -> Dict[str, float]:
        """
        Calculate growth rates for specified financial metrics
        
        Args:
            financial_data (pd.DataFrame): Time series financial data
            metrics (List[str]): List of metrics to calculate growth rates for
            periods (int, optional): Number of periods to calculate growth over (default: 4 quarters = 1 year)
            
        Returns:
            Dict[str, float]: Dictionary of calculated growth rates
        """
        growth_rates = {}
        
        if financial_data.empty or len(financial_data) <= periods:
            return growth_rates
        
        try:
            # Sort by year and quarter
            financial_data = financial_data.sort_values(by=['Năm', 'Quý'])
            
            for metric in metrics:
                if metric in financial_data.columns:
                    # Get current and previous values
                    current_value = financial_data.iloc[-1][metric]
                    previous_value = financial_data.iloc[-1-periods][metric]
                    
                    # Calculate growth rate if previous value is not zero
                    if previous_value != 0:
                        growth_rate = ((current_value - previous_value) / abs(previous_value)) * 100
                        growth_rates[f"{metric}_growth"] = growth_rate
        
        except Exception as e:
            print(f"Error calculating growth rates: {e}")
        
        return growth_rates
    
    @staticmethod
    def calculate_sector_averages(sector_data: List[Dict[str, float]]) -> Dict[str, float]:
        """
        Calculate average financial metrics for a sector
        
        Args:
            sector_data (List[Dict[str, float]]): List of financial metrics dictionaries for companies in a sector
            
        Returns:
            Dict[str, float]: Dictionary of average sector metrics
        """
        if not sector_data:
            return {}
        
        # Initialize result dictionary
        averages = {}
        
        try:
            # Get all metric keys
            all_keys = set()
            for company_data in sector_data:
                all_keys.update(company_data.keys())
            
            # Calculate averages for each metric
            for key in all_keys:
                values = [
                    company_data[key] 
                    for company_data in sector_data 
                    if key in company_data and not pd.isna(company_data[key])
                ]
                
                if values:
                    averages[f"avg_{key}"] = sum(values) / len(values)
        
        except Exception as e:
            print(f"Error calculating sector averages: {e}")
        
        return averages
    
    @staticmethod
    def compare_with_sector(company_metrics: Dict[str, float], 
                          sector_metrics: Dict[str, float]) -> Dict[str, float]:
        """
        Compare company metrics with sector averages
        
        Args:
            company_metrics (Dict[str, float]): Company financial metrics
            sector_metrics (Dict[str, float]): Sector average metrics
            
        Returns:
            Dict[str, float]: Dictionary with comparison results (% difference from sector average)
        """
        comparison = {}
        
        try:
            for company_key, company_value in company_metrics.items():
                # Find corresponding sector average
                sector_key = f"avg_{company_key}"
                
                if sector_key in sector_metrics and sector_metrics[sector_key] != 0:
                    # Calculate percentage difference from sector average
                    diff_pct = ((company_value - sector_metrics[sector_key]) / sector_metrics[sector_key]) * 100
                    comparison[f"{company_key}_vs_sector"] = diff_pct
        
        except Exception as e:
            print(f"Error comparing with sector averages: {e}")
        
        return comparison