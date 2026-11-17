# Oración de Bolsillo · Guía de puesta en marcha (100 % automático, sin n8n)

Una vez configurado, el sistema hace solo todo esto:

- **Cada día** comprueba reservas por tipo y repone una semana de contenido, sin acumular versículos cuando faltan oraciones.
- **Cinco veces al día** prepara y publica reels narrados de 720 × 1280, con texto sincronizado y portada propia. Dos oraciones, dos reflexiones y un versículo diarios.
- **Cada 15 días** renueva el permiso de Instagram (el token dura 60 días).

Tú solo tienes que hacer esta configuración **una vez** (≈ 1 hora). Después, revisar de vez en cuando.

> La actualización incluye doce pruebas de regresión y muestras de los tres formatos generadas con Edge TTS. La publicación con la nueva portada debe verificarse en el primer despliegue de GitHub Actions. El simulacro del paso 7 comprueba la conexión y la disponibilidad del archivo sin publicar.

---

## Paso 1 · Crear la cuenta de Instagram

1. Crea la cuenta **@oraciondebolsillo** (nombre: Oración de Bolsillo).
2. Ajustes → **Tipo de cuenta → Cambiar a cuenta profesional** (Creador o Empresa). Es obligatorio para la API.
3. Foto de perfil: `salida/foto_perfil.jpg` (la "O" con cruz). Si no existe, ejecuta `componer.bat` (Windows).
4. Biografía:
   ```
   Oración de Bolsillo 🙏
   Una oración para cada momento de tu vida
   ✝️ Versículos • Reflexiones • Oraciones
   Guárdala y llévala contigo 🤍
   ```

## Paso 2 · GitHub (el "cerebro" gratuito)

1. Crea cuenta en <https://github.com>.
2. **New repository** → nombre `oracion-de-bolsillo` → **Public** (necesario para Pages gratis) → Create.
3. **Add file → Upload files**: arrastra **todo el contenido** de esta carpeta (incluida la carpeta oculta `.github`; si tu explorador no la muestra, activa "mostrar archivos ocultos"). Commit.
4. En el repositorio: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
5. **Settings → Actions → General → Workflow permissions → Read and write permissions** → Save.

## Paso 3 · Clave de Claude (Anthropic API)

Claude Pro **no** incluye la API; es un pago aparte por uso (céntimos por semana con este uso).

1. Entra en <https://console.anthropic.com> → Billing → añade 5 € de crédito (desactiva la recarga automática si quieres tope).
2. **API Keys → Create Key** → copia la clave (`sk-ant-...`). Guárdala, solo se ve una vez.

## Paso 4 · Aplicación de Meta (permiso para publicar)

1. Entra en <https://developers.facebook.com> con tu Facebook → **Mis apps → Crear app**.
2. Tipo **Empresa (Business)**; caso de uso "Gestionar mensajes y contenido en Instagram".
3. En el panel de la app: **Instagram → Configuración de la API con inicio de sesión de Instagram** (*API setup with Instagram business login*).
4. **Añadir cuenta de Instagram** / agregar `@oraciondebolsillo` (puede pedir que la aceptes como tester desde Instagram: Ajustes → Sitios web y permisos → Invitaciones de tester).
5. Pulsa **Generar token** para la cuenta y acepta los permisos (`instagram_business_basic` e `instagram_business_content_publish`). Copia el token largo.

Si los nombres del menú son distintos, busca "Instagram login" / "Generate token".

## Paso 5 · Token de GitHub para renovar el permiso (GH_PAT)

1. GitHub → tu foto → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. Repository access: **Only select repositories → oracion-de-bolsillo**.
3. Permissions → Repository → **Secrets: Read and write**.
4. Caducidad: la máxima. Copia el token.

## Paso 6 · Guardar los 3 secretos

Repositorio → **Settings → Secrets and variables → Actions → New repository secret**:

| Nombre | Valor |
|---|---|
| `IG_TOKEN` | token de Instagram (paso 4) |
| `ANTHROPIC_API_KEY` | clave de Claude (paso 3) |
| `GH_PAT` | token de GitHub (paso 5) |

