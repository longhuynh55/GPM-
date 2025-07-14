# 📊 Professional Financial Analysis Platform

**A comprehensive web application for financial analysis of listed companies on Vietnamese stock market**

## 🌟 Overview

This project provides a comprehensive financial analysis platform that allows users to research and evaluate the financial performance of companies listed on HOSE, HNX, and UPCoM exchanges from 2020-2024. The system integrates advanced analytical tools, interactive visualizations, and detailed reporting capabilities.

## 🎯 Key Features

### 📈 Home Page
- **Market Overview**: General statistics on number of companies and industries
- **Key Indicators**: Display average ROE and ROA across the market
- **Top 10 Companies**: Ranking companies by highest ROE
- **Industry Analysis**: Comparison table of financial indicators by industry
- **Quick Search**: Company lookup by stock code

### 🔍 Company Analysis
- **Smart Search**: Auto-suggestion when entering company codes
- **Company Information**: Name, code, exchange, ICB industry classification
- **Trend Charts**: Revenue and profit visualization over years
- **Complete Financial Statements**:
  - Balance Sheet
  - Income Statement
  - Cash Flow Statement
- **Year Selection**: View data from 2020-2024

### 📋 Export Report
- **Flexible Formats**: HTML (online view) or PDF (download)
- **Interface Customization**: Layout, colors, font size
- **Content Customization**: Show/hide specific sections
- **Time Range**: Select number of years (up to 5 years)

## 📊 Database Structure

### Main Financial Data (7,745 rows each)
- **BCTC.csv**: Comprehensive financial statements (169 columns)
- **BCDKT.csv**: Balance sheet (55 columns)
- **KQKD.csv**: Income statement (34 columns)
- **LCTT.csv**: Cash flow statement (31 columns)
- **TM.csv**: Notes to financial statements (86 columns)

### Aggregated Data
- **Average_by_Code.csv**: Average indicators by company (1,604 rows, 23 columns)
- **Average_by_Sector.csv**: Average indicators by industry (37 rows, 23 columns)

## 📈 Report Content

### 1. Company Information
- Stock code, company name, exchange listing
- ICB industry classification (3 levels)
- Business sector overview

### 2. Industry Comparison
- **Profitability Ratios**: ROA, ROE, ROS, EBIT Margin, EBITDA Margin
- **Growth Indicators**: Revenue, profit, and asset growth
- **Liquidity Ratios**: Current ratio, quick ratio
- **Leverage Ratios**: Debt/assets, debt/equity
- **Efficiency Ratios**: Asset turnover, inventory turnover

### 3. Financial Statement Analysis
- Detailed income statement analysis
- Balance sheet structure
- Cash flow analysis
- Trend assessment

### 4. In-depth Analysis
- Profitability analysis
- Growth analysis
- Capital structure analysis
- Operational efficiency analysis

### 5. Forecasting & Recommendations
- 3-year financial forecasts
- Financial health assessment
- Improvement recommendations
- Priority levels

## ⚠️ System Limitations

### Financial Industry Specifics
The system uses a standard report template for all companies, leading to some limitations:

- **Banks**: Missing specific items like interest income, credit risk provisions
- **Securities**: No distinction between brokerage, proprietary trading, advisory revenue
- **Insurance**: Missing insurance premiums, claims, technical reserves

**Recommendation**: For financial companies, additional reference to original reports and industry-specific analysis is recommended.

## 🛠️ Technology Stack

- **Frontend**: HTML, CSS, JavaScript
- **Backend**: [To be specified]
- **Database**: CSV files
- **Visualization**: [Chart library to be specified]
- **Export**: HTML/PDF generation

## 📁 Project Structure

```
project/
├── data/
│   ├── BCTC.csv
│   ├── BCDKT.csv
│   ├── KQKD.csv
│   ├── LCTT.csv
│   ├── TM.csv
│   ├── Average_by_Code.csv
│   └── Average_by_Sector.csv
├── src/
│   ├── pages/
│   │   ├── home/
│   │   ├── company-analysis/
│   │   └── export-report/
│   ├── components/
│   └── utils/
└── docs/
```

## 🚀 Usage Guide

1. **Access Homepage**: View market overview
2. **Search Company**: Enter stock code
3. **Analysis**: View indicators and charts
4. **Export Report**: Choose format and customize
5. **Download**: Save PDF report or view HTML

## 📊 Sample Data

- **Time Period**: 2020-2024
- **Number of Companies**: 1,604 companies
- **Number of Industries**: 37 industries
- **Frequency**: Quarterly and annual data

## 🔧 Installation

```bash
# Clone the repository
git clone [repository-url]

# Install dependencies
npm install

# Run the application
npm start
```

## 📱 Screenshots

[Add screenshots of the application interface here]

## 🌐 Demo

[Add demo link if available]

## 📝 License

This project is developed for educational purposes at University of Economics and Law. Please refer to the LICENSE file for more details.

## 📞 Contact

- **Author**: Liêu Hoài Phúc
- **Email**: phuclieu03@gmail.com
- **University**: University of Economics and Law
## 🙏 Acknowledgments

Special thanks to data sources from:
- **FiinProx**: Financial data provider
- **HOSE** (Ho Chi Minh Stock Exchange)
- **HNX** (Hanoi Stock Exchange)
- **UPCoM** (Unlisted Public Company Market)

---

⭐ **If you find this project useful, please give it a star!** ⭐
