# Control de Activos / Inventario

App web en Flask + SQLite para controlar equipos, movimientos de stock, revisiones técnicas, vales y códigos QR.

La base de datos es un archivo (`instance/inventario.db`) que se crea solo la primera vez que arranca la app. No hay que instalar MySQL ni configurar nada.

---

## Publicarla en internet (gratis) con PythonAnywhere

### 1. Subir el código a GitHub
1. Entra a https://github.com → **New repository** → ponle un nombre (ej. `mi-app-inventario`) → **Create repository**.
2. En la página del repo haz clic en **uploading an existing file**.
3. Arrastra **el contenido de esta carpeta** (no el .zip): `app.py`, `db.py`, `requirements.txt`, `procesar_excel.py`, `.gitignore`, y las carpetas `templates` y `extras`.
4. Clic en **Commit changes**.

### 2. Crear la cuenta en PythonAnywhere
1. Entra a https://www.pythonanywhere.com → **Pricing & signup** → **Create a Beginner account** (gratis).
2. Tu **usuario** define tu link final: `https://TU_USUARIO.pythonanywhere.com`

### 3. Instalar la app
En PythonAnywhere ve a **Consoles → Bash** y ejecuta (cambia TU_USUARIO_GITHUB y el nombre del repo):

```bash
git clone https://github.com/TU_USUARIO_GITHUB/mi-app-inventario.git
cd mi-app-inventario
pip3.10 install --user -r requirements.txt
```

### 4. Crear la página web
1. Pestaña **Web** → **Add a new web app** → **Next** → **Manual configuration** → **Python 3.10** → **Next**.
2. En la sección **Code**, en *Source code*, escribe: `/home/TU_USUARIO/mi-app-inventario`
3. Clic en el enlace **WSGI configuration file**, borra todo lo que tiene y pega esto (cambia TU_USUARIO):

```python
import sys

ruta = '/home/TU_USUARIO/mi-app-inventario'
if ruta not in sys.path:
    sys.path.insert(0, ruta)

from app import app as application
```
4. Guarda (**Save**), vuelve a la pestaña **Web**.
5. Activa **Force HTTPS**.
6. Clic en el botón verde **Reload**.

### 5. Listo
Abre `https://TU_USUARIO.pythonanywhere.com`, entra a **Regístrate aquí**, crea tu cuenta y ya puedes usar todo.

---

## Mantenimiento

**Actualizar la app** después de cambiar código en GitHub: en la consola Bash

```bash
cd ~/mi-app-inventario && git pull
```
y luego **Reload** en la pestaña Web.

**Renovar el plan gratis:** las cuentas gratis piden extender el web app cada cierto tiempo. En la pestaña **Web** hay un botón para extender; si no lo presionas, la página se desactiva (tus datos no se borran).

**Cerrar el registro de cuentas:** por defecto cualquiera con el link puede crear una cuenta. Cuando ya tengas las cuentas que necesitas, puedes cerrarlo: en el archivo WSGI agrega, arriba de `from app import ...`:

```python
import os
os.environ['REGISTRO_ABIERTO'] = '0'
```

**Respaldo de datos:** todo vive en `instance/inventario.db`. Descárgalo desde la pestaña **Files** de PythonAnywhere de vez en cuando.

---

## Probarla en tu computadora
```bash
pip install -r requirements.txt
python app.py
```
Abre http://localhost:5000

## Notas
- `extras/INTERFAz.xlsm` y `extras/base_mysql_original.sql` son los archivos originales (la web ya no usa MySQL).
- `procesar_excel.py` sincroniza equipos desde un Excel: `python procesar_excel.py archivo.xlsm` (necesita `pandas` y `openpyxl`).
- Las contraseñas se guardan encriptadas (hash). Las cuentas de la versión anterior (MySQL) no se migran: hay que crearlas de nuevo.
