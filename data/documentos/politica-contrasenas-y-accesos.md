# Política de Credenciales y Gestión de Accesos — Dicsys

**Versión:** 3.3 — Vigente desde marzo 2026
**Área responsable:** IT y Seguridad

## Autenticación

El acceso a los sistemas corporativos se realiza mediante el proveedor de
identidad único (SSO). El segundo factor es **obligatorio** para todos los
sistemas que expongan información de clientes.

## Requisitos de las claves

| Requisito | Valor |
|---|---|
| Longitud mínima | 14 caracteres |
| Reutilización | prohibida en las últimas 10 |
| Vencimiento | sin vencimiento forzado |
| Verificación contra filtraciones conocidas | obligatoria |

No se exige rotación periódica: la evidencia indica que degrada la calidad de las
claves. Sí se fuerza el cambio ante cualquier sospecha de compromiso.

## Gestor de claves

El uso del gestor corporativo de contraseñas es obligatorio. Está prohibido
almacenar credenciales en archivos, planillas, repositorios de código o notas.

## Altas y bajas

1. El alta la solicita el líder e incluye el perfil de accesos requerido.
2. La baja se ejecuta el mismo día del egreso, antes del fin de la jornada.
3. Las cuentas de servicio tienen responsable asignado y revisión semestral.
4. Los accesos de terceros vencen automáticamente a los 90 días.

## Accesos privilegiados

Los accesos administrativos son nominados, temporales y quedan registrados. No
existen cuentas administrativas compartidas.
