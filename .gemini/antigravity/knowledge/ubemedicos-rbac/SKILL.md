---
name: ubemedicos-rbac
description: Detalles sobre el control de acceso basado en roles (RBAC) tanto en el backend como en el frontend. Úsalo cuando el usuario necesite definir permisos, configurar redirecciones tras el login o entender los tipos de cuenta disponibles.
---

# Ubemedicos RBAC (Roles & Permissions)

## Roles Definidos (Backend)
El sistema utiliza el campo `primary_role` en el modelo `User` para determinar el alcance del usuario.

| Rol | Descripción | Target Path (Frontend) |
| :--- | :--- | :--- |
| `super_admin` | Acceso total al sistema y base de datos. | `/admin` |
| `admin` | Personal administrativo general. | `/admin` |
| `admin_validation` | Encargado de validar médicos y pagos. | `/admin` |
| `admin_privacy` | Auditor de logs y privacidad. | `/admin/privacy/access-logs` |
| `privacy_auditor` | Rol específico para auditoría de eventos. | `/admin/privacy/access-logs` |
| `professional` | Médicos/Profesionales de la salud. | `/professional` |
| `patient` | Pacientes/Usuarios finales. | `/patient/appointments` |

## Control de Acceso en Backend
- **Decorador**: `@api_roles_required('rol1', 'rol2')` en las vistas de Django.
- **Lugar**: Generalmente en `apps.core.decorators`.
- **Efecto**: Si el usuario no tiene uno de los roles, devuelve `403 Forbidden`.

## Lógica de Redirección (Frontend)
La función `resolveHomeByRole(role)` en `pages/login.vue` centraliza hacia dónde se envía al usuario después de autenticarse con éxito.
- Es vital mantener esta lógica sincronizada con las rutas protegidas.

## Menús y Navegación
- Las barras laterales (`Sidebar`) deben filtrar sus elementos basándose en el rol del usuario actual.
- No mostrar enlaces a `/admin` si el rol es `patient`.
