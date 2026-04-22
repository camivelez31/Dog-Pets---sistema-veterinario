import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from flask import send_file
from factories import MascotaFactory, EmpleadoFactory, FacturaFactory
from strategies import obtener_estrategia_pago
from observers import NotificationCenter, AuditoriaObserver
from decorators import (
    FacturaBase,
    ConsultaDecorator,
    VacunaDecorator,
    GuarderiaDecorator,
    BanoDecorator,
    DesparasitacionDecorator
)
import io


app = Flask(__name__)
app.secret_key = "dogpets_clave_secreta_2026"
DATABASE = "database.db"


# -------------------------------
# USUARIOS DE PRUEBA
# -------------------------------
usuarios = [
    {
        "id": 1,
        "nombre": "Maria Camila",
        "usuario": "recepcionista",
        "password": "1234",
        "rol": "recepcionista"
    },
    {
        "id": 2,
        "nombre": "Stiven Jiménez",
        "usuario": "veterinario",
        "password": "1234",
        "rol": "veterinario"
    },
    {
        "id": 3,
        "nombre": "Sandra Milena",
        "usuario": "guarderia",
        "password": "1234",
        "rol": "guarderia"
    },
    {
        "id": 4,
        "nombre": "Administrador",
        "usuario": "admin",
        "password": "1234",
        "rol": "admin"
    }
]


# -------------------------------
# BASE DE DATOS
# -------------------------------
from database import DatabaseSingleton

