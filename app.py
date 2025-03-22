from flask import Flask, render_template, request, jsonify, make_response, send_file, abort
import pandas as pd
import os
import numpy as np
import json
import io
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Sử dụng Agg backend để tránh lỗi trên server không có GUI
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
from datetime import datetime
import base64
import traceback

# Không nhập WeasyPrint trực tiếp, mà kiểm tra nó có sẵn không
PDF_AVAILABLE = False
try:
    from weasyprint import HTML, CSS
    PDF_AVAILABLE = True
    print("WeasyPrint available - PDF export enabled")
except ImportError:
    print("WeasyPrint not available - PDF export disabled")
    print("To enable PDF export, install GTK3 and WeasyPrint following the instructions at:")
    print("https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation")

app = Flask(__name__)

# Data loading
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

def load_data():
    data = {
        'avg_by_code': pd.read_csv(os.path.join(DATA_DIR, 'Average_by_Code.csv'), encoding='utf-8'),
        'avg_by_sector': pd.read_csv(os.path.join(DATA_DIR, 'Average_by_Sector.csv'), encoding='utf-8'),
        'balance_sheet': pd.read_csv(os.path.join(DATA_DIR, 'BCDKT.csv'), encoding='utf-8'),
        'fin_statements': pd.read_csv(os.path.join(DATA_DIR, 'BCTC.csv'), encoding='utf-8'),
        'income_statement': pd.read_csv(os.path.join(DATA_DIR, 'KQKD.csv'), encoding='utf-8'),
        'cash_flow': pd.read_csv(os.path.join(DATA_DIR, 'LCTT.csv'), encoding='utf-8'),
        'disclosures': pd.read_csv(os.path.join(DATA_DIR, 'TM.csv'), encoding='utf-8')
    }
   
    # Try to load company info from Excel file if available
    try:
        thongtin_path = os.path.join(DATA_DIR, 'thongtin.xlsx')
        if os.path.exists(thongtin_path):
            data['company_info'] = pd.read_excel(thongtin_path)
            print("Company info loaded from thongtin.xlsx")
    except Exception as e:
        print(f"Error loading thongtin.xlsx: {e}")
   
    return data


# Load data once when the app starts
try:
    app_data = load_data()
    print("Data loaded successfully")
except Exception as e:
    print(f"Error loading data: {e}")
    app_data = {}


@app.route('/')
def index():
    # Get list of sectors for dropdown
    sectors = app_data['avg_by_sector']['Sector'].tolist() if 'avg_by_sector' in app_data else []
   
    # Get top performing companies by ROE
    top_companies = []
    if 'avg_by_code' in app_data:
        top_companies = app_data['avg_by_code'].sort_values(by='ROE (%)', ascending=False).head(10)[['Mã', 'ROE (%)']].to_dict(orient='records')
   
    # Get average financial ratios by sector
    sector_metrics = []
    if 'avg_by_sector' in app_data:
        sector_metrics = app_data['avg_by_sector'][['Sector', 'Average ROA', 'Average ROE', 'Average ROS']].head(5).to_dict(orient='records')
   
    # General market data
    market_data = {
        'total_companies': len(app_data['avg_by_code']) if 'avg_by_code' in app_data else 0,
        'avg_market_roe': app_data['avg_by_code']['ROE (%)'].mean() if 'avg_by_code' in app_data else 0,
        'avg_market_roa': app_data['avg_by_code']['ROA (%)'].mean() if 'avg_by_code' in app_data else 0,
        'sectors_count': len(sectors)
    }
   
    # Get all company codes for search autocomplete
    all_companies = []
    if 'fin_statements' in app_data:
        all_companies = sorted(app_data['fin_statements']['Mã'].unique().tolist())
   
    return render_template('index.html',
                           sectors=sectors,
                           top_companies=top_companies,
                           sector_metrics=sector_metrics,
                           market_data=market_data,
                           all_companies=all_companies)


@app.route('/api/companies')
def get_companies():
    """API endpoint for company search suggestions"""
    search_term = request.args.get('term', '').upper()
   
    # Get list of companies from fin_statements data
    companies = []
    if 'fin_statements' in app_data:
        # Get unique company codes and corresponding names
        df = app_data['fin_statements'][['Mã', 'Tên công ty']].drop_duplicates()
        companies = [
            {'value': row['Mã'], 'label': f"{row['Mã']} - {row['Tên công ty']}"}
            for _, row in df.iterrows()
        ]
       
        # Filter based on search term
        if search_term:
            companies = [
                company for company in companies
                if search_term in company['value'] or
                search_term.lower() in company['label'].lower()
            ]
       
        # Sort alphabetically by code
        companies = sorted(companies, key=lambda x: x['value'])
   
    return jsonify(companies)


@app.route('/sector_analysis')
def sector_analysis():
    # Get the sector parameter from the query string
    selected_sector = request.args.get('sector', None)
   
    # Get all available sectors for the dropdown
    sectors = app_data['avg_by_sector']['Sector'].tolist() if 'avg_by_sector' in app_data else []
   
    # If a sector is selected, get the sector data
    sector_info = {}
    sector_metrics = {}
    trend_analysis = {}
    trend_data = {}
    top_companies = []
    sector_comparisons = {}
   
    if selected_sector:
        # Get sector metrics
        sector_row = app_data['avg_by_sector'][app_data['avg_by_sector']['Sector'] == selected_sector]
        if not sector_row.empty:
            sector_metrics = {
                'Average_ROA': sector_row['Average ROA'].values[0],
                'Average_ROE': sector_row['Average ROE'].values[0],
                'Average_ROS': sector_row['Average ROS'].values[0],
                'Average_EBITDA_Margin': sector_row['Average EBITDA Margin'].values[0],
                'Average_D_E_Ratio': sector_row['Average D/E Ratio'].values[0]
            }
       
        # Get companies in this sector for the top companies list
        companies_in_sector = []
        if 'fin_statements' in app_data:
            sector_filter = app_data['fin_statements']['Ngành ICB - cấp 3'] == selected_sector
            companies_in_sector = app_data['fin_statements'][sector_filter]['Mã'].unique()
       
        # Get company metrics for companies in this sector
        if 'avg_by_code' in app_data and len(companies_in_sector) > 0:
            sector_companies = app_data['avg_by_code'][app_data['avg_by_code']['Mã'].isin(companies_in_sector)]
            # Sort by ROE and get top 10
            top_companies_df = sector_companies.sort_values(by='ROE (%)', ascending=False).head(10)
           
            # Format for the template
            top_companies = [
                {
                    'code': row['Mã'],
                    'name': row['Mã'],  # Would ideally get company name from another dataset
                    'roe': row['ROE (%)'],
                    'roa': row['ROA (%)'],
                    'ros': row['ROS (%)'],
                    'revenue_growth': row['Revenue Growth (%)']
                }
                for _, row in top_companies_df.iterrows()
            ]
       
        # Basic sector info
        sector_info = {
            'company_count': len(companies_in_sector),
            'market_share': 5.0,  # Placeholder value
            'description': f"Thông tin về ngành {selected_sector} sẽ được hiển thị ở đây."
        }
       
        # Placeholder trend analysis
        trend_analysis = {
            'profitability_comment': f"Phân tích xu hướng khả năng sinh lời của ngành {selected_sector} trong giai đoạn 2020-2024.",
            'liquidity_comment': f"Phân tích xu hướng thanh khoản của ngành {selected_sector} trong giai đoạn 2020-2024.",
            'leverage_comment': f"Phân tích xu hướng đòn bẩy của ngành {selected_sector} trong giai đoạn 2020-2024.",
            'growth_comment': f"Phân tích xu hướng tăng trưởng của ngành {selected_sector} trong giai đoạn 2020-2024."
        }
       
        # Placeholder trend data for charts
        trend_data = {
            'profitability': json.dumps({
                'labels': ['2020', '2021', '2022', '2023', '2024'],
                'roa': [5.2, 6.1, 5.8, 6.5, 7.0],
                'roe': [12.5, 13.2, 12.8, 14.0, 15.2],
                'ros': [8.3, 9.1, 8.7, 9.5, 10.2]
            }),
            'liquidity': json.dumps({
                'labels': ['2020', '2021', '2022', '2023', '2024'],
                'current_ratio': [1.8, 1.9, 1.85, 2.0, 2.1],
                'quick_ratio': [1.2, 1.3, 1.25, 1.4, 1.5]
            }),
            'leverage': json.dumps({
                'labels': ['2020', '2021', '2022', '2023', '2024'],
                'debt_to_assets': [48, 47, 46, 45, 44],
                'debt_to_equity': [92, 89, 85, 82, 79]
            }),
            'growth': json.dumps({
                'labels': ['2020', '2021', '2022', '2023', '2024'],
                'revenue_growth': [5, 12, 8, 15, 10],
                'net_income_growth': [7, 14, 9, 18, 12]
            })
        }
       
        # Placeholder sector comparisons
        sector_comparisons = {
            'comment': f"So sánh ngành {selected_sector} với các ngành khác.",
            'data': json.dumps([
                {'name': selected_sector, 'roa': 6.5, 'roe': 15.0, 'ros': 10.0, 'ebitda_margin': 18.0, 'revenue_growth': 12.0, 'debt_to_equity': 80.0},
                {'name': 'Ngành A', 'roa': 5, 'roe': 12, 'ros': 8, 'ebitda_margin': 15, 'revenue_growth': 10, 'debt_to_equity': 75},
                {'name': 'Ngành B', 'roa': 7, 'roe': 16, 'ros': 11, 'ebitda_margin': 20, 'revenue_growth': 15, 'debt_to_equity': 85},
                {'name': 'Ngành C', 'roa': 4, 'roe': 10, 'ros': 7, 'ebitda_margin': 14, 'revenue_growth': 8, 'debt_to_equity': 70},
                {'name': 'Ngành D', 'roa': 8, 'roe': 18, 'ros': 12, 'ebitda_margin': 22, 'revenue_growth': 16, 'debt_to_equity': 90}
            ])
        }
   
    return render_template('sector_analysis.html',
                           sectors=sectors,
                           selected_sector=selected_sector,
                           sector_info=sector_info,
                           sector_metrics=sector_metrics,
                           trend_analysis=trend_analysis,
                           trend_data=trend_data,
                           top_companies=top_companies,
                           sector_comparisons=sector_comparisons)


# Update the company_analysis function to include available years data
@app.route('/company_analysis')
def company_analysis():
    # Get the company code parameter from the query string
    selected_company_code = request.args.get('code', None)
   
    # Initialize variables to pass to the template
    company_info = {}
    company_metrics = {}
    financial_time_series = {}
    ratio_time_series = {}
    ratio_analysis = {}
    balance_sheet = {}
    income_statement = {}
    financial_statements = {}
    competitor_comparison = {}
    company_ranking = {}
    company_profile = ""
    available_years = []
    balance_sheets = {}
    income_statements = {}
    cash_flows = {}
    financial_revenue_series = json.dumps({'labels': [], 'revenue': []})
    financial_profit_series = json.dumps({'labels': [], 'profit': []})
   
    if selected_company_code:
        try:
            # Get company data from fin_statements
            if 'fin_statements' in app_data:
                company_data = app_data['fin_statements'][app_data['fin_statements']['Mã'] == selected_company_code]
                if not company_data.empty:
                    # Get company name and basic info
                    company_name = company_data['Tên công ty'].iloc[0] if 'Tên công ty' in company_data.columns else f"Công ty {selected_company_code}"
                    exchange = company_data['Sàn'].iloc[0] if 'Sàn' in company_data.columns else "N/A"
                    icb_level1 = company_data['Ngành ICB - cấp 1'].iloc[0] if 'Ngành ICB - cấp 1' in company_data.columns else "N/A"
                    icb_level2 = company_data['Ngành ICB - cấp 2'].iloc[0] if 'Ngành ICB - cấp 2' in company_data.columns else "N/A"
                    icb_level3 = company_data['Ngành ICB - cấp 3'].iloc[0] if 'Ngành ICB - cấp 3' in company_data.columns else "N/A"
                   
                    # Set company_info
                    company_info = {
                        'name': company_name,
                        'exchange': exchange,
                        'icb_level1': icb_level1,
                        'icb_level2': icb_level2,
                        'icb_level3': icb_level3,
                        'sector': icb_level1  # For backward compatibility with existing template
                    }
                  
                    # Get company ranking within its industry (ICB level 3)
                    if 'balance_sheet' in app_data and icb_level3 != "N/A":
                        # Filter companies in the same industry
                        industry_companies = app_data['balance_sheet'][
                            app_data['balance_sheet']['Ngành ICB - cấp 3'] == icb_level3
                        ]
                       
                        # Get the latest data for each company
                        latest_data = []
                        for company in industry_companies['Mã'].unique():
                            company_bs = industry_companies[industry_companies['Mã'] == company].sort_values(by=['Năm', 'Quý'], ascending=False)
                            if not company_bs.empty:
                                company_latest = company_bs.iloc[0]
                                if 'TỔNG CỘNG TÀI SẢN' in company_latest and not pd.isna(company_latest['TỔNG CỘNG TÀI SẢN']):
                                    latest_data.append({
                                        'code': company,
                                        'total_assets': company_latest['TỔNG CỘNG TÀI SẢN']
                                    })
                       
                        # Sort by total assets
                        latest_data.sort(key=lambda x: x['total_assets'], reverse=True)
                       
                        # Find the rank of selected company
                        company_rank = next((i+1 for i, item in enumerate(latest_data) if item['code'] == selected_company_code), 0)
                        total_companies = len(latest_data)
                       
                        company_ranking = {
                            'rank': company_rank,
                            'total': total_companies,
                            'industry': icb_level3
                        }
            
            # Get available years for the company
            available_years = []
            
            if 'balance_sheet' in app_data:
                bs_data = app_data['balance_sheet'][app_data['balance_sheet']['Mã'] == selected_company_code]
                if not bs_data.empty and 'Năm' in bs_data.columns:
                    bs_years = bs_data['Năm'].dropna().astype(int).unique().tolist()
                    available_years.extend(bs_years)
            
            if 'income_statement' in app_data:
                is_data = app_data['income_statement'][app_data['income_statement']['Mã'] == selected_company_code]
                if not is_data.empty and 'Năm' in is_data.columns:
                    is_years = is_data['Năm'].dropna().astype(int).unique().tolist()
                    available_years.extend(is_years)
                
            if 'cash_flow' in app_data:
                cf_data = app_data['cash_flow'][app_data['cash_flow']['Mã'] == selected_company_code]
                if not cf_data.empty and 'Năm' in cf_data.columns:
                    cf_years = cf_data['Năm'].dropna().astype(int).unique().tolist()
                    available_years.extend(cf_years)
            
            # Remove duplicates and sort years
            available_years = sorted(list(set(available_years)), reverse=True) if available_years else []
            
            # Prepare data for the financial statements by year feature
            if 'balance_sheet' in app_data:
                balance_sheet_data = app_data['balance_sheet'][app_data['balance_sheet']['Mã'] == selected_company_code]
                if not balance_sheet_data.empty:
                    balance_sheets = balance_sheet_data.to_dict('records')
            
            if 'income_statement' in app_data:
                income_statement_data = app_data['income_statement'][app_data['income_statement']['Mã'] == selected_company_code]
                if not income_statement_data.empty:
                    income_statements = income_statement_data.to_dict('records')
            
            if 'cash_flow' in app_data:
                cash_flow_data = app_data['cash_flow'][app_data['cash_flow']['Mã'] == selected_company_code]
                if not cash_flow_data.empty:
                    cash_flows = cash_flow_data.to_dict('records')
                   
            # Get company profile information from thongtin.xlsx
            if 'company_info' in app_data:
                company_detail = app_data['company_info'][app_data['company_info']['Mã CK'] == selected_company_code]
                if not company_detail.empty:
                    # Check if 'Thông tin' column exists and extract profile information
                    if 'Thông tin' in company_detail.columns:
                        company_profile = company_detail['Thông tin'].iloc[0]
                        if pd.notna(company_profile):
                            company_info['profile'] = company_profile
                   
                    # Add additional details if available
                    for col in company_detail.columns:
                        if col not in ['Mã', 'Thông tin']:
                            value = company_detail[col].iloc[0]
                            if not pd.isna(value):
                                company_info[col.lower().replace(' ', '_')] = value
           
            # Get company metrics from avg_by_code
            if 'avg_by_code' in app_data:
                company_row = app_data['avg_by_code'][app_data['avg_by_code']['Mã'] == selected_company_code]
                if not company_row.empty:
                    # Extract metrics with safe handling
                    metrics_fields = [
                        ('ROA (%)', 'ROA', 0),
                        ('ROE (%)', 'ROE', 0),
                        ('ROS (%)', 'ROS', 0),
                        ('EBITDA Margin (%)', 'EBITDA_Margin', 0),
                        ('Current Ratio', 'Current_Ratio', 0),
                        ('Quick Ratio', 'Quick_Ratio', 0),
                        ('D/A (%)', 'Debt_to_Assets', 0),
                        ('D/E (%)', 'Debt_to_Equity', 0),
                        ('E/A (%)', 'Equity_to_Assets', 0),
                        ('Interest Coverage Ratio', 'Interest_Coverage', 0),
                        ('Inventory Turnover', 'Inventory_Turnover', 0),
                        ('Accounts Receivable Turnover', 'Receivables_Turnover', 0),
                        ('Total Asset Turnover', 'Asset_Turnover', 0)
                    ]
                    
                    company_metrics = {}
                    for src_field, dest_field, default_val in metrics_fields:
                        company_metrics[dest_field] = company_row[src_field].values[0] if src_field in company_row.columns and not pd.isna(company_row[src_field].values[0]) else default_val
                    
                    # Add placeholder comparison values (these would be calculated properly in a full implementation)
                    for field in ['ROA', 'ROE', 'ROS', 'EBITDA_Margin', 'Current_Ratio', 'Quick_Ratio', 
                                'Debt_to_Assets', 'Debt_to_Equity', 'Equity_to_Assets', 'Interest_Coverage',
                                'Inventory_Turnover', 'Receivables_Turnover', 'Asset_Turnover']:
                        company_metrics[f"{field}_vs_sector"] = 0.0
            
            # Prepare revenue and profit series data with error handling
            financial_revenue_series = json.dumps({'labels': [], 'revenue': []})
            financial_profit_series = json.dumps({'labels': [], 'profit': []})

            if 'income_statement' in app_data:
                # Filter data for the selected company
                company_income_data = app_data['income_statement'][app_data['income_statement']['Mã'] == selected_company_code]
                
                # Debug information
                print(f"Rows found for company {selected_company_code}: {len(company_income_data)}")
                
                # Sort by year and quarter to create time series
                if not company_income_data.empty:
                    print(f"Columns available: {company_income_data.columns.tolist()}")
                    # Make sure required columns exist before processing
                    required_columns = ['Năm', 'Quý']
                    if all(col in company_income_data.columns for col in required_columns):
                        company_income_data = company_income_data.sort_values(by=['Năm', 'Quý'])
                        
                        # Handle revenue chart
                        if 'Doanh thu thuần' in company_income_data.columns:
                            # Create time labels (Year-Quarter)
                            time_labels = [f"{int(row['Năm'])}-Q{int(row['Quý'])}" for _, row in company_income_data.iterrows() 
                                          if pd.notna(row['Năm']) and pd.notna(row['Quý'])]
                            
                            # Extract revenue data (convert to billion VND for display)
                            revenue_data = [float(row['Doanh thu thuần'])/1e9 if pd.notna(row['Doanh thu thuần']) else 0 
                                          for _, row in company_income_data.iterrows() 
                                          if pd.notna(row['Năm']) and pd.notna(row['Quý'])]
                            
                            # Create JSON object for revenue data if we have data points
                            if len(time_labels) > 0 and len(time_labels) == len(revenue_data):
                                financial_revenue_series = json.dumps({
                                    'labels': time_labels,
                                    'revenue': revenue_data
                                })
                                print(f"Revenue data prepared with {len(time_labels)} data points")
                        
                        # Handle profit data with careful column checking
                        profit_column = None
                        if 'Lợi nhuận sau thuế thu nhập doanh nghiệp' in company_income_data.columns:
                            profit_column = 'Lợi nhuận sau thuế thu nhập doanh nghiệp'
                        elif 'Lợi nhuận sau thuế thu nhập doanh nghiệp.1' in company_income_data.columns:
                            profit_column = 'Lợi nhuận sau thuế thu nhập doanh nghiệp.1'
                        
                        if profit_column:
                            # Create time labels (Year-Quarter)
                            time_labels = [f"{int(row['Năm'])}-Q{int(row['Quý'])}" for _, row in company_income_data.iterrows()
                                          if pd.notna(row['Năm']) and pd.notna(row['Quý'])]
                            
                            # Extract profit data (convert to billion VND for display)
                            profit_data = [float(row[profit_column])/1e9 if pd.notna(row[profit_column]) else 0 
                                          for _, row in company_income_data.iterrows()
                                          if pd.notna(row['Năm']) and pd.notna(row['Quý'])]
                            
                            # Create JSON object for profit data if we have data points
                            if len(time_labels) > 0 and len(time_labels) == len(profit_data):
                                financial_profit_series = json.dumps({
                                    'labels': time_labels,
                                    'profit': profit_data
                                })
                                print(f"Profit data prepared with {len(time_labels)} data points using column {profit_column}")
        
        except Exception as e:
            # Log the error but continue with empty/default data
            print(f"Error processing company data for {selected_company_code}: {e}")
            traceback.print_exc()
    
    # Get all company codes for search autocomplete
    all_companies = []
    if 'fin_statements' in app_data:
        all_companies = sorted(app_data['fin_statements']['Mã'].unique().tolist())
        
    return render_template('company_analysis.html',
                          selected_company_code=selected_company_code,
                          company_info=company_info,
                          company_metrics=company_metrics,
                          financial_time_series=financial_time_series,
                          ratio_time_series=ratio_time_series,
                          ratio_analysis=ratio_analysis,
                          balance_sheet=balance_sheet,
                          income_statement=income_statement,
                          financial_statements=financial_statements,
                          competitor_comparison=competitor_comparison,
                          company_ranking=company_ranking,
                          company_profile=company_profile,
                          all_companies=all_companies,
                          financial_revenue_series=financial_revenue_series,
                          financial_profit_series=financial_profit_series,
                          available_years=available_years,
                          balance_sheets=balance_sheets,
                          income_statements=income_statements,
                          cash_flows=cash_flows)