## Paso 7 · Primeras pruebas

1. Pestaña **Actions → Publicar → Run workflow**: turno `manana`, deja marcado **simulacro** → Run. Debe terminar en verde y crear el vídeo sin publicar nada. Si falla, abre el registro rojo y envíame el texto del error.
2. Repite **sin** simulacro: se publicará la primera publicación real. Míralo en Instagram.
3. **Actions → Generar semana → Run workflow** para comprobar que Claude genera contenido nuevo (solo genera si quedan menos de 22 pendientes; marca *forzar* para obligarlo).
4. A partir de aquí el calendario va solo.

## Formato y calendario actual

- Diario, 12:17 UTC: versículo. 07:17 Bogotá y 06:17 Ciudad de México.
- Diario, 16:17 UTC: reflexión. 11:17 Bogotá y 10:17 Ciudad de México.
- Diario, 20:17 UTC: reflexión. 15:17 Bogotá y 14:17 Ciudad de México.
- Diario, 23:17 UTC: oración. 18:17 Bogotá y 17:17 Ciudad de México.
- Diario, 02:17 UTC: oración. 21:17 Bogotá y 20:17 Ciudad de México del día anterior.
- Son horas de inicio de GitHub Actions. La preparación y las colas pueden retrasar la publicación.
- Voz Dalia (es-MX), velocidad +4%. Edge TTS recibe el guion y devuelve audio y tiempos de cada palabra. Requiere conexión. Si la voz falla, se detiene esa ejecución y la pieza sigue pendiente.
- Los guiones nuevos se solicitan a Anthropic en lotes pequeños con salida JSON estructurada. En Sonnet 5.5 se desactiva el razonamiento previo para reservar los tokens al texto.
- La oración completa se escucha en el vídeo. El texto cambia siguiendo el audio, con música baja y cierre para seguir la cuenta. No se genera animación de personajes.
- `datos/config.json` controla la voz, el límite de duración y los hashtags. `con_voz: false` recupera el formato anterior.
- Hashtags amplios en minúscula, máximo cinco. #fyp se alterna por id con #oracion para comparar resultados, sin asumir que garantice alcance. Se guardan los hashtags usados y el formato en el historial de publicación.
- El sistema conserva el contenido publicado. Las piezas antiguas pendientes también usan la voz y el nuevo diseño.
- Prueba local sin publicar: `python -m automatizacion.publicar preparar --turno noche --salida sitio`.
- Regresiones: `python -m unittest discover -s automatizacion -p 'test_*.py' -v`.


## Mantenimiento

- **Ver qué hay en cola:** `datos/cola.json` (estado `pendiente`, `publicado`, `error`, `borrador`). Puedes editarlo directamente en GitHub (lápiz).
- **Revisar antes de publicar:** en `datos/config.json` pon `"aprobar_automaticamente": false`; lo generado quedará como `borrador` y tú lo cambias a `pendiente`.
- **Parada de emergencia:** Actions → cada flujo → ⋯ → **Disable workflow**.
- **Errores:** GitHub te envía un correo si un flujo falla. Una publicación falla 3 veces y se marca `error`; el sistema sigue con la siguiente.
- **Música propia:** pon archivos de audio libres de derechos en la carpeta `musica/`; si está vacía, se sintetiza un fondo suave.
- **Solo imagen en vez de reel:** `"publicar_como": "imagen"` en `config.json`.

## Honestidad sobre los límites

- Los versículos se copian de un banco verificado de **19 versículos RVR1960**; con 3 al día se repetirán pasadas unas 3 semanas (siempre el menos usado). Amplíalos despacio con los pendientes de `datos/versiculos_pendientes.json` verificando cada texto.
- La RVR1960 tiene derechos (Sociedades Bíblicas Unidas). Citar versículos sueltos con referencia es práctica habitual, pero no es asesoría legal.
- Nada de esto garantiza seguidores ni dinero: lo que funciona es constancia, calidad y tiempo. Revisa de vez en cuando las estadísticas y los comentarios.
- Instagram puede limitar cuentas nuevas con publicación automática; si pasa, baja a 2 publicaciones al día.
