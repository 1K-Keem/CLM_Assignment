try:
    from app.database import DATABASE_PATH, initialize_database
except ModuleNotFoundError:
    from database import DATABASE_PATH, initialize_database


if __name__ == "__main__":
    initialize_database()
    print(f"Database ready: {DATABASE_PATH}")
