import base64
import csv
import io
import os
import secrets
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from functools import wraps
import sqlite3

import qrcode
from flask import (Flask, Response, abort, flash, redirect, render_template,
                   request, session)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from db import INSTANCE_DIR, conectar_bd, init_db

app = Flask(__name__)
# Para que Flask sepa que está detrás de https en el hosting
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


# ---------------------------------------------------------------- Configuración
def cargar_secret_key():
    """Usa SECRET_KEY si existe; si no, crea una al azar y la guarda en instance/."""
    desde_entorno = os.environ.get('SECRET_KEY')
    if desde_entorno:
        return desde_entorno
    ruta = os.path.join(INSTANCE_DIR, 'secret.key')
    try:
        if os.path.exists(ruta):
            with open(ruta) as f:
                return f.read().strip()
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        clave = secrets.token_hex(32)
        with open(ruta, 'w') as f:
            f.write(clave)
        return clave
    except OSError:
        return secrets.token_hex(32)


app.secret_key = cargar_secret_key()

# Poner REGISTRO_ABIERTO=0 para que nadie más pueda crear cuentas desde internet
REGISTRO_ABIERTO = os.environ.get('REGISTRO_ABIERTO', '1') != '0'

try:
    from zoneinfo import ZoneInfo
    ZONA = ZoneInfo(os.environ.get('ZONA_HORARIA', 'America/Monterrey'))
except Exception:
    ZONA = timezone(timedelta(hours=-6))

MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
         'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


def ahora():
    return datetime.now(ZONA)


# Crea las tablas la primera vez que arranca
init_db()


def login_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        if 'logueado' not in session:
            flash('Por favor, inicia sesión para acceder al sistema.', 'warning')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorador


# ---------------------------------------------------------------- Usuarios
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            with closing(conectar_bd()) as conn:
                usuario = conn.execute(
                    "SELECT * FROM usuarios WHERE username = ?", (username,)
                ).fetchone()
            if usuario and check_password_hash(usuario['password'], password):
                session['logueado'] = True
                session['nombre'] = usuario['nombre_completo']
                return redirect('/')
            flash('Usuario o contraseña incorrectos.', 'danger')
        except Exception as e:
            flash(f'Error de conexión a la base de datos: {e}', 'danger')
    return render_template('login.html')


@app.route('/registro_usuario', methods=['GET', 'POST'])
def registro_usuario():
    if not REGISTRO_ABIERTO:
        flash('El registro de cuentas nuevas está cerrado.', 'warning')
        return redirect('/login')
    if request.method == 'POST':
        nombre = request.form['nombre_completo']
        username = request.form['username']
        password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        try:
            with closing(conectar_bd()) as conn:
                conn.execute(
                    "INSERT INTO usuarios (nombre_completo, username, password, rol) "
                    "VALUES (?, ?, ?, 'Administrador')", (nombre, username, password))
                conn.commit()
            flash('¡Cuenta creada con éxito! Ahora puedes iniciar sesión.', 'success')
            return redirect('/login')
        except sqlite3.IntegrityError:
            flash('Ese nombre de usuario ya existe. Por favor elige otro.', 'danger')
        except Exception as e:
            flash(f'Error en el sistema: {e}', 'danger')
    return render_template('registro_usuario.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ---------------------------------------------------------------- Panel de control
@app.route('/')
@login_requerido
def panel_control():
    with closing(conectar_bd()) as conn:
        total_activos = conn.execute(
            "SELECT SUM(existencia) AS total FROM equipos").fetchone()['total'] or 0

        en_taller = conn.execute(
            "SELECT COUNT(*) AS taller FROM equipos WHERE condicion_actual = 'En taller'"
        ).fetchone()['taller']

        datos_clasificacion = conn.execute(
            "SELECT clasificacion, COUNT(*) AS cantidad FROM equipos GROUP BY clasificacion"
        ).fetchall()

        filas_mov = conn.execute("""
            SELECT strftime('%Y-%m', fecha_transaccion) AS ym, COUNT(*) AS total
            FROM transacciones_stock
            GROUP BY ym
            ORDER BY ym DESC
            LIMIT 6
        """).fetchall()
        datos_movimientos = [
            {'mes': MESES[int(f['ym'][5:7]) - 1], 'total': f['total']}
            for f in filas_mov if f['ym']
        ]

        filas_alertas = conn.execute("""
            SELECT denominacion, ultima_revision, fecha_siguiente_revision FROM (
                SELECT e.denominacion,
                       (SELECT fecha_servicio FROM revisiones_tecnicas r
                         WHERE r.equipo_id = e.equipo_id
                         ORDER BY r.revision_id DESC LIMIT 1) AS ultima_revision,
                       (SELECT fecha_siguiente_revision FROM revisiones_tecnicas r
                         WHERE r.equipo_id = e.equipo_id
                         ORDER BY r.revision_id DESC LIMIT 1) AS fecha_siguiente_revision
                FROM equipos e
            )
            WHERE fecha_siguiente_revision IS NOT NULL AND fecha_siguiente_revision <> ''
        """).fetchall()

    hoy = ahora().date()
    notificaciones = []
    for f in filas_alertas:
        try:
            f['dias_faltantes'] = (date.fromisoformat(f['fecha_siguiente_revision']) - hoy).days
        except ValueError:
            continue
        notificaciones.append(f)
    notificaciones.sort(key=lambda x: x['dias_faltantes'])

    return render_template('index.html',
                           total=total_activos,
                           reparacion=en_taller,
                           alertas=notificaciones,
                           datos_clas=datos_clasificacion,
                           datos_mov=datos_movimientos)


# ---------------------------------------------------------------- Catálogo
@app.route('/catalogo')
@login_requerido
def catalogo_equipos():
    with closing(conectar_bd()) as conn:
        lista_equipos = conn.execute("""
            SELECT e.*,
                   (SELECT fecha_siguiente_revision FROM revisiones_tecnicas r
                     WHERE r.equipo_id = e.equipo_id
                     ORDER BY r.revision_id DESC LIMIT 1) AS proxima_revision
            FROM equipos e ORDER BY e.equipo_id DESC
        """).fetchall()
    return render_template('catalogo.html', activos=lista_equipos)


@app.route('/descargar_reporte')
@login_requerido
def descargar_reporte():
    try:
        with closing(conectar_bd()) as conn:
            equipos = conn.execute(
                "SELECT equipo_id, denominacion, clasificacion, existencia, "
                "condicion_actual, area_asignada FROM equipos").fetchall()

        salida = io.StringIO()
        salida.write('\ufeff')  # para que Excel muestre bien los acentos
        escritor = csv.writer(salida)
        escritor.writerow(['ID', 'Denominacion', 'Clasificacion', 'Existencia',
                           'Condicion_Actual', 'Area_Asignada'])
        for eq in equipos:
            escritor.writerow([eq['equipo_id'], eq['denominacion'], eq['clasificacion'],
                               eq['existencia'], eq['condicion_actual'], eq['area_asignada']])
        return Response(salida.getvalue(), mimetype='text/csv', headers={
            "Content-Disposition": "attachment;filename=reporte_inventario.csv"})
    except Exception as e:
        flash(f'Error al generar el reporte: {e}', 'danger')
        return redirect('/catalogo')


@app.route('/nuevo_registro', methods=['GET', 'POST'])
@login_requerido
def registrar_activo():
    if request.method == 'POST':
        try:
            with closing(conectar_bd()) as conn:
                conn.execute(
                    "INSERT INTO equipos (denominacion, clasificacion, existencia, area_asignada, "
                    "condicion_actual, suministrador, fecha_adquisicion, notas_adicionales) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (request.form['denominacion'], request.form['clasificacion'],
                     request.form['existencia'], request.form['area_asignada'],
                     request.form['condicion_actual'], request.form['suministrador'],
                     request.form['fecha_adquisicion'], request.form['notas_adicionales']))
                conn.commit()
            flash('¡Registro guardado exitosamente!', 'success')
            return redirect('/catalogo')
        except Exception as e:
            flash(f'Error al registrar: {e}', 'danger')
    return render_template('registro.html')


# ---------------------------------------------------------------- Revisiones y estados
@app.route('/nueva_revision/<int:id>', methods=['GET', 'POST'])
@login_requerido
def registrar_revision(id):
    with closing(conectar_bd()) as conn:
        if request.method == 'POST':
            try:
                conn.execute(
                    "INSERT INTO revisiones_tecnicas (equipo_id, fecha_servicio, tipo_servicio, "
                    "detalles, fecha_siguiente_revision, tecnico_encargado) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (id, request.form['fecha_servicio'], request.form['tipo_servicio'],
                     request.form['detalles'], request.form['fecha_siguiente_revision'],
                     request.form['tecnico_encargado']))
                conn.execute(
                    "UPDATE equipos SET condicion_actual = 'Operativo' WHERE equipo_id = ?", (id,))
                conn.commit()
                flash('¡Servicio registrado! Equipo Operativo.', 'success')
                return redirect('/')
            except Exception as e:
                flash(f'Error: {e}', 'danger')

        equipo = conn.execute(
            "SELECT denominacion FROM equipos WHERE equipo_id = ?", (id,)).fetchone()
    if not equipo:
        abort(404)
    return render_template('revision.html', equipo=equipo, equipo_id=id)


def _cambiar_estado(id, estado):
    with closing(conectar_bd()) as conn:
        conn.execute("UPDATE equipos SET condicion_actual = ? WHERE equipo_id = ?", (estado, id))
        conn.commit()


@app.route('/estado_taller/<int:id>')
@login_requerido
def mandar_a_taller(id):
    _cambiar_estado(id, 'En taller')
    flash('Alerta: Equipo enviado a Taller.', 'warning')
    return redirect('/catalogo')


@app.route('/estado_operativo/<int:id>')
@login_requerido
def regresar_operativo(id):
    _cambiar_estado(id, 'Operativo')
    flash('Equipo regresado a Operativo.', 'success')
    return redirect('/catalogo')


# ---------------------------------------------------------------- Movimientos de stock
@app.route('/movimientos', methods=['GET', 'POST'])
@login_requerido
def registrar_movimiento():
    with closing(conectar_bd()) as conn:
        if request.method == 'POST':
            equipo_id = request.form['equipo_id']
            tipo_operacion = request.form['tipo_operacion']
            cantidad = int(request.form['cantidad'])
            operador = request.form['operador']
            justificacion = request.form['justificacion']

            equipo = conn.execute(
                "SELECT existencia, condicion_actual FROM equipos WHERE equipo_id = ?",
                (equipo_id,)).fetchone()
            if not equipo:
                flash('Error: el equipo seleccionado no existe.', 'danger')
                return redirect('/movimientos')

            if tipo_operacion == 'Egreso' and equipo['condicion_actual'] == 'En taller':
                flash('Error: No puedes registrar la salida de un equipo que está "En taller".', 'danger')
                return redirect('/movimientos')

            if tipo_operacion == 'Egreso' and equipo['existencia'] < cantidad:
                flash(f"Error: Intentas sacar {cantidad} pero solo hay {equipo['existencia']} disponibles.", 'danger')
                return redirect('/movimientos')

            try:
                # El trigger de la base ajusta las existencias automáticamente
                conn.execute(
                    "INSERT INTO transacciones_stock (equipo_id, tipo_operacion, cantidad_operada, "
                    "operador, justificacion, fecha_transaccion) VALUES (?, ?, ?, ?, ?, ?)",
                    (equipo_id, tipo_operacion, cantidad, operador, justificacion,
                     ahora().strftime('%Y-%m-%d %H:%M:%S')))

                if tipo_operacion == 'Egreso' and equipo['existencia'] == cantidad:
                    conn.execute(
                        "UPDATE equipos SET condicion_actual = 'Asignado' WHERE equipo_id = ?",
                        (equipo_id,))
                elif tipo_operacion == 'Ingreso' and equipo['condicion_actual'] == 'Asignado':
                    conn.execute(
                        "UPDATE equipos SET condicion_actual = 'Operativo' WHERE equipo_id = ?",
                        (equipo_id,))

                conn.commit()
                flash('¡Transacción registrada exitosamente!', 'success')
            except Exception as e:
                flash(f'Error en la transacción: {e}', 'danger')
            return redirect('/catalogo')

        equipos = conn.execute(
            "SELECT equipo_id, denominacion, existencia, condicion_actual "
            "FROM equipos ORDER BY denominacion ASC").fetchall()
    return render_template('movimientos.html', equipos=equipos)


# ---------------------------------------------------------------- Detalle, QR y vales
@app.route('/equipo/<int:id>')
@login_requerido
def detalle_equipo(id):
    with closing(conectar_bd()) as conn:
        equipo = conn.execute("SELECT * FROM equipos WHERE equipo_id = ?", (id,)).fetchone()
        if not equipo:
            abort(404)
        historial = conn.execute(
            "SELECT * FROM transacciones_stock WHERE equipo_id = ? "
            "ORDER BY fecha_transaccion DESC", (id,)).fetchall()
        mantenimientos = conn.execute(
            "SELECT * FROM revisiones_tecnicas WHERE equipo_id = ? "
            "ORDER BY fecha_servicio DESC", (id,)).fetchall()

    # El QR apunta al link real de la página (o a URL_PUBLICA si la defines)
    base_url = (os.environ.get('URL_PUBLICA') or request.url_root).rstrip('/')
    qr = qrcode.make(f"{base_url}/equipo/{id}")
    buf = io.BytesIO()
    qr.save(buf, format='PNG')
    qr_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return render_template('detalle_equipo.html', equipo=equipo, historial=historial,
                           mantenimientos=mantenimientos, qr_code=qr_base64)


@app.route('/imprimir_vale/<int:id_transaccion>')
@login_requerido
def imprimir_vale(id_transaccion):
    with closing(conectar_bd()) as conn:
        movimiento = conn.execute("""
            SELECT t.*, e.denominacion, e.clasificacion
            FROM transacciones_stock t
            JOIN equipos e ON t.equipo_id = e.equipo_id
            WHERE t.transaccion_id = ?
        """, (id_transaccion,)).fetchone()
    if not movimiento:
        abort(404)
    return render_template('vale_pdf.html', m=movimiento)


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
