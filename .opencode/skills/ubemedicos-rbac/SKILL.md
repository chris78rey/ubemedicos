---
name: ubemedicos-rbac
description: Detalles sobre el control de acceso basado en roles (RBAC) tanto en el backend como en el frontend. 脷salo cuando el usuario necesite definir permisos, configurar redirecciones tras el login o entender los tipos de cuenta disponibles.
---

# Ubemedicos RBAC (Roles & Permissions)

## Roles Definidos (Backend)
El sistema utiliza el campo `primary_role` en el modelo `User` para determinar el alcance del usuario.

| Rol | Descripci贸n | Target Path (Frontend) |
| :--- | :--- | :--- |
| `super_admin` | Acceso total al sistema y base de datos. | `/admin` |
| `admin` | Personal administrativo general. | `/admin` |
| `admin_validation` | Encargado de validar m茅dicos y pagos. | `/admin` |
| `admin_privacy` | Auditor de logs y privacidad. | `/admin/privacy/access-logs` |
| `privacy_auditor` | Rol espec铆fico para auditor铆a de eventos. | `/admin/privacy/access-logs` |
| `professional` | M茅dicos/Profesionales de la salud. | `/professional` |
| `patient` | Pacientes/Usuarios finales. | `/patient/appointments` |

## Control de Acceso en Backend
- **Decorador**: `@api_roles_required('rol1', 'rol2')` en las vistas de Django.
- **Lugar**: Generalmente en `apps.core.decorators`.
- **Efecto**: Si el usuario no tiene uno de los roles, devuelve `403 Forbidden`.

## L贸gica de Redirecci贸n (Frontend)
La funci贸n `resolveHomeByRole(role)` en `pages/login.vue` centraliza hacia d贸nde se env铆a al usuario despu茅s de autenticarse con 茅xito.
- Es vital mantener esta l贸gica sincronizada con las rutas protegidas.

## Men煤s y Navegaci贸n
- Las barras laterales (`Sidebar`) deben filtrar sus elementos bas谩ndose en el rol del usuario actual.
- No mostrar enlaces a `/admin` si el rol es `patient`.

## Creaci髇 de Cuentas Administrativas
A diferencia de los pacientes y profesionales, no existe un flujo de registro p鷅lico para roles administrativos.
- **M閠odo**: La creaci髇 de nuevos administradores (admin, privacy_auditor, etc.) se realiza exclusivamente a trav閟 del **Django Admin del backend**.
- **Requisito**: Solo usuarios con privilegios de super_admin (is_superuser=True) pueden dar de alta a otros miembros del equipo administrativo.
- **Proceso**:
    1. Acceder al panel nativo de Django.
    2. Crear usuario con el CustomUserCreationForm.
    3. Asignar el primary_role correspondiente para asegurar que el frontend lo redirija a la secci髇 correcta tras el login.
