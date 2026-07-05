import psycopg2

def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="distributed_storage",
        user="postgres",
        password="5432"
    )