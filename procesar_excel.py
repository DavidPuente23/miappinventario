"""Sincroniza equipos desde un Excel hacia la base de la app.

Uso:   python procesar_excel.py ruta/al/archivo.xlsm
(Requiere pandas y openpyxl. Solo se usa de forma local o en la consola del hosting.)
"""
import sys

from db import conectar_bd, init_db


def sincronizar_desde_excel(ruta_excel):
    import pandas as pd  # se importa aquí para que la web no lo necesite

    init_db()
    conn = conectar_bd()
    try:
        print(f"Intentando abrir el archivo Excel: {ruta_excel}")
        # Cambia 'Hoja1' por el nombre real de tu pestaña en Excel
        df = pd.read_excel(ruta_excel, sheet_name='Hoja1')

        for _, row in df.iterrows():
            nombre = str(row['nombre']).strip()
            categoria = str(row['categoria']).strip()
            proveedor = str(row['proveedor']).strip()

            existe = conn.execute(
                "SELECT equipo_id FROM equipos WHERE denominacion = ?", (nombre,)).fetchone()

            if existe:
                print(f"Actualizando: {nombre}")
                conn.execute(
                    "UPDATE equipos SET clasificacion = ?, suministrador = ? WHERE denominacion = ?",
                    (categoria, proveedor, nombre))
            else:
                print(f"Insertando nuevo: {nombre}")
                conn.execute(
                    "INSERT INTO equipos (denominacion, clasificacion, suministrador, existencia, "
                    "condicion_actual) VALUES (?, ?, ?, 1, 'Operativo')",
                    (nombre, categoria, proveedor))

        conn.commit()
        print("\n--- ¡Sincronización completada con éxito desde Excel! ---")
    except Exception as e:
        print(f"\n[ERROR] Ocurrió un fallo al procesar el Excel: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python procesar_excel.py ruta/al/archivo.xlsm")
        sys.exit(1)
    sincronizar_desde_excel(sys.argv[1])