@app.route('/comparison')
@app.route('/comparison')
def comparison():
    # Get comparison parameters
    comparison_type = request.args.get('type', None)
    company1 = request.args.get('company1', None)
    company2 = request.args.get('company2', None)
    company3 = request.args.get('company3', None)
    sector1 = request.args.get('sector1', None)
    sector2 = request.args.get('sector2', None)
    sector3 = request.args.get('sector3', None)
    company = request.args.get('company', None)
    sector = request.args.get('sector', None)
    
    # Get financial statement selection parameters
    show_balance_sheet = request.args.get('show_balance_sheet', 'off') == 'on'
    show_income_statement = request.args.get('show_income_statement', 'off') == 'on'
    show_cash_flow = request.args.get('show_cash_flow', 'off') == 'on'
    
    # Default to showing all if none selected
    if not (show_balance_sheet or show_income_statement or show_cash_flow):
        show_balance_sheet = show_income_statement = show_cash_flow = True
   
    # Get list of sectors for dropdowns
    sectors = app_data['avg_by_sector']['Sector'].tolist() if 'avg_by_sector' in app_data else []
   
    # Initialize comparison results
    comparison_results = {}
   
    if comparison_type:
        # Create base comparison results structure
        comparison_results = {
            'overview_comment': "Phân tích tổng quan về các chỉ số tài chính.",
            'overview': [],
            'financial_statements': {
                'balance_sheet': {
                    'show': show_balance_sheet,
                    'years': [],
                    'entities': []
                },
                'income_statement': {
                    'show': show_income_statement,
                    'years': [],
                    'entities': []
                },
                'cash_flow': {
                    'show': show_cash_flow,
                    'years': [],
                    'entities': []
                }
            },
            'profitability_comment': "Phân tích khả năng sinh lời của các đối tượng so sánh.",
            'leverage_comment': "Phân tích cơ cấu vốn và thanh khoản của các đối tượng so sánh.",
            'growth_comment': "Phân tích tăng trưởng của các đối tượng so sánh.",
            'valuation_comment': "Phân tích định giá của các đối tượng so sánh.",
            'valuation': [],
            'time_series': json.dumps({
                'labels': ['2020', '2021', '2022', '2023', '2024'],
                'entities': []
            }),
            'historical': json.dumps({
                'labels': ['2020', '2021', '2022', '2023', '2024'],
                'entities': []
            }),
            'strengths_weaknesses': [],
            'conclusion': "Kết luận tổng thể về so sánh các đối tượng."
        }
        
        # List of companies/sectors to compare
        entities = []
        entity_names = []
        
        # Get entity data based on comparison type
        if comparison_type == 'companies':
            if company1:
                entities.append(('company', company1))
                entity_names.append(company1)
            if company2:
                entities.append(('company', company2))
                entity_names.append(company2)
            if company3:
                entities.append(('company', company3))
                entity_names.append(company3)
        elif comparison_type == 'sectors':
            if sector1:
                entities.append(('sector', sector1))
                entity_names.append(sector1)
            if sector2:
                entities.append(('sector', sector2))
                entity_names.append(sector2)
            if sector3:
                entities.append(('sector', sector3))
                entity_names.append(sector3)
        elif comparison_type == 'company_with_sector':
            if company:
                entities.append(('company', company))
                entity_names.append(company)
            if sector:
                entities.append(('sector', sector))
                entity_names.append(sector)
        
        # Get financial statement data for each entity
        all_years = set()
        
        # Process each entity
        for entity_idx, (entity_type, entity_id) in enumerate(entities):
            # Get financial statements for each entity (company or sector average)
            fin_data = get_entity_financial_data(entity_type, entity_id, 
                                                show_balance_sheet, 
                                                show_income_statement, 
                                                show_cash_flow)
            
            # Add entity to overview
            overview = {
                'name': entity_id,
                'roe': 15.0 - entity_idx * 0.5,
                'roa': 7.0 - entity_idx * 0.3,
                'ros': 12.0 - entity_idx * 0.5,
                'ebitda_margin': 18.0 - entity_idx * 0.5,
                'current_ratio': 1.8 - entity_idx * 0.1,
                'debt_to_equity': 60.0 - entity_idx * 1.0,
                'revenue_growth': 10.0 - entity_idx * 0.5
            }
            comparison_results['overview'].append(overview)
            
            # Add entity to valuation
            valuation = {
                'name': entity_id,
                'pe': 15.5 - entity_idx * 0.3,
                'pb': 2.3 - entity_idx * 0.1,
                'ps': 1.8 - entity_idx * 0.1,
                'ev_ebitda': 8.2 - entity_idx * 0.2,
                'dividend_yield': 3.5 - entity_idx * 0.1
            }
            comparison_results['valuation'].append(valuation)
            
            # Add entity to strengths_weaknesses
            strengths_weaknesses = {
                'name': entity_id,
                'strengths': ['Biên lợi nhuận cao', 'Tăng trưởng doanh thu ổn định', 'Cơ cấu vốn tốt'],
                'weaknesses': ['Chi phí vận hành cao', 'Doanh thu từ thị trường quốc tế thấp']
            }
            comparison_results['strengths_weaknesses'].append(strengths_weaknesses)
            
            # Placeholders for time series and historical data
            time_series_entity = {
                'name': entity_id,
                'roa': [5.5 - entity_idx * 0.3, 6.0 - entity_idx * 0.3, 6.5 - entity_idx * 0.3, 7.0 - entity_idx * 0.3, 7.5 - entity_idx * 0.3],
                'roe': [13.0 - entity_idx * 0.5, 14.0 - entity_idx * 0.5, 14.5 - entity_idx * 0.5, 15.0 - entity_idx * 0.5, 15.5 - entity_idx * 0.5],
                'ros': [10.0 - entity_idx * 0.5, 10.5 - entity_idx * 0.5, 11.0 - entity_idx * 0.5, 11.5 - entity_idx * 0.5, 12.0 - entity_idx * 0.5],
                'ebitda_margin': [17.0 - entity_idx * 0.5, 17.5 - entity_idx * 0.5, 18.0 - entity_idx * 0.5, 18.5 - entity_idx * 0.5, 19.0 - entity_idx * 0.5],
                'debt_to_assets': [40 + entity_idx * 1, 39 + entity_idx * 1, 38 + entity_idx * 1, 37 + entity_idx * 1, 36 + entity_idx * 1],
                'debt_to_equity': [65 + entity_idx * 1, 63 + entity_idx * 1, 62 + entity_idx * 1, 60 + entity_idx * 1, 58 + entity_idx * 1],
                'interest_coverage': [7 - entity_idx * 0.5, 8 - entity_idx * 0.5, 9 - entity_idx * 0.5, 10 - entity_idx * 0.5, 11 - entity_idx * 0.5],
                'current_ratio': [1.6 - entity_idx * 0.05, 1.7 - entity_idx * 0.05, 1.75 - entity_idx * 0.05, 1.8 - entity_idx * 0.05, 1.85 - entity_idx * 0.05],
                'revenue_growth': [8 - entity_idx * 0.5, 10 - entity_idx * 0.5, 12 - entity_idx * 0.5, 11 - entity_idx * 0.5, 9 - entity_idx * 0.5],
                'net_income_growth': [10 - entity_idx * 0.5, 12 - entity_idx * 0.5, 15 - entity_idx * 0.5, 13 - entity_idx * 0.5, 11 - entity_idx * 0.5],
                'assets_growth': [7 - entity_idx * 0.5, 9 - entity_idx * 0.5, 10 - entity_idx * 0.5, 8 - entity_idx * 0.5, 7 - entity_idx * 0.5],
                'equity_growth': [9 - entity_idx * 0.5, 11 - entity_idx * 0.5, 12 - entity_idx * 0.5, 10 - entity_idx * 0.5, 9 - entity_idx * 0.5],
                'pe': [14 - entity_idx * 0.5, 15 - entity_idx * 0.5, 15.5 - entity_idx * 0.5, 16 - entity_idx * 0.5, 15.5 - entity_idx * 0.5],
                'pb': [2.0 - entity_idx * 0.1, 2.1 - entity_idx * 0.1, 2.2 - entity_idx * 0.1, 2.3 - entity_idx * 0.1, 2.2 - entity_idx * 0.1],
                'ps': [1.6 - entity_idx * 0.1, 1.7 - entity_idx * 0.1, 1.8 - entity_idx * 0.1, 1.9 - entity_idx * 0.1, 1.8 - entity_idx * 0.1],
                'ev_ebitda': [7.5 - entity_idx * 0.2, 7.8 - entity_idx * 0.2, 8.0 - entity_idx * 0.2, 8.2 - entity_idx * 0.2, 8.0 - entity_idx * 0.2]
            }
            
            historical_entity = {
                'name': entity_id,
                'revenue': [1000 - entity_idx * 50, 1100 - entity_idx * 60, 1230 - entity_idx * 70, 1365 - entity_idx * 80, 1485 - entity_idx * 90],
                'net_profit': [120 - entity_idx * 10, 140 - entity_idx * 12, 165 - entity_idx * 15, 190 - entity_idx * 17, 210 - entity_idx * 20],
                'total_assets': [2000 - entity_idx * 100, 2180 - entity_idx * 110, 2375 - entity_idx * 120, 2565 - entity_idx * 130, 2745 - entity_idx * 140],
                'equity': [1200 - entity_idx * 100, 1320 - entity_idx * 110, 1450 - entity_idx * 120, 1595 - entity_idx * 130, 1740 - entity_idx * 140],
                'operating_cash_flow': [150 - entity_idx * 15, 170 - entity_idx * 17, 195 - entity_idx * 20, 215 - entity_idx * 22, 235 - entity_idx * 25],
                'free_cash_flow': [100 - entity_idx * 10, 115 - entity_idx * 12, 135 - entity_idx * 15, 150 - entity_idx * 17, 165 - entity_idx * 20]
            }
            
            # Add financial statement data
            if fin_data is not None:
                all_years.update(fin_data.get('years', []))
                
                # Add balance sheet data
                if show_balance_sheet and 'balance_sheet' in fin_data:
                    comparison_results['financial_statements']['balance_sheet']['entities'].append({
                        'name': entity_id,
                        'data': fin_data.get('balance_sheet', {})
                    })
                
                # Add income statement data
                if show_income_statement and 'income_statement' in fin_data:
                    comparison_results['financial_statements']['income_statement']['entities'].append({
                        'name': entity_id,
                        'data': fin_data.get('income_statement', {})
                    })
                
                # Add cash flow data
                if show_cash_flow and 'cash_flow' in fin_data:
                    comparison_results['financial_statements']['cash_flow']['entities'].append({
                        'name': entity_id,
                        'data': fin_data.get('cash_flow', {})
                    })
            
            # Update the time series and historical data
            time_series_data = json.loads(comparison_results['time_series'])
            time_series_data['entities'].append(time_series_entity)
            comparison_results['time_series'] = json.dumps(time_series_data)
            
            historical_data = json.loads(comparison_results['historical'])
            historical_data['entities'].append(historical_entity)
            comparison_results['historical'] = json.dumps(historical_data)
        
        # Sort years and add to the structure
        sorted_years = sorted(list(all_years))
        comparison_results['financial_statements']['balance_sheet']['years'] = sorted_years
        comparison_results['financial_statements']['income_statement']['years'] = sorted_years
        comparison_results['financial_statements']['cash_flow']['years'] = sorted_years
        
    # Get all company codes for search autocomplete
    all_companies = []
    if 'fin_statements' in app_data:
        all_companies = sorted(app_data['fin_statements']['Mã'].unique().tolist())
   
    return render_template('comparison.html',
                           sectors=sectors,
                           comparison_type=comparison_type,
                           company1=company1,
                           company2=company2,
                           company3=company3,
                           sector1=sector1,
                           sector2=sector2,
                           sector3=sector3,
                           company=company,
                           sector=sector,
                           comparison_results=comparison_results,
                           selected_sector=sector,  # For the company_with_sector form
                           all_companies=all_companies,
                           show_balance_sheet=show_balance_sheet,
                           show_income_statement=show_income_statement,
                           show_cash_flow=show_cash_flow)

def get_entity_financial_data(entity_type, entity_id, show_balance_sheet, show_income_statement, show_cash_flow):
    """Get financial data for a company or sector"""
    if entity_type == 'company':
        return get_company_financial_data(entity_id, show_balance_sheet, show_income_statement, show_cash_flow)
    elif entity_type == 'sector':
        return get_sector_average_financial_data(entity_id, show_balance_sheet, show_income_statement, show_cash_flow)
    return None

