"""
Database Models Package for Financial Analysis Application

This package contains database model definitions for the application.
Since we're primarily working with CSV data in this version, this package
may be extended in future versions to include proper database models
if a database integration is added.

Current structure:
- No database models are implemented in the initial version.
- Data is loaded directly from CSV files using pandas.

Future considerations:
- Add SQLAlchemy ORM models for companies, financial statements, and metrics
- Implement data persistence for user preferences and saved analyses
"""

# This file is a placeholder for future database models
# For now, we're using pandas DataFrames to handle the data

# When actual database models are added, they would be imported and exposed here
# Example:
# from models.company import Company
# from models.financial_statement import FinancialStatement
# from models.financial_metric import FinancialMetric
# 
# __all__ = ['Company', 'FinancialStatement', 'FinancialMetric']