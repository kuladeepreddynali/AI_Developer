import os
import logging
import sys

# Ensure project root is on sys.path so top-level imports like `config` work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from config import settings

logger = logging.getLogger(__name__)


class SchemaRetrival:
  def __init__(self):
    self.embedding_model = settings.EMBED_MODEL
    
    self.chroma_db_path = settings.CHROMA_DB_PATH
    # self.google_key = google_key # Store the API key
    os.makedirs(self.chroma_db_path,exist_ok=True)
    self.embeddings = HuggingFaceEmbeddings(
                  model=self.embedding_model,
                  model_kwargs={'device': 'cpu'})
    logger.info("Initialized Hugging face model with model: %s",self.embedding_model)
    
  def db_count_collections(self):
    vector_db = Chroma(
        persist_directory=self.chroma_db_path,
        embedding_function=self.embeddings
    )
    return vector_db._collection.count()

  def load_vector_store(self):
    if not os.path.exists(self.chroma_db_path):
      logger.warning("vector Db store is not found : %s. Please check once it should be initialized before",self.chroma_db_path)
      raise Exception("Failed to load vector DB because file not found at %s",self.chroma_db_path)
      
    vector_db = Chroma(
        persist_directory=self.chroma_db_path,
        embedding_function=self.embeddings
    )
    logger.info("count Vector db collection %s", vector_db._collection.count())
    return vector_db

  def build_vector_store(self,docs_list):
    logger.info("Vector db is building ...")
    vector_db = Chroma.from_documents(
        documents =docs_list,
        embedding=self.embeddings,
        persist_directory=self.chroma_db_path
    )
    logger.info("Vector db is built")
    return vector_db

  def invoke(self,vector_db,user_query,fetch_number=5):
    logger.info("Executing vector_db schema lookup for : %s", user_query)
    try:
      matching_docs = vector_db.similarity_search(user_query,k=fetch_number)
      # content = "\n".join(doc.page_content for doc in matching_docs)
      return matching_docs
    except Exception as e:
      error = f"Excpetion on vector schema search:{e}",
      logger.exception(error)
      raise error



if __name__=="__main__":
    # with SchemaExtractor() as sql:
    #     print('sql connection extablished')
    #     doc_list = []
    #     table_data = sql.get_all_tables()
    #     print("fetching table data,",table_data)
    #     for i in table_data:
    #         table_name = i[0]
    #         print('i', table_name)
    #         cols = [{"column_name": col[1],'Format': col[2],"sample_values":sql.get_sample_data(col[1],i[0])}  for col in sql.get_column_data(i[0])]
    #         # print(i[0], cols)
    #         doc = metadata_to_text({
    #             "table_name":table_name,
    #             "columns":cols
    #             })
    #         doc_list.append(doc)
     
    schema_retriever = SchemaRetrival()

    # vector_db = schema_retriever.build_vector_store(
    # doc_list
    # )
    # results = vector_db.similarity_search(
    #     "show unpaid invoices",
    #     k=3
    #     )
    # print(results)
    # print('final_one by one')
    # for doc in results:
    #     print(doc.metadata)
    #     print(doc.page_content)






    vector_db = schema_retriever.load_vector_store()
    # results = schema_retriever.invoke(vector_db,
    #     "show unpaid invoices",
    #     3
    #     )
    # print(results)
    # print('final_one by one')
    # for doc in results:
    #     print(doc.metadata)
    #     print(doc.page_content)