def get_company_financial_data(company_code, show_balance_sheet, show_income_statement, show_cash_flow):
    """Retrieve financial data for a specific company"""
    result = {
        'years': set(),
        'balance_sheet': {},
        'income_statement': {},
        'cash_flow': {}
    }
    
    # Get Balance Sheet data
    if show_balance_sheet and 'balance_sheet' in app_data:
        bs_data = app_data['balance_sheet'][app_data['balance_sheet']['Mã'] == company_code]
        if not bs_data.empty:
            for _, row in bs_data.iterrows():
                if pd.notna(row['Năm']):
                    year = str(int(row['Năm']))
                    result['years'].add(year)
                    
                    if year not in result['balance_sheet']:
                        result['balance_sheet'][year] = {
                            'total_assets': float(row['TỔNG CỘNG TÀI SẢN']) if 'TỔNG CỘNG TÀI SẢN' in row and pd.notna(row['TỔNG CỘNG TÀI SẢN']) else 0,
                            'current_assets': float(row['TÀI SẢN NGẮN HẠN']) if 'TÀI SẢN NGẮN HẠN' in row and pd.notna(row['TÀI SẢN NGẮN HẠN']) else 0,
                            'non_current_assets': float(row['TÀI SẢN DÀI HẠN']) if 'TÀI SẢN DÀI HẠN' in row and pd.notna(row['TÀI SẢN DÀI HẠN']) else 0,
                            'liabilities': float(row['NỢ PHẢI TRẢ']) if 'NỢ PHẢI TRẢ' in row and pd.notna(row['NỢ PHẢI TRẢ']) else 0,
                            'equity': float(row['VỐN CHỦ SỞ HỮU']) if 'VỐN CHỦ SỞ HỮU' in row and pd.notna(row['VỐN CHỦ SỞ HỮU']) else 0
                        }
    
    # Get Income Statement data
    if show_income_statement and 'income_statement' in app_data:
        is_data = app_data['income_statement'][app_data['income_statement']['Mã'] == company_code]
        if not is_data.empty:
            for _, row in is_data.iterrows():
                if pd.notna(row['Năm']):
                    year = str(int(row['Năm']))
                    result['years'].add(year)
                    
                    if year not in result['income_statement']:
                        result['income_statement'][year] = {
                            'revenue': float(row['Doanh thu thuần']) if 'Doanh thu thuần' in row and pd.notna(row['Doanh thu thuần']) else 0,
                            'gross_profit': float(row['Lợi nhuận gộp về bán hàng và cung cấp dịch vụ']) if 'Lợi nhuận gộp về bán hàng và cung cấp dịch vụ' in row and pd.notna(row['Lợi nhuận gộp về bán hàng và cung cấp dịch vụ']) else 0,
                            'operating_profit': float(row['Lợi nhuận thuần từ hoạt động kinh doanh']) if 'Lợi nhuận thuần từ hoạt động kinh doanh' in row and pd.notna(row['Lợi nhuận thuần từ hoạt động kinh doanh']) else 0,
                            'profit_before_tax': float(row['Tổng lợi nhuận kế toán trước thuế']) if 'Tổng lợi nhuận kế toán trước thuế' in row and pd.notna(row['Tổng lợi nhuận kế toán trước thuế']) else 0,
                            'net_profit': float(row['Lợi nhuận sau thuế thu nhập doanh nghiệp']) if 'Lợi nhuận sau thuế thu nhập doanh nghiệp' in row and pd.notna(row['Lợi nhuận sau thuế thu nhập doanh nghiệp']) else 0
                        }
    
    # Get Cash Flow data
    if show_cash_flow and 'cash_flow' in app_data:
        cf_data = app_data['cash_flow'][app_data['cash_flow']['Mã'] == company_code]
        if not cf_data.empty:
            for _, row in cf_data.iterrows():
                if pd.notna(row['Năm']):
                    year = str(int(row['Năm']))
                    result['years'].add(year)
                    
                    if year not in result['cash_flow']:
                        result['cash_flow'][year] = {
                            'operating_cash_flow': float(row['Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh (TT)']) if 'Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh (TT)' in row and pd.notna(row['Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh (TT)']) else 0,
                            'investing_cash_flow': float(row['Lưu chuyển tiền tệ ròng từ hoạt động đầu tư (TT)']) if 'Lưu chuyển tiền tệ ròng từ hoạt động đầu tư (TT)' in row and pd.notna(row['Lưu chuyển tiền tệ ròng từ hoạt động đầu tư (TT)']) else 0,
                            'financing_cash_flow': float(row['Lưu chuyển tiền tệ từ hoạt động tài chính (TT)']) if 'Lưu chuyển tiền tệ từ hoạt động tài chính (TT)' in row and pd.notna(row['Lưu chuyển tiền tệ từ hoạt động tài chính (TT)']) else 0,
                            'net_cash_flow': float(row['Lưu chuyển tiền thuần trong kỳ (TT)']) if 'Lưu chuyển tiền thuần trong kỳ (TT)' in row and pd.notna(row['Lưu chuyển tiền thuần trong kỳ (TT)']) else 0
                        }
    
    result['years'] = sorted(list(result['years']))
    return result

def get_sector_average_financial_data(sector_name, show_balance_sheet, show_income_statement, show_cash_flow):
    """Get average financial data for a sector"""
    # In a real implementation, this would calculate sector averages
    # For now, return placeholder data
    return None


@app.route('/api/sector_data/<sector>')
def sector_data(sector):
    # API endpoint for fetching sector data
    if 'avg_by_sector' in app_data:
        sector_data = app_data['avg_by_sector'][app_data['avg_by_sector']['Sector'] == sector]
        if not sector_data.empty:
            return jsonify(sector_data.iloc[0].to_dict())
    return jsonify({})


@app.route('/api/company_data/<code>')
def company_data(code):
    # API endpoint for fetching company data
    if 'avg_by_code' in app_data:
        company_data = app_data['avg_by_code'][app_data['avg_by_code']['Mã'] == code]
        if not company_data.empty:
            return jsonify(company_data.iloc[0].to_dict())
    return jsonify({})


# Thêm route mới để hiển thị trang xuất báo cáo
@app.route('/export_report')
def export_report_page():
    try:
        # Lấy danh sách công ty từ dữ liệu
        companies = []
        if 'fin_statements' in app_data:
            # Lấy mã công ty và tên công ty không trùng lặp
            df = app_data['fin_statements'][['Mã', 'Tên công ty']].drop_duplicates()
            companies = [
                {'code': row['Mã'], 'name': row['Tên công ty']}
                for _, row in df.iterrows()
            ]
            # Sắp xếp theo mã công ty
            companies = sorted(companies, key=lambda x: x['code'])
        
        return render_template('export_report.html', companies=companies, pdf_available=PDF_AVAILABLE)
    except Exception as e:
        print(f"Error in export_report_page: {e}")
        traceback.print_exc()
        return "Đã xảy ra lỗi khi tải trang xuất báo cáo. Vui lòng thử lại sau.", 500

# Thêm route để xử lý việc xuất báo cáo
@app.route('/generate_report/<company_code>')
def generate_report(company_code):
    try:
        # Kiểm tra tham số công ty
        if not company_code:
            return "Không tìm thấy mã công ty", 400
        
        # Lấy dữ liệu công ty
        company_data = get_company_report_data(company_code)
        
        # Kiểm tra nếu có lỗi trong dữ liệu công ty
        if company_data is None:
            return render_template('error_template.html', 
                                  error_message=f"Không tìm thấy dữ liệu cho công ty {company_code}",
                                  company_code=company_code), 404
        
        # Check if there's error information
        if 'error' in company_data:
            return render_template('error_template.html',
                                  error_message=f"Đã xảy ra lỗi khi xử lý dữ liệu công ty {company_code}: {company_data['error']}",
                                  company_code=company_code), 500
        
        # Thêm thông tin về khả năng xuất PDF
        company_data['pdf_available'] = PDF_AVAILABLE
        
        # Render template báo cáo với dữ liệu
        rendered_template = render_template('report_template.html', **company_data)
        
        # Xử lý các thông số request
        output_format = request.args.get('format', 'html')
        
        if output_format == 'pdf' and PDF_AVAILABLE:
            try:
                # Tạo PDF từ HTML
                pdf = HTML(string=rendered_template).write_pdf()
                
                # Tạo response với file PDF
                response = make_response(pdf)
                response.headers['Content-Type'] = 'application/pdf'
                response.headers['Content-Disposition'] = f'attachment; filename=Bao_Cao_{company_code}.pdf'
                
                return response
            except Exception as e:
                print(f"Error generating PDF: {e}")
                traceback.print_exc()
                return render_template('error_template.html',
                                      error_message="Đã xảy ra lỗi khi tạo PDF. Vui lòng thử lại hoặc chọn định dạng HTML.",
                                      company_code=company_code), 500
        elif output_format == 'pdf' and not PDF_AVAILABLE:
            # Thông báo người dùng rằng PDF không khả dụng
            return render_template('error_template.html',
                                  error_message="Xuất file PDF không khả dụng do thiếu thư viện WeasyPrint. Vui lòng cài đặt WeasyPrint theo hướng dẫn hoặc sử dụng định dạng HTML.",
                                  company_code=company_code), 501
        else:
            # Trả về HTML
            return rendered_template
    except Exception as e:
        # Create a clean error page with detailed information
        print(f"Unexpected error in generate_report: {e}")
        traceback.print_exc()
        return render_template('error_template.html',
                              error_message=f"Đã xảy ra lỗi không mong muốn: {str(e)}",
                              company_code=company_code), 500

