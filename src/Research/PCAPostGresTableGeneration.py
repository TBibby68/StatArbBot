import pandas as pd
import psycopg2
import configparser

# this file just creates a new postgres table designed to fit the PCA backtesting data in - 100 stocks 

def GeneratePCATable():
    # 1) import tickers from excel using pandas:
    stock_tickers = pd.read_excel("banks to trade on.xlsx")
    tickers = stock_tickers.iloc[:, 0].dropna().unique().tolist()

    # 2) define SQL query: 
    columns_sql = ", ".join([f'"{ticker}" FLOAT' for ticker in tickers])
    create_table_sql = f"CREATE TABLE hundred_stock_prices ({columns_sql});"

    # 3) run on my postgres database:
    config = configparser.ConfigParser()
    config.read('db_config.ini')

    params = config['postgresql']

    # Use unpacking to connect
    conn = psycopg2.connect(**params)
    
    cur = conn.cursor()
    cur.execute(create_table_sql)

    conn.commit()
    cur.close()
    conn.close()

# run the function
GeneratePCATable()