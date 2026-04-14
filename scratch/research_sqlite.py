from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

try:
    # Try calling from_conn_string
    conn = SqliteSaver.from_conn_string("data/test.db")
    print(f"from_conn_string result type: {type(conn)}")
    
    # Try using as context manager
    with SqliteSaver.from_conn_string("data/test.db") as saver:
        print(f"Inside context manager, type: {type(saver)}")
except Exception as e:
    print(f"Error: {e}")