def get_db_connection():
    return DatabaseSingleton().get_connection()


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            documento TEXT NOT NULL UNIQUE,
            telefono TEXT NOT NULL,
            correo TEXT NOT NULL,
            direccion TEXT
        )
    """)

    columnas_clientes = [col["name"] for col in cursor.execute("PRAGMA table_info(clientes)").fetchall()]

    if "estado" not in columnas_clientes:
        cursor.execute("ALTER TABLE clientes ADD COLUMN estado TEXT NOT NULL DEFAULT 'Activo'")

    clientes_db = conn.execute("""
    SELECT * FROM clientes
    ORDER BY nombre ASC
    """).fetchall()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mascotas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        especie TEXT NOT NULL,
        raza TEXT,
        edad INTEGER,
        cliente_id INTEGER NOT NULL,
        FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    """)

    columnas_mascotas = [col["name"] for col in cursor.execute("PRAGMA table_info(mascotas)").fetchall()]

    if "estado" not in columnas_mascotas:
        cursor.execute("ALTER TABLE mascotas ADD COLUMN estado TEXT NOT NULL DEFAULT 'Activo'")


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS citas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mascota_id INTEGER NOT NULL,
        fecha TEXT NOT NULL,
        hora TEXT NOT NULL,
        servicio TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'Pendiente',
        observaciones TEXT,
        FOREIGN KEY (mascota_id) REFERENCES mascotas (id)
        )
    """)

    columnas_citas = [col["name"] for col in cursor.execute("PRAGMA table_info(citas)").fetchall()]

    if "veterinario_id" not in columnas_citas:
        cursor.execute("ALTER TABLE citas ADD COLUMN veterinario_id INTEGER")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historias_clinicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mascota_id INTEGER NOT NULL UNIQUE,
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (mascota_id) REFERENCES mascotas (id)
        )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS consultas_clinicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            historia_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            motivo TEXT NOT NULL,
            diagnostico TEXT NOT NULL,
            tratamiento TEXT NOT NULL,
            observaciones TEXT,
            FOREIGN KEY (historia_id) REFERENCES historias_clinicas (id)
        )
    """)

    cursor.execute("""
        INSERT INTO historias_clinicas (mascota_id)
        SELECT mascotas.id
        FROM mascotas
        WHERE mascotas.id NOT IN (
            SELECT mascota_id FROM historias_clinicas
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guarderia_estadias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mascota_id INTEGER NOT NULL,
            fecha_hora_ingreso TEXT NOT NULL,
            fecha_hora_salida TEXT,
            observaciones_ingreso TEXT,
            estado TEXT NOT NULL DEFAULT 'Activa',
            total_horas REAL,
            FOREIGN KEY (mascota_id) REFERENCES mascotas (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guarderia_incidencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estadia_id INTEGER NOT NULL,
            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            tipo TEXT NOT NULL DEFAULT 'General',
            descripcion TEXT NOT NULL,
            atendida INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (estadia_id) REFERENCES guarderia_estadias (id)
        )
    """)

    columnas_incidencias = [col["name"] for col in cursor.execute("PRAGMA table_info(guarderia_incidencias)").fetchall()]

    if "tipo" not in columnas_incidencias:
        cursor.execute("ALTER TABLE guarderia_incidencias ADD COLUMN tipo TEXT NOT NULL DEFAULT 'General'")

    if "atendida" not in columnas_incidencias:
        cursor.execute("ALTER TABLE guarderia_incidencias ADD COLUMN atendida INTEGER NOT NULL DEFAULT 0")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            mascota_id INTEGER NOT NULL,
            fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            estado TEXT NOT NULL DEFAULT 'Pendiente',
            total REAL NOT NULL DEFAULT 0,
            motivo_anulacion TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id),
            FOREIGN KEY (mascota_id) REFERENCES mascotas (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detalle_factura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id INTEGER NOT NULL,
            concepto TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            total_linea REAL NOT NULL,
            FOREIGN KEY (factura_id) REFERENCES facturas (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id INTEGER NOT NULL,
            fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            metodo_pago TEXT NOT NULL,
            FOREIGN KEY (factura_id) REFERENCES facturas (id)
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS veterinarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            especialidad TEXT,
            estado TEXT NOT NULL DEFAULT 'Disponible'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS empleados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            usuario TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            rol TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'Activo'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_nombre TEXT NOT NULL,
            usuario_rol TEXT NOT NULL,
            accion TEXT NOT NULL,
            modulo TEXT NOT NULL,
            detalle TEXT,
            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    


    conn.commit()
    conn.close()


init_db()


# -------------------------------
# HELPERS
# -------------------------------
def login_requerido():
    return "rol" in session


def rol_requerido(rol):
    return session.get("rol") == rol

def registrar_auditoria(accion, modulo, detalle=""):
    if "nombre" not in session or "rol" not in session:
        return

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO auditoria (usuario_nombre, usuario_rol, accion, modulo, detalle)
        VALUES (?, ?, ?, ?, ?)
    """, (
        session.get("nombre", "Desconocido"),
        session.get("rol", "Sin rol"),
        accion,
        modulo,
        detalle
    ))
    conn.commit()
    conn.close()


notifier = NotificationCenter()
notifier.subscribe(AuditoriaObserver(registrar_auditoria))

# -------------------------------
# RUTAS GENERALES
# -------------------------------
@app.route("/")
def inicio():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario_form = request.form.get("usuario", "").strip()
        password_form = request.form.get("password", "").strip()

        conn = get_db_connection()

        empleado = conn.execute("""
            SELECT * FROM empleados
            WHERE usuario = ? AND password = ? AND estado = 'Activo'
        """, (usuario_form, password_form)).fetchone()

        conn.close()

        if empleado:
            session["usuario_id"] = empleado["id"]
            session["nombre"] = empleado["nombre"]
            session["rol"] = empleado["rol"]
            return redirect(url_for("dashboard"))

        for usuario in usuarios:
            if usuario["usuario"] == usuario_form and usuario["password"] == password_form:
                session["usuario_id"] = usuario["id"]
                session["nombre"] = usuario["nombre"]
                session["rol"] = usuario["rol"]
                return redirect(url_for("dashboard"))

        return render_template("login.html", error="Usuario o contraseña incorrectos")

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if not login_requerido():
        return redirect(url_for("login"))

    rol = session.get("rol")

    conn = get_db_connection()

    if rol == "recepcionista":
        citas_hoy = conn.execute("""
            SELECT COUNT(*) FROM citas
            WHERE fecha = date('now','localtime')
        """).fetchone()[0]

        citas_proximas = conn.execute("""
            SELECT COUNT(*) FROM citas
            WHERE fecha > date('now','localtime')
        """).fetchone()[0]

        citas_canceladas = conn.execute("""
            SELECT COUNT(*) FROM citas
            WHERE estado = 'Cancelada'
        """).fetchone()[0]

        citas_lista = conn.execute("""
            SELECT 
                citas.hora,
                mascotas.nombre AS mascota,
                clientes.nombre AS cliente,
                citas.estado
            FROM citas
            JOIN mascotas ON citas.mascota_id = mascotas.id
            JOIN clientes ON mascotas.cliente_id = clientes.id
            WHERE citas.fecha = date('now','localtime')
            ORDER BY citas.hora ASC
            LIMIT 5
        """).fetchall()

        guarderia_activas = conn.execute("""
            SELECT COUNT(*) FROM guarderia_estadias
            WHERE estado = 'Activa'
        """).fetchone()[0]

        ingresos_hoy = conn.execute("""
            SELECT COUNT(*) FROM guarderia_estadias
            WHERE date(fecha_hora_ingreso) = date('now','localtime')
        """).fetchone()[0]

        salidas_pendientes = conn.execute("""
            SELECT COUNT(*) FROM guarderia_estadias
            WHERE estado = 'Activa'
        """).fetchone()[0]

        guarderia_lista = conn.execute("""
            SELECT
                guarderia_estadias.fecha_hora_ingreso,
                mascotas.nombre AS mascota,
                clientes.nombre AS cliente
            FROM guarderia_estadias
            JOIN mascotas ON guarderia_estadias.mascota_id = mascotas.id
            JOIN clientes ON mascotas.cliente_id = clientes.id
            WHERE date(guarderia_estadias.fecha_hora_ingreso) = date('now','localtime')
            ORDER BY guarderia_estadias.fecha_hora_ingreso ASC
            LIMIT 5
        """).fetchall()

        facturas_pendientes = conn.execute("""
            SELECT COUNT(*) FROM facturas
            WHERE estado = 'Pendiente'
        """).fetchone()[0]

        facturas_lista = conn.execute("""
            SELECT
                clientes.nombre AS cliente,
                mascotas.nombre AS mascota,
                facturas.total,
                facturas.estado
            FROM facturas
            JOIN clientes ON facturas.cliente_id = clientes.id
            JOIN mascotas ON facturas.mascota_id = mascotas.id
            ORDER BY facturas.id DESC
            LIMIT 5
        """).fetchall()

        veterinarios_disponibles = conn.execute("""
            SELECT
                veterinarios.id,
                veterinarios.nombre AS veterinario,
                veterinarios.estado AS estado_base,
                citas.hora,
                mascotas.nombre AS mascota,
                citas.servicio
            FROM veterinarios
            LEFT JOIN citas
                ON citas.veterinario_id = veterinarios.id
               AND citas.fecha = date('now','localtime')
               AND citas.estado IN ('Pendiente', 'Confirmada')
            LEFT JOIN mascotas ON citas.mascota_id = mascotas.id
            ORDER BY veterinarios.nombre ASC, citas.hora ASC
        """).fetchall()

        conn.close()

        return render_template(
            "recepcionista/dashboard.html",
            nombre=session["nombre"],
            rol=session["rol"],
            citas_hoy=citas_hoy,
            citas_proximas=citas_proximas,
            citas_canceladas=citas_canceladas,
            citas_lista=citas_lista,
            guarderia_activas=guarderia_activas,
            ingresos_hoy=ingresos_hoy,
            salidas_pendientes=salidas_pendientes,
            guarderia_lista=guarderia_lista,
            facturas_pendientes=facturas_pendientes,
            facturas_lista=facturas_lista,
            veterinarios_disponibles=veterinarios_disponibles
        )

    elif rol == "veterinario":
        citas_hoy = conn.execute("""
            SELECT COUNT(*) FROM citas
            WHERE fecha = date('now','localtime')
              AND estado IN ('Pendiente', 'Confirmada')
        """).fetchone()[0]

        historias_total = conn.execute("""
            SELECT COUNT(*) FROM historias_clinicas
        """).fetchone()[0]

        consultas_total = conn.execute("""
            SELECT COUNT(*) FROM consultas_clinicas
        """).fetchone()[0]

        citas_lista = conn.execute("""
            SELECT
                citas.id,
                citas.fecha,
                citas.hora,
                citas.servicio,
                citas.estado,
                mascotas.nombre AS mascota_nombre,
                clientes.nombre AS cliente_nombre,
                historias_clinicas.id AS historia_id
            FROM citas
            JOIN mascotas ON citas.mascota_id = mascotas.id
            JOIN clientes ON mascotas.cliente_id = clientes.id
            JOIN historias_clinicas ON historias_clinicas.mascota_id = mascotas.id
            WHERE citas.fecha = date('now','localtime')
              AND citas.estado IN ('Pendiente', 'Confirmada')
            ORDER BY citas.hora ASC
        """).fetchall()

        
        incidencias_medicas = conn.execute("""
            SELECT
                guarderia_incidencias.id,
                guarderia_incidencias.fecha_hora,
                guarderia_incidencias.descripcion,
                guarderia_incidencias.atendida,
                mascotas.nombre AS mascota_nombre,
                clientes.nombre AS cliente_nombre,
                historias_clinicas.id AS historia_id
            FROM guarderia_incidencias
            JOIN guarderia_estadias ON guarderia_incidencias.estadia_id = guarderia_estadias.id
            JOIN mascotas ON guarderia_estadias.mascota_id = mascotas.id
            JOIN clientes ON mascotas.cliente_id = clientes.id
            JOIN historias_clinicas ON historias_clinicas.mascota_id = mascotas.id
            WHERE guarderia_incidencias.tipo = 'Médica'
            ORDER BY guarderia_incidencias.fecha_hora DESC
            LIMIT 5
        """).fetchall()

        conn.close()

        return render_template(
            "veterinario/dashboard.html",
            nombre=session["nombre"],
            citas_hoy=citas_hoy,
            historias_total=historias_total,
            consultas_total=consultas_total,
            citas_lista=citas_lista,
            incidencias_medicas=incidencias_medicas
        )
    


    elif rol == "guarderia":
        guarderia_activas = conn.execute("""
            SELECT COUNT(*) FROM guarderia_estadias
            WHERE estado = 'Activa'
        """).fetchone()[0]

        ingresos_hoy = conn.execute("""
            SELECT COUNT(*) FROM guarderia_estadias
            WHERE date(fecha_hora_ingreso) = date('now','localtime')
        """).fetchone()[0]

        salidas_pendientes = conn.execute("""
            SELECT COUNT(*) FROM guarderia_estadias
            WHERE estado = 'Activa'
        """).fetchone()[0]

        estadias_activas = conn.execute("""
            SELECT
                guarderia_estadias.id,
                guarderia_estadias.fecha_hora_ingreso,
                guarderia_estadias.observaciones_ingreso,
                mascotas.nombre AS mascota_nombre,
                clientes.nombre AS cliente_nombre
            FROM guarderia_estadias
            JOIN mascotas ON guarderia_estadias.mascota_id = mascotas.id
            JOIN clientes ON mascotas.cliente_id = clientes.id
            WHERE guarderia_estadias.estado = 'Activa'
            ORDER BY guarderia_estadias.fecha_hora_ingreso ASC
            LIMIT 5
        """).fetchall()

        incidencias_hoy = conn.execute("""
            SELECT COUNT(*) FROM guarderia_incidencias
            WHERE date(fecha_hora) = date('now','localtime')
        """).fetchone()[0]

        conn.close()

        return render_template(
            "guarderia/dashboard.html",
            nombre=session["nombre"],
            guarderia_activas=guarderia_activas,
            ingresos_hoy=ingresos_hoy,
            salidas_pendientes=salidas_pendientes,
            incidencias_hoy=incidencias_hoy,
            estadias_activas=estadias_activas
        )
    

    elif rol == "admin":
        total_clientes = conn.execute("""
            SELECT COUNT(*) FROM clientes
        """).fetchone()[0]

        total_mascotas = conn.execute("""
            SELECT COUNT(*) FROM mascotas
        """).fetchone()[0]

        total_citas = conn.execute("""
            SELECT COUNT(*) FROM citas
        """).fetchone()[0]

        total_empleados = conn.execute("""
            SELECT COUNT(*) FROM empleados
        """).fetchone()[0]

        total_veterinarios = conn.execute("""
            SELECT COUNT(*) FROM veterinarios
        """).fetchone()[0]

        facturas_pendientes = conn.execute("""
            SELECT COUNT(*) FROM facturas
            WHERE estado = 'Pendiente'
        """).fetchone()[0]

        veterinarios_lista = conn.execute("""
            SELECT *
            FROM veterinarios
            ORDER BY id DESC
            LIMIT 5
        """).fetchall()

        resumen_facturas = conn.execute("""
            SELECT estado, COUNT(*) as total
            FROM facturas
            GROUP BY estado
        """).fetchall()

        ultimas_citas = conn.execute("""
            SELECT
                citas.fecha,
                citas.hora,
                citas.estado,
                clientes.nombre AS cliente_nombre,
                mascotas.nombre AS mascota_nombre,
                veterinarios.nombre AS veterinario_nombre
            FROM citas
            JOIN mascotas ON citas.mascota_id = mascotas.id
            JOIN clientes ON mascotas.cliente_id = clientes.id
            LEFT JOIN veterinarios ON citas.veterinario_id = veterinarios.id
            ORDER BY citas.id DESC
            LIMIT 5
        """).fetchall()

        ultimas_facturas = conn.execute("""
            SELECT
                facturas.id,
                facturas.fecha,
                facturas.total,
                facturas.estado,
                clientes.nombre AS cliente_nombre,
                mascotas.nombre AS mascota_nombre
            FROM facturas
            JOIN clientes ON facturas.cliente_id = clientes.id
            JOIN mascotas ON facturas.mascota_id = mascotas.id
            ORDER BY facturas.id DESC
            LIMIT 5
        """).fetchall()

        conn.close()

        return render_template(
            "admin/dashboard.html",
            nombre=session["nombre"],
            rol=session["rol"],
            total_clientes=total_clientes,
            total_mascotas=total_mascotas,
            total_citas=total_citas,
            total_empleados=total_empleados,
            total_veterinarios=total_veterinarios,
            facturas_pendientes=facturas_pendientes,
            veterinarios_lista=veterinarios_lista,
            resumen_facturas=resumen_facturas,
            ultimas_citas=ultimas_citas,
            ultimas_facturas=ultimas_facturas
        )

    conn.close()
    return "Rol no soportado todavía", 403




@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -------------------------------
# CLIENTES - RECEPCIONISTA
# -------------------------------
@app.route("/recepcionista/clientes")
def clientes():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") not in ["recepcionista", "guarderia"]:
        return "No autorizado", 403

    conn = get_db_connection()
    clientes_db = conn.execute("SELECT * FROM clientes ORDER BY id DESC").fetchall()
    conn.close()

    return render_template(
        "recepcionista/clientes.html",
        nombre=session["nombre"],
        rol=session["rol"],
        clientes=clientes_db
    )


@app.route("/recepcionista/clientes/crear", methods=["POST"])
def crear_cliente():
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    nombre = request.form.get("nombre", "").strip()
    documento = request.form.get("documento", "").strip()
    telefono = request.form.get("telefono", "").strip()
    correo = request.form.get("correo", "").strip()
    direccion = request.form.get("direccion", "").strip()

    if not nombre or not documento or not telefono or not correo:
        flash("Los campos nombre, documento, teléfono y correo son obligatorios.", "error")
        return redirect(url_for("clientes"))

    conn = None

    try:
        conn = get_db_connection()

        conn.execute("""
            INSERT INTO clientes (nombre, documento, telefono, correo, direccion)
            VALUES (?, ?, ?, ?, ?)
        """, (nombre, documento, telefono, correo, direccion))

        conn.commit()

    except sqlite3.IntegrityError:
        if conn:
            conn.rollback()
        flash("Ya existe un cliente con ese documento.", "error")
        return redirect(url_for("clientes"))

    finally:
        if conn:
            conn.close()

    notifier.notify("Crear cliente", {
    "modulo": "Clientes",
    "detalle": f"Cliente: {nombre}, documento: {documento}"
    })

    flash("Cliente registrado correctamente.", "success")
    return redirect(url_for("clientes"))


# -------------------------------
# MASCOTAS
# -------------------------------
@app.route("/recepcionista/mascotas")
def mascotas():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") not in ["recepcionista", "admin"]:
        return "No autorizado", 403

    conn = get_db_connection()

    mascotas_db = conn.execute("""
        SELECT mascotas.*, clientes.nombre as cliente_nombre
        FROM mascotas
        JOIN clientes ON mascotas.cliente_id = clientes.id
        ORDER BY mascotas.id DESC
    """).fetchall()

    clientes_db = conn.execute("SELECT * FROM clientes ORDER BY nombre ASC").fetchall()

    conn.close()

    return render_template(
        "recepcionista/mascotas.html",
        mascotas=mascotas_db,
        clientes=clientes_db,
        nombre=session["nombre"],
        rol=session["rol"]
    )


@app.route("/recepcionista/mascotas/crear", methods=["POST"])
def crear_mascota():
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    nombre = request.form.get("nombre")
    especie = request.form.get("especie")
    raza = request.form.get("raza")
    edad = request.form.get("edad")
    cliente_id = request.form.get("cliente_id")

    if not nombre or not especie or not cliente_id:
        flash("Nombre, especie y cliente son obligatorios", "error")
        return redirect(url_for("mascotas"))
    
    mascota = MascotaFactory.crear(nombre, especie, raza, edad, cliente_id)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO mascotas (nombre, especie, raza, edad, cliente_id)
    VALUES (?, ?, ?, ?, ?)
""", (
    mascota["nombre"],
    mascota["especie"],
    mascota["raza"],
    mascota["edad"],
    mascota["cliente_id"]
))

    mascota_id = cursor.lastrowid

    cursor.execute("""
    INSERT INTO historias_clinicas (mascota_id)
    VALUES (?)
""", (mascota_id,))

    conn.commit()
    conn.close()

    notifier.notify("Crear mascota", {
    "modulo": "Mascotas",
    "detalle": f"Mascota: {mascota['nombre']}, cliente ID: {mascota['cliente_id']}"
    })

    flash("Mascota registrada correctamente", "success")
    return redirect(url_for("mascotas"))


@app.route("/recepcionista/mascotas/editar/<int:mascota_id>", methods=["POST"])
def editar_mascota(mascota_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") not in ["recepcionista", "admin"]:
        return "No autorizado", 403

    nombre = request.form.get("nombre", "").strip()
    especie = request.form.get("especie", "").strip()
    raza = request.form.get("raza", "").strip()
    edad = request.form.get("edad", "").strip()
    cliente_id = request.form.get("cliente_id", "").strip()

    if not nombre or not especie or not cliente_id:
        flash("Nombre, especie y cliente son obligatorios.", "error")
        return redirect(url_for("mascotas"))

    conn = get_db_connection()
    conn.execute("""
        UPDATE mascotas
        SET nombre = ?, especie = ?, raza = ?, edad = ?, cliente_id = ?
        WHERE id = ?
    """, (nombre, especie, raza, edad if edad else None, cliente_id, mascota_id))
    conn.commit()
    conn.close()

    flash("Mascota actualizada correctamente.", "success")
    return redirect(url_for("mascotas"))


@app.route("/recepcionista/mascotas/cambiar-estado/<int:mascota_id>", methods=["POST"])
def cambiar_estado_mascota(mascota_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") not in ["recepcionista", "admin"]:
        return "No autorizado", 403

    conn = get_db_connection()

    mascota = conn.execute("""
        SELECT * FROM mascotas WHERE id = ?
    """, (mascota_id,)).fetchone()

    if not mascota:
        conn.close()
        flash("La mascota no existe.", "error")
        return redirect(url_for("mascotas"))

    nuevo_estado = "Inactivo" if mascota["estado"] == "Activo" else "Activo"

    conn.execute("""
        UPDATE mascotas
        SET estado = ?
        WHERE id = ?
    """, (nuevo_estado, mascota_id))

    conn.commit()
    conn.close()

    flash("Estado de la mascota actualizado.", "success")
    return redirect(url_for("mascotas"))

@app.route("/recepcionista/mascotas/eliminar/<int:mascota_id>", methods=["POST"])
def eliminar_mascota(mascota_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") not in ["recepcionista", "admin"]:
        return "No autorizado", 403

    conn = get_db_connection()

    tiene_citas = conn.execute("SELECT 1 FROM citas WHERE mascota_id = ? LIMIT 1", (mascota_id,)).fetchone()
    tiene_historia = conn.execute("SELECT 1 FROM historias_clinicas WHERE mascota_id = ? LIMIT 1", (mascota_id,)).fetchone()
    tiene_guarderia = conn.execute("SELECT 1 FROM guarderia_estadias WHERE mascota_id = ? LIMIT 1", (mascota_id,)).fetchone()

    if tiene_citas or tiene_historia or tiene_guarderia:
        conn.close()
        flash("No se puede eliminar la mascota porque tiene registros relacionados. Mejor cámbiala a Inactiva.", "error")
        return redirect(url_for("mascotas"))

    conn.execute("DELETE FROM mascotas WHERE id = ?", (mascota_id,))
    conn.commit()
    conn.close()

    flash("Mascota eliminada correctamente.", "success")
    return redirect(url_for("mascotas"))

# -------------------------------
# CITAS
# -------------------------------
@app.route("/recepcionista/citas")
def citas():
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    fecha_agenda = request.args.get("fecha", "").strip()
    if not fecha_agenda:
        fecha_agenda = date.today().strftime("%Y-%m-%d")

    conn = get_db_connection()

    citas_db = conn.execute("""
        SELECT 
            citas.id,
            citas.fecha,
            citas.hora,
            citas.servicio,
            citas.estado,
            citas.observaciones,
            mascotas.nombre AS mascota_nombre,
            clientes.nombre AS cliente_nombre,
            veterinarios.nombre AS veterinario_nombre
        FROM citas
        JOIN mascotas ON citas.mascota_id = mascotas.id
        JOIN clientes ON mascotas.cliente_id = clientes.id
        LEFT JOIN veterinarios ON citas.veterinario_id = veterinarios.id
        ORDER BY citas.fecha DESC, citas.hora ASC
    """).fetchall()

    mascotas_db = conn.execute("""
        SELECT 
            mascotas.id,
            mascotas.nombre AS mascota_nombre,
            clientes.nombre AS cliente_nombre
        FROM mascotas
        JOIN clientes ON mascotas.cliente_id = clientes.id
        ORDER BY mascotas.nombre ASC
    """).fetchall()

    veterinarios_db = conn.execute("""
        SELECT * FROM veterinarios
        WHERE estado = 'Disponible'
        ORDER BY nombre ASC
    """).fetchall()

    conn.close()

    return render_template(
        "recepcionista/citas.html",
        nombre=session["nombre"],
        rol=session["rol"],
        citas=citas_db,
        mascotas=mascotas_db,
        veterinarios=veterinarios_db,
        fecha_agenda=fecha_agenda
    )


@app.route("/recepcionista/citas/crear", methods=["POST"])
def crear_cita():
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    mascota_id = request.form.get("mascota_id", "").strip()
    fecha = request.form.get("fecha", "").strip()
    hora = request.form.get("hora", "").strip()
    servicio = request.form.get("servicio", "").strip()
    veterinario_id = request.form.get("veterinario_id", "").strip()
    estado = request.form.get("estado", "Pendiente").strip()
    observaciones = request.form.get("observaciones", "").strip()

    if not mascota_id or not fecha or not hora or not servicio:
        flash("Mascota, fecha, hora y servicio son obligatorios.", "error")
        return redirect(url_for("citas"))

    # Validar que el veterinario no tenga otra cita dentro de un rango de 2 horas
    conn = get_db_connection()

    citas_veterinario = conn.execute("""
        SELECT fecha, hora
        FROM citas
        WHERE veterinario_id = ?
          AND fecha = ?
          AND estado IN ('Pendiente', 'Confirmada', 'Atendida')
    """, (veterinario_id, fecha)).fetchall()

    hora_nueva = datetime.strptime(hora, "%H:%M")

    for cita_existente in citas_veterinario:
        hora_existente = datetime.strptime(cita_existente["hora"], "%H:%M")
        diferencia_minutos = abs((hora_nueva - hora_existente).total_seconds()) / 60

        if diferencia_minutos < 120:
            conn.close()
            flash("Ese veterinario ya tiene una cita en un rango menor a 2 horas.", "error")
            return redirect(url_for("citas"))
    
    
        conn = get_db_connection()

    cita_existente = conn.execute("""
        SELECT id FROM citas
        WHERE fecha = ? AND hora = ?
          AND estado IN ('Pendiente', 'Confirmada', 'Atendida')
    """, (fecha, hora)).fetchone()

    if cita_existente:
        conn.close()
        flash("Esa franja horaria ya está ocupada. Elige otra hora.", "error")
        return redirect(url_for("citas"))

    # Validar que el veterinario no tenga otra cita dentro de un rango de 2 horas
    citas_veterinario = conn.execute("""
        SELECT fecha, hora
        FROM citas
        WHERE veterinario_id = ?
          AND fecha = ?
          AND estado IN ('Pendiente', 'Confirmada', 'Atendida')
    """, (veterinario_id, fecha)).fetchall()

    hora_nueva = datetime.strptime(hora, "%H:%M")

    for cita_existente_vet in citas_veterinario:
        hora_existente = datetime.strptime(cita_existente_vet["hora"], "%H:%M")
        diferencia_minutos = abs((hora_nueva - hora_existente).total_seconds()) / 60

        if diferencia_minutos < 120:
            conn.close()
            flash("Ese veterinario ya tiene una cita en un rango menor a 2 horas.", "error")
            return redirect(url_for("citas"))

    conn.execute("""
        INSERT INTO citas (mascota_id, fecha, hora, servicio, estado, observaciones, veterinario_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (mascota_id, fecha, hora, servicio, estado, observaciones, veterinario_id))

    conn.commit()
    conn.close()

    flash("Cita registrada correctamente.", "success")
    
    notifier.notify("Crear cita", {
    "modulo": "Citas",
    "detalle": f"Mascota ID {mascota_id}, fecha {fecha}, hora {hora}, servicio {servicio}, veterinario ID {veterinario_id}"
    })
    
    
    return redirect(url_for("citas"))


@app.route("/recepcionista/citas/reprogramar/<int:cita_id>", methods=["POST"])
def reprogramar_cita(cita_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    nueva_fecha = request.form.get("nueva_fecha", "").strip()
    nueva_hora = request.form.get("nueva_hora", "").strip()

    if not nueva_fecha or not nueva_hora:
        flash("La nueva fecha y hora son obligatorias.", "error")
        return redirect(url_for("citas"))

    conn = get_db_connection()
    cita = conn.execute("SELECT * FROM citas WHERE id = ?", (cita_id,)).fetchone()

    if not cita:
        conn.close()
        flash("La cita no existe.", "error")
        return redirect(url_for("citas"))

    fecha_hora_actual_cita = datetime.strptime(f"{cita['fecha']} {cita['hora']}", "%Y-%m-%d %H:%M")
    ahora = datetime.now()

    diferencia_horas = (fecha_hora_actual_cita - ahora).total_seconds() / 3600

    if diferencia_horas < 12:
        conn.close()
        flash("No se puede reprogramar una cita con menos de 12 horas de anticipación.", "error")
        return redirect(url_for("citas"))

    franja_ocupada = conn.execute("""
        SELECT id FROM citas
        WHERE fecha = ? AND hora = ?
          AND estado IN ('Pendiente', 'Confirmada', 'Atendida')
          AND id != ?
    """, (nueva_fecha, nueva_hora, cita_id)).fetchone()

    if franja_ocupada:
        conn.close()
        flash("La nueva franja horaria ya está ocupada.", "error")
        return redirect(url_for("citas"))

    conn.execute("""
        UPDATE citas
        SET fecha = ?, hora = ?
        WHERE id = ?
    """, (nueva_fecha, nueva_hora, cita_id))

    conn.commit()
    conn.close()

    flash("Cita reprogramada correctamente.", "success")

    notifier.notify("Reprogramar cita", {
    "modulo": "Citas",
    "detalle": f"Cita ID {cita_id}, nueva fecha {nueva_fecha}, nueva hora {nueva_hora}"
    })
    return redirect(url_for("citas"))


@app.route("/recepcionista/citas/cancelar/<int:cita_id>", methods=["POST"])
def cancelar_cita(cita_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    conn = get_db_connection()
    cita = conn.execute("SELECT * FROM citas WHERE id = ?", (cita_id,)).fetchone()

    if not cita:
        conn.close()
        flash("La cita no existe.", "error")
        return redirect(url_for("citas"))

    if cita["estado"] == "Cancelada":
        conn.close()
        flash("La cita ya está cancelada.", "error")
        return redirect(url_for("citas"))

    fecha_hora_cita = datetime.strptime(f"{cita['fecha']} {cita['hora']}", "%Y-%m-%d %H:%M")
    ahora = datetime.now()

    diferencia_horas = (fecha_hora_cita - ahora).total_seconds() / 3600

    if diferencia_horas < 12:
        conn.close()
        flash("No se puede cancelar una cita con menos de 12 horas de anticipación.", "error")
        return redirect(url_for("citas"))

    conn.execute("""
        UPDATE citas
        SET estado = 'Cancelada'
        WHERE id = ?
    """, (cita_id,))

    conn.commit()
    conn.close()

    flash("Cita cancelada correctamente.", "success")

    notifier.notify("Cancelar cita", {
    "modulo": "Citas",
    "detalle": f"Cita ID {cita_id}"
    })

    return redirect(url_for("citas"))

@app.route("/recepcionista/citas/agenda-data")
def agenda_data():
    if not login_requerido():
        return jsonify({"error": "No autenticado"}), 401

    if session.get("rol") != "recepcionista":
        return jsonify({"error": "No autorizado"}), 403

    fecha = request.args.get("fecha", "").strip()
    if not fecha:
        fecha = date.today().strftime("%Y-%m-%d")

    conn = get_db_connection()

    agenda = conn.execute("""
        SELECT
            citas.id,
            citas.fecha,
            citas.hora,
            citas.servicio,
            citas.estado,
            citas.observaciones,
            mascotas.nombre AS mascota_nombre,
            clientes.nombre AS cliente_nombre,
            veterinarios.nombre AS veterinario_nombre
        FROM citas
        JOIN mascotas ON citas.mascota_id = mascotas.id
        JOIN clientes ON mascotas.cliente_id = clientes.id
        LEFT JOIN veterinarios ON citas.veterinario_id = veterinarios.id
        WHERE citas.fecha = ?
          AND citas.estado IN ('Pendiente', 'Confirmada', 'Atendida')
        ORDER BY citas.hora ASC
    """, (fecha,)).fetchall()

    conn.close()

    return jsonify([
        {
            "id": fila["id"],
            "fecha": fila["fecha"],
            "hora": fila["hora"],
            "servicio": fila["servicio"],
            "estado": fila["estado"],
            "observaciones": fila["observaciones"] or "",
            "mascota": fila["mascota_nombre"],
            "cliente": fila["cliente_nombre"],
            "veterinario": fila["veterinario_nombre"] or "Sin asignar"
        }
        for fila in agenda
    ])


@app.route("/recepcionista/citas/no-asistio/<int:cita_id>", methods=["POST"])
def marcar_no_show(cita_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    conn = get_db_connection()
    cita = conn.execute("SELECT * FROM citas WHERE id = ?", (cita_id,)).fetchone()

    if not cita:
        conn.close()
        flash("La cita no existe.", "error")
        return redirect(url_for("citas"))

    if cita["estado"] in ["Cancelada", "Atendida", "No asistió"]:
        conn.close()
        flash("No se puede marcar esta cita como No asistió.", "error")
        return redirect(url_for("citas"))

    fecha_hora_cita = datetime.strptime(f"{cita['fecha']} {cita['hora']}", "%Y-%m-%d %H:%M")
    ahora = datetime.now()

    if fecha_hora_cita > ahora:
        conn.close()
        flash("Solo se puede marcars No asistió en citas vencidas.", "error")
        return redirect(url_for("citas"))

    conn.execute("""
        UPDATE citas
        SET estado = 'No asistió'
        WHERE id = ?
    """, (cita_id,))

    conn.commit()
    conn.close()

    flash("La cita fue marcada como No asistió.", "success")

    notifier.notify("Marcar no asistió", {
    "modulo": "Citas",
    "detalle": f"Cita ID {cita_id}"
    })

    return redirect(url_for("citas"))


# -------------------------------
# HISTORIA CLINICA - SOLO LECTURA RECEPCIONISTA
# -------------------------------
@app.route("/recepcionista/historias")
def historias():
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    conn = get_db_connection()

    historias_db = conn.execute("""
        SELECT 
            historias_clinicas.id,
            historias_clinicas.fecha_creacion,
            mascotas.id AS mascota_id,
            mascotas.nombre AS mascota_nombre,
            mascotas.especie,
            mascotas.raza,
            mascotas.edad,
            clientes.nombre AS cliente_nombre
        FROM historias_clinicas
        JOIN mascotas ON historias_clinicas.mascota_id = mascotas.id
        JOIN clientes ON mascotas.cliente_id = clientes.id
        ORDER BY historias_clinicas.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "recepcionista/historias.html",
        nombre=session["nombre"],
        rol=session["rol"],
        historias=historias_db
    )


@app.route("/recepcionista/historias/<int:historia_id>")
def detalle_historia(historia_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    conn = get_db_connection()

    historia = conn.execute("""
        SELECT 
            historias_clinicas.id,
            historias_clinicas.fecha_creacion,
            mascotas.nombre AS mascota_nombre,
            mascotas.especie,
            mascotas.raza,
            mascotas.edad,
            clientes.nombre AS cliente_nombre,
            clientes.documento,
            clientes.telefono,
            clientes.correo
        FROM historias_clinicas
        JOIN mascotas ON historias_clinicas.mascota_id = mascotas.id
        JOIN clientes ON mascotas.cliente_id = clientes.id
        WHERE historias_clinicas.id = ?
    """, (historia_id,)).fetchone()

    consultas = conn.execute("""
        SELECT *
        FROM consultas_clinicas
        WHERE historia_id = ?
        ORDER BY fecha DESC, id DESC
    """, (historia_id,)).fetchall()

    conn.close()

    if not historia:
        flash("La historia clínica no existe.", "error")
        return redirect(url_for("historias"))

    return render_template(
        "recepcionista/detalle_historia.html",
        nombre=session["nombre"],
        rol=session["rol"],
        historia=historia,
        consultas=consultas
    )


@app.route("/recepcionista/historia/pdf/<int:historia_id>")
def descargar_historia_pdf(historia_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") not in ["recepcionista", "admin"]:
        return "No autorizado", 403

    conn = get_db_connection()

    historia = conn.execute("""
        SELECT hc.*, m.nombre AS mascota, c.nombre AS cliente
        FROM historias_clinicas hc
        JOIN mascotas m ON hc.mascota_id = m.id
        JOIN clientes c ON m.cliente_id = c.id
        WHERE hc.id = ?
    """, (historia_id,)).fetchone()

    consultas = conn.execute("""
        SELECT * FROM consultas_clinicas
        WHERE historia_id = ?
        ORDER BY fecha DESC
    """, (historia_id,)).fetchall()

    conn.close()

    # 📄 Crear PDF en memoria
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    y = 750

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Historia Clínica Veterinaria")

    y -= 30
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, y, f"Mascota: {historia['mascota']}")
    y -= 20
    pdf.drawString(50, y, f"Cliente: {historia['cliente']}")

    y -= 30
    pdf.drawString(50, y, "Consultas:")

    y -= 20

    for consulta in consultas:
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(50, y, f"Fecha: {consulta['fecha']}")

        y -= 15
        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, y, f"Motivo: {consulta['motivo']}")

        y -= 15
        pdf.drawString(50, y, f"Diagnóstico: {consulta['diagnostico']}")

        y -= 15
        pdf.drawString(50, y, f"Tratamiento: {consulta['tratamiento']}")

        y -= 25

        # salto de página si se llena
        if y < 100:
            pdf.showPage()
            y = 750

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"historia_{historia_id}.pdf",
        mimetype="application/pdf"
    )

    # -------------------------------
# GUARDERIA
# -------------------------------
@app.route("/recepcionista/guarderia")
def guarderia():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") not in ["recepcionista", "guarderia"]:
        return "No autorizado", 403

    conn = get_db_connection()

    mascotas_db = conn.execute("""
        SELECT 
            mascotas.id,
            mascotas.nombre AS mascota_nombre,
            clientes.nombre AS cliente_nombre
        FROM mascotas
        JOIN clientes ON mascotas.cliente_id = clientes.id
        ORDER BY mascotas.nombre ASC
    """).fetchall()

    estadias_db = conn.execute("""
        SELECT
            guarderia_estadias.id,
            guarderia_estadias.fecha_hora_ingreso,
            guarderia_estadias.fecha_hora_salida,
            guarderia_estadias.observaciones_ingreso,
            guarderia_estadias.estado,
            guarderia_estadias.total_horas,
            mascotas.nombre AS mascota_nombre,
            clientes.nombre AS cliente_nombre
        FROM guarderia_estadias
        JOIN mascotas ON guarderia_estadias.mascota_id = mascotas.id
        JOIN clientes ON mascotas.cliente_id = clientes.id
        ORDER BY guarderia_estadias.id DESC
    """).fetchall()

    incidencias_db = conn.execute("""
        SELECT
            guarderia_incidencias.id,
            guarderia_incidencias.fecha_hora,
            guarderia_incidencias.tipo,
            guarderia_incidencias.descripcion,
            guarderia_incidencias.atendida,
            guarderia_estadias.id AS estadia_id,
            mascotas.nombre AS mascota_nombre,
            clientes.nombre AS cliente_nombre
        FROM guarderia_incidencias
        JOIN guarderia_estadias ON guarderia_incidencias.estadia_id = guarderia_estadias.id
        JOIN mascotas ON guarderia_estadias.mascota_id = mascotas.id
        JOIN clientes ON mascotas.cliente_id = clientes.id
        ORDER BY guarderia_incidencias.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "recepcionista/guarderia.html",
        nombre=session["nombre"],
        rol=session["rol"],
        mascotas=mascotas_db,
        estadias=estadias_db,
        incidencias=incidencias_db
    )

@app.route("/recepcionista/guarderia/ingreso", methods=["POST"])
def registrar_ingreso_guarderia():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") not in ["recepcionista", "guarderia"]:
        return "No autorizado", 403

    mascota_id = request.form.get("mascota_id", "").strip()
    observaciones_ingreso = request.form.get("observaciones_ingreso", "").strip()

    if not mascota_id:
        flash("Debes seleccionar una mascota.", "error")
        return redirect(url_for("guarderia"))

    conn = get_db_connection()

    estadia_activa = conn.execute("""
        SELECT id FROM guarderia_estadias
        WHERE mascota_id = ? AND estado = 'Activa'
    """, (mascota_id,)).fetchone()

    if estadia_activa:
        conn.close()
        flash("Esta mascota ya tiene una estadía activa.", "error")
        return redirect(url_for("guarderia"))

    fecha_hora_ingreso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        INSERT INTO guarderia_estadias (
            mascota_id,
            fecha_hora_ingreso,
            observaciones_ingreso,
            estado
        )
        VALUES (?, ?, ?, 'Activa')
    """, (mascota_id, fecha_hora_ingreso, observaciones_ingreso))

    conn.commit()
    conn.close()

    flash("Ingreso a guardería registrado correctamente.", "success")
    return redirect(url_for("guarderia"))


@app.route("/recepcionista/guarderia/salida/<int:estadia_id>", methods=["POST"])
def registrar_salida_guarderia(estadia_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") not in ["recepcionista", "guarderia"]:
        return "No autorizado", 403

    conn = get_db_connection()

    estadia = conn.execute("""
        SELECT * FROM guarderia_estadias
        WHERE id = ?
    """, (estadia_id,)).fetchone()

    if not estadia:
        conn.close()
        flash("La estadía no existe.", "error")
        return redirect(url_for("guarderia"))

    if estadia["estado"] != "Activa":
        conn.close()
        flash("Solo se puede registrar salida de una estadía activa.", "error")
        return redirect(url_for("guarderia"))

    fecha_hora_salida = datetime.now()
    fecha_hora_ingreso = datetime.strptime(estadia["fecha_hora_ingreso"], "%Y-%m-%d %H:%M:%S")

    total_horas = round((fecha_hora_salida - fecha_hora_ingreso).total_seconds() / 3600, 2)

    conn.execute("""
        UPDATE guarderia_estadias
        SET fecha_hora_salida = ?, estado = 'Finalizada', total_horas = ?
        WHERE id = ?
    """, (fecha_hora_salida.strftime("%Y-%m-%d %H:%M:%S"), total_horas, estadia_id))

    conn.commit()
    conn.close()

    flash("Salida de guardería registrada correctamente.", "success")
    return redirect(url_for("guarderia"))

@app.route("/recepcionista/guarderia/incidencia/<int:estadia_id>", methods=["POST"])
def registrar_incidencia_guarderia(estadia_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") not in ["recepcionista", "guarderia"]:
        return "No autorizado", 403

    tipo = request.form.get("tipo", "").strip()
    descripcion = request.form.get("descripcion", "").strip()

    if not tipo or not descripcion:
        flash("El tipo y la descripción de la incidencia son obligatorios.", "error")
        return redirect(url_for("guarderia"))

    conn = get_db_connection()

    estadia = conn.execute("""
        SELECT * FROM guarderia_estadias
        WHERE id = ?
    """, (estadia_id,)).fetchone()

    if not estadia:
        conn.close()
        flash("La estadía no existe.", "error")
        return redirect(url_for("guarderia"))

    if estadia["estado"] != "Activa":
        conn.close()
        flash("Solo se pueden registrar incidencias en estadías activas.", "error")
        return redirect(url_for("guarderia"))

    conn.execute("""
        INSERT INTO guarderia_incidencias (estadia_id, tipo, descripcion)
        VALUES (?, ?, ?)
    """, (estadia_id, tipo, descripcion))

    conn.commit()
    conn.close()

    flash("Incidencia registrada correctamente.", "success")
    return redirect(url_for("guarderia"))

# -------------------------------
# FACTURACION
# -------------------------------
@app.route("/recepcionista/facturacion")
def facturacion():
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    conn = get_db_connection()

    mascotas_db = conn.execute("""
        SELECT 
            mascotas.id,
            mascotas.nombre AS mascota_nombre,
            clientes.id AS cliente_id,
            clientes.nombre AS cliente_nombre
        FROM mascotas
        JOIN clientes ON mascotas.cliente_id = clientes.id
        ORDER BY mascotas.nombre ASC
    """).fetchall()

    facturas_db = conn.execute("""
        SELECT
            facturas.id,
            facturas.fecha,
            facturas.estado,
            facturas.total,
            facturas.motivo_anulacion,
            clientes.nombre AS cliente_nombre,
            mascotas.nombre AS mascota_nombre
        FROM facturas
        JOIN clientes ON facturas.cliente_id = clientes.id
        JOIN mascotas ON facturas.mascota_id = mascotas.id
        ORDER BY facturas.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "recepcionista/facturacion.html",
        nombre=session["nombre"],
        rol=session["rol"],
        mascotas=mascotas_db,
        facturas=facturas_db
    )


@app.route("/recepcionista/facturacion/crear", methods=["POST"])
def crear_factura():
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    cliente_id = request.form.get("cliente_id", "").strip()
    mascota_id = request.form.get("mascota_id", "").strip()
    concepto = request.form.get("concepto", "").strip()
    cantidad = request.form.get("cantidad", "").strip()
    precio_unitario = request.form.get("precio_unitario", "").strip()

    if not cliente_id or not mascota_id or not concepto or not cantidad or not precio_unitario:
        flash("Todos los campos de la factura son obligatorios.", "error")
        return redirect(url_for("facturacion"))

    try:
        cantidad = int(cantidad)
        precio_unitario = float(precio_unitario)
    except ValueError:
        flash("Cantidad y precio unitario deben ser numéricos.", "error")
        return redirect(url_for("facturacion"))

    # DECORATOR
    factura_decorada = FacturaBase()

    if concepto == "Consulta":
        factura_decorada = ConsultaDecorator(factura_decorada)
    elif concepto == "Vacuna":
        factura_decorada = VacunaDecorator(factura_decorada)
    elif concepto == "Guardería":
        factura_decorada = GuarderiaDecorator(factura_decorada)
    elif concepto == "Baño":
        factura_decorada = BanoDecorator(factura_decorada)
    elif concepto == "Desparasitación":
        factura_decorada = DesparasitacionDecorator(factura_decorada)

    descripcion_factura = factura_decorada.get_descripcion()

    total_linea = cantidad * precio_unitario

    # FACTORY
    factura = FacturaFactory.crear(cliente_id, mascota_id, "Pendiente", total_linea)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO facturas (cliente_id, mascota_id, estado, total)
        VALUES (?, ?, ?, ?)
    """, (
        factura["cliente_id"],
        factura["mascota_id"],
        factura["estado"],
        factura["total"]
    ))

    factura_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO detalle_factura (factura_id, concepto, cantidad, precio_unitario, total_linea)
        VALUES (?, ?, ?, ?, ?)
    """, (factura_id, descripcion_factura, cantidad, precio_unitario, total_linea))

    conn.commit()
    conn.close()

    notifier.notify("Generar factura", {
        "modulo": "Facturación",
        "detalle": f"Factura ID {factura_id}, cliente ID {cliente_id}, mascota ID {mascota_id}, total {total_linea}"
    })

    flash("Factura generada correctamente.", "success")
    return redirect(url_for("facturacion"))


@app.route("/recepcionista/facturacion/pagar/<int:factura_id>", methods=["POST"])
def registrar_pago_factura(factura_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    metodo_pago = request.form.get("metodo_pago", "").strip()
    

    if not metodo_pago:
        flash("Debes seleccionar un método de pago.", "error")
        return redirect(url_for("facturacion"))

    conn = get_db_connection()
    factura = conn.execute("""
        SELECT * FROM facturas
        WHERE id = ?
    """, (factura_id,)).fetchone()

    if not factura:
        conn.close()
        flash("La factura no existe.", "error")
        return redirect(url_for("facturacion"))

    if factura["estado"] != "Pendiente":
        conn.close()
        flash("Solo se pueden pagar facturas en estado Pendiente.", "error")
        return redirect(url_for("facturacion"))
    
    estrategia = obtener_estrategia_pago(metodo_pago)
    mensaje_pago = estrategia.procesar_pago(factura["total"])

    conn.execute("""
        INSERT INTO pagos (factura_id, metodo_pago)
        VALUES (?, ?)
    """, (factura_id, metodo_pago))

    conn.execute("""
        UPDATE facturas
        SET estado = 'Pagada'
        WHERE id = ?
    """, (factura_id,))

    conn.commit()
    conn.close()

    flash("Pago registrado correctamente.", "success")

    notifier.notify("Registrar pago", {
    "modulo": "Facturación",
    "detalle": f"Factura ID {factura_id}, método {metodo_pago}"
    })

    return redirect(url_for("facturacion"))


@app.route("/recepcionista/facturacion/anular/<int:factura_id>", methods=["POST"])
def anular_factura(factura_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if not rol_requerido("recepcionista"):
        return "No autorizado", 403

    motivo_anulacion = request.form.get("motivo_anulacion", "").strip()

    if not motivo_anulacion:
        flash("El motivo de anulación es obligatorio.", "error")
        return redirect(url_for("facturacion"))

    conn = get_db_connection()
    factura = conn.execute("""
        SELECT * FROM facturas
        WHERE id = ?
    """, (factura_id,)).fetchone()

    if not factura:
        conn.close()
        flash("La factura no existe.", "error")
        return redirect(url_for("facturacion"))

    if factura["estado"] == "Pagada":
        conn.close()
        flash("No se puede anular una factura pagada.", "error")
        return redirect(url_for("facturacion"))

    if factura["estado"] == "Anulada":
        conn.close()
        flash("La factura ya está anulada.", "error")
        return redirect(url_for("facturacion"))

    conn.execute("""
        UPDATE facturas
        SET estado = 'Anulada', motivo_anulacion = ?
        WHERE id = ?
    """, (motivo_anulacion, factura_id))

    conn.commit()
    conn.close()

    flash("Factura anulada correctamente.", "success")
    notifier.notify("Anular factura", {
    "modulo": "Facturación",
    "detalle": f"Factura ID {factura_id}, motivo: {motivo_anulacion}"
    })

    return redirect(url_for("facturacion"))

# -------------------------------
# VETERINARIO
# -------------------------------
@app.route("/veterinario/historias")
def veterinario_historias():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "veterinario":
        return "No autorizado", 403

    conn = get_db_connection()

    historias_db = conn.execute("""
        SELECT 
            historias_clinicas.id,
            historias_clinicas.fecha_creacion,
            mascotas.nombre AS mascota_nombre,
            mascotas.especie,
            mascotas.raza,
            mascotas.edad,
            clientes.nombre AS cliente_nombre
        FROM historias_clinicas
        JOIN mascotas ON historias_clinicas.mascota_id = mascotas.id
        JOIN clientes ON mascotas.cliente_id = clientes.id
        ORDER BY historias_clinicas.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "veterinario/historias.html",
        nombre=session["nombre"],
        historias=historias_db
    )


@app.route("/veterinario/historias/<int:historia_id>")
def veterinario_detalle_historia(historia_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "veterinario":
        return "No autorizado", 403

    conn = get_db_connection()

    historia = conn.execute("""
        SELECT 
            historias_clinicas.id,
            historias_clinicas.fecha_creacion,
            mascotas.nombre AS mascota_nombre,
            mascotas.especie,
            mascotas.raza,
            mascotas.edad,
            clientes.nombre AS cliente_nombre,
            clientes.documento,
            clientes.telefono,
            clientes.correo
        FROM historias_clinicas
        JOIN mascotas ON historias_clinicas.mascota_id = mascotas.id
        JOIN clientes ON mascotas.cliente_id = clientes.id
        WHERE historias_clinicas.id = ?
    """, (historia_id,)).fetchone()

    consultas = conn.execute("""
        SELECT *
        FROM consultas_clinicas
        WHERE historia_id = ?
        ORDER BY fecha DESC, id DESC
    """, (historia_id,)).fetchall()

    citas_relacionadas = conn.execute("""
        SELECT
            citas.id,
            citas.fecha,
            citas.hora,
            citas.servicio,
            citas.estado
        FROM citas
        JOIN historias_clinicas ON historias_clinicas.mascota_id = citas.mascota_id
        WHERE historias_clinicas.id = ?
        ORDER BY citas.fecha DESC, citas.hora DESC
    """, (historia_id,)).fetchall()

    incidencias_guarderia = conn.execute("""
    SELECT
        guarderia_incidencias.id,
        guarderia_incidencias.fecha_hora,
        guarderia_incidencias.tipo,
        guarderia_incidencias.descripcion,
        guarderia_incidencias.atendida,
        guarderia_estadias.id AS estadia_id
    FROM guarderia_incidencias
    JOIN guarderia_estadias ON guarderia_incidencias.estadia_id = guarderia_estadias.id
    JOIN historias_clinicas ON historias_clinicas.mascota_id = guarderia_estadias.mascota_id
    WHERE historias_clinicas.id = ?
    ORDER BY guarderia_incidencias.fecha_hora DESC
""", (historia_id,)).fetchall()

    conn.close()

    if not historia:
        flash("La historia clínica no existe.", "error")
        return redirect(url_for("veterinario_historias"))

    return render_template(
        "veterinario/detalle_historia.html",
        nombre=session["nombre"],
        historia=historia,
        consultas=consultas,
        citas_relacionadas=citas_relacionadas,
        incidencias_guarderia=incidencias_guarderia
    )


@app.route("/veterinario/consultas/crear", methods=["POST"])
def crear_consulta_clinica():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "veterinario":
        return "No autorizado", 403

    historia_id = request.form.get("historia_id", "").strip()
    cita_id = request.form.get("cita_id", "").strip()
    incidencia_id = request.form.get("incidencia_id", "").strip()
    motivo = request.form.get("motivo", "").strip()
    diagnostico = request.form.get("diagnostico", "").strip()
    tratamiento = request.form.get("tratamiento", "").strip()
    observaciones = request.form.get("observaciones", "").strip()

    if not historia_id or not motivo or not diagnostico or not tratamiento:
        flash("Motivo, diagnóstico y tratamiento son obligatorios.", "error")
        return redirect(url_for("veterinario_detalle_historia", historia_id=historia_id))

    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO consultas_clinicas (
            historia_id, fecha, motivo, diagnostico, tratamiento, observaciones
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (historia_id, fecha_actual, motivo, diagnostico, tratamiento, observaciones))

    if cita_id:
        cursor.execute("""
            UPDATE citas
            SET estado = 'Atendida'
            WHERE id = ?
        """, (cita_id,))

    if incidencia_id:
        cursor.execute("""
            UPDATE guarderia_incidencias
            SET atendida = 1
            WHERE id = ?
        """, (incidencia_id,))

    conn.commit()
    conn.close()

    flash("Consulta clínica registrada correctamente.", "success")
    notifier.notify("Registrar consulta clínica", {
    "modulo": "Historia clínica",
    "detalle": f"Historia ID {historia_id}, cita ID {cita_id if cita_id else 'Sin cita'}, incidencia ID {incidencia_id if incidencia_id else 'Sin incidencia'}"
    })

    return redirect(url_for("veterinario_detalle_historia", historia_id=historia_id))


# -------------------------------
# ADMIN - VETERINARIOS
# -------------------------------
@app.route("/admin/veterinarios")
def admin_veterinarios():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    conn = get_db_connection()
    veterinarios = conn.execute("""
        SELECT * FROM veterinarios
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    return render_template(
        "admin/veterinarios.html",
        nombre=session["nombre"],
        veterinarios=veterinarios
    )


@app.route("/admin/veterinarios/crear", methods=["POST"])
def crear_veterinario():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    nombre = request.form.get("nombre", "").strip()
    especialidad = request.form.get("especialidad", "").strip()
    estado = request.form.get("estado", "").strip()

    if not nombre or not estado:
        flash("Nombre y estado son obligatorios.", "error")
        return redirect(url_for("admin_veterinarios"))

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO veterinarios (nombre, especialidad, estado)
        VALUES (?, ?, ?)
    """, (nombre, especialidad, estado))
    conn.commit()
    conn.close()

    flash("Veterinario registrado correctamente.", "success")
    return redirect(url_for("admin_veterinarios"))

# -------------------------------
# ADMIN - EMPLEADOS
# -------------------------------
@app.route("/admin/empleados")
def admin_empleados():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    conn = get_db_connection()
    empleados_db = conn.execute("""
        SELECT * FROM empleados
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    return render_template(
        "admin/empleados.html",
        nombre=session["nombre"],
        empleados=empleados_db
    )


@app.route("/admin/empleados/crear", methods=["POST"])
def crear_empleado():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    nombre = request.form.get("nombre", "").strip()
    usuario = request.form.get("usuario", "").strip()
    password = request.form.get("password", "").strip()
    rol = request.form.get("rol", "").strip()
    estado = request.form.get("estado", "").strip()

    if not nombre or not usuario or not password or not rol or not estado:
        flash("Todos los campos del empleado son obligatorios.", "error")
        return redirect(url_for("admin_empleados"))
    
    empleado = EmpleadoFactory.crear(nombre, usuario, password, rol, estado)

    conn = get_db_connection()

    existe = conn.execute("""
        SELECT id FROM empleados
        WHERE usuario = ?
    """, (empleado["usuario"],)).fetchone()

    if existe:
        conn.close()
        flash("Ya existe un empleado con ese usuario.", "error")
        return redirect(url_for("admin_empleados"))

    conn.execute("""
    INSERT INTO empleados (nombre, usuario, password, rol, estado)
    VALUES (?, ?, ?, ?, ?)
    """, (
        empleado["nombre"],
        empleado["usuario"],
        empleado["password"],
        empleado["rol"],
        empleado["estado"]
    ))

    conn.commit()
    conn.close()

    flash("Empleado creado correctamente.", "success")
    return redirect(url_for("admin_empleados"))


@app.route("/admin/empleados/cambiar-estado/<int:empleado_id>", methods=["POST"])
def cambiar_estado_empleado(empleado_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    conn = get_db_connection()

    empleado = conn.execute("""
        SELECT * FROM empleados
        WHERE id = ?
    """, (empleado_id,)).fetchone()

    if not empleado:
        conn.close()
        flash("El empleado no existe.", "error")
        return redirect(url_for("admin_empleados"))

    nuevo_estado = "Inactivo" if empleado["estado"] == "Activo" else "Activo"

    conn.execute("""
        UPDATE empleados
        SET estado = ?
        WHERE id = ?
    """, (nuevo_estado, empleado_id))

    conn.commit()
    conn.close()

    flash("Estado del empleado actualizado correctamente.", "success")
    return redirect(url_for("admin_empleados"))

# -------------------------------
# ADMIN - CLIENTES
# -------------------------------
@app.route("/admin/clientes")
def admin_clientes():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    busqueda = request.args.get("q", "").strip()

    conn = get_db_connection()

    if busqueda:
        clientes_db = conn.execute("""
            SELECT *
            FROM clientes
            WHERE nombre LIKE ? OR documento LIKE ? OR correo LIKE ?
            ORDER BY id DESC
        """, (f"%{busqueda}%", f"%{busqueda}%", f"%{busqueda}%")).fetchall()
    else:
        clientes_db = conn.execute("""
            SELECT *
            FROM clientes
            ORDER BY id DESC
        """).fetchall()

    conn.close()

    return render_template(
        "admin/clientes.html",
        nombre=session["nombre"],
        clientes=clientes_db,
        busqueda=busqueda
    )


@app.route("/admin/clientes/cambiar-estado/<int:cliente_id>", methods=["POST"])
def admin_cambiar_estado_cliente(cliente_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    conn = get_db_connection()

    cliente = conn.execute("""
        SELECT * FROM clientes
        WHERE id = ?
    """, (cliente_id,)).fetchone()

    if not cliente:
        conn.close()
        flash("El cliente no existe.", "error")
        return redirect(url_for("admin_clientes"))

    nuevo_estado = "Inactivo" if cliente["estado"] == "Activo" else "Activo"

    conn.execute("""
        UPDATE clientes
        SET estado = ?
        WHERE id = ?
    """, (nuevo_estado, cliente_id))

    conn.commit()
    conn.close()

    flash("Estado del cliente actualizado correctamente.", "success")
    return redirect(url_for("admin_clientes"))

# -------------------------------
# ADMIN - MASCOTAS
# -------------------------------
@app.route("/admin/mascotas")
def admin_mascotas():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    busqueda = request.args.get("q", "").strip()

    conn = get_db_connection()

  
    if busqueda:
        mascotas_db = conn.execute("""
            SELECT mascotas.*, clientes.nombre AS cliente_nombre
            FROM mascotas
            JOIN clientes ON mascotas.cliente_id = clientes.id
            WHERE mascotas.nombre LIKE ?
               OR mascotas.especie LIKE ?
               OR mascotas.raza LIKE ?
               OR clientes.nombre LIKE ?
            ORDER BY mascotas.id DESC
        """, (
            f"%{busqueda}%",
            f"%{busqueda}%",
            f"%{busqueda}%",
            f"%{busqueda}%"
        )).fetchall()
    else:
        mascotas_db = conn.execute("""
            SELECT mascotas.*, clientes.nombre AS cliente_nombre
            FROM mascotas
            JOIN clientes ON mascotas.cliente_id = clientes.id
            ORDER BY mascotas.id DESC
        """).fetchall()

 
    clientes_db = conn.execute("""
        SELECT * FROM clientes
        ORDER BY nombre ASC
    """).fetchall()

    conn.close()

    return render_template(
        "admin/mascotas.html",
        nombre=session["nombre"],
        mascotas=mascotas_db,
        busqueda=busqueda,
        clientes=clientes_db   
    )




@app.route("/admin/mascotas/cambiar-estado/<int:mascota_id>", methods=["POST"])
def admin_cambiar_estado_mascota(mascota_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    conn = get_db_connection()

    mascota = conn.execute("""
        SELECT * FROM mascotas
        WHERE id = ?
    """, (mascota_id,)).fetchone()

    if not mascota:
        conn.close()
        flash("La mascota no existe.", "error")
        return redirect(url_for("admin_mascotas"))

    nuevo_estado = "Inactivo" if mascota["estado"] == "Activo" else "Activo"

    conn.execute("""
        UPDATE mascotas
        SET estado = ?
        WHERE id = ?
    """, (nuevo_estado, mascota_id))

    conn.commit()
    conn.close()

    flash("Estado de la mascota actualizado correctamente.", "success")
    return redirect(url_for("admin_mascotas"))

@app.route("/admin/mascotas/editar/<int:mascota_id>", methods=["POST"])
def admin_editar_mascota(mascota_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    nombre = request.form.get("nombre", "").strip()
    especie = request.form.get("especie", "").strip()
    raza = request.form.get("raza", "").strip()
    edad = request.form.get("edad", "").strip()
    cliente_id = request.form.get("cliente_id", "").strip()

    if not nombre or not especie or not cliente_id:
        flash("Nombre, especie y cliente son obligatorios.", "error")
        return redirect(url_for("admin_mascotas"))

    conn = get_db_connection()
    conn.execute("""
        UPDATE mascotas
        SET nombre = ?, especie = ?, raza = ?, edad = ?, cliente_id = ?
        WHERE id = ?
    """, (nombre, especie, raza, edad if edad else None, cliente_id, mascota_id))
    conn.commit()
    conn.close()

    flash("Mascota actualizada correctamente.", "success")
    return redirect(url_for("admin_mascotas"))


# -------------------------------
# ADMIN - CITAS
# -------------------------------
@app.route("/admin/citas")
def admin_citas():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    busqueda = request.args.get("q", "").strip()

    conn = get_db_connection()

    if busqueda:
        citas_db = conn.execute("""
            SELECT
                citas.*,
                mascotas.nombre AS mascota_nombre,
                clientes.nombre AS cliente_nombre,
                veterinarios.nombre AS veterinario_nombre
            FROM citas
            JOIN mascotas ON citas.mascota_id = mascotas.id
            JOIN clientes ON mascotas.cliente_id = clientes.id
            LEFT JOIN veterinarios ON citas.veterinario_id = veterinarios.id
            WHERE mascotas.nombre LIKE ?
               OR clientes.nombre LIKE ?
               OR citas.fecha LIKE ?
               OR citas.servicio LIKE ?
            ORDER BY citas.fecha DESC, citas.hora ASC
        """, (f"%{busqueda}%", f"%{busqueda}%", f"%{busqueda}%", f"%{busqueda}%")).fetchall()
    else:
        citas_db = conn.execute("""
            SELECT
                citas.*,
                mascotas.nombre AS mascota_nombre,
                clientes.nombre AS cliente_nombre,
                veterinarios.nombre AS veterinario_nombre
            FROM citas
            JOIN mascotas ON citas.mascota_id = mascotas.id
            JOIN clientes ON mascotas.cliente_id = clientes.id
            LEFT JOIN veterinarios ON citas.veterinario_id = veterinarios.id
            ORDER BY citas.fecha DESC, citas.hora ASC
        """).fetchall()

    conn.close()

    return render_template(
        "admin/citas.html",
        nombre=session["nombre"],
        citas=citas_db,
        busqueda=busqueda
    )

@app.route("/admin/citas/cambiar-estado/<int:cita_id>", methods=["POST"])
def admin_cambiar_estado_cita(cita_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    nuevo_estado = request.form.get("estado", "").strip()

    conn = get_db_connection()

    conn.execute("""
        UPDATE citas
        SET estado = ?
        WHERE id = ?
    """, (nuevo_estado, cita_id))

    conn.commit()
    conn.close()

    flash("Estado de la cita actualizado correctamente.", "success")
    return redirect(url_for("admin_citas"))


# -------------------------------
# ADMIN - FACTURAS
# -------------------------------
@app.route("/admin/facturas")
def admin_facturas():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    fecha = request.args.get("fecha", "").strip()
    estado = request.args.get("estado", "").strip()
    cliente = request.args.get("cliente", "").strip()

    conn = get_db_connection()

    query = """
        SELECT
            facturas.*,
            clientes.nombre AS cliente_nombre,
            mascotas.nombre AS mascota_nombre
        FROM facturas
        JOIN clientes ON facturas.cliente_id = clientes.id
        JOIN mascotas ON facturas.mascota_id = mascotas.id
        WHERE 1=1
    """

    params = []

    if fecha:
        query += " AND date(facturas.fecha) = ?"
        params.append(fecha)

    if estado:
        query += " AND facturas.estado = ?"
        params.append(estado)

    if cliente:
        query += " AND clientes.nombre LIKE ?"
        params.append(f"%{cliente}%")

    query += " ORDER BY facturas.id DESC"

    facturas_db = conn.execute(query, params).fetchall()

    conn.close()

    return render_template(
        "admin/facturas.html",
        nombre=session["nombre"],
        facturas=facturas_db,
        fecha=fecha,
        estado=estado,
        cliente=cliente
    )

@app.route("/admin/facturas/<int:factura_id>")
def admin_detalle_factura(factura_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    conn = get_db_connection()

    factura = conn.execute("""
        SELECT
            facturas.*,
            clientes.nombre AS cliente_nombre,
            clientes.documento AS cliente_documento,
            clientes.telefono AS cliente_telefono,
            clientes.correo AS cliente_correo,
            mascotas.nombre AS mascota_nombre
        FROM facturas
        JOIN clientes ON facturas.cliente_id = clientes.id
        JOIN mascotas ON facturas.mascota_id = mascotas.id
        WHERE facturas.id = ?
    """, (factura_id,)).fetchone()

    detalle = conn.execute("""
        SELECT *
        FROM detalle_factura
        WHERE factura_id = ?
        ORDER BY id ASC
    """, (factura_id,)).fetchall()

    pagos = conn.execute("""
        SELECT *
        FROM pagos
        WHERE factura_id = ?
        ORDER BY id DESC
    """, (factura_id,)).fetchall()

    conn.close()

    if not factura:
        flash("La factura no existe.", "error")
        return redirect(url_for("admin_facturas"))

    return render_template(
        "admin/detalle_factura.html",
        nombre=session["nombre"],
        factura=factura,
        detalle=detalle,
        pagos=pagos
    )
# -------------------------------
# ADMIN - AUDITORIA
# -------------------------------
@app.route("/admin/auditoria")
def admin_auditoria():
    if not login_requerido():
        return redirect(url_for("login"))

    if session.get("rol") != "admin":
        return "No autorizado", 403

    busqueda = request.args.get("q", "").strip()

    conn = get_db_connection()

    if busqueda:
        registros = conn.execute("""
            SELECT *
            FROM auditoria
            WHERE usuario_nombre LIKE ?
               OR usuario_rol LIKE ?
               OR accion LIKE ?
               OR modulo LIKE ?
               OR detalle LIKE ?
            ORDER BY id DESC
        """, (
            f"%{busqueda}%",
            f"%{busqueda}%",
            f"%{busqueda}%",
            f"%{busqueda}%",
            f"%{busqueda}%"
        )).fetchall()
    else:
        registros = conn.execute("""
            SELECT *
            FROM auditoria
            ORDER BY id DESC
            LIMIT 200
        """).fetchall()

    conn.close()

    return render_template(
        "admin/auditoria.html",
        nombre=session["nombre"],
        registros=registros,
        busqueda=busqueda
    )

if __name__ == "__main__":
    app.run(debug=True)