# Hàm lấy dữ liệu cho báo cáo
# Integrated function to generate complete company report data
def get_company_report_data(company_code):
    result = {
        'company_code': company_code,
        'report_date': datetime.now().strftime('%d/%m/%Y'),
    }
    
    try:
        # Check if company exists in financial statements
        if 'fin_statements' not in app_data:
            print(f"No financial statements data available")
            return None
            
        company_info = app_data['fin_statements'][app_data['fin_statements']['Mã'] == company_code]
        if company_info.empty:
            print(f"Company {company_code} not found in financial statements")
            return None
        
        # Set basic company information
        result['company_name'] = company_info['Tên công ty'].iloc[0]
        result['exchange'] = company_info['Sàn'].iloc[0] if 'Sàn' in company_info.columns else "N/A"
        
        # Set industry information with default values if missing
        result['industry_level1'] = company_info['Ngành ICB - cấp 1'].iloc[0] if 'Ngành ICB - cấp 1' in company_info.columns else "N/A"
        result['industry_level2'] = company_info['Ngành ICB - cấp 2'].iloc[0] if 'Ngành ICB - cấp 2' in company_info.columns else "N/A"
        result['industry_level3'] = company_info['Ngành ICB - cấp 3'].iloc[0] if 'Ngành ICB - cấp 3' in company_info.columns else "N/A"
        
        # Get financial data sheets with proper error handling
        balance_sheet = pd.DataFrame()
        income_statement = pd.DataFrame()
        cash_flow = pd.DataFrame()
        
        if 'balance_sheet' in app_data:
            balance_sheet = app_data['balance_sheet'][app_data['balance_sheet']['Mã'] == company_code].sort_values(by=['Năm', 'Quý'])
            
        if 'income_statement' in app_data:
            income_statement = app_data['income_statement'][app_data['income_statement']['Mã'] == company_code].sort_values(by=['Năm', 'Quý'])
            
        if 'cash_flow' in app_data:
            cash_flow = app_data['cash_flow'][app_data['cash_flow']['Mã'] == company_code].sort_values(by=['Năm', 'Quý'])
        
        # Get sector averages if available
        sector_avg = {}
        if 'avg_by_sector' in app_data and result['industry_level3'] != "N/A":
            sector_data = app_data['avg_by_sector'][app_data['avg_by_sector']['Sector'] == result['industry_level3']]
            if not sector_data.empty:
                sector_avg = sector_data.iloc[0].to_dict()
                result['sector_avg'] = sector_avg
        
        # Get company metrics if available
        if 'avg_by_code' in app_data:
            company_metrics = app_data['avg_by_code'][app_data['avg_by_code']['Mã'] == company_code]
            if not company_metrics.empty:
                result['company_metrics'] = company_metrics.iloc[0].to_dict()
        
        # Gather all available years from all data sources
        years = []
        
        if not balance_sheet.empty and 'Năm' in balance_sheet.columns:
            years.extend(balance_sheet['Năm'].dropna().astype(int).unique())
        
        if not income_statement.empty and 'Năm' in income_statement.columns:
            years.extend(income_statement['Năm'].dropna().astype(int).unique())
            
        if not cash_flow.empty and 'Năm' in cash_flow.columns:
            years.extend(cash_flow['Năm'].dropna().astype(int).unique())
        
        # Remove duplicates and sort years
        years = sorted(list(set(years)))
        
        # Check if we have any years data
        if not years:
            print(f"No yearly financial data found for company {company_code}")
            result['years'] = []
            result['financial_data'] = {}
            result['financial_ratios'] = {}
            return result
        
        # Take up to 5 most recent years
        years = years[-5:] if len(years) > 5 else years
        
        financial_data = {}
        
        for year in years:
            year_data = {
                'balance_sheet': {
                    'total_assets': 0,
                    'current_assets': 0,
                    'fixed_assets': 0,
                    'liabilities': 0,
                    'equity': 0,
                    'inventory': 0,  # Added for quick ratio calculation
                    'short_term_debt': 0,  # Added for liquidity ratio calculations
                },
                'income_statement': {
                    'revenue': 0,
                    'gross_profit': 0,
                    'operating_profit': 0,
                    'profit_before_tax': 0,
                    'net_profit': 0,
                    'interest_expense': 0,  # Added for interest coverage ratio
                    'ebit': 0,  # Added for EBIT margin
                    'ebitda': 0,  # Added for EBITDA margin
                },
                'cash_flow': {
                    'operating_cash_flow': 0,
                    'investing_cash_flow': 0,
                    'financing_cash_flow': 0,
                }
            }
            
            # Get balance sheet data for the year
            if not balance_sheet.empty:
                year_bs = balance_sheet[balance_sheet['Năm'] == year].sort_values(by='Quý', ascending=False)
                if not year_bs.empty:
                    last_quarter_bs = year_bs.iloc[0]
                    
                    # Safe data extraction with default values
                    for field, bs_field in [
                        ('total_assets', 'TỔNG CỘNG TÀI SẢN'),
                        ('current_assets', 'TÀI SẢN NGẮN HẠN'),
                        ('fixed_assets', 'TÀI SẢN DÀI HẠN'),
                        ('liabilities', 'NỢ PHẢI TRẢ'),
                        ('equity', 'VỐN CHỦ SỞ HỮU'),
                        ('inventory', 'Hàng tồn kho, ròng'),
                        ('short_term_debt', 'Nợ ngắn hạn')
                    ]:
                        if bs_field in last_quarter_bs and pd.notna(last_quarter_bs[bs_field]):
                            year_data['balance_sheet'][field] = last_quarter_bs[bs_field]
            
            # Get income statement data for the year
            if not income_statement.empty:
                year_is = income_statement[income_statement['Năm'] == year].sort_values(by='Quý', ascending=False)
                if not year_is.empty:
                    last_quarter_is = year_is.iloc[0]
                    
                    # Safe data extraction with default values
                    for field, is_field in [
                        ('revenue', 'Doanh thu thuần'),
                        ('gross_profit', 'Lợi nhuận gộp về bán hàng và cung cấp dịch vụ'),
                        ('operating_profit', 'Lợi nhuận thuần từ hoạt động kinh doanh'),
                        ('profit_before_tax', 'Tổng lợi nhuận kế toán trước thuế'),
                        ('net_profit', 'Lợi nhuận sau thuế thu nhập doanh nghiệp'),
                        ('interest_expense', 'Trong đó: Chi phí lãi vay')
                    ]:
                        if is_field in last_quarter_is and pd.notna(last_quarter_is[is_field]):
                            year_data['income_statement'][field] = last_quarter_is[is_field]
                    
                    # Calculate EBIT (Earnings Before Interest and Taxes)
                    interest_expense = year_data['income_statement']['interest_expense']
                    profit_before_tax = year_data['income_statement']['profit_before_tax']
                    if interest_expense > 0 or profit_before_tax > 0:
                        year_data['income_statement']['ebit'] = profit_before_tax + interest_expense
                    
                    # Calculate EBITDA (EBIT + Depreciation & Amortization)
                    depreciation = 0
                    if not cash_flow.empty:
                        year_cf = cash_flow[cash_flow['Năm'] == year].sort_values(by='Quý', ascending=False)
                        if not year_cf.empty and 'Khấu hao TSCĐ' in year_cf.iloc[0] and pd.notna(year_cf.iloc[0]['Khấu hao TSCĐ']):
                            depreciation = year_cf.iloc[0]['Khấu hao TSCĐ']
                    
                    year_data['income_statement']['ebitda'] = year_data['income_statement']['ebit'] + depreciation
            
            # Get cash flow data for the year
            if not cash_flow.empty:
                year_cf = cash_flow[cash_flow['Năm'] == year].sort_values(by='Quý', ascending=False)
                if not year_cf.empty:
                    last_quarter_cf = year_cf.iloc[0]
                    
                    # Safe data extraction with default values
                    for field, cf_field in [
                        ('operating_cash_flow', 'Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh (TT)'),
                        ('investing_cash_flow', 'Lưu chuyển tiền tệ ròng từ hoạt động đầu tư (TT)'),
                        ('financing_cash_flow', 'Lưu chuyển tiền tệ từ hoạt động tài chính (TT)')
                    ]:
                        if cf_field in last_quarter_cf and pd.notna(last_quarter_cf[cf_field]):
                            year_data['cash_flow'][field] = last_quarter_cf[cf_field]
            
            financial_data[str(int(year))] = year_data
        
        result['financial_data'] = financial_data
        result['years'] = [str(int(year)) for year in years]
        
        # Calculate financial ratios with proper error handling
        financial_ratios = {}
        
        for year in years:
            ratios = {
                # Profitability Ratios
                'ROA': 0,
                'ROE': 0,
                'ROS': 0,
                'Gross_Profit_Margin': 0,
                'EBIT_Margin': 0,
                'EBITDA_Margin': 0,
                
                # Liquidity Ratios
                'Current_Ratio': 0,
                'Quick_Ratio': 0,
                
                # Leverage Ratios
                'Debt_to_Equity': 0,
                'Debt_to_Assets': 0,
                'Interest_Coverage': 0,
                
                # Efficiency Ratios
                'Asset_Turnover': 0,
                'Inventory_Turnover': 0,
                'Receivables_Turnover': 0,
                'Working_Capital_Turnover': 0
            }
            
            year_str = str(int(year))
            year_data = financial_data.get(year_str, {})
            bs_data = year_data.get('balance_sheet', {})
            is_data = year_data.get('income_statement', {})
            
            # Calculate Profitability Ratios
            
            # ROA (Return on Assets)
            total_assets = bs_data.get('total_assets', 0)
            net_profit = is_data.get('net_profit', 0)
            if total_assets > 0 and net_profit != 0:
                ratios['ROA'] = (net_profit / total_assets) * 100
            
            # ROE (Return on Equity)
            equity = bs_data.get('equity', 0)
            if equity > 0 and net_profit != 0:
                ratios['ROE'] = (net_profit / equity) * 100
            
            # ROS (Return on Sales)
            revenue = is_data.get('revenue', 0)
            if revenue > 0 and net_profit != 0:
                ratios['ROS'] = (net_profit / revenue) * 100
            
            # Gross Profit Margin
            gross_profit = is_data.get('gross_profit', 0)
            if revenue > 0 and gross_profit != 0:
                ratios['Gross_Profit_Margin'] = (gross_profit / revenue) * 100
            
            # EBIT Margin
            ebit = is_data.get('ebit', 0)
            if revenue > 0 and ebit != 0:
                ratios['EBIT_Margin'] = (ebit / revenue) * 100
            
            # EBITDA Margin
            ebitda = is_data.get('ebitda', 0)
            if revenue > 0 and ebitda != 0:
                ratios['EBITDA_Margin'] = (ebitda / revenue) * 100
            
            # Calculate Liquidity Ratios
            
            # Current Ratio
            current_assets = bs_data.get('current_assets', 0)
            short_term_debt = bs_data.get('short_term_debt', 0)
            if short_term_debt > 0:
                ratios['Current_Ratio'] = current_assets / short_term_debt
            
            # Quick Ratio
            inventory = bs_data.get('inventory', 0)
            if short_term_debt > 0:
                ratios['Quick_Ratio'] = (current_assets - inventory) / short_term_debt
            
            # Calculate Leverage Ratios
            
            # Debt to Equity Ratio
            liabilities = bs_data.get('liabilities', 0)
            if equity > 0 and liabilities != 0:
                ratios['Debt_to_Equity'] = (liabilities / equity) * 100
            
            # Debt to Assets Ratio
            if total_assets > 0 and liabilities != 0:
                ratios['Debt_to_Assets'] = (liabilities / total_assets) * 100
            
            # Interest Coverage Ratio
            interest_expense = is_data.get('interest_expense', 0)
            if interest_expense > 0 and ebit != 0:
                ratios['Interest_Coverage'] = ebit / interest_expense
            
            # Calculate Efficiency Ratios
            
            # Asset Turnover
            if total_assets > 0 and revenue != 0:
                ratios['Asset_Turnover'] = revenue / total_assets
            
            # Inventory Turnover
            # Normally would use Cost of Goods Sold, but we can approximate using revenue if needed
            if inventory > 0 and revenue != 0:
                cogs = revenue - gross_profit if gross_profit > 0 else revenue * 0.7  # Approximate COGS if unavailable
                ratios['Inventory_Turnover'] = cogs / inventory
            
            # Receivables Turnover
            # Need to extract accounts receivable from balance sheet
            accounts_receivable = 0
            if not balance_sheet.empty:
                year_bs = balance_sheet[balance_sheet['Năm'] == year].sort_values(by='Quý', ascending=False)
                if not year_bs.empty and 'Các khoản phải thu ngắn hạn' in year_bs.iloc[0] and pd.notna(year_bs.iloc[0]['Các khoản phải thu ngắn hạn']):
                    accounts_receivable = year_bs.iloc[0]['Các khoản phải thu ngắn hạn']
            
            if accounts_receivable > 0 and revenue != 0:
                ratios['Receivables_Turnover'] = revenue / accounts_receivable
            
            # Working Capital Turnover
            working_capital = current_assets - short_term_debt
            if working_capital > 0 and revenue != 0:
                ratios['Working_Capital_Turnover'] = revenue / working_capital
            
            financial_ratios[year_str] = ratios
        
        result['financial_ratios'] = financial_ratios
        
        # Generate charts safely
        try:
            if len(years) > 0:
                prepare_financial_charts(result)
            else:
                # Initialize empty chart placeholders
                result['revenue_profit_chart'] = None
                result['ratios_chart'] = None
                result['balance_sheet_chart'] = None
                result['comparison_chart'] = None
        except Exception as e:
            print(f"Error preparing charts for {company_code}: {e}")
            traceback.print_exc()
            result['revenue_profit_chart'] = None
            result['ratios_chart'] = None
            result['balance_sheet_chart'] = None
            result['comparison_chart'] = None
        
        # ===== 1. Generate Financial Forecast =====
        try:
            result['financial_forecast'] = generate_financial_forecast(financial_data, years)
            result['forecast_years'] = [str(int(years[-1]) + i + 1) for i in range(3)]  # Next 3 years
            
            # Generate forecast chart
            if result['financial_forecast']:
                result['forecast_chart'] = generate_forecast_chart(
                    years, 
                    result['forecast_years'], 
                    financial_data, 
                    result['financial_forecast']
                )
            else:
                result['forecast_chart'] = None
        except Exception as e:
            print(f"Error generating financial forecasts: {e}")
            traceback.print_exc()
            result['financial_forecast'] = None
            result['forecast_years'] = None
            result['forecast_chart'] = None
        
        # ===== 2. Generate Financial Health Assessment =====
        try:
            # Generate financial health assessment
            result['financial_health'] = generate_financial_health_assessment(
                financial_data, 
                financial_ratios, 
                years, 
                sector_avg
            )
            
            # Generate business recommendations
            if result['financial_health']:
                result['business_recommendations'] = generate_business_recommendations(
                    financial_data, 
                    financial_ratios, 
                    years, 
                    result['financial_health']
                )
            else:
                result['business_recommendations'] = None
        except Exception as e:
            print(f"Error generating financial health assessment: {e}")
            traceback.print_exc()
            result['financial_health'] = None
            result['business_recommendations'] = None
        
        # ===== 3. Generate Valuation Data =====
        try:
            result['valuation_data'] = generate_valuation_data(
                company_code, 
                financial_data, 
                years, 
                result.get('sector_avg', {})
            )
            
            # Generate valuation chart
            if result['valuation_data']:
                result['valuation_chart'] = generate_valuation_chart(
                    result['valuation_data'], 
                    result.get('sector_avg', {})
                )
            else:
                result['valuation_chart'] = None
        except Exception as e:
            print(f"Error generating valuation data: {e}")
            traceback.print_exc()
            result['valuation_data'] = None
            result['valuation_chart'] = None
        
        # ===== 4. Generate Risk Factors Analysis =====
        try:
            result['risk_factors'] = generate_risk_factors(
                company_code, 
                financial_data, 
                financial_ratios, 
                years, 
                result.get('sector_avg', {}), 
                result.get('company_metrics', {})
            )
        except Exception as e:
            print(f"Error generating risk factors: {e}")
            traceback.print_exc()
            result['risk_factors'] = None
        
        # ===== 5. Generate Investment Recommendation =====
        try:
            result['recommendation'] = generate_recommendation(
                company_code, 
                financial_data, 
                financial_ratios, 
                years,
                result.get('sector_avg', {}), 
                result.get('company_metrics', {}),
                result.get('valuation_data', {})
            )
        except Exception as e:
            print(f"Error generating recommendation: {e}")
            traceback.print_exc()
            result['recommendation'] = None
        
        return result
    
    except Exception as e:
        print(f"Error in get_company_report_data for {company_code}: {e}")
        traceback.print_exc()
        
        # Return a minimal result with the error information for troubleshooting
        result['error'] = str(e)
        result['years'] = []
        result['financial_data'] = {}
        result['financial_ratios'] = {}
        return result


# New helper functions for financial forecasting and analysis

def generate_financial_forecast(financial_data, years):
    """
    Generate financial forecasts for the next 3 years based on historical data,
    using only financial statement data without market values
    """
    if not years or len(years) < 2:
        return None
    
    forecast_data = {}
    forecast_years = [int(years[-1]) + i + 1 for i in range(3)]  # Next 3 years
    
    # Convert years to strings for dictionary access
    year_strs = [str(int(year)) for year in years]
    
    # Calculate growth rates from historical data
    growth_rates = {
        'revenue': 0,
        'gross_profit': 0,
        'net_profit': 0,
        'total_assets': 0,
        'equity': 0
    }
    
    # Use the last 3 years (or fewer if not available) to calculate average growth rates
    historical_years = year_strs[-3:] if len(year_strs) >= 3 else year_strs
    
    for metric in growth_rates.keys():
        values = []
        for i in range(1, len(historical_years)):
            prev_year = historical_years[i-1]
            curr_year = historical_years[i]
            
            # Get values from income statement
            if metric in ['revenue', 'gross_profit', 'net_profit']:
                prev_value = financial_data.get(prev_year, {}).get('income_statement', {}).get(metric, 0)
                curr_value = financial_data.get(curr_year, {}).get('income_statement', {}).get(metric, 0)
            # Get values from balance sheet
            else:
                prev_value = financial_data.get(prev_year, {}).get('balance_sheet', {}).get(metric, 0)
                curr_value = financial_data.get(curr_year, {}).get('balance_sheet', {}).get(metric, 0)
            
            # Calculate growth rate if both values are valid
            if prev_value > 0 and curr_value > 0:
                annual_growth = (curr_value / prev_value) - 1
                values.append(annual_growth)
        
        # Calculate average growth rate, use a moderate default if no valid data
        growth_rates[metric] = sum(values) / len(values) if values else 0.05
        
        # Cap extreme growth rates to reasonable values (-20% to 30%)
        growth_rates[metric] = max(min(growth_rates[metric], 0.3), -0.2)
    
    # Get latest financial values as base for forecasting
    latest_year = year_strs[-1]
    latest_data = financial_data.get(latest_year, {})
    
    latest_revenue = latest_data.get('income_statement', {}).get('revenue', 0)
    latest_gross_profit = latest_data.get('income_statement', {}).get('gross_profit', 0)
    latest_net_profit = latest_data.get('income_statement', {}).get('net_profit', 0)
    latest_total_assets = latest_data.get('balance_sheet', {}).get('total_assets', 0)
    latest_equity = latest_data.get('balance_sheet', {}).get('equity', 0)
    
    # Generate forecast for each year
    for i, year in enumerate(forecast_years):
        # Apply compound growth for each year in the forecast
        forecast_multiplier = (1 + growth_rates['revenue']) ** (i + 1)
        gross_profit_multiplier = (1 + growth_rates['gross_profit']) ** (i + 1)
        net_profit_multiplier = (1 + growth_rates['net_profit']) ** (i + 1)
        assets_multiplier = (1 + growth_rates['total_assets']) ** (i + 1)
        equity_multiplier = (1 + growth_rates['equity']) ** (i + 1)
        
        forecast_revenue = latest_revenue * forecast_multiplier
        forecast_gross_profit = latest_gross_profit * gross_profit_multiplier
        forecast_net_profit = latest_net_profit * net_profit_multiplier
        forecast_total_assets = latest_total_assets * assets_multiplier
        forecast_equity = latest_equity * equity_multiplier
        
        # Calculate EBIT (approximate as 1.3x net profit if not enough data)
        forecast_ebit = forecast_net_profit * 1.3
        
        # Calculate profit before tax (approximate as 1.2x net profit)
        forecast_profit_before_tax = forecast_net_profit * 1.2
        
        forecast_data[str(year)] = {
            'revenue': forecast_revenue,
            'gross_profit': forecast_gross_profit,
            'profit_before_tax': forecast_profit_before_tax,
            'net_profit': forecast_net_profit,
            'total_assets': forecast_total_assets,
            'equity': forecast_equity,
            'ebit': forecast_ebit
        }
    
    return forecast_data
def generate_financial_health_assessment(financial_data, financial_ratios, years, sector_avg=None):
    """
    Generate a financial health assessment based solely on financial statements,
    without using market data
    """
    if not years:
        return None
    
    # Get latest financial year data
    latest_year = str(int(years[-1]))
    
    # Gather key financial ratios
    latest_ratios = financial_ratios.get(latest_year, {})
    
    # Initialize assessment
    assessment = {
        'profitability': {
            'score': 0,  # -2 to 2 scale
            'details': []
        },
        'liquidity': {
            'score': 0,  # -2 to 2 scale
            'details': []
        },
        'leverage': {
            'score': 0,  # -2 to 2 scale
            'details': []
        },
        'efficiency': {
            'score': 0,  # -2 to 2 scale
            'details': []
        },
        'growth': {
            'score': 0,  # -2 to 2 scale
            'details': []
        },
        'overall_rating': 'Trung bình',  # Default
        'overall_score': 0,
        'strengths': [],
        'weaknesses': [],
        'summary': ''
    }
    
    # 1. Assess Profitability
    roe = latest_ratios.get('ROE', 0)
    roa = latest_ratios.get('ROA', 0)
    ros = latest_ratios.get('ROS', 0)
    
    # Get sector averages if available
    sector_roe = sector_avg.get('Average ROE', 10) if sector_avg else 10  # Default benchmark
    sector_roa = sector_avg.get('Average ROA', 5) if sector_avg else 5  # Default benchmark
    sector_ros = sector_avg.get('Average ROS', 8) if sector_avg else 8  # Default benchmark
    
    # Score ROE
    if roe > sector_roe * 1.2:
        assessment['profitability']['score'] += 1
        assessment['profitability']['details'].append(f"ROE ({roe:.2f}%) cao hơn trung bình ngành ({sector_roe:.2f}%)")
        assessment['strengths'].append(f"ROE cao ({roe:.2f}%), hiệu quả sử dụng vốn tốt")
    elif roe < sector_roe * 0.8:
        assessment['profitability']['score'] -= 1
        assessment['profitability']['details'].append(f"ROE ({roe:.2f}%) thấp hơn trung bình ngành ({sector_roe:.2f}%)")
        assessment['weaknesses'].append(f"ROE thấp ({roe:.2f}%), hiệu quả sử dụng vốn hạn chế")
    else:
        assessment['profitability']['details'].append(f"ROE ({roe:.2f}%) tương đương trung bình ngành ({sector_roe:.2f}%)")
    
    # Score ROA
    if roa > sector_roa * 1.2:
        assessment['profitability']['score'] += 1
        assessment['profitability']['details'].append(f"ROA ({roa:.2f}%) cao hơn trung bình ngành ({sector_roa:.2f}%)")
        assessment['strengths'].append(f"ROA cao ({roa:.2f}%), hiệu quả sử dụng tài sản tốt")
    elif roa < sector_roa * 0.8:
        assessment['profitability']['score'] -= 1
        assessment['profitability']['details'].append(f"ROA ({roa:.2f}%) thấp hơn trung bình ngành ({sector_roa:.2f}%)")
        assessment['weaknesses'].append(f"ROA thấp ({roa:.2f}%), hiệu quả sử dụng tài sản hạn chế")
    else:
        assessment['profitability']['details'].append(f"ROA ({roa:.2f}%) tương đương trung bình ngành ({sector_roa:.2f}%)")
    
    # 2. Assess Liquidity
    current_ratio = latest_ratios.get('Current_Ratio', 0)
    quick_ratio = latest_ratios.get('Quick_Ratio', 0)
    
    # Score Current Ratio
    if current_ratio > 2:
        assessment['liquidity']['score'] += 1
        assessment['liquidity']['details'].append(f"Tỷ số thanh toán hiện hành ({current_ratio:.2f}) rất tốt")
        assessment['strengths'].append("Khả năng thanh toán ngắn hạn tốt")
    elif current_ratio < 1:
        assessment['liquidity']['score'] -= 1
        assessment['liquidity']['details'].append(f"Tỷ số thanh toán hiện hành ({current_ratio:.2f}) thấp, dưới 1.0")
        assessment['weaknesses'].append("Khả năng thanh toán ngắn hạn có thể gặp khó khăn")
    else:
        assessment['liquidity']['details'].append(f"Tỷ số thanh toán hiện hành ({current_ratio:.2f}) ở mức an toàn")
    
    # Score Quick Ratio
    if quick_ratio > 1.5:
        assessment['liquidity']['score'] += 1
        assessment['liquidity']['details'].append(f"Tỷ số thanh toán nhanh ({quick_ratio:.2f}) rất tốt")
    elif quick_ratio < 0.8:
        assessment['liquidity']['score'] -= 1
        assessment['liquidity']['details'].append(f"Tỷ số thanh toán nhanh ({quick_ratio:.2f}) thấp, dưới 0.8")
    else:
        assessment['liquidity']['details'].append(f"Tỷ số thanh toán nhanh ({quick_ratio:.2f}) ở mức phù hợp")
    
    # 3. Assess Leverage
    debt_to_assets = latest_ratios.get('Debt_to_Assets', 0)
    debt_to_equity = latest_ratios.get('Debt_to_Equity', 0)
    
    sector_da = sector_avg.get('Average D/A Ratio', 50) if sector_avg else 50  # Default benchmark
    sector_de = sector_avg.get('Average D/E Ratio', 100) if sector_avg else 100  # Default benchmark
    
    # Score Debt to Assets
    if debt_to_assets < sector_da * 0.8:
        assessment['leverage']['score'] += 1
        assessment['leverage']['details'].append(f"Tỷ lệ Nợ/Tài sản ({debt_to_assets:.2f}%) thấp hơn trung bình ngành")
        assessment['strengths'].append("Cơ cấu vốn an toàn, ít sử dụng nợ")
    elif debt_to_assets > sector_da * 1.2:
        assessment['leverage']['score'] -= 1
        assessment['leverage']['details'].append(f"Tỷ lệ Nợ/Tài sản ({debt_to_assets:.2f}%) cao hơn trung bình ngành")
        assessment['weaknesses'].append("Tỷ lệ nợ cao có thể tăng rủi ro tài chính")
    else:
        assessment['leverage']['details'].append(f"Tỷ lệ Nợ/Tài sản ({debt_to_assets:.2f}%) ở mức hợp lý")
    
    # 4. Assess Growth Trends
    if len(years) >= 3:
        # Check revenue growth trend
        year_strs = [str(int(year)) for year in years[-3:]]
        revenue_trend = [financial_data.get(y, {}).get('income_statement', {}).get('revenue', 0) for y in year_strs]
        
        # Calculate revenue growth rate
        if all(revenue_trend[i] > 0 for i in range(len(revenue_trend))):
            rev_growth_rates = []
            for i in range(1, len(revenue_trend)):
                if revenue_trend[i-1] > 0:
                    growth_rate = (revenue_trend[i] / revenue_trend[i-1] - 1) * 100
                    rev_growth_rates.append(growth_rate)
            
            avg_rev_growth = sum(rev_growth_rates) / len(rev_growth_rates) if rev_growth_rates else 0
            
            if avg_rev_growth > 15:
                assessment['growth']['score'] += 1
                assessment['growth']['details'].append(f"Tăng trưởng doanh thu mạnh ({avg_rev_growth:.2f}% trung bình/năm)")
                assessment['strengths'].append(f"Tăng trưởng doanh thu cao ({avg_rev_growth:.2f}%/năm)")
            elif avg_rev_growth < 0:
                assessment['growth']['score'] -= 1
                assessment['growth']['details'].append(f"Doanh thu suy giảm ({avg_rev_growth:.2f}% trung bình/năm)")
                assessment['weaknesses'].append(f"Doanh thu có xu hướng giảm ({avg_rev_growth:.2f}%/năm)")
            else:
                assessment['growth']['details'].append(f"Tăng trưởng doanh thu ổn định ({avg_rev_growth:.2f}% trung bình/năm)")
        
        # Check profit growth trend
        profit_trend = [financial_data.get(y, {}).get('income_statement', {}).get('net_profit', 0) for y in year_strs]
        
        # Calculate profit growth rate
        if all(profit_trend[i] > 0 for i in range(len(profit_trend))):
            profit_growth_rates = []
            for i in range(1, len(profit_trend)):
                if profit_trend[i-1] > 0:
                    growth_rate = (profit_trend[i] / profit_trend[i-1] - 1) * 100
                    profit_growth_rates.append(growth_rate)
            
            avg_profit_growth = sum(profit_growth_rates) / len(profit_growth_rates) if profit_growth_rates else 0
            
            if avg_profit_growth > 20:
                assessment['growth']['score'] += 1
                assessment['growth']['details'].append(f"Tăng trưởng lợi nhuận mạnh ({avg_profit_growth:.2f}% trung bình/năm)")
                assessment['strengths'].append(f"Tăng trưởng lợi nhuận cao ({avg_profit_growth:.2f}%/năm)")
            elif avg_profit_growth < 0:
                assessment['growth']['score'] -= 1
                assessment['growth']['details'].append(f"Lợi nhuận suy giảm ({avg_profit_growth:.2f}% trung bình/năm)")
                assessment['weaknesses'].append(f"Lợi nhuận có xu hướng giảm ({avg_profit_growth:.2f}%/năm)")
            else:
                assessment['growth']['details'].append(f"Tăng trưởng lợi nhuận ổn định ({avg_profit_growth:.2f}% trung bình/năm)")
    
    # 5. Assess Efficiency
    asset_turnover = latest_ratios.get('Asset_Turnover', 0)
    inventory_turnover = latest_ratios.get('Inventory_Turnover', 0)
    
    sector_at = sector_avg.get('Average Total Asset Turnover', 0.8) if sector_avg else 0.8  # Default benchmark
    sector_it = sector_avg.get('Average Inventory Turnover', 5) if sector_avg else 5  # Default benchmark
    
    # Score Asset Turnover
    if asset_turnover > sector_at * 1.2:
        assessment['efficiency']['score'] += 1
        assessment['efficiency']['details'].append(f"Vòng quay tài sản ({asset_turnover:.2f} lần) cao hơn trung bình ngành")
        assessment['strengths'].append("Hiệu quả sử dụng tài sản cao")
    elif asset_turnover < sector_at * 0.8:
        assessment['efficiency']['score'] -= 1
        assessment['efficiency']['details'].append(f"Vòng quay tài sản ({asset_turnover:.2f} lần) thấp hơn trung bình ngành")
        assessment['weaknesses'].append("Hiệu quả sử dụng tài sản thấp")
    else:
        assessment['efficiency']['details'].append(f"Vòng quay tài sản ({asset_turnover:.2f} lần) ở mức hợp lý")
    
    # Calculate overall score and rating
    assessment['overall_score'] = (
        assessment['profitability']['score'] + 
        assessment['liquidity']['score'] + 
        assessment['leverage']['score'] + 
        assessment['growth']['score'] + 
        assessment['efficiency']['score']
    )
    
    # Determine overall rating based on score
    if assessment['overall_score'] >= 4:
        assessment['overall_rating'] = 'Xuất sắc'
    elif assessment['overall_score'] >= 2:
        assessment['overall_rating'] = 'Tốt'
    elif assessment['overall_score'] >= 0:
        assessment['overall_rating'] = 'Trung bình'
    elif assessment['overall_score'] >= -2:
        assessment['overall_rating'] = 'Cần cải thiện'
    else:
        assessment['overall_rating'] = 'Yếu'
    
    # Generate summary
    assessment['summary'] = f"""
    Đánh giá tổng thể về tình hình tài chính của công ty ở mức {assessment['overall_rating'].upper()}.
    
    Về khả năng sinh lời, công ty có ROE {roe:.2f}% và ROA {roa:.2f}%, 
    {
    'vượt trội so với trung bình ngành' 
    if assessment['profitability']['score'] > 0 
    else 'thấp hơn trung bình ngành' 
    if assessment['profitability']['score'] < 0 
    else 'tương đương với mức trung bình ngành'
    }.
    
    Về tình hình thanh khoản, với tỷ số thanh toán hiện hành {current_ratio:.2f} lần, công ty 
    {
    'có khả năng đáp ứng tốt các nghĩa vụ ngắn hạn' 
    if assessment['liquidity']['score'] > 0 
    else 'có thể gặp khó khăn trong việc đáp ứng các nghĩa vụ ngắn hạn' 
    if assessment['liquidity']['score'] < 0 
    else 'có thể đáp ứng được các nghĩa vụ ngắn hạn ở mức hợp lý'
    }.
    
    Về cơ cấu vốn, với tỷ lệ Nợ/Tài sản {debt_to_assets:.2f}%, công ty 
    {
    'có cơ cấu vốn an toàn với tỷ lệ nợ thấp' 
    if assessment['leverage']['score'] > 0 
    else 'có tỷ lệ nợ cao, tiềm ẩn rủi ro tài chính' 
    if assessment['leverage']['score'] < 0 
    else 'duy trì cơ cấu vốn ở mức hợp lý'
    }.
    
    Về hiệu quả hoạt động, công ty 
    {
    'sử dụng hiệu quả các tài sản để tạo ra doanh thu' 
    if assessment['efficiency']['score'] > 0 
    else 'có hiệu quả sử dụng tài sản thấp' 
    if assessment['efficiency']['score'] < 0 
    else 'có hiệu quả hoạt động ở mức trung bình'
    }.
    
    Về tăng trưởng, công ty 
    {
    'đang có xu hướng tăng trưởng mạnh' 
    if assessment['growth']['score'] > 0 
    else 'đang đối mặt với sự sụt giảm về doanh thu và/hoặc lợi nhuận' 
    if assessment['growth']['score'] < 0 
    else 'duy trì mức tăng trưởng ổn định'
    }.
    """
    
    # Ensure reasonable number of strengths and weaknesses
    assessment['strengths'] = assessment['strengths'][:5]  # Limit to top 5
    assessment['weaknesses'] = assessment['weaknesses'][:5]  # Limit to top 5
    
    # Add default items if too few
    if len(assessment['strengths']) < 3:
        default_strengths = [
            "Vị thế kinh doanh ổn định",
            "Khả năng thích ứng với biến động thị trường",
            "Có tiềm năng phát triển dài hạn"
        ]
        assessment['strengths'].extend(default_strengths[:3 - len(assessment['strengths'])])
    
    if len(assessment['weaknesses']) < 3:
        default_weaknesses = [
            "Đối mặt với áp lực cạnh tranh từ các đối thủ trong ngành",
            "Chịu ảnh hưởng từ biến động kinh tế vĩ mô",
            "Cần đổi mới để duy trì khả năng cạnh tranh"
        ]
        assessment['weaknesses'].extend(default_weaknesses[:3 - len(assessment['weaknesses'])])
    
    return assessment

def generate_business_recommendations(financial_data, financial_ratios, years, financial_health):
    """
    Generate business improvement recommendations based on financial statement analysis
    """
    if not years or not financial_health:
        return None
    
    # Get weaknesses to address
    weaknesses = financial_health.get('weaknesses', [])
    
    # Initialize recommendations
    recommendations = {
        'strategic': [],  # Long-term strategic recommendations
        'operational': [], # Operational improvement recommendations
        'financial': [],  # Financial management recommendations
        'summary': '',  # Summary of key recommendations
        'priority': 'Trung bình'  # Overall priority level (Cao, Trung bình, Thấp)
    }
    
    # Analyze profitability issues
    if financial_health['profitability']['score'] < 0:
        # Low profitability recommendations
        recommendations['strategic'].append("Xem xét lại chiến lược giá và sản phẩm để cải thiện biên lợi nhuận")
        recommendations['operational'].append("Thực hiện chương trình cắt giảm chi phí và tối ưu hóa hiệu quả hoạt động")
        recommendations['financial'].append("Đánh giá lại các khoản đầu tư không hiệu quả và tái cơ cấu danh mục đầu tư")
    
    # Analyze liquidity issues
    if financial_health['liquidity']['score'] < 0:
        # Low liquidity recommendations
        recommendations['strategic'].append("Xem xét cơ cấu lại các khoản nợ ngắn hạn thành dài hạn để cải thiện thanh khoản")
        recommendations['operational'].append("Cải thiện quy trình quản lý vốn lưu động và chu kỳ chuyển đổi tiền mặt")
        recommendations['financial'].append("Tăng cường kiểm soát hàng tồn kho và các khoản phải thu để cải thiện thanh khoản")
    
    # Analyze leverage issues
    if financial_health['leverage']['score'] < 0:
        # High leverage recommendations
        recommendations['strategic'].append("Xây dựng kế hoạch giảm dần tỷ lệ nợ nhằm cải thiện cơ cấu vốn")
        recommendations['financial'].append("Cân nhắc tăng vốn chủ sở hữu thông qua phát hành thêm cổ phiếu hoặc giữ lại lợi nhuận")
    
    # Analyze efficiency issues
    if financial_health['efficiency']['score'] < 0:
        # Low efficiency recommendations
        recommendations['operational'].append("Rà soát lại cơ cấu tài sản và thanh lý các tài sản không hiệu quả")
        recommendations['operational'].append("Cải thiện quy trình sản xuất và chuỗi cung ứng để tăng hiệu quả sử dụng tài sản")
    
    # Analyze growth issues
    if financial_health['growth']['score'] < 0:
        # Low growth recommendations
        recommendations['strategic'].append("Đa dạng hóa sản phẩm/dịch vụ và mở rộng thị trường để tăng tốc độ tăng trưởng")
        recommendations['strategic'].append("Đầu tư vào nghiên cứu phát triển và đổi mới để tạo động lực tăng trưởng mới")
    
    # Add general recommendations if lists are too short
    if len(recommendations['strategic']) < 2:
        default_strategic = [
            "Tập trung vào các phân khúc thị trường có biên lợi nhuận cao hơn",
            "Xây dựng chiến lược kinh doanh bền vững dựa trên lợi thế cạnh tranh của công ty"
        ]
        recommendations['strategic'].extend(default_strategic[:2 - len(recommendations['strategic'])])
    
    if len(recommendations['operational']) < 2:
        default_operational = [
            "Ứng dụng công nghệ để tự động hóa và tối ưu hóa các quy trình nội bộ",
            "Cải thiện hệ thống quản lý chi phí và hiệu quả hoạt động"
        ]
        recommendations['operational'].extend(default_operational[:2 - len(recommendations['operational'])])
    
    if len(recommendations['financial']) < 2:
        default_financial = [
            "Tối ưu hóa cơ cấu vốn để cân bằng giữa rủi ro và lợi nhuận",
            "Cải thiện quản lý dòng tiền và hoạch định tài chính dài hạn"
        ]
        recommendations['financial'].extend(default_financial[:2 - len(recommendations['financial'])])
    
    # Determine priority level based on overall financial health score
    if financial_health['overall_score'] <= -3:
        recommendations['priority'] = 'Cao'
    elif financial_health['overall_score'] <= 0:
        recommendations['priority'] = 'Trung bình-Cao'
    elif financial_health['overall_score'] <= 3:
        recommendations['priority'] = 'Trung bình'
    else:
        recommendations['priority'] = 'Thấp'
    
    # Generate summary of key recommendations based on priority
    if recommendations['priority'] in ['Cao', 'Trung bình-Cao']:
        # High priority situation - focus on addressing major weaknesses
        key_recs = []
        if financial_health['liquidity']['score'] < 0:
            key_recs.append("cải thiện thanh khoản")
        if financial_health['leverage']['score'] < 0:
            key_recs.append("giảm tỷ lệ nợ")
        if financial_health['profitability']['score'] < 0:
            key_recs.append("nâng cao khả năng sinh lời")
        
        if key_recs:
            recommendations['summary'] = f"Ưu tiên hành động ngay để {', '.join(key_recs)}. "
        else:
            recommendations['summary'] = "Cần có kế hoạch cải thiện toàn diện về hiệu quả tài chính. "
        
        recommendations['summary'] += "Đây là những vấn đề cần giải quyết sớm để đảm bảo sự ổn định và phát triển trong tương lai."
    else:
        # Lower priority situation - focus on enhancement and growth
        recommendations['summary'] = "Tập trung vào việc duy trì sự ổn định tài chính hiện tại và đẩy mạnh tăng trưởng. "
        
        if financial_health['growth']['score'] <= 0:
            recommendations['summary'] += "Nên chú trọng vào chiến lược tăng trưởng doanh thu và mở rộng thị trường. "
        else:
            recommendations['summary'] += "Tiếp tục khai thác các cơ hội tăng trưởng và tối ưu hóa hiệu quả hoạt động. "
        
        recommendations['summary'] += "Những cải tiến nhỏ trong quản lý chi phí và tối ưu hóa vốn có thể mang lại lợi ích đáng kể."
    
    return recommendations
def generate_valuation_data(company_code, financial_data, years, sector_avg):
    """
    Generate financial analysis metrics based solely on financial statements (no market data)
    """
    if not years:
        return None
    
    # Get latest financial year data
    latest_year = str(int(years[-1]))
    latest_data = financial_data.get(latest_year, {})
    
    # Extract key financial data (all from financial statements, no market data)
    total_assets = latest_data.get('balance_sheet', {}).get('total_assets', 0)
    equity = latest_data.get('balance_sheet', {}).get('equity', 0)
    liabilities = latest_data.get('balance_sheet', {}).get('liabilities', 0)
    revenue = latest_data.get('income_statement', {}).get('revenue', 0)
    net_profit = latest_data.get('income_statement', {}).get('net_profit', 0)
    operating_profit = latest_data.get('income_statement', {}).get('operating_profit', 0)
    
    # Calculate intrinsic valuation metrics
    # ROE = Return on Equity
    roe = (net_profit / equity) * 100 if equity > 0 else 0
    
    # ROA = Return on Assets
    roa = (net_profit / total_assets) * 100 if total_assets > 0 else 0
    
    # Asset Turnover = Revenue / Total Assets
    asset_turnover = revenue / total_assets if total_assets > 0 else 0
    
    # Debt Ratio = Total Liabilities / Total Assets
    debt_ratio = (liabilities / total_assets) * 100 if total_assets > 0 else 0
    
    # Debt-to-Equity = Total Liabilities / Equity
    debt_to_equity = (liabilities / equity) * 100 if equity > 0 else 0
    
    # Net Profit Margin = Net Profit / Revenue
    profit_margin = (net_profit / revenue) * 100 if revenue > 0 else 0
    
    # Operating Profit Margin = Operating Profit / Revenue
    operating_margin = (operating_profit / revenue) * 100 if revenue > 0 else 0
    
    # Calculate DuPont analysis components (ROE decomposition)
    # ROE = (Net Profit / Revenue) * (Revenue / Total Assets) * (Total Assets / Equity)
    net_profit_margin = net_profit / revenue if revenue > 0 else 0
    asset_turnover_ratio = revenue / total_assets if total_assets > 0 else 0
    equity_multiplier = total_assets / equity if equity > 0 else 0
    
    # Calculate Z-Score (simplified Altman's Z-Score for private companies)
    # Z = 0.717*X1 + 0.847*X2 + 3.107*X3 + 0.420*X4 + 0.998*X5
    # Where:
    # X1 = Working Capital / Total Assets
    # X2 = Retained Earnings / Total Assets
    # X3 = EBIT / Total Assets
    # X4 = Book Value of Equity / Total Liabilities
    # X5 = Sales / Total Assets
    
    working_capital = latest_data.get('balance_sheet', {}).get('current_assets', 0) - latest_data.get('balance_sheet', {}).get('short_term_debt', 0)
    retained_earnings = latest_data.get('balance_sheet', {}).get('retained_earnings', equity * 0.6)  # Estimate if not available
    ebit = latest_data.get('income_statement', {}).get('ebit', operating_profit)
    
    x1 = working_capital / total_assets if total_assets > 0 else 0
    x2 = retained_earnings / total_assets if total_assets > 0 else 0
    x3 = ebit / total_assets if total_assets > 0 else 0
    x4 = equity / liabilities if liabilities > 0 else 0
    x5 = revenue / total_assets if total_assets > 0 else 0
    
    z_score = 0.717*x1 + 0.847*x2 + 3.107*x3 + 0.420*x4 + 0.998*x5
    
    # Sustainable Growth Rate (SGR) = ROE * (1 - Dividend Payout Ratio)
    # Assuming a default dividend payout of 30% if not available
    dividend_payout = 0.3  # Default assumption
    sgr = roe * (1 - dividend_payout) / 100 if roe > 0 else 0
    
    # Economic Value Added (EVA) = NOPAT - (WACC * Invested Capital)
    # Simplified version with assumptions
    nopat = operating_profit * 0.8  # Approximate NOPAT as Operating Profit * (1 - Tax Rate)
    wacc = 0.1  # Weighted Average Cost of Capital (assumption)
    invested_capital = total_assets - latest_data.get('balance_sheet', {}).get('cash_and_equivalents', 0)
    eva = nopat - (wacc * invested_capital)
    
    return {
        'date': datetime.now().strftime('%d/%m/%Y'),
        'total_assets': total_assets,
        'equity': equity,
        'liabilities': liabilities,
        'debt_ratio': debt_ratio,
        'debt_to_equity': debt_to_equity,
        'roe': roe,
        'roa': roa,
        'asset_turnover': asset_turnover,
        'profit_margin': profit_margin,
        'operating_margin': operating_margin,
        'dupont_analysis': {
            'profit_margin': net_profit_margin * 100,
            'asset_turnover': asset_turnover_ratio,
            'equity_multiplier': equity_multiplier
        },
        'z_score': z_score,
        'financial_strength': get_z_score_interpretation(z_score),
        'sustainable_growth_rate': sgr * 100,
        'economic_value_added': eva
    }
def get_z_score_interpretation(z_score):
    """
    Interpret Altman's Z-Score for financial strength assessment
    """
    if z_score > 2.9:
        return "Vùng an toàn - Rủi ro phá sản thấp"
    elif z_score > 1.23:
        return "Vùng xám - Cần theo dõi"
    else:
        return "Vùng nguy hiểm - Rủi ro tài chính cao"

def generate_risk_factors(company_code, financial_data, financial_ratios, years, sector_avg, company_metrics):
    """
    Generate risk and opportunity factors analysis
    """
    if not years:
        return None
    
    # Initialize risk factors lists
    positive_factors = []
    negative_factors = []
    
    # Get latest financial ratios
    latest_year = str(int(years[-1]))
    latest_ratios = financial_ratios.get(latest_year, {})
    
    # Analyze debt levels
    debt_to_equity = latest_ratios.get('Debt_to_Equity', 0)
    if debt_to_equity > 0:
        sector_de = sector_avg.get('Average D/E Ratio', 0)
        if debt_to_equity < sector_de * 0.8:
            positive_factors.append("Tỷ lệ nợ/vốn chủ sở hữu thấp hơn trung bình ngành, giảm rủi ro tài chính.")
        elif debt_to_equity > sector_de * 1.2:
            negative_factors.append("Tỷ lệ nợ/vốn chủ sở hữu cao hơn trung bình ngành, tăng rủi ro tài chính.")
    
    # Analyze liquidity
    current_ratio = latest_ratios.get('Current_Ratio', 0)
    if current_ratio > 0:
        if current_ratio < 1.0:
            negative_factors.append("Tỷ số thanh toán hiện hành dưới 1.0, tiềm ẩn rủi ro thanh khoản ngắn hạn.")
        elif current_ratio > 2.0:
            positive_factors.append("Tỷ số thanh toán hiện hành tốt, khả năng đáp ứng các nghĩa vụ ngắn hạn cao.")
    
    # Analyze profitability
    roe = latest_ratios.get('ROE', 0)
    roa = latest_ratios.get('ROA', 0)
    sector_roe = sector_avg.get('Average ROE', 0)
    sector_roa = sector_avg.get('Average ROA', 0)
    
    if roe > 0 and sector_roe > 0:
        if roe > sector_roe * 1.2:
            positive_factors.append("ROE cao hơn trung bình ngành, hiệu quả sử dụng vốn tốt.")
        elif roe < sector_roe * 0.8:
            negative_factors.append("ROE thấp hơn trung bình ngành, hiệu quả sử dụng vốn còn hạn chế.")
    
    if roa > 0 and sector_roa > 0:
        if roa > sector_roa * 1.2:
            positive_factors.append("ROA cao hơn trung bình ngành, hiệu quả sử dụng tài sản tốt.")
        elif roa < sector_roa * 0.8:
            negative_factors.append("ROA thấp hơn trung bình ngành, hiệu quả sử dụng tài sản còn hạn chế.")
    
    # Analyze growth trends
    if len(years) >= 3:
        # Check revenue growth trend
        recent_years = [str(int(y)) for y in years[-3:]]
        revenue_trend = [financial_data.get(y, {}).get('income_statement', {}).get('revenue', 0) for y in recent_years]
        
        if all(revenue_trend[i] > revenue_trend[i-1] for i in range(1, len(revenue_trend))):
            positive_factors.append("Doanh thu tăng trưởng ổn định qua các năm gần đây.")
        elif all(revenue_trend[i] < revenue_trend[i-1] for i in range(1, len(revenue_trend))):
            negative_factors.append("Doanh thu suy giảm liên tục qua các năm gần đây.")
        
        # Check profit growth trend
        profit_trend = [financial_data.get(y, {}).get('income_statement', {}).get('net_profit', 0) for y in recent_years]
        
        if all(profit_trend[i] > profit_trend[i-1] for i in range(1, len(profit_trend))):
            positive_factors.append("Lợi nhuận tăng trưởng ổn định qua các năm gần đây.")
        elif all(profit_trend[i] < profit_trend[i-1] for i in range(1, len(profit_trend))):
            negative_factors.append("Lợi nhuận suy giảm liên tục qua các năm gần đây.")
    
    # Industry-specific factors based on ICB level 1 or 3
    industry = company_metrics.get('industry', "")
    
    # Add default positive and negative factors if lists are too short
    if len(positive_factors) < 3:
        default_positives = [
            "Vị thế cạnh tranh trong ngành.", 
            "Tiềm năng tăng trưởng dài hạn.", 
            "Khả năng thích ứng với thay đổi thị trường."
        ]
        positive_factors.extend(default_positives[:3 - len(positive_factors)])
    
    if len(negative_factors) < 3:
        default_negatives = [
            "Áp lực cạnh tranh trong ngành gia tăng.", 
            "Biến động chi phí đầu vào.", 
            "Rủi ro biến động tỷ giá và lãi suất."
        ]
        negative_factors.extend(default_negatives[:3 - len(negative_factors)])
    
    return {
        'positive': positive_factors,
        'negative': negative_factors
    }

def generate_recommendation(company_code, financial_data, financial_ratios, years, sector_avg, company_metrics, valuation_data):
    """
    Generate investment recommendation based on financial analysis
    """
    if not years:
        return None
    
    # Initialize recommendation components
    rating = "Trung lập"  # Default rating
    target_price = valuation_data.get('current_price', 0) * 1.05  # Default 5% above current price
    reasons = []
    conclusion = ""
    
    # Get latest financial ratios and metrics
    latest_year = str(int(years[-1]))
    latest_ratios = financial_ratios.get(latest_year, {})
    
    # Analyze profitability vs. sector
    roe = latest_ratios.get('ROE', 0)
    roa = latest_ratios.get('ROA', 0)
    ros = latest_ratios.get('ROS', 0)
    
    sector_roe = sector_avg.get('Average ROE', 0)
    sector_roa = sector_avg.get('Average ROA', 0)
    sector_ros = sector_avg.get('Average ROS', 0)
    
    profitability_score = 0
    
    if roe > 0 and sector_roe > 0:
        if roe > sector_roe * 1.2:
            profitability_score += 1
            reasons.append(f"ROE ({roe:.2f}%) cao hơn trung bình ngành ({sector_roe:.2f}%)")
        elif roe < sector_roe * 0.8:
            profitability_score -= 1
    
    if roa > 0 and sector_roa > 0:
        if roa > sector_roa * 1.2:
            profitability_score += 1
            reasons.append(f"ROA ({roa:.2f}%) cao hơn trung bình ngành ({sector_roa:.2f}%)")
        elif roa < sector_roa * 0.8:
            profitability_score -= 1
    
    # Analyze growth trends
    growth_score = 0
    
    if len(years) >= 3:
        # Check revenue growth trend
        recent_years = [str(int(y)) for y in years[-3:]]
        revenue_trend = [financial_data.get(y, {}).get('income_statement', {}).get('revenue', 0) for y in recent_years]
        
        if all(revenue_trend[i] > revenue_trend[i-1] * 1.05 for i in range(1, len(revenue_trend))):
            growth_score += 1
            reasons.append("Doanh thu có xu hướng tăng trưởng ổn định")
        elif all(revenue_trend[i] < revenue_trend[i-1] for i in range(1, len(revenue_trend))):
            growth_score -= 1
        
        # Check profit growth trend
        profit_trend = [financial_data.get(y, {}).get('income_statement', {}).get('net_profit', 0) for y in recent_years]
        
        if all(profit_trend[i] > profit_trend[i-1] * 1.05 for i in range(1, len(profit_trend))):
            growth_score += 1
            reasons.append("Lợi nhuận có xu hướng tăng trưởng ổn định")
        elif all(profit_trend[i] < profit_trend[i-1] for i in range(1, len(profit_trend))):
            growth_score -= 1
    
    # Analyze valuation
    valuation_score = 0
    pe_ratio = valuation_data.get('PE', 0)
    pb_ratio = valuation_data.get('PB', 0)
    
    sector_pe = sector_avg.get('Average PE', 15)  # Default PE of 15 if not available
    sector_pb = sector_avg.get('Average PB', 1.5)  # Default PB of 1.5 if not available
    
    if pe_ratio > 0 and sector_pe > 0:
        if pe_ratio < sector_pe * 0.8:
            valuation_score += 1
            reasons.append(f"P/E ({pe_ratio:.2f}) thấp hơn trung bình ngành ({sector_pe:.2f})")
        elif pe_ratio > sector_pe * 1.2:
            valuation_score -= 1
    
    if pb_ratio > 0 and sector_pb > 0:
        if pb_ratio < sector_pb * 0.8:
            valuation_score += 1
            reasons.append(f"P/B ({pb_ratio:.2f}) thấp hơn trung bình ngành ({sector_pb:.2f})")
        elif pb_ratio > sector_pb * 1.2:
            valuation_score -= 1
    
    # Analyze financial health
    health_score = 0
    
    debt_to_equity = latest_ratios.get('Debt_to_Equity', 0)
    current_ratio = latest_ratios.get('Current_Ratio', 0)
    
    if debt_to_equity > 0:
        sector_de = sector_avg.get('Average D/E Ratio', 100)  # Default D/E of 100% if not available
        if debt_to_equity < sector_de * 0.8:
            health_score += 1
            reasons.append("Tỷ lệ nợ/vốn chủ sở hữu thấp, giảm rủi ro tài chính")
        elif debt_to_equity > sector_de * 1.2:
            health_score -= 1
    
    if current_ratio > 0:
        if current_ratio > 1.5:
            health_score += 1
            reasons.append(f"Tỷ số thanh toán hiện hành tốt ({current_ratio:.2f})")
        elif current_ratio < 1.0:
            health_score -= 1
    
    # Calculate overall score and determine rating
    overall_score = profitability_score + growth_score + valuation_score + health_score
    
    if overall_score >= 3:
        rating = "Mua"
        target_price = valuation_data.get('current_price', 0) * 1.15  # 15% upside
    elif overall_score >= 1:
        rating = "Tích lũy"
        target_price = valuation_data.get('current_price', 0) * 1.1  # 10% upside
    elif overall_score <= -3:
        rating = "Bán"
        target_price = valuation_data.get('current_price', 0) * 0.85  # 15% downside
    elif overall_score <= -1:
        rating = "Giảm tỷ trọng"
        target_price = valuation_data.get('current_price', 0) * 0.9  # 10% downside
    else:
        rating = "Trung lập"
        target_price = valuation_data.get('current_price', 0) * 1.05  # 5% upside
    
    # Generate conclusion based on rating
    if rating == "Mua":
        conclusion = f"Công ty {company_code} hiện đang có các chỉ số tài chính vượt trội so với trung bình ngành, với ROE, ROA cao và xu hướng tăng trưởng tích cực. Khuyến nghị MUA với giá mục tiêu {target_price:,.0f} VNĐ."
    elif rating == "Tích lũy":
        conclusion = f"Công ty {company_code} có các chỉ số tài chính tốt và tiềm năng tăng trưởng. Khuyến nghị TÍCH LŨY với giá mục tiêu {target_price:,.0f} VNĐ."
    elif rating == "Bán":
        conclusion = f"Công ty {company_code} đang có các chỉ số tài chính kém, rủi ro cao. Khuyến nghị BÁN với giá mục tiêu {target_price:,.0f} VNĐ."
    elif rating == "Giảm tỷ trọng":
        conclusion = f"Công ty {company_code} có một số chỉ số tài chính yếu, tiềm ẩn rủi ro. Khuyến nghị GIẢM TỶ TRỌNG với giá mục tiêu {target_price:,.0f} VNĐ."
    else:
        conclusion = f"Công ty {company_code} có các chỉ số tài chính ở mức trung bình. Khuyến nghị TRUNG LẬP với giá mục tiêu {target_price:,.0f} VNĐ."
    
    # Ensure we have at least 3 reasons
    if len(reasons) < 3:
        default_reasons = [
            "Định giá ở mức hợp lý so với triển vọng tăng trưởng",
            "Cơ cấu tài chính lành mạnh",
            "Tiềm năng phát triển dài hạn"
        ]
        reasons.extend(default_reasons[:3 - len(reasons)])
    
    return {
        'rating': rating,
        'target_price': target_price,
        'reasons': reasons,
        'conclusion': conclusion
    }

def generate_forecast_chart(historical_years, forecast_years, historical_data, forecast_data):
    """
    Generate an improved chart for financial forecasts with better visual clarity
    """
    try:
        # Set a clean, professional style
        plt.style.use('seaborn-v0_8-whitegrid')
        
        # Create a larger figure with better proportions
        plt.figure(figsize=(12, 7))
        
        # Ensure proper DPI for clear rendering
        plt.rcParams['figure.dpi'] = 100
        
        # Convert years to strings for consistent handling
        historical_years = [str(int(year)) for year in historical_years]
        
        # Extract historical revenue and profit data
        historical_revenue = [historical_data.get(year, {}).get('income_statement', {}).get('revenue', 0)/1e9 for year in historical_years]
        historical_profit = [historical_data.get(year, {}).get('income_statement', {}).get('net_profit', 0)/1e9 for year in historical_years]
        
        # Extract forecast revenue and profit data
        forecast_revenue = [forecast_data.get(year, {}).get('revenue', 0)/1e9 for year in forecast_years]
        forecast_profit = [forecast_data.get(year, {}).get('net_profit', 0)/1e9 for year in forecast_years]
        
        # Skip if all values are zero
        if sum(historical_revenue) == 0 and sum(historical_profit) == 0 and sum(forecast_revenue) == 0 and sum(forecast_profit) == 0:
            return None
        
        # Combine all years for the x-axis
        all_years = historical_years + forecast_years
        
        # Plot historical data with solid lines and clear markers
        plt.plot(historical_years, historical_revenue, marker='o', linestyle='-', linewidth=2.5, 
                 color='#1f77b4', label='Doanh thu thực tế')
        plt.plot(historical_years, historical_profit, marker='o', linestyle='-', linewidth=2.5, 
                 color='#2ca02c', label='Lợi nhuận thực tế')
        
        # Plot forecast data with dashed lines and distinct markers
        plt.plot(forecast_years, forecast_revenue, marker='s', linestyle='--', linewidth=2.5, 
                 color='#1f77b4', label='Doanh thu dự báo')
        plt.plot(forecast_years, forecast_profit, marker='s', linestyle='--', linewidth=2.5, 
                 color='#2ca02c', label='Lợi nhuận dự báo')
        
        # Improve grid appearance
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # Add a dividing line between historical and forecast data
        plt.axvline(x=historical_years[-1], color='gray', linestyle='--', alpha=0.7)
        
        # Add "Forecast" annotation at the dividing line
        mid_y = (max(historical_revenue + forecast_revenue) + min(historical_profit + forecast_profit)) / 2
        plt.text(historical_years[-1], mid_y, 'Dự báo', 
                 ha='right', va='center', bbox=dict(facecolor='#fff9cc', alpha=0.8, edgecolor='#e6e6e6', 
                                                  boxstyle='round,pad=0.5'))
        
        # Add value labels for key points (first, last historical, and last forecast)
        # Revenue labels
        plt.text(historical_years[0], historical_revenue[0], f'{historical_revenue[0]:.1f}', 
                 ha='center', va='bottom', fontsize=9)
        plt.text(historical_years[-1], historical_revenue[-1], f'{historical_revenue[-1]:.1f}', 
                 ha='center', va='bottom', fontsize=9)
        plt.text(forecast_years[-1], forecast_revenue[-1], f'{forecast_revenue[-1]:.1f}', 
                 ha='center', va='bottom', fontsize=9)
        
        # Profit labels
        plt.text(historical_years[0], historical_profit[0], f'{historical_profit[0]:.1f}', 
                 ha='center', va='top', fontsize=9)
        plt.text(historical_years[-1], historical_profit[-1], f'{historical_profit[-1]:.1f}', 
                 ha='center', va='top', fontsize=9)
        plt.text(forecast_years[-1], forecast_profit[-1], f'{forecast_profit[-1]:.1f}', 
                 ha='center', va='top', fontsize=9)
        
        # Improve axis labels and title
        plt.xlabel('Năm', fontsize=12, fontweight='bold')
        plt.ylabel('Tỷ VNĐ', fontsize=12, fontweight='bold')
        plt.title('Dự báo kết quả kinh doanh', fontsize=16, fontweight='bold', pad=20)
        
        # Set tick parameters for better readability
        plt.tick_params(axis='both', which='major', labelsize=10)
        
        # Improve legend appearance and placement
        plt.legend(loc='best', frameon=True, fancybox=True, shadow=True, fontsize=10)
        
        # Tighten layout to use space efficiently
        plt.tight_layout()
        
        # Add subtle background color to differentiate forecast area
        ax = plt.gca()
        forecast_idx = len(historical_years)
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # Add subtle background shading for the forecast region
        rect = plt.Rectangle((forecast_idx - 0.5, ylim[0]), xlim[1] - forecast_idx + 0.5, 
                             ylim[1] - ylim[0], color='#f9f9f9', alpha=0.3, zorder=-1)
        ax.add_patch(rect)
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        buf.seek(0)
        
        # Convert to base64
        forecast_chart = base64.b64encode(buf.getvalue()).decode('utf-8')
        plt.close()
        
        return forecast_chart
        
    except Exception as e:
        print(f"Error generating forecast chart: {e}")
        traceback.print_exc()
        return None

def generate_valuation_chart(valuation_data, sector_avg):
    """
    Generate chart comparing valuation metrics with sector averages
    """
    try:
        plt.figure(figsize=(10, 6))
        
        # Extract valuation metrics
        company_metrics = [
            valuation_data.get('PE', 0),
            valuation_data.get('PB', 0),
            valuation_data.get('PS', 0),
            valuation_data.get('EV_EBITDA', 0),
            valuation_data.get('Dividend_Yield', 0)
        ]
        
        # Extract sector average metrics with defaults
        sector_metrics = [
            sector_avg.get('Average PE', 15),
            sector_avg.get('Average PB', 1.5),
            sector_avg.get('Average PS', 1.5),
            sector_avg.get('Average EV_EBITDA', 10),
            sector_avg.get('Average Dividend_Yield', 3)
        ]
        
        # Skip if all values are zero
        if sum(company_metrics) == 0 and sum(sector_metrics) == 0:
            return None
        
        # Metrics labels
        labels = ['P/E', 'P/B', 'P/S', 'EV/EBITDA', 'Tỷ suất cổ tức (%)']
        
        # Set up bar positions
        x = np.arange(len(labels))
        width = 0.35
        
        # Create bars
        plt.bar(x - width/2, company_metrics, width, label='Công ty', color='#3498db')
        plt.bar(x + width/2, sector_metrics, width, label='Trung bình ngành', color='#e74c3c')
        
        # Add details
        plt.xlabel('Chỉ số định giá', fontsize=12)
        plt.ylabel('Giá trị', fontsize=12)
        plt.title('So sánh định giá với trung bình ngành', fontsize=14, fontweight='bold')
        plt.xticks(x, labels, fontsize=10)
        plt.legend(fontsize=10)
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # Add value labels on bars
        for i, v in enumerate(company_metrics):
            if v > 0:
                plt.text(i - width/2, v, f'{v:.2f}', ha='center', va='bottom', fontsize=9)
        
        for i, v in enumerate(sector_metrics):
            if v > 0:
                plt.text(i + width/2, v, f'{v:.2f}', ha='center', va='bottom', fontsize=9)
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        
        # Convert to base64
        valuation_chart = base64.b64encode(buf.getvalue()).decode('utf-8')
        plt.close()
        
        return valuation_chart
        
    except Exception as e:
        print(f"Error generating valuation chart: {e}")
        traceback.print_exc()
        return None

# Hàm tạo biểu đồ cho báo cáo
# Add these functions to your prepare_financial_charts function in app.py

def prepare_financial_charts(data):
    years = data.get('years', [])
    if not years or len(years) < 2:
        # Need at least 2 years of data for meaningful charts
        data['revenue_profit_chart'] = None
        data['ratios_chart'] = None
        data['balance_sheet_chart'] = None
        data['comparison_chart'] = None
        # Initialize the new chart variables
        data['profitability_chart'] = None
        data['growth_chart'] = None
        data['liquidity_chart'] = None
        data['leverage_chart'] = None
        data['efficiency_chart'] = None
        return
    
    # Thiết lập style cho biểu đồ
    plt.style.use('seaborn-v0_8-whitegrid')
    
    # Cấu hình font
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
    
    # Đặt chất lượng biểu đồ
    plt.rcParams['figure.dpi'] = 100
    plt.rcParams['savefig.dpi'] = 100
    
    # Generate original charts (keep existing code)
    # ...
    
    # Generate the new specialized charts
    try:
        generate_profitability_chart(data)
    except Exception as e:
        print(f"Error creating profitability chart: {e}")
        traceback.print_exc()
        data['profitability_chart'] = None
        
    try:
        generate_growth_chart(data)
    except Exception as e:
        print(f"Error creating growth chart: {e}")
        traceback.print_exc()
        data['growth_chart'] = None
        
    try:
        generate_liquidity_chart(data)
    except Exception as e:
        print(f"Error creating liquidity chart: {e}")
        traceback.print_exc()
        data['liquidity_chart'] = None
        
    try:
        generate_leverage_chart(data)
    except Exception as e:
        print(f"Error creating leverage chart: {e}")
        traceback.print_exc()
        data['leverage_chart'] = None
        
    try:
        generate_efficiency_chart(data)
    except Exception as e:
        print(f"Error creating efficiency chart: {e}")
        traceback.print_exc()
        data['efficiency_chart'] = None

