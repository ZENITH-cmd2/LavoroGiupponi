
import sqlite3
from pathlib import Path
import pandas as pd

# Fix for SQLite and pandas Timestamp
sqlite3.register_adapter(pd.Timestamp, lambda ts: ts.isoformat() if pd.notna(ts) else None)

class Database:
    DB_NAME = "calor_systems.db"
    SCHEMA_FILE = "calor_systems_schema.sql"

    def __init__(self, root_path):
        self.root_path = Path(root_path)
        self.db_path = self.root_path / "db" / self.DB_NAME
        self.schema_path = self.root_path / "db" / self.SCHEMA_FILE

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def initialize(self):
        if not self.schema_path.exists():
            print(f"Schema file not found at {self.schema_path}")
            return False
            
        conn = self.get_connection()
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema = f.read()
            conn.executescript(schema)
            conn.commit()
            print("Database initialized successfully.")
            return True
        except Exception as e:
            print(f"Error initializing database: {e}")
            return False
        finally:
            conn.close()
