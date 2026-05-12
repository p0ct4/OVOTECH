from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("DATABASE_URL")

if not url:
    print("❌ ERROR: No encontré DATABASE_URL")
    print("💡 Asegúrate de tener un archivo .env en esta carpeta con:")
    print('   DATABASE_URL=postgresql://...')
    exit()

# Ocultar password al imprimir
safe = url.split('@')[1] if '@' in url else "oculto"
print(f"🔌 Intentando conectar a Neon: postgresql://***@{safe}")

try:
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        version = result.fetchone()[0]
        print("✅ ¡CONEXIÓN EXITOSA!")
        print(f"🗄️  Servidor: {version[:60]}")
        
        # Probar crear tabla
        conn.execute(text("CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY)"))
        conn.execute(text("DROP TABLE test_table"))
        print("✅ Puedes crear tablas. Todo listo.")
        
except Exception as e:
    print(f"❌ Error: {e}")