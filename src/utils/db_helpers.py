"""Database batch operations helpers for improved performance."""

import re
from typing import Any, Awaitable, Callable, Dict, List, TypeVar

import asyncpg
from loguru import logger

T = TypeVar("T")

# PostgreSQL reserved words - prevent SQL injection via identifier names
# List from: https://www.postgresql.org/docs/current/sql-keywords-appendix.html
POSTGRESQL_RESERVED_WORDS = frozenset(
    [
        "ALL",
        "ANALYSE",
        "ANALYZE",
        "AND",
        "ANY",
        "ARRAY",
        "AS",
        "ASC",
        "ASYMMETRIC",
        "AUTHORIZATION",
        "BETWEEN",
        "BINARY",
        "BOTH",
        "CASE",
        "CAST",
        "CHECK",
        "COLLATE",
        "COLLATION",
        "COLUMN",
        "CONCURRENTLY",
        "CONSTRAINT",
        "CREATE",
        "CROSS",
        "CURRENT_CATALOG",
        "CURRENT_DATE",
        "CURRENT_ROLE",
        "CURRENT_SCHEMA",
        "CURRENT_TIME",
        "CURRENT_TIMESTAMP",
        "CURRENT_USER",
        "DEFAULT",
        "DEFERRABLE",
        "DESC",
        "DISTINCT",
        "DO",
        "ELSE",
        "END",
        "EXCEPT",
        "FALSE",
        "FETCH",
        "FOR",
        "FOREIGN",
        "FREEZE",
        "FROM",
        "FULL",
        "GRANT",
        "GROUP",
        "HAVING",
        "ILIKE",
        "IN",
        "INITIALLY",
        "INNER",
        "INTERSECT",
        "INTO",
        "IS",
        "ISNULL",
        "JOIN",
        "LATERAL",
        "LEADING",
        "LEFT",
        "LIKE",
        "LIMIT",
        "LOCALTIME",
        "LOCALTIMESTAMP",
        "NATURAL",
        "NOT",
        "NOTNULL",
        "NULL",
        "OFFSET",
        "ON",
        "ONLY",
        "OR",
        "ORDER",
        "OUTER",
        "OVERLAPS",
        "PLACING",
        "PRIMARY",
        "REFERENCES",
        "RETURNING",
        "RIGHT",
        "SELECT",
        "SESSION_USER",
        "SIMILAR",
        "SOME",
        "SYMMETRIC",
        "TABLE",
        "TABLESAMPLE",
        "THEN",
        "TO",
        "TRAILING",
        "TRUE",
        "UNION",
        "UNIQUE",
        "USER",
        "USING",
        "VARIADIC",
        "VERBOSE",
        "WHEN",
        "WHERE",
        "WINDOW",
        "WITH",
    ]
)


def _parse_command_tag(command_tag: str) -> int:
    """
    Parse PostgreSQL command tag to extract affected row count.

    PostgreSQL command tags follow the format 'COMMAND N' where N is the count.
    Examples: 'UPDATE 5', 'DELETE 3', 'INSERT 0 1'

    Args:
        command_tag: PostgreSQL command tag string

    Returns:
        Number of affected rows, or 0 if parsing fails
    """
    try:
        parts = command_tag.split()
        if len(parts) >= 2:
            return int(parts[-1])
        return 0
    except (ValueError, IndexError):
        logger.warning(f"Failed to parse command tag: {command_tag}")
        return 0


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
    # Max length 63 characters (PostgreSQL NAMEDATALEN - 1)
    pattern = r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$"
    if not re.match(pattern, identifier):
        return False

    # Check if it's a reserved word
    if identifier.upper() in POSTGRESQL_RESERVED_WORDS:
        return False

    return True


async def batch_insert(
    conn: asyncpg.Connection,
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

    placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
    column_list = ", ".join(columns)
    query = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"

    total_inserted = 0

    # Process in batches
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]

        try:
            async with conn.transaction():
                await conn.executemany(query, batch)
            total_inserted += len(batch)

            logger.debug(f"Inserted batch of {len(batch)} rows into {table}")
        except Exception as e:
            logger.error(f"Failed to insert batch into {table}: {e}")
            raise

    logger.info(f"Batch inserted {total_inserted} rows into {table}")
    return total_inserted


async def batch_update(
    conn: asyncpg.Connection,
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
            # Group updates by their column sets for executemany optimization
            from collections import defaultdict
            groups: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)

            for update_data in batch:
                if id_column not in update_data:
                    logger.warning(f"Skipping update without {id_column}: {update_data}")
                    continue
                update_dict = update_data.copy()
                update_dict.pop(id_column)
                if not update_dict:
                    continue
                # Validate columns
                valid_cols = tuple(
                    col for col in sorted(update_dict.keys())
                    if validate_sql_identifier(col)
                )
                if valid_cols:
                    groups[valid_cols].append(update_data)

            async with conn.transaction():
                for cols, group_updates in groups.items():
                    # Build parameterized query for this column group
                    param_num = 1
                    set_parts = []
                    for col in cols:
                        set_parts.append(f"{col} = ${param_num}")
                        param_num += 1
                    set_clause = ", ".join(set_parts)
                    query = f"UPDATE {table} SET {set_clause} WHERE {id_column} = ${param_num}"

                    # Build args list for executemany
                    args_list = []
                    for update_data in group_updates:
                        update_dict = update_data.copy()
                        row_id = update_dict.pop(id_column)
                        values = tuple(update_dict[col] for col in cols) + (row_id,)
                        args_list.append(values)

                    # Use executemany for true batch execution
                    await conn.executemany(query, args_list)
                    total_updated += len(args_list)

            logger.debug(f"Updated batch of {len(batch)} rows in {table}")

        except Exception as e:
            logger.error(f"Failed to update batch in {table}: {e}")
            raise

    logger.info(f"Batch updated {total_updated} rows in {table}")
    return total_updated


async def batch_delete(
    conn: asyncpg.Connection,
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
            query = f"DELETE FROM {table} WHERE {id_column} = ANY($1::bigint[])"

            async with conn.transaction():
                result = await conn.execute(query, batch)

            batch_deleted = _parse_command_tag(result)
            total_deleted += batch_deleted

            logger.debug(f"Deleted batch of {batch_deleted} rows from {table}")

        except Exception as e:
            logger.error(f"Failed to delete batch from {table}: {e}")
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
    conn: asyncpg.Connection,
    operations: List[Callable[[asyncpg.Connection], Awaitable[Any]]],
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
        async with conn.transaction():
            # Execute all operations
            for operation in operations:
                result = await operation(conn)
                results.append(result)

        logger.info(f"Transaction completed successfully with {len(operations)} operations")

        return results

    except Exception as e:
        logger.error(f"Transaction failed, rolled back: {e}")
        raise
