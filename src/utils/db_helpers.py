"""Database batch operations helpers for improved performance."""

import logging
import re
from typing import List, Dict, Any, TypeVar, Callable, Awaitable, Optional
from contextlib import asynccontextmanager

import aiosqlite

logger = logging.getLogger(__name__)

T = TypeVar("T")

# SQLite reserved words - prevent SQL injection via identifier names
SQLITE_RESERVED_WORDS = frozenset([
    "ABORT", "ACTION", "ADD", "ALTER", "AND", "AS", "ASC",
    "BEGIN", "BETWEEN", "BY",
    "CASCADE", "CASE", "CHECK", "COLLATE", "COLUMN", "COMMIT", "CONSTRAINT", "CREATE", "CROSS", "CURRENT",
    "DATABASE", "DEFAULT", "DELETE", "DESC", "DISTINCT", "DROP",
    "EACH", "ELSE", "END", "ESCAPE", "EXCEPT", "EXISTS", "EXPLAIN",
    "FAIL", "FILTER", "FOR", "FOREIGN", "FROM", "FULL",
    "GLOB", "GROUP",
    "HAVING",
    "IF", "IGNORE", "IMMEDIATE", "IN", "INDEX", "INNER", "INSERT", "INSTEAD", "INTERSECT", "INTO", "IS", "ISNULL",
    "JOIN",
    "KEY",
    "LEFT", "LIKE", "LIMIT",
    "MATCH",
    "NATURAL", "NO", "NOT", "NOTNULL", "NULL",
    "OF", "OFFSET", "ON", "OR", "ORDER", "OUTER",
    "PLAN", "PRAGMA", "PRIMARY",
    "QUERY",
    "RAISE", "RECURSIVE", "REFERENCES", "REGEXP", "REINDEX", "RELEASE", "RENAME", "REPLACE", "RESTRICT", "RIGHT", "ROLLBACK", "ROW",
    "SAVEPOINT", "SELECT", "SET",
    "TABLE", "TEMP", "TEMPORARY", "THEN", "TO", "TRANSACTION", "TRIGGER",
    "UNION", "UNIQUE", "UPDATE", "USING",
    "VACUUM", "VALUES", "VIEW", "VIRTUAL",
    "WHEN", "WHERE", "WITH", "WITHOUT",
])


def validate_sql_identifier(identifier: str) -> bool:
    """
    Validate SQL identifier (table or column name) to prevent SQL injection.
    
    Args:
        identifier: Table or column name to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Only allow alphanumeric characters and underscores
    # Must start with a letter or underscore
    # Max length 64 characters (MySQL/SQLite limit)
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_]{0,63}$'
    if not re.match(pattern, identifier):
        return False
    
    # Check if it's a reserved word
    if identifier.upper() in SQLITE_RESERVED_WORDS:
        return False
    
    return True


async def batch_insert(
    conn: aiosqlite.Connection,
    table: str,
    columns: List[str],
    rows: List[tuple],
    batch_size: int = 100,
) -> int:
    """
    Insert multiple rows in batches for better performance.
    
    Args:
        conn: Database connection
        table: Table name (will be validated)
        columns: Column names (will be validated)
        rows: List of tuples with values to insert
        batch_size: Number of rows to insert per batch
        
    Returns:
        Total number of rows inserted
        
    Raises:
        ValueError: If table or column names are invalid
        
    Example:
        ```python
        async with db.get_connection() as conn:
            inserted = await batch_insert(
                conn,
                "users",
                ["email", "name", "created_at"],
                [
                    ("user1@example.com", "User 1", "2024-01-01"),
                    ("user2@example.com", "User 2", "2024-01-02"),
                ]
            )
        ```
    """
    if not rows:
        return 0
    
    # Validate table name
    if not validate_sql_identifier(table):
        raise ValueError(f"Invalid table name: {table}")
    
    # Validate column names
    for col in columns:
        if not validate_sql_identifier(col):
            raise ValueError(f"Invalid column name: {col}")
    
    placeholders = ", ".join(["?"] * len(columns))
    column_list = ", ".join(columns)
    query = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"
    
    total_inserted = 0
    
    # Process in batches
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        
        try:
            await conn.executemany(query, batch)
            await conn.commit()
            total_inserted += len(batch)
            
            logger.debug(f"Inserted batch of {len(batch)} rows into {table}")
        except Exception as e:
            logger.error(f"Failed to insert batch into {table}: {e}")
            await conn.rollback()
            raise
    
    logger.info(f"Batch inserted {total_inserted} rows into {table}")
    return total_inserted


async def batch_update(
    conn: aiosqlite.Connection,
    table: str,
    updates: List[Dict[str, Any]],
    id_column: str = "id",
    batch_size: int = 100,
) -> int:
    """
    Update multiple rows in batches.
    
    Args:
        conn: Database connection
        table: Table name (will be validated)
        updates: List of dicts with 'id' and fields to update
        id_column: Name of the ID column (default: "id", will be validated)
        batch_size: Number of rows to update per batch
        
    Returns:
        Total number of rows updated
        
    Raises:
        ValueError: If table or column names are invalid
        
    Example:
        ```python
        async with db.get_connection() as conn:
            updated = await batch_update(
                conn,
                "users",
                [
                    {"id": 1, "is_active": True},
                    {"id": 2, "is_active": False},
                ]
            )
        ```
    """
    if not updates:
        return 0
    
    # Validate table and id_column names
    if not validate_sql_identifier(table):
        raise ValueError(f"Invalid table name: {table}")
    if not validate_sql_identifier(id_column):
        raise ValueError(f"Invalid column name: {id_column}")
    
    total_updated = 0
    
    # Process in batches
    for i in range(0, len(updates), batch_size):
        batch = updates[i : i + batch_size]
        
        try:
            for update_data in batch:
                if id_column not in update_data:
                    logger.warning(f"Skipping update without {id_column}: {update_data}")
                    continue
                
                # Make a copy to avoid modifying the original
                update_dict = update_data.copy()
                row_id = update_dict.pop(id_column)
                
                if not update_dict:
                    continue
                
                # Validate column names
                for col in update_dict.keys():
                    if not validate_sql_identifier(col):
                        logger.warning(f"Skipping invalid column name: {col}")
                        continue
                
                # Build SET clause
                set_clause = ", ".join([f"{k} = ?" for k in update_dict.keys()])
                values = list(update_dict.values()) + [row_id]
                
                query = f"UPDATE {table} SET {set_clause} WHERE {id_column} = ?"
                
                cursor = await conn.execute(query, values)
                total_updated += cursor.rowcount
            
            await conn.commit()
            logger.debug(f"Updated batch of {len(batch)} rows in {table}")
            
        except Exception as e:
            logger.error(f"Failed to update batch in {table}: {e}")
            await conn.rollback()
            raise
    
    logger.info(f"Batch updated {total_updated} rows in {table}")
    return total_updated


async def batch_delete(
    conn: aiosqlite.Connection,
    table: str,
    ids: List[int],
    id_column: str = "id",
    batch_size: int = 500,
) -> int:
    """
    Delete multiple rows in batches.
    
    Args:
        conn: Database connection
        table: Table name (will be validated)
        ids: List of IDs to delete
        id_column: Name of the ID column (default: "id", will be validated)
        batch_size: Number of rows to delete per batch
        
    Returns:
        Total number of rows deleted
        
    Raises:
        ValueError: If table or column names are invalid
        
    Example:
        ```python
        async with db.get_connection() as conn:
            deleted = await batch_delete(conn, "users", [1, 2, 3, 4, 5])
        ```
    """
    if not ids:
        return 0
    
    # Validate table and id_column names
    if not validate_sql_identifier(table):
        raise ValueError(f"Invalid table name: {table}")
    if not validate_sql_identifier(id_column):
        raise ValueError(f"Invalid column name: {id_column}")
    
    total_deleted = 0
    
    # Process in batches
    for i in range(0, len(ids), batch_size):
        batch = ids[i : i + batch_size]
        
        try:
            placeholders = ", ".join(["?"] * len(batch))
            query = f"DELETE FROM {table} WHERE {id_column} IN ({placeholders})"
            
            cursor = await conn.execute(query, batch)
            await conn.commit()
            
            batch_deleted = cursor.rowcount
            total_deleted += batch_deleted
            
            logger.debug(f"Deleted batch of {batch_deleted} rows from {table}")
            
        except Exception as e:
            logger.error(f"Failed to delete batch from {table}: {e}")
            await conn.rollback()
            raise
    
    logger.info(f"Batch deleted {total_deleted} rows from {table}")
    return total_deleted


async def batch_process(
    items: List[T],
    processor: Callable[[T], Awaitable[Any]],
    batch_size: int = 10,
    continue_on_error: bool = False,
) -> List[Any]:
    """
    Process items in batches with async processor function.
    
    Args:
        items: List of items to process
        processor: Async function to process each item
        batch_size: Number of items to process concurrently
        continue_on_error: If True, continue processing on errors
        
    Returns:
        List of processing results
        
    Example:
        ```python
        async def process_user(user):
            # Do something with user
            return user.id
            
        results = await batch_process(users, process_user, batch_size=5)
        ```
    """
    import asyncio
    
    results = []
    errors = []
    
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        
        tasks = [processor(item) for item in batch]
        
        if continue_on_error:
            # Gather with return_exceptions to continue on errors
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    errors.append(result)
                    logger.error(f"Error processing item: {result}")
                else:
                    results.append(result)
        else:
            # Fail fast on any error
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
        
        logger.debug(f"Processed batch of {len(batch)} items")
    
    if errors:
        logger.warning(f"Encountered {len(errors)} errors during batch processing")
    
    logger.info(f"Batch processed {len(results)} items successfully")
    return results


async def execute_in_transaction(
    conn: aiosqlite.Connection,
    operations: List[Callable[[aiosqlite.Connection], Awaitable[Any]]],
) -> List[Any]:
    """
    Execute multiple database operations in a transaction.
    
    Args:
        conn: Database connection
        operations: List of async functions that take connection as argument
        
    Returns:
        List of operation results
        
    Raises:
        Exception: If any operation fails (transaction is rolled back)
        
    Example:
        ```python
        async def create_user(conn):
            await conn.execute("INSERT INTO users ...")
            
        async def create_profile(conn):
            await conn.execute("INSERT INTO profiles ...")
            
        async with db.get_connection() as conn:
            results = await execute_in_transaction(
                conn,
                [create_user, create_profile]
            )
        ```
    """
    results = []
    
    try:
        # Execute all operations
        for operation in operations:
            result = await operation(conn)
            results.append(result)
        
        # Commit transaction
        await conn.commit()
        logger.info(f"Transaction completed successfully with {len(operations)} operations")
        
        return results
        
    except Exception as e:
        # Rollback on any error
        await conn.rollback()
        logger.error(f"Transaction failed, rolled back: {e}")
        raise
