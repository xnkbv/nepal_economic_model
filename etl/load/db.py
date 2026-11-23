import os
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text

# Read the settings from the .env file into environment variables
load_dotenv()


def get_engine():
    """Create a connection to the PostgreSQL database using the settings in .env."""
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
        host=os.environ["PG_HOST"],
        port=int(os.environ["PG_PORT"]),
        database=os.environ["PG_DATABASE"],
    )
    return create_engine(url)


# Runs only when you execute this file directly, as a connection test
if __name__ == "__main__":
    engine = get_engine()
    with engine.connect() as conn:
        print("Connected to database:", conn.execute(text("SELECT current_database()")).scalar())
        print(conn.execute(text("SELECT version()")).scalar())