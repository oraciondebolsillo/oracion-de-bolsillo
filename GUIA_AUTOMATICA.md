# Oración de Bolsillo · Guía de puesta en marcha (100 % automático, sin n8n)

Una vez configurado, el sistema hace solo todo esto:

- **Cada domingo** pide a Claude la semana siguiente (21 publicaciones: mañana = versículo, tarde = reflexión, noche = oración).
- **3 veces al día** crea la imagen/reel, la sube a una web pública gratuita (GitHub Pages) y la publica en Instagram.
- **Cada 15 días** renueva el permiso de Instagram (el token dura 60 días).

Tú solo tienes que hacer esta configuración **una vez** (≈ 1 hora). Después, revisar de vez en cuando.

> Importante: el sistema se ha probado con servidores simulados (52 comprobaciones correctas), **no contra los servicios reales**. Es normal que el primer día haya que retocar algún detalle (sobre todo los menús de Meta, que cambian de nombre). El paso 7 (simulacro) está pensado para detectarlo sin publicar nada.

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

## Horarios (hora UTC → Colombia / España)

| Turno | UTC | Colombia | España (invierno / verano) |
|---|---|---|---|
| Mañana | 12:00 | 7:00 | 13:00 / 14:00 |
| Tarde | 18:00 | 13:00 | 19:00 / 20:00 |
| Noche | 02:00 | 21:00 | 03:00 / 04:00 |

Se cambian en `.github/workflows/publicar.yml` (líneas `cron`). GitHub puede retrasar unos minutos las ejecuciones.

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
