
import sqlite3
import logging
from langchain_core.documents import Document

import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)
import json
from config import settings

logger = logging.getLogger(__name__)

class SchemaExtractor:
    def __init__(self):
        self.conn = None
        self.cursor =None

    def __enter__(self):
        self.conn = sqlite3.connect(settings.SQL_DB_PATH)
        self.cursor = self.conn.cursor()
        logger.info("SQL connection established to %s", settings.SQL_DB_PATH)
        return self  

    def __exit__(self, exc_type, exc_val, exc_tb):
        
        if self.conn:
            self.cursor.close()
            self.conn.close()
            print("Connection closed automatically!")

    def get_all_tables(self):
        self.cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            """)

        table_data = self.cursor.fetchall()
        return table_data
        
    def get_column_data(self,table_name):
        
        self.cursor.execute(f"""
            PRAGMA table_info({table_name})
            """)
        
        col_data = self.cursor.fetchall()
        # print(col_data)
        return col_data
    
    def get_sample_data(self,col_name,table_name):
        # print(col_name,table_name)
        self.cursor.execute(f"""
               SELECT DISTINCT {col_name} FROM {table_name} WHERE {col_name} IS NOT NULL
            """
        )
        unique_values = [row[0] for row in self.cursor.fetchall()]
        
        if len(unique_values)<=5:
            return unique_values
        else:
            return unique_values[:5]
        # if len()

def meta_str(meta):
    return f"""
    Table Name: {meta['table_name']}

    Columns:[
      {', \n      '.join(f'"column_name" :{data["column_name"]} ,"Format" : {data["Format"]} ,"sample_values" : {data["sample_values"]}'  for data in meta['columns'])}
     ]
     
    """
    

def metadata_to_text(meta):

    data_str = meta_str(meta)
    doc = Document(
                page_content = data_str,
                metadata = {
                    'table_name':meta['table_name']
                }
            )
    return doc

import os
if __name__=="__main__":
    path = settings.DATA_PATH
    os.makedirs(path,exist_ok=True)
    path = settings.JSON_FILE_PATH
    with SchemaExtractor() as sql:
        print('sql connection extablished')
        doc_list = []
        doc_data_list = []
        table_data = sql.get_all_tables()
        print("fetching table data,",table_data)
        for i in table_data:
            # print('i', i)
            cols = [{"column_name": col[1],'Format': col[2],"sample_values":sql.get_sample_data(col[1],i[0])}  for col in sql.get_column_data(i[0])]
            doc_data = {
                "table_name":i[0],
                "columns":cols
                }
            doc_data_list.append(doc_data)
            # print(i[0], cols)
            doc = metadata_to_text(doc_data)
            
            doc_list.append(doc)
    
    with open(path,"w",encoding="utf-8") as json_file:
        json.dump(doc_data_list, json_file, indent=4)

    print(" Sucessfully json file created")

    

    