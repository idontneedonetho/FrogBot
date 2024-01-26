# database.py
import sqlite3
import asyncio
import time

DATABASE_FILE = 'user_points.db'

async def initialize_database():
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_points (
                user_id INTEGER PRIMARY KEY,
                points INTEGER NOT NULL DEFAULT 0
            )
        ''')
        conn.commit()
        cursor.close()
    await initialize_database()

def db_access_with_retry(sql_operation, *args, max_attempts=5, delay=1, timeout=10.0):
    for attempt in range(max_attempts):
        try:
            with sqlite3.connect(DATABASE_FILE, timeout=timeout) as conn:
                cursor = conn.cursor()
                cursor.execute(sql_operation, *args)
                if sql_operation.strip().upper().startswith('SELECT'):
                    results = cursor.fetchall()
                    cursor.close()
                    return results
                conn.commit()
                cursor.close()
                return
        except sqlite3.OperationalError as e:
            print(f"Failed to execute sql operation: {e}")
            if attempt == max_attempts - 1:
                raise
            time.sleep(delay)

def initialize_points_database(user):
    rows = db_access_with_retry('SELECT points FROM user_points WHERE user_id = ?', (user.id,))
    if rows:
        return {user.id: rows[0][0]}
    else:
        db_access_with_retry('INSERT INTO user_points (user_id, points) VALUES (?, ?)', (user.id, 0))
        return {user.id: 0}

async def update_points(user_id, points):
    try:
        db_access_with_retry('UPDATE user_points SET points = ? WHERE user_id = ?', (points, user_id))
        return True
    except Exception as e:
        print(f"Failed to update points: {e}")
        return False

def get_user_points(user_id, user_points):
    return user_points.get(user_id, 0)