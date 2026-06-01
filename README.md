# DOG PETS - Sistema de Gestión Veterinaria

## Descripción

DOG PETS es un sistema web desarrollado en Flask para la gestión de una clínica veterinaria.

Permite administrar:

- Clientes
- Mascotas
- Citas
- Historias clínicas
- Guardería
- Facturación
- Pagos
- Auditoría

## Tecnologías utilizadas

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- ReportLab

## Patrones de diseño implementados

- Singleton
- Factory
- Strategy
- Observer
- Decorator

## Instalación

```bash
git clone https://github.com/camivelez31/Dog-Pets---sistema-veterinario.git
cd Dog-Pets---sistema-veterinario
pip install flask
pip install reportlab
python app.py
```

Abrir en:

```
http://127.0.0.1:5000
```

## Historial de desarrollo

- Crear módulo de citas
- Módulo de citas implementado con gestión de agenda y disponibilidad veterinaria.
- Implementación del módulo de auditoría para registrar acciones críticas del sistema.
- Implementación del patrón Factory para la creación de mascotas, empleados y facturas.
- Desarrollo del módulo de facturación con generación de facturas, detalle y registro de pagos.
- Correcciones en la gestión de mascotas, incluyendo edición, activación e inactivación.

## Documentación 

### Descripción general

DOG PETS es un sistema web para la gestión de una clínica veterinaria. Permite administrar clientes, mascotas, citas, historias clínicas, guardería, facturación, pagos y auditoría.

### Funcionalidades principales

- Registro y gestión de clientes.
- Registro y gestión de mascotas.
- Creación, reprogramación y cancelación de citas.
- Consulta y actualización de historias clínicas.
- Registro de consultas veterinarias.
- Gestión de guardería e incidencias.
- Generación de facturas.
- Registro de pagos.
- Auditoría de acciones críticas.

### Roles del sistema

#### Administrador
- Gestión de empleados.
- Gestión de veterinarios.
- Consulta de auditoría.
- Consulta de facturación.

#### Recepcionista
- Registro de clientes.
- Registro de mascotas.
- Gestión de citas.
- Generación de facturas.
- Registro de pagos.
- Consulta de historias clínicas.

#### Veterinario
- Consulta de agenda.
- Registro de consultas clínicas.
- Consulta de historias clínicas.
- Atención de incidencias médicas.

#### Guardería
- Registro de ingresos y salidas.
- Registro de incidencias.
- Seguimiento de mascotas hospedadas.

### Arquitectura

Frontend:
- HTML
- CSS
- JavaScript

Backend:
- Python
- Flask

Base de datos:
- SQLite

### Patrones de diseño implementados

- Singleton
- Factory
- Strategy
- Observer
- Decorator

## Integrantes

- Maria Camila Vélez Mazo
- Sandra Milena Londoño Loaiza
- Jesús David Meza Montiel
