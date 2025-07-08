import polars as pl
from typing import Set
from .base import DatabaseAdapter
import sqlite3
import logging

logger = logging.getLogger(__name__)

class SQLiteAdapter(DatabaseAdapter):
    """SQLite adapter placeholder implementation.

    Note: SQLite is primarily intended for development and testing,
    not for production CNPJ data loading due to performance limitations.
    """

    def __init__(self, config):
        super().__init__(config)
        self.db_file = getattr(config, 'sqlite_db_file', getattr(config, 'sqlite_db_file', ':memory:'))
        self.conn = None
        self._ensure_tracking_table()

    def connect(self):
        """Establish SQLite connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_file)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to SQLite database at {self.db_file}")

    def disconnect(self):
        """Close SQLite connection."""
        if self.conn:
            self.conn.close()
            logger.info("SQLite connection closed")
            self.conn = None

    def _ensure_tracking_table(self):
        """Ensure the processed_files tracking table exists."""
        self.connect()
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_files (
                directory TEXT NOT NULL,
                filename TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (directory, filename)
            )
            """
        )
        self.conn.commit()
        cur.close()
    
    def ensure_tracking_table(self):
        """Public method to ensure tracking table exists."""
        self._ensure_tracking_table()

    def bulk_upsert(self, df: pl.DataFrame, table: str, **kwargs):
        """Bulk upsert data into SQLite table."""
        if df.height == 0:
            logger.warning(f"Empty DataFrame for table '{table}', skipping bulk_upsert")
            return

        self.connect()
        columns = df.columns
        columns_str = ", ".join(f'"{col}"' for col in columns)
        placeholders = ", ".join(['?' for _ in columns])
        sql = f"INSERT OR REPLACE INTO {table} ({columns_str}) VALUES ({placeholders})"

        values = [tuple(row) for row in df.iter_rows()]

        cur = self.conn.cursor()
        cur.executemany(sql, values)
        self.conn.commit()
        cur.close()
        logger.info(f"Upserted {len(values)} rows into '{table}'")

    def get_processed_files(self, directory: str) -> Set[str]:
        """Get set of processed files for a directory."""
        self.connect()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT filename FROM processed_files WHERE directory = ?",
            (directory,)
        )
        rows = cur.fetchall()
        cur.close()
        return {row[0] for row in rows}

    def mark_processed(self, directory: str, filename: str):
        """Mark file as processed."""
        self.connect()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO processed_files (directory, filename) VALUES (?, ?)",
            (directory, filename)
        )
        self.conn.commit()
        cur.close()

    def is_processed(self, directory: str, filename: str) -> bool:
        """Check if a file has already been processed."""
        self.connect()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT 1 FROM processed_files WHERE directory = ? AND filename = ? LIMIT 1",
            (directory, filename)
        )
        exists = cur.fetchone() is not None
        cur.close()
        return exists
