# Classio Education — integración del directorio docente

## Contrato de producto

Classio Technology conserva la aplicación de gestión y aprendizaje. Classio Education es la puerta pública para encontrar docentes. Un visitante puede filtrar por niños, adolescentes o adultos, buscar por materia y abrir una ficha sin registrarse. Solicitar un vínculo abre el acceso de la app, conserva un identificador público opaco y lleva al perfil del docente en Comunidad, donde el estudiante elige materias y confirma el envío. No se crea un vínculo automáticamente.

El docente edita una presentación profesional separada del perfil privado. Elige las materias, etapas e idiomas que aparecen, la modalidad y los textos de presentación. La publicación web requiere una acción afirmativa y el perfil de Comunidad visible. Correo y teléfono profesionales tienen opciones independientes para Comunidad autenticada y para la web pública. Ninguna fila preexistente se publica por la migración. Si se retira la publicación, se oculta inmediatamente de la lista y la ficha; si se oculta el perfil de Comunidad, se suspende o se elimina la cuenta, la ficha también se retira. El consentimiento de publicación y sus cambios quedan en un registro separado. Un dato que un tercero haya copiado o indexado puede persistir fuera de Classio; la interfaz advierte de ello.

La búsqueda pública usa una RPC limitada que devuelve solo los campos de la ficha publicada; nunca consulta directamente `profiles` desde el navegador ni devuelve identificadores internos del docente. Las rutas protegidas resuelven el identificador público solo después de autenticar al estudiante. La información de alumnos, historial, pagos, clases y calendarios no forma parte de la ficha. El directorio no añade geolocalización del visitante ni eventos de publicidad. Los avisos de privacidad versionados explican el tratamiento y se publican en los tres idiomas con la misma versión que la app.

## Orden de despliegue

1. Validar la migración `streamlit/migrations/classio_education_teacher_profiles.sql` en una transacción reversible y comprobar tabla, RLS, funciones, grants y retirada automática. Aplicarla antes de publicar la app o el sitio. No modifica registros de pagos, clases ni perfiles existentes.
2. Publicar Expo con el editor de perfil y la ruta de conexión, junto con los avisos de privacidad versionados.
3. Publicar el directorio en `masterclassio.com/education/` y el enlace desde la portada. Mantener la página accesible aunque ningún docente haya optado por publicar; se muestra un estado vacío claro.
4. Hacer las pruebas beta con una cuenta docente y una estudiantil: publicación, filtros, ocultación, cuatro permisos de contacto, correo de acceso, conexión, cambio de idioma y retirada. Repetir en móvil y escritorio, tema claro y oscuro. Inspeccionar que un visitante anónimo no recibe campos privados ni el ID interno.

## Decisiones pendientes fuera del código

El titular y su abogado revisarán el texto legal y las transferencias internacionales antes de una campaña pública amplia. Las pruebas con cuentas reales y la aprobación de la experiencia pertenecen a la beta. No hay un cobro ni una comisión de intermediación implementados en esta fase.
