---
name: ubemedicos-frontend-guide
description: Guía de estándares y arquitectura del frontend en Nuxt 3 y Vuetify. Úsalo cuando el usuario pida crear nuevas páginas, componentes visuales, manejar la autenticación en el cliente o entender la estructura de carpetas en web_frontend/.
---

# Ubemedicos Frontend Guide

## Tech Stack
- **Framework**: Nuxt 3 (SSR: false - Modo SPA).
- **UI Library**: Vuetify 3 con Material Design Icons (`mdi`).
- **Styling**: SASS (Vuetify) y CSS scoped en componentes.
- **Language**: TypeScript (`lang=ts`).
- **Package Manager**: **Bun** (Recomendado por su velocidad en este entorno).

## Configuración Base
El proyecto requiere los archivos `package.json`, `nuxt.config.ts` y el plugin `plugins/vuetify.ts` en la raíz de `web_frontend/`. Si faltan, deben ser restaurados siguiendo el estándar de Nuxt 3 + Vuetify.

## Carpeta `web_frontend/`
- **`pages/`**: Estructura de rutas basada en archivos.
  - `/` -> `pages/index.vue` (Portal público/Buscador).
  - `/login` -> `pages/login.vue`.
  - `/register` -> `pages/register.vue`.
  - `/admin/` -> Dashboard administrativo.
  - `/professional/` -> Dashboard del profesional.
  - `/patient/` -> Portal del paciente.
- **`layouts/`**: Plantillas generales (default, empty, admin_layout).
- **`plugins/`**: Configuración de Vuetify y otras utilidades.
- **`public/`**: Assets estáticos (imágenes, logos).

## Estándares de Diseño
- **Estética Premium**: Usar componentes de Vuetify (`v-card`, `v-btn`, `v-text-field`) con elevación, bordes redondeados (`rounded="xl"` o `"lg"`) y espaciado consistente.
- **Iconografía**: Usar `mdi-` (ej. `mdi-email-outline`, `mdi-lock-outline`).
- **Responsive**: Usar el sistema de grids de Vuetify (`v-row`, `v-col`) con breakpoints (`cols="12" md="6"`).

## Autenticación y API
- **Token**: Se almacena en una cookie llamada `access_token` usando `useCookie('access_token')`.
- **Headers**: Todas las llamadas que requieren autenticación deben incluir el header `Authorization: Bearer <token>`.
- **Base URL**: Se obtiene de `useRuntimeConfig().public.apiBaseUrl` (valor por defecto: `http://127.0.0.1:8000/api/v1`).
- **Fetch**: Usar `$fetch` de Nuxt para peticiones asíncronas.

## Manejo de Formularios y APIs
- **Dinero/Tarifas**: Al enviar campos numéricos (como `consultation_fee`), enviar solo el valor numérico como string o número. **EVITAR** añadir símbolos como `$` o comas de miles, ya que el backend usa validación estricta de `Decimal`.
- **Carga de Archivos**:
  - Usar `FormData` para enviar archivos.
  - Para **reemplazar** un archivo existente, usar el método `PATCH` hacia el endpoint del recurso específico (`/documents/<id>`).
  - El backend está configurado para manejar multipart en `PATCH` manualmente.
- **CSRF**: No es necesario enviar el header `X-CSRFToken` si se usa el header `Authorization`, ya que los endpoints de la API están marcados como `@csrf_exempt`.
