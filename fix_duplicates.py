import sqlite3

# Connect to your SQLite database file (app.db)
conn = sqlite3.connect("app.db")
cursor = conn.cursor()

# Find all duplicate emails
cursor.execute("""
    SELECT email, COUNT(*) as count
    FROM user
    GROUP BY email
    HAVING count > 1
""")
duplicates = cursor.fetchall()

if not duplicates:
    print("✅ No duplicate emails found.")
else:
    print(f"⚠️ Found {len(duplicates)} duplicate email(s). Removing duplicates...")

    for email, count in duplicates:
        # Keep the user with the smallest id (assumed original) and delete others
        cursor.execute("""
            DELETE FROM user
            WHERE email = ?
            AND id NOT IN (
                SELECT MIN(id) FROM user WHERE email = ?
            )
        """, (email, email))

    conn.commit()
    print("✅ Duplicates removed successfully.")

conn.close()
