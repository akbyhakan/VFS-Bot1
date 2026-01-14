"""
Database module with connection pooling support.
"""

import sqlite3
from queue import Queue
from threading import Lock
from contextlib import contextmanager


class Database:
    """Database class with connection pooling for efficient database operations."""
    
    def __init__(self, db_path: str, pool_size: int = 5):
        """
        Initialize the database with connection pooling.
        
        Args:
            db_path: Path to the SQLite database file.
            pool_size: Number of connections to maintain in the pool.
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool = Queue(maxsize=pool_size)
        self._lock = Lock()
        self._initialized = False
        
        # Pre-populate the connection pool
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize the connection pool with database connections."""
        with self._lock:
            if not self._initialized:
                for _ in range(self.pool_size):
                    conn = self._create_connection()
                    self._pool.put(conn)
                self._initialized = True
    
    def _create_connection(self) -> sqlite3.Connection:
        """
        Create a new database connection.
        
        Returns:
            A new SQLite connection object.
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get a connection from the pool.
        
        Returns:
            A database connection from the pool.
        """
        return self._pool.get()
    
    def release_connection(self, conn: sqlite3.Connection):
        """
        Release a connection back to the pool.
        
        Args:
            conn: The connection to release.
        """
        self._pool.put(conn)
    
    @contextmanager
    def connection(self):
        """
        Context manager for database connections.
        
        Yields:
            A database connection that will be automatically released.
        """
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.release_connection(conn)
    
    def execute(self, query: str, params: tuple = None):
        """
        Execute a query and return the results.
        
        Args:
            query: SQL query to execute.
            params: Optional parameters for the query.
            
        Returns:
            List of rows returned by the query.
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.fetchall()
    
    def execute_many(self, query: str, params_list: list):
        """
        Execute a query with multiple parameter sets.
        
        Args:
            query: SQL query to execute.
            params_list: List of parameter tuples.
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
    
    def close_all(self):
        """Close all connections in the pool."""
        while not self._pool.empty():
            conn = self._pool.get_nowait()
            conn.close()
        self._initialized = False