def generate_profitability_chart(data):
    """Generate chart for profitability ratios comparison with sector average"""
    if 'company_metrics' not in data or 'sector_avg' not in data:
        data['profitability_chart'] = None
        return
        
    plt.figure(figsize=(10, 6))
    
    # Extract profitability metrics
    metrics = ['ROA (%)', 'ROE (%)', 'ROS (%)', 'EBIT Margin (%)', 'EBITDA Margin (%)', 'Gross Profit Margin (%)']
    company_values = []
    sector_values = []
    
    # Get company metrics
    company_metrics = data['company_metrics']
    company_values = [
        company_metrics.get('ROA (%)', 0),
        company_metrics.get('ROE (%)', 0),
        company_metrics.get('ROS (%)', 0),
        company_metrics.get('EBIT Margin (%)', 0),
        company_metrics.get('EBITDA Margin (%)', 0),
        company_metrics.get('Gross Profit Margin (%)', 0)
    ]
    
    # Get sector averages
    sector_avg = data['sector_avg']
    sector_values = [
        sector_avg.get('Average ROA', 0),
        sector_avg.get('Average ROE', 0),
        sector_avg.get('Average ROS', 0),
        sector_avg.get('Average EBIT Margin', 0),
        sector_avg.get('Average EBITDA Margin', 0),
        sector_avg.get('Average Gross Profit Margin', 0)
    ]
    
    # Skip if all values are zero
    if sum(company_values) == 0 and sum(sector_values) == 0:
        data['profitability_chart'] = None
        return
        
    # Create the chart
    x = np.arange(len(metrics))
    width = 0.35
    
    plt.bar(x - width/2, company_values, width, label=data['company_code'], color='#3498db')
    plt.bar(x + width/2, sector_values, width, label='Trung bình ngành', color='#e74c3c')
    
    plt.xlabel('Chỉ số', fontsize=12)
    plt.ylabel('Phần trăm (%)', fontsize=12)
    plt.title('So sánh chỉ số sinh lời với trung bình ngành', fontsize=14, fontweight='bold')
    plt.xticks(x, metrics, fontsize=10, rotation=45, ha='right')
    plt.legend(fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    # Add value labels
    for i, v in enumerate(company_values):
        if v > 0:
            plt.text(i - width/2, v + 0.5, f'{v:.1f}%', ha='center', fontsize=9)
    
    for i, v in enumerate(sector_values):
        if v > 0:
            plt.text(i + width/2, v + 0.5, f'{v:.1f}%', ha='center', fontsize=9)
    
    # Save chart
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    data['profitability_chart'] = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()

def generate_growth_chart(data):
    """Generate chart for growth ratios comparison with sector average"""
    if 'company_metrics' not in data or 'sector_avg' not in data:
        data['growth_chart'] = None
        return
        
    plt.figure(figsize=(10, 6))
    
    # Extract growth metrics
    metrics = ['Revenue Growth (%)', 'Net Income Growth (%)', 'Total Assets Growth (%)']
    company_values = []
    sector_values = []
    
    # Get company metrics
    company_metrics = data['company_metrics']
    company_values = [
        company_metrics.get('Revenue Growth (%)', 0),
        company_metrics.get('Net Income Growth (%)', 0),
        company_metrics.get('Total Assets Growth (%)', 0)
    ]
    
    # Get sector averages
    sector_avg = data['sector_avg']
    sector_values = [
        sector_avg.get('Average Revenue Growth', 0),
        sector_avg.get('Average Net Income Growth', 0),
        sector_avg.get('Average Total Assets Growth', 0)
    ]
    
    # Skip if all values are zero
    if sum(company_values) == 0 and sum(sector_values) == 0:
        data['growth_chart'] = None
        return
        
    # Create the chart
    x = np.arange(len(metrics))
    width = 0.35
    
    plt.bar(x - width/2, company_values, width, label=data['company_code'], color='#3498db')
    plt.bar(x + width/2, sector_values, width, label='Trung bình ngành', color='#e74c3c')
    
    plt.xlabel('Chỉ số', fontsize=12)
    plt.ylabel('Phần trăm (%)', fontsize=12)
    plt.title('So sánh chỉ số tăng trưởng với trung bình ngành', fontsize=14, fontweight='bold')
    plt.xticks(x, metrics, fontsize=10)
    plt.legend(fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    # Add value labels
    for i, v in enumerate(company_values):
        plt.text(i - width/2, v + (1 if v >= 0 else -3), f'{v:.1f}%', ha='center', fontsize=9)
    
    for i, v in enumerate(sector_values):
        plt.text(i + width/2, v + (1 if v >= 0 else -3), f'{v:.1f}%', ha='center', fontsize=9)
    
    # Save chart
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    data['growth_chart'] = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()

def generate_liquidity_chart(data):
    """Generate chart for liquidity ratios comparison with sector average"""
    if 'company_metrics' not in data or 'sector_avg' not in data:
        data['liquidity_chart'] = None
        return
        
    plt.figure(figsize=(10, 6))
    
    # Extract liquidity metrics
    metrics = ['Current Ratio', 'Quick Ratio', 'Interest Coverage Ratio']
    company_values = []
    sector_values = []
    
    # Get company metrics
    company_metrics = data['company_metrics']
    company_values = [
        company_metrics.get('Current Ratio', 0),
        company_metrics.get('Quick Ratio', 0),
        company_metrics.get('Interest Coverage Ratio', 0)
    ]
    
    # Get sector averages
    sector_avg = data['sector_avg']
    sector_values = [
        sector_avg.get('Average Current Ratio', 0),
        sector_avg.get('Average Quick Ratio', 0),
        sector_avg.get('Average Interest Coverage Ratio', 0)
    ]
    
    # Skip if all values are zero
    if sum(company_values) == 0 and sum(sector_values) == 0:
        data['liquidity_chart'] = None
        return
        
    # Create the chart
    x = np.arange(len(metrics))
    width = 0.35
    
    plt.bar(x - width/2, company_values, width, label=data['company_code'], color='#3498db')
    plt.bar(x + width/2, sector_values, width, label='Trung bình ngành', color='#e74c3c')
    
    plt.xlabel('Chỉ số', fontsize=12)
    plt.ylabel('Lần', fontsize=12)
    plt.title('So sánh chỉ số thanh khoản với trung bình ngành', fontsize=14, fontweight='bold')
    plt.xticks(x, metrics, fontsize=10)
    plt.legend(fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    # Add value labels
    for i, v in enumerate(company_values):
        if v > 0:
            plt.text(i - width/2, v + 0.1, f'{v:.2f}', ha='center', fontsize=9)
    
    for i, v in enumerate(sector_values):
        if v > 0:
            plt.text(i + width/2, v + 0.1, f'{v:.2f}', ha='center', fontsize=9)
    
    # Save chart
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    data['liquidity_chart'] = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()

def generate_leverage_chart(data):
    """Generate chart for leverage ratios comparison with sector average"""
    if 'company_metrics' not in data or 'sector_avg' not in data:
        data['leverage_chart'] = None
        return
        
    plt.figure(figsize=(10, 6))
    
    # Extract leverage metrics
    metrics = ['D/A (%)', 'D/E (%)', 'E/A (%)']
    company_values = []
    sector_values = []
    
    # Get company metrics
    company_metrics = data['company_metrics']
    company_values = [
        company_metrics.get('D/A (%)', 0),
        company_metrics.get('D/E (%)', 0),
        company_metrics.get('E/A (%)', 0)
    ]
    
    # Get sector averages
    sector_avg = data['sector_avg']
    sector_values = [
        sector_avg.get('Average D/A Ratio', 0),
        sector_avg.get('Average D/E Ratio', 0),
        sector_avg.get('Average E/A Ratio', 0)
    ]
    
    # Skip if all values are zero
    if sum(company_values) == 0 and sum(sector_values) == 0:
        data['leverage_chart'] = None
        return
        
    # Create the chart
    x = np.arange(len(metrics))
    width = 0.35
    
    plt.bar(x - width/2, company_values, width, label=data['company_code'], color='#3498db')
    plt.bar(x + width/2, sector_values, width, label='Trung bình ngành', color='#e74c3c')
    
    plt.xlabel('Chỉ số', fontsize=12)
    plt.ylabel('Phần trăm (%)', fontsize=12)
    plt.title('So sánh chỉ số đòn bẩy với trung bình ngành', fontsize=14, fontweight='bold')
    plt.xticks(x, metrics, fontsize=10)
    plt.legend(fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    # Add value labels
    for i, v in enumerate(company_values):
        if v > 0:
            plt.text(i - width/2, v + 1, f'{v:.1f}%', ha='center', fontsize=9)
    
    for i, v in enumerate(sector_values):
        if v > 0:
            plt.text(i + width/2, v + 1, f'{v:.1f}%', ha='center', fontsize=9)
    
    # Save chart
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    data['leverage_chart'] = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()

def generate_efficiency_chart(data):
    """Generate chart for efficiency ratios comparison with sector average"""
    if 'company_metrics' not in data or 'sector_avg' not in data:
        data['efficiency_chart'] = None
        return
        
    plt.figure(figsize=(10, 6))
    
    # Extract efficiency metrics
    metrics = ['Total Asset Turnover', 'Inventory Turnover', 'Accounts Receivable Turnover', 'Working Capital Turnover']
    company_values = []
    sector_values = []
    
    # Get company metrics
    company_metrics = data['company_metrics']
    company_values = [
        company_metrics.get('Total Asset Turnover', 0),
        company_metrics.get('Inventory Turnover', 0),
        company_metrics.get('Accounts Receivable Turnover', 0),
        company_metrics.get('Working Capital Turnover', 0)
    ]
    
    # Get sector averages
    sector_avg = data['sector_avg']
    sector_values = [
        sector_avg.get('Average Total Asset Turnover', 0),
        sector_avg.get('Average Inventory Turnover', 0),
        sector_avg.get('Average Accounts Receivable Turnover', 0),
        sector_avg.get('Average Working Capital Turnover', 0)
    ]
    
    # Skip if all values are zero
    if sum(company_values) == 0 and sum(sector_values) == 0:
        data['efficiency_chart'] = None
        return
        
    # Create the chart
    x = np.arange(len(metrics))
    width = 0.35
    
    plt.bar(x - width/2, company_values, width, label=data['company_code'], color='#3498db')
    plt.bar(x + width/2, sector_values, width, label='Trung bình ngành', color='#e74c3c')
    
    plt.xlabel('Chỉ số', fontsize=12)
    plt.ylabel('Lần', fontsize=12)
    plt.title('So sánh chỉ số hiệu quả hoạt động với trung bình ngành', fontsize=14, fontweight='bold')
    plt.xticks(x, metrics, fontsize=10, rotation=15, ha='right')
    plt.legend(fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    # Add value labels
    for i, v in enumerate(company_values):
        if v > 0:
            plt.text(i - width/2, v + 0.1, f'{v:.2f}', ha='center', fontsize=9)
    
    for i, v in enumerate(sector_values):
        if v > 0:
            plt.text(i + width/2, v + 0.1, f'{v:.2f}', ha='center', fontsize=9)
    
    # Save chart
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    data['efficiency_chart'] = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()
# Add this new API endpoint to app.py

@app.route('/api/financial_statements/<company_code>')
def get_financial_statements(company_code):
    """API endpoint for retrieving financial statements by year"""
    year = request.args.get('year', None)
    
    if not year:
        return jsonify({"error": "Year parameter is required"}), 400
    
    try:
        year = int(year)
    except ValueError:
        return jsonify({"error": "Year must be a valid integer"}), 400
    
    # Initialize result structure
    result = {
        "balance_sheet": None,
        "income_statement": None,
        "cash_flow": None
    }
    
    try:
        # Get balance sheet data
        if 'balance_sheet' in app_data:
            balance_sheet_data = app_data['balance_sheet'][
                (app_data['balance_sheet']['Mã'] == company_code) & 
                (app_data['balance_sheet']['Năm'] == year)
            ]
            
            if not balance_sheet_data.empty:
                # Sort by quarter to get the latest quarter data
                balance_sheet_data = balance_sheet_data.sort_values(by='Quý', ascending=False)
                latest_bs = balance_sheet_data.iloc[0]
                
                # Extract relevant fields
                result["balance_sheet"] = {
                    "current_assets": float(latest_bs['TÀI SẢN NGẮN HẠN']) if 'TÀI SẢN NGẮN HẠN' in latest_bs and pd.notna(latest_bs['TÀI SẢN NGẮN HẠN']) else None,
                    "cash_and_equivalents": float(latest_bs['Tiền và tương đương tiền']) if 'Tiền và tương đương tiền' in latest_bs and pd.notna(latest_bs['Tiền và tương đương tiền']) else None,
                    "short_term_investments": float(latest_bs['Đầu tư tài chính ngắn hạn']) if 'Đầu tư tài chính ngắn hạn' in latest_bs and pd.notna(latest_bs['Đầu tư tài chính ngắn hạn']) else None,
                    "short_term_receivables": float(latest_bs['Các khoản phải thu ngắn hạn']) if 'Các khoản phải thu ngắn hạn' in latest_bs and pd.notna(latest_bs['Các khoản phải thu ngắn hạn']) else None,
                    "inventory": float(latest_bs['Hàng tồn kho, ròng']) if 'Hàng tồn kho, ròng' in latest_bs and pd.notna(latest_bs['Hàng tồn kho, ròng']) else None,
                    "other_current_assets": float(latest_bs['Tài sản ngắn hạn khác']) if 'Tài sản ngắn hạn khác' in latest_bs and pd.notna(latest_bs['Tài sản ngắn hạn khác']) else None,
                    "non_current_assets": float(latest_bs['TÀI SẢN DÀI HẠN']) if 'TÀI SẢN DÀI HẠN' in latest_bs and pd.notna(latest_bs['TÀI SẢN DÀI HẠN']) else None,
                    "fixed_assets": float(latest_bs['Tài sản cố định']) if 'Tài sản cố định' in latest_bs and pd.notna(latest_bs['Tài sản cố định']) else None,
                    "long_term_investments": float(latest_bs['Đầu tư dài hạn']) if 'Đầu tư dài hạn' in latest_bs and pd.notna(latest_bs['Đầu tư dài hạn']) else None,
                    "other_non_current_assets": float(latest_bs['Tài sản dài hạn khác']) if 'Tài sản dài hạn khác' in latest_bs and pd.notna(latest_bs['Tài sản dài hạn khác']) else None,
                    "total_assets": float(latest_bs['TỔNG CỘNG TÀI SẢN']) if 'TỔNG CỘNG TÀI SẢN' in latest_bs and pd.notna(latest_bs['TỔNG CỘNG TÀI SẢN']) else None,
                    "liabilities": float(latest_bs['NỢ PHẢI TRẢ']) if 'NỢ PHẢI TRẢ' in latest_bs and pd.notna(latest_bs['NỢ PHẢI TRẢ']) else None,
                    "current_liabilities": float(latest_bs['Nợ ngắn hạn']) if 'Nợ ngắn hạn' in latest_bs and pd.notna(latest_bs['Nợ ngắn hạn']) else None,
                    "non_current_liabilities": float(latest_bs['Nợ dài hạn']) if 'Nợ dài hạn' in latest_bs and pd.notna(latest_bs['Nợ dài hạn']) else None,
                    "equity": float(latest_bs['VỐN CHỦ SỞ HỮU']) if 'VỐN CHỦ SỞ HỮU' in latest_bs and pd.notna(latest_bs['VỐN CHỦ SỞ HỮU']) else None,
                    "owner_equity": float(latest_bs['Vốn góp của chủ sở hữu']) if 'Vốn góp của chủ sở hữu' in latest_bs and pd.notna(latest_bs['Vốn góp của chủ sở hữu']) else None,
                    "retained_earnings": float(latest_bs['Lãi chưa phân phối']) if 'Lãi chưa phân phối' in latest_bs and pd.notna(latest_bs['Lãi chưa phân phối']) else None,
                    "total_liabilities_and_equity": float(latest_bs['TỔNG CỘNG NGUỒN VỐN']) if 'TỔNG CỘNG NGUỒN VỐN' in latest_bs and pd.notna(latest_bs['TỔNG CỘNG NGUỒN VỐN']) else None
                }
        
        # Get income statement data
        if 'income_statement' in app_data:
            income_statement_data = app_data['income_statement'][
                (app_data['income_statement']['Mã'] == company_code) & 
                (app_data['income_statement']['Năm'] == year)
            ]
            
            if not income_statement_data.empty:
                # Sort by quarter to get the latest quarter data
                income_statement_data = income_statement_data.sort_values(by='Quý', ascending=False)
                latest_is = income_statement_data.iloc[0]
                
                # Extract relevant fields
                result["income_statement"] = {
                    "total_revenue": float(latest_is['Doanh thu bán hàng và cung cấp dịch vụ']) if 'Doanh thu bán hàng và cung cấp dịch vụ' in latest_is and pd.notna(latest_is['Doanh thu bán hàng và cung cấp dịch vụ']) else None,
                    "revenue_deductions": float(latest_is['Doanh thu bán hàng và cung cấp dịch vụ']) - float(latest_is['Doanh thu thuần']) if 'Doanh thu bán hàng và cung cấp dịch vụ' in latest_is and 'Doanh thu thuần' in latest_is and pd.notna(latest_is['Doanh thu bán hàng và cung cấp dịch vụ']) and pd.notna(latest_is['Doanh thu thuần']) else None,
                    "net_revenue": float(latest_is['Doanh thu thuần']) if 'Doanh thu thuần' in latest_is and pd.notna(latest_is['Doanh thu thuần']) else None,
                    "cost_of_goods_sold": float(latest_is['Doanh thu thuần']) - float(latest_is['Lợi nhuận gộp về bán hàng và cung cấp dịch vụ']) if 'Doanh thu thuần' in latest_is and 'Lợi nhuận gộp về bán hàng và cung cấp dịch vụ' in latest_is and pd.notna(latest_is['Doanh thu thuần']) and pd.notna(latest_is['Lợi nhuận gộp về bán hàng và cung cấp dịch vụ']) else None,
                    "gross_profit": float(latest_is['Lợi nhuận gộp về bán hàng và cung cấp dịch vụ']) if 'Lợi nhuận gộp về bán hàng và cung cấp dịch vụ' in latest_is and pd.notna(latest_is['Lợi nhuận gộp về bán hàng và cung cấp dịch vụ']) else None,
                    "financial_income": float(latest_is['Doanh thu hoạt động tài chính']) if 'Doanh thu hoạt động tài chính' in latest_is and pd.notna(latest_is['Doanh thu hoạt động tài chính']) else None,
                    "financial_expenses": float(latest_is['Chi phí tài chính']) if 'Chi phí tài chính' in latest_is and pd.notna(latest_is['Chi phí tài chính']) else None,
                    "interest_expense": float(latest_is['Trong đó: Chi phí lãi vay']) if 'Trong đó: Chi phí lãi vay' in latest_is and pd.notna(latest_is['Trong đó: Chi phí lãi vay']) else None,
                    "selling_expenses": float(latest_is['Chi phí bán hàng']) if 'Chi phí bán hàng' in latest_is and pd.notna(latest_is['Chi phí bán hàng']) else None,
                    "administrative_expenses": float(latest_is['Chi phí quản lý doanh  nghiệp']) if 'Chi phí quản lý doanh  nghiệp' in latest_is and pd.notna(latest_is['Chi phí quản lý doanh  nghiệp']) else None,
                    "operating_profit": float(latest_is['Lợi nhuận thuần từ hoạt động kinh doanh']) if 'Lợi nhuận thuần từ hoạt động kinh doanh' in latest_is and pd.notna(latest_is['Lợi nhuận thuần từ hoạt động kinh doanh']) else None,
                    "other_income": None,  # Not directly available in the dataset
                    "other_expenses": None,  # Not directly available in the dataset
                    "other_profit": float(latest_is['Lợi nhuận khác']) if 'Lợi nhuận khác' in latest_is and pd.notna(latest_is['Lợi nhuận khác']) else None,
                    "profit_before_tax": float(latest_is['Tổng lợi nhuận kế toán trước thuế']) if 'Tổng lợi nhuận kế toán trước thuế' in latest_is and pd.notna(latest_is['Tổng lợi nhuận kế toán trước thuế']) else None,
                    "current_tax": float(latest_is['Chi phí thuế thu nhập doanh nghiệp']) if 'Chi phí thuế thu nhập doanh nghiệp' in latest_is and pd.notna(latest_is['Chi phí thuế thu nhập doanh nghiệp']) else None,
                    "deferred_tax": None,  # Not directly available in the dataset
                    "profit_after_tax": float(latest_is['Lợi nhuận sau thuế thu nhập doanh nghiệp']) if 'Lợi nhuận sau thuế thu nhập doanh nghiệp' in latest_is and pd.notna(latest_is['Lợi nhuận sau thuế thu nhập doanh nghiệp']) else None,
                    "basic_earnings_per_share": float(latest_is['Lãi cơ bản trên cổ phiếu']) if 'Lãi cơ bản trên cổ phiếu' in latest_is and pd.notna(latest_is['Lãi cơ bản trên cổ phiếu']) else None
                }
        
        # Get cash flow statement data
        if 'cash_flow' in app_data:
            cash_flow_data = app_data['cash_flow'][
                (app_data['cash_flow']['Mã'] == company_code) & 
                (app_data['cash_flow']['Năm'] == year)
            ]
            
            if not cash_flow_data.empty:
                # Sort by quarter to get the latest quarter data
                cash_flow_data = cash_flow_data.sort_values(by='Quý', ascending=False)
                latest_cf = cash_flow_data.iloc[0]
                
                # Extract relevant fields
                result["cash_flow"] = {
                    "profit_before_tax": float(latest_cf['Tổng lợi nhuận kế toán trước thuế.1']) if 'Tổng lợi nhuận kế toán trước thuế.1' in latest_cf and pd.notna(latest_cf['Tổng lợi nhuận kế toán trước thuế.1']) else None,
                    "adjustments": None,  # Need to calculate from multiple fields
                    "depreciation": float(latest_cf['Khấu hao TSCĐ']) if 'Khấu hao TSCĐ' in latest_cf and pd.notna(latest_cf['Khấu hao TSCĐ']) else None,
                    "interest_expense": None,  # Would need to cross-reference with income statement
                    "net_cash_from_operating": float(latest_cf['Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh (TT)']) if 'Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh (TT)' in latest_cf and pd.notna(latest_cf['Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh (TT)']) else None,
                    "purchase_of_fixed_assets": float(latest_cf['Tiền chi để mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác (TT)']) if 'Tiền chi để mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác (TT)' in latest_cf and pd.notna(latest_cf['Tiền chi để mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác (TT)']) else None,
                    "proceeds_from_disposals": float(latest_cf['Tiền thu từ thanh lý, nhượng bán TSCĐ và các tài sản dài hạn khác (TT)']) if 'Tiền thu từ thanh lý, nhượng bán TSCĐ và các tài sản dài hạn khác (TT)' in latest_cf and pd.notna(latest_cf['Tiền thu từ thanh lý, nhượng bán TSCĐ và các tài sản dài hạn khác (TT)']) else None,
                    "loans_to_other_entities": float(latest_cf['Tiền chi cho vay, mua các công cụ nợ của đợn vị khác (TT)']) if 'Tiền chi cho vay, mua các công cụ nợ của đợn vị khác (TT)' in latest_cf and pd.notna(latest_cf['Tiền chi cho vay, mua các công cụ nợ của đợn vị khác (TT)']) else None,
                    "collections_from_loans": float(latest_cf['Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác (TT)']) if 'Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác (TT)' in latest_cf and pd.notna(latest_cf['Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác (TT)']) else None,
                    "net_cash_from_investing": float(latest_cf['Lưu chuyển tiền tệ ròng từ hoạt động đầu tư (TT)']) if 'Lưu chuyển tiền tệ ròng từ hoạt động đầu tư (TT)' in latest_cf and pd.notna(latest_cf['Lưu chuyển tiền tệ ròng từ hoạt động đầu tư (TT)']) else None,
                    "proceeds_from_issuing_shares": float(latest_cf['Tiền thu từ phát hành cổ phiếu, nhận góp vốn của chủ sở hữu (TT)']) if 'Tiền thu từ phát hành cổ phiếu, nhận góp vốn của chủ sở hữu (TT)' in latest_cf and pd.notna(latest_cf['Tiền thu từ phát hành cổ phiếu, nhận góp vốn của chủ sở hữu (TT)']) else None,
                    "proceeds_from_borrowings": float(latest_cf['Tiền thu được các khoản đi vay (TT)']) if 'Tiền thu được các khoản đi vay (TT)' in latest_cf and pd.notna(latest_cf['Tiền thu được các khoản đi vay (TT)']) else None,
                    "repayments_of_borrowings": float(latest_cf['Tiền trả nợ gốc vay (TT)']) if 'Tiền trả nợ gốc vay (TT)' in latest_cf and pd.notna(latest_cf['Tiền trả nợ gốc vay (TT)']) else None,
                    "dividends_paid": float(latest_cf['Cổ tức đã trả (TT)']) if 'Cổ tức đã trả (TT)' in latest_cf and pd.notna(latest_cf['Cổ tức đã trả (TT)']) else None,
                    "net_cash_from_financing": float(latest_cf['Lưu chuyển tiền tệ từ hoạt động tài chính (TT)']) if 'Lưu chuyển tiền tệ từ hoạt động tài chính (TT)' in latest_cf and pd.notna(latest_cf['Lưu chuyển tiền tệ từ hoạt động tài chính (TT)']) else None,
                    "net_cash_flow": float(latest_cf['Lưu chuyển tiền thuần trong kỳ (TT)']) if 'Lưu chuyển tiền thuần trong kỳ (TT)' in latest_cf and pd.notna(latest_cf['Lưu chuyển tiền thuần trong kỳ (TT)']) else None,
                    "cash_beginning": float(latest_cf['Tiền và tương đương tiền đầu kỳ (TT)']) if 'Tiền và tương đương tiền đầu kỳ (TT)' in latest_cf and pd.notna(latest_cf['Tiền và tương đương tiền đầu kỳ (TT)']) else None,
                    "cash_ending": float(latest_cf['Tiền và tương đương tiền đầu kỳ (TT)']) + float(latest_cf['Lưu chuyển tiền thuần trong kỳ (TT)']) if 'Tiền và tương đương tiền đầu kỳ (TT)' in latest_cf and 'Lưu chuyển tiền thuần trong kỳ (TT)' in latest_cf and pd.notna(latest_cf['Tiền và tương đương tiền đầu kỳ (TT)']) and pd.notna(latest_cf['Lưu chuyển tiền thuần trong kỳ (TT)']) else None
                }
        
        return jsonify(result)
    
    except Exception as e:
        print(f"Error fetching financial statements for {company_code}, year {year}: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
