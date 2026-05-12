from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("DATABASE_URL")
print(f"Conectando a: {url[:50]}...")

try:
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        print("✅ ¡Conexión a la NUBE exitosa!")
        print(f"Servidor: {result.fetchone()[0][:50]}...")
except Exception as e:
    print(f"❌ Error: {e}")