Se preparó un README orientado al estado real del proyecto: backend en Django, frontend en Nuxt 3 SPA con Vuetify, conexión local a PostgreSQL y pruebas API por módulos. El arranque en desarrollo apunta a `config.settings.dev`, el frontend consume por defecto `http://127.0.0.1:8000/api/v1`, y ya existen pruebas para auth, perfiles, disponibilidad, ciclo de vida de citas, pagos y auditoría. También se detectó un punto delicado: el repositorio empaquetado incluye `.nuxt` y archivos en `backend/media`, pero el `.gitignore` actual no los excluye todavía.     

A continuación va el contenido listo para copiar y pegar como `README_DESARROLLO_PRUEBAS.md`:

````md
# README de desarrollo, pruebas y diagnóstico — Ubemedicos

## 1. Objetivo

Este documento define cómo debe trabajar el desarrollador en ambiente de desarrollo para:

- levantar el proyecto sin contaminar el repositorio,
- ejecutar pruebas mínimas antes de subir cambios,
- revisar qué artefactos **no** deben subirse,
- usar herramientas y comandos de diagnóstico cuando algo falle.

---

## 2. Stack actual del proyecto

El proyecto trabaja con la siguiente base técnica:

- **Backend:** Django
- **Base de datos:** PostgreSQL
- **Frontend:** Nuxt 3 + Vue 3 + Vuetify
- **Ambiente local de Django:** `config.settings.dev`
- **API base por defecto:** `http://127.0.0.1:8000/api/v1`

---

## 3. Preparación inicial del ambiente de desarrollo

## 3.1. Variables de entorno

El desarrollador debe crear un archivo `.env` a partir de `.env.example`.

Ejemplo base:

```env
DJANGO_SETTINGS_MODULE=config.settings.dev
DJANGO_SECRET_KEY=changeme-dev-secret
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

DB_NAME=appdb
DB_USER=appuser
DB_PASSWORD=apppass
DB_HOST=127.0.0.1
DB_PORT=5432
````

---

## 3.2. Backend

Desde la raíz del proyecto:

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 3.3. Base de datos PostgreSQL en Docker

El desarrollador debe levantar solo PostgreSQL con el compose existente:

```bash
docker compose -f infra/docker-compose.yml up -d
```

Verificación:

```bash
docker compose -f infra/docker-compose.yml ps
```

Si todo está correcto, el contenedor de PostgreSQL debe aparecer en estado saludable o iniciando.

---

## 3.4. Migraciones y datos demo

El desarrollador debe ejecutar:

```bash
cd backend
python manage.py migrate
python manage.py seed_initial_data
```

Esto permite disponer de usuarios demo, especialidades y datos básicos para pruebas manuales.

---

## 3.5. Levantar backend

Desde `backend/`:

```bash
python manage.py runserver
```

El backend debe quedar disponible en:

```text
http://127.0.0.1:8000
```

---

## 3.6. Levantar frontend

Desde `web_frontend/`:

```bash
npm install
npm run dev
```

El frontend debe tomar la URL de la API desde:

```env
NUXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Si no se define, usará esa misma por defecto.

---

## 4. Usuarios demo recomendados para pruebas

Después de ejecutar `seed_initial_data`, el desarrollador puede usar cuentas demo como referencia:

* `superadmin@demo.local`
* `admin@demo.local`
* `privacy@demo.local`
* `paciente@demo.local`
* `profesional@demo.local`

Se recomienda revisar las credenciales exactas definidas por el comando seed antes de compartir capturas o reportes.

---

## 5. Qué NO debe subirse al repositorio

## 5.1. Nunca debe subirse

* `.env`
* `.venv/`
* `__pycache__/`
* archivos compilados temporales de Python
* `dist/`
* `build/`
* **`.nuxt/`**
* **`backend/media/`**
* dumps improvisados de base de datos
* archivos PDF de pruebas reales
* capturas o archivos con datos sensibles
* backups manuales creados solo para depuración

---

## 5.2. Advertencia importante

En el estado actual del proyecto, el desarrollador debe revisar el `.gitignore` porque ya ignora:

* `.venv/`
* `__pycache__/`
* `.env`
* `dist/`
* `build/`

pero todavía debe controlarse manualmente que no se suban:

* `.nuxt/`
* `backend/media/`

Por seguridad y limpieza del repositorio, se recomienda agregar estas entradas al `.gitignore` antes de abrir un PR:

```gitignore
web_frontend/.nuxt/
backend/media/
*.log
*.sqlite3
```

---

## 6. Qué sí debe revisarse antes de subir cambios

Antes de subir cambios, el desarrollador debe validar lo siguiente:

### 6.1. Revisión técnica mínima

* que el backend levante sin traceback,
* que el frontend levante sin errores fatales,
* que la base de datos esté accesible,
* que no existan imports rotos,
* que no existan variables hardcodeadas con rutas personales,
* que no existan secretos en archivos versionados.

### 6.2. Revisión funcional mínima

* que login funcione,
* que logout funcione,
* que `/auth/me` funcione con token,
* que el rol redirija o habilite la vista correcta,
* que no existan errores 500 en operaciones básicas,
* que las respuestas de error sean coherentes.

### 6.3. Revisión de persistencia

* que una creación realmente inserte datos,
* que una edición realmente actualice datos,
* que un delete realmente quite o desactive según el caso,
* que no se rompan relaciones por cambios parciales.

### 6.4. Revisión visual mínima

* que no existan pantallas en blanco,
* que no existan errores visibles de consola en navegador,
* que formularios invaliden correctamente,
* que los listados carguen y no queden en loading infinito.

---

## 7. Suite mínima de pruebas que debe ejecutarse

## 7.1. Prueba completa del backend

Desde `backend/`:

```bash
python manage.py test
```

---

## 7.2. Pruebas por módulo

Cuando el cambio sea puntual, el desarrollador puede ejecutar por bloques:

### Auth y usuarios

```bash
python manage.py test apps.users.tests_api
```

### Catálogos

```bash
python manage.py test apps.catalogs.tests_api
```

### Pacientes

```bash
python manage.py test apps.patients.tests_api
```

### Perfil profesional

```bash
python manage.py test apps.professionals.tests_api_profile
```

### Validación administrativa de profesionales

```bash
python manage.py test apps.professionals.tests_api_admin
```

### Disponibilidad del profesional

```bash
python manage.py test apps.appointments.tests_api
```

### Bloqueos de disponibilidad

```bash
python manage.py test apps.appointments.tests_api_blocks
```

### Reserva y flujo de citas

```bash
python manage.py test apps.appointments.tests_api_booking
python manage.py test apps.appointments.tests_api_lifecycle
```

### Pagos

```bash
python manage.py test apps.payments.tests_api
```

### Auditoría

```bash
python manage.py test apps.audits.tests_api
```

---

## 8. Checklist funcional obligatoria en desarrollo

## 8.1. Autenticación

El desarrollador debe probar:

* login válido,
* login inválido,
* `GET /api/v1/auth/me`,
* `GET /api/v1/users/me`,
* logout.

---

## 8.2. Registro

El desarrollador debe probar:

* registro de paciente,
* registro de profesional,
* creación del perfil relacionado,
* validación de campos obligatorios,
* mensajes de error limpios cuando falten datos.

---

## 8.3. Paciente

El desarrollador debe probar:

* ver su perfil,
* editar su perfil,
* validación de fecha de nacimiento,
* restricción de acceso a rutas que no le correspondan.

---

## 8.4. Profesional

El desarrollador debe probar:

* ver su perfil,
* editar su perfil,
* validar especialidad activa,
* validar licencia duplicada,
* cargar y reemplazar documentos,
* consultar estado de verificación,
* enviar solicitud de verificación.

---

## 8.5. Administrador de validación

El desarrollador debe probar:

* listar solicitudes,
* ver detalle,
* asignar revisión,
* iniciar revisión,
* revisar documento,
* solicitar corrección,
* aprobar,
* rechazar,
* descargar documento.

---

## 8.6. Disponibilidad del profesional

El desarrollador debe probar:

* listar disponibilidad,
* crear slot,
* editar slot,
* validar traslapes,
* eliminar slot si aplica.

---

## 8.7. Bloques de agenda

El desarrollador debe probar:

* listar bloques,
* crear bloque,
* validar cruce con otro bloque,
* validar cruce con cita activa,
* editar bloque,
* eliminar bloque.

---

## 8.8. Citas

El desarrollador debe probar:

* búsqueda pública de profesionales,
* slots disponibles,
* creación de cita por paciente,
* cancelación por paciente,
* confirmación por profesional,
* cancelación por profesional,
* completar cita,
* marcar no-show.

---

## 8.9. Pagos demo

El desarrollador debe probar:

* crear intento de pago,
* evitar duplicación mientras esté pendiente,
* marcar pago exitoso,
* marcar pago fallido,
* reembolso,
* reembolso con cancelación de cita,
* verificar sincronización entre pago y cita.

---

## 8.10. Auditoría

El desarrollador debe probar:

* listado de logs por admin,
* acceso por privacy auditor,
* exportación CSV,
* filtros,
* detalle de evento,
* vista de trazabilidad propia por usuario,
* restricciones por rol.

---

## 9. Herramientas de diagnóstico recomendadas

## 9.1. Backend

Herramientas recomendadas:

* consola del backend,
* `python manage.py test`,
* `python manage.py shell`,
* logs del servidor de desarrollo,
* trazas de excepción completas.

Comandos útiles:

```bash
python manage.py check
python manage.py showmigrations
python manage.py shell
```

---

## 9.2. Base de datos

Herramientas recomendadas:

* `docker compose`
* `docker logs`
* `psql`
* cliente visual como DBeaver o pgAdmin

Comandos útiles:

```bash
docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.yml logs -f db
docker exec -it ubemedicos_postgres psql -U appuser -d appdb
```

Consultas útiles dentro de PostgreSQL:

```sql
\dt
SELECT NOW();
SELECT COUNT(*) FROM users_user;
SELECT COUNT(*) FROM professionals_professionalprofile;
SELECT COUNT(*) FROM appointments_appointment;
SELECT COUNT(*) FROM payments_payment;
```

---

## 9.3. Frontend

Herramientas recomendadas:

* DevTools del navegador
* pestaña **Network**
* pestaña **Console**
* pestaña **Application / Cookies**
* Vue DevTools si está disponible

Debe revisarse especialmente:

* si existe la cookie `access_token`,
* si la petición sale con header `Authorization: Bearer ...`,
* si la URL base es correcta,
* si hay errores CORS,
* si hay errores 401, 403, 409 o 500.

---

## 9.4. API manual

Herramientas recomendadas:

* Postman
* Insomnia
* Bruno
* `curl`

Ejemplo de login:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"admin@demo.local\",\"password\":\"Admin123!\"}"
```

Ejemplo de consulta autenticada:

```bash
curl http://127.0.0.1:8000/api/v1/auth/me \
  -H "Authorization: Bearer TOKEN_AQUI"
```

---

## 10. Diagnóstico rápido por tipo de error

## 10.1. Error 401

Posibles causas:

* no se envió token,
* token expirado,
* cookie ausente,
* login no completado.

Debe revisarse:

* cookie `access_token`,
* header `Authorization`,
* respuesta del login.

---

## 10.2. Error 403

Posibles causas:

* el usuario no tiene el rol correcto.

Debe revisarse:

* rol del usuario,
* ruta accedida,
* endpoint exacto,
* pantalla que intenta consumirlo.

---

## 10.3. Error 409

Posibles causas:

* duplicidad de licencia,
* traslape de horario,
* conflicto de bloque,
* conflicto de estado de negocio.

Debe revisarse:

* payload enviado,
* datos existentes en base,
* lógica de validación del módulo.

---

## 10.4. Error 500

Posibles causas:

* excepción de backend,
* migraciones faltantes,
* tabla inexistente,
* dato nulo inesperado,
* código desalineado entre frontend y backend.

Debe revisarse:

* consola de Django,
* migraciones,
* estado de PostgreSQL,
* payload exacto que generó el fallo.

---

## 10.5. Frontend carga pero no trae datos

Posibles causas:

* `apiBaseUrl` incorrecto,
* backend apagado,
* token no enviado,
* error de CORS,
* endpoint mal escrito.

Debe revisarse:

* Network del navegador,
* respuesta real del backend,
* URL final de la petición,
* consola del navegador.

---

## 11. Flujo de trabajo recomendado antes de abrir PR

El desarrollador debe seguir este orden:

1. levantar PostgreSQL,
2. levantar backend,
3. levantar frontend,
4. ejecutar prueba manual del flujo afectado,
5. ejecutar pruebas automáticas del módulo afectado,
6. ejecutar revisión visual mínima,
7. revisar `git status`,
8. confirmar que no se estén subiendo `.env`, `.nuxt`, `media`, logs o archivos temporales,
9. recién entonces preparar commit y PR.

---

## 12. Revisión de `git status` obligatoria

Antes de hacer commit, el desarrollador debe ejecutar:

```bash
git status
```

Y debe confirmar que **no** aparezcan:

* `.env`
* `web_frontend/.nuxt/`
* `backend/media/`
* archivos PDF
* logs
* dumps temporales
* archivos de editor accidentales

---

## 13. Regla de oro para desarrollo

Si un cambio toca backend y frontend al mismo tiempo, el desarrollador no debe asumir que “compila” significa que “funciona”.

Siempre debe validarse:

* respuesta HTTP,
* persistencia en base,
* render en pantalla,
* permisos por rol,
* ausencia de errores en consola y logs.

---

## 14. Estado mínimo para considerar un cambio como revisable

Un cambio puede considerarse listo para revisión solo si:

* el backend arranca,
* el frontend arranca,
* no hay error 500 en el flujo tocado,
* la base responde,
* el flujo afectado fue probado manualmente,
* al menos el módulo afectado pasó sus pruebas automáticas,
* no se están subiendo artefactos temporales o sensibles.

---

```

Además conviene dejar una advertencia operativa: en el material del repo empaquetado sí aparecen pruebas específicas para disponibilidad, bloques, ciclo de vida de citas, pagos y auditoría, por lo que la revisión en desarrollo debería girar alrededor de esos módulos primero, no solo de login y registro. :contentReference[oaicite:5]{index=5} :contentReference[oaicite:6]{index=6}

Se puede entregar también una segunda versión más corta, tipo “README ejecutivo de una sola página”, para que el programador junior la use como checklist diaria.
```
