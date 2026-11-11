# Ficha técnica — Contenerización Lift-and-Shift

> **Versión 2.0** — Stacks: WildFly 25 / Java 17, PHP, **WordPress**, **Angular 12**, **.NET 5**.  
> **Uso:** una ficha por aplicación (o por familia idéntica).  
> **Fuente de verdad:** entrevista + revisión de código/config **en pantalla** (sin copia local) + opcional `assess_containerization.py`.  
> **Objetivo:** clasificar el esfuerzo y definir el diseño mínimo de contenedor.

---

## Metadatos de la entrevista

| Campo | Valor |
|-------|-------|
| Aplicación | |
| Código interno / alias | |
| Fecha entrevista | |
| Entrevistador(es) | |
| Interlocutores (rol) | |
| Duración | |
| Medio (Meet/Teams/presencial) | |
| ¿Código mostrado en pantalla? | Sí / No / Parcial |
| ¿Se ejecutó assess_containerization.py? | Sí / No — archivo reporte: |
| Grabación / acta autorizada | Sí / No |
| Clasificación preliminar | ☐ Lift puro ☐ Lift + ajustes ☐ Refactor parcial ☐ No apto L&S |
| Confianza de la clasificación | Alta / Media / Baja |

### Evidencia vista en pantalla (sin retener código)

Anotar **qué se vio**, no pegar código:

| # | Artefacto visto | Ruta/módulo (solo referencia) | Hallazgo clave | Captura/nota autorizada |
|---|-----------------|-------------------------------|----------------|-------------------------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

**Checklist de revisión en llamada (pedir compartir pantalla):**

- [ ] Build (`pom.xml` / `build.gradle` / `composer.json` / `package.json` / `*.csproj`)
- [ ] Artefacto de despliegue (WAR/EAR / `dist/` / publish / estructura WP)
- [ ] Config por ambiente (properties, XML, `.env`, `wp-config`, `appsettings`, `environment.ts`)
- [ ] Datasources / ConnectionStrings / DB_* 
- [ ] Logging (log4j / jboss / monolog / serilog / WP debug)
- [ ] Paths de escritura (uploads, temp, storage, `wp-content/uploads`, data dir)
- [ ] Scripts start/stop/deploy/CLI / wp-cron / hosted services
- [ ] Health / readiness si existe
- [ ] Docker/CI existente (si hay)
- [ ] (WP) plugins/themes, Multisite, object-cache
- [ ] (Angular) SPA vs SSR, lockfile, Node engines
- [ ] (.NET) TFM net5.0, WinForms/WPF, health checks

---

## 1. Identificación y alcance

| Campo | Valor |
|-------|-------|
| Descripción funcional (1–2 líneas) | |
| Criticidad (P1/P2/P3) | |
| Dueño funcional | |
| Dueño técnico | |
| Stack | ☐ WildFly 25 + Java 17 ☐ PHP ☐ WordPress ☐ Angular 12 ☐ .NET 5 ☐ Híbrido ☐ Otro: ___ |
| Versión exacta runtime | WildFly __ / Java __ / PHP __ / WP __ / Node __ / .NET __ |
| Vendor JDK / SDK (si aplica) | Temurin / Corretto / Oracle / MS SDK / Otro |
| Tipo de empaquetado | WAR / EAR / JAR / PHP app / WP / SPA dist / DLL+deps / Otro |
| Modo WildFly | ☐ Standalone ☐ Domain ☐ N/A |
| Nº instancias actuales (Dev/QA/Prod) | |
| Objetivo contenedor | ☐ Solo local/dev ☐ QA ☐ Producción |
| Orquestación destino | ☐ Compose ☐ K8s/OCP ☐ ECS/otros ☐ Por definir |
| Restricción: sin código fuera del cliente | Sí |

**Notas de alcance:**

>

---

## 2. Empaquetado y build

### 2.1 Java / WildFly

| Campo | Valor | Evidencia (pantalla) |
|-------|-------|----------------------|
| Herramienta de build | Maven / Gradle / Ant / Manual | |
| ¿Build reproducible en CI? | Sí / No / Parcial | |
| Artefacto final y nombre | | |
| Context path / nombre deployment | | |
| Módulos custom en `$JBOSS_HOME/modules` | Sí / No — lista: | |
| Perfil `standalone*.xml` usado | | |
| Subsystems críticos (datasources, messaging, mail, security…) | | |
| Scripts JBoss CLI / post-deploy | Sí / No — cuándo corren: | |
| Paths absolutos en config o código | Sí / No — ejemplos: | |

### 2.2 PHP (no WordPress)

| Campo | Valor | Evidencia (pantalla) |
|-------|-------|----------------------|
| Framework | Laravel / Symfony / CI / Legacy / Otro | |
| SAPI actual | Apache mod_php / PHP-FPM+Nginx / Otro | |
| Composer + lock en prod | Sí / No | |
| Extensiones requeridas | | |
| Document root | | |
| Rewrite / `.htaccess` / vhost | | |
| OPcache en prod | Sí / No — validate_timestamps: | |
| Crons / queues / workers | | |

### 2.3 WordPress

| Campo | Valor | Evidencia (pantalla) |
|-------|-------|----------------------|
| Versión WordPress (core) | | |
| Multisite | Sí / No | |
| SAPI actual | Apache mod_php / PHP-FPM+Nginx / Otro | |
| `wp-config.php` usa getenv/env | Sí / No / Parcial | |
| DB_HOST / secretos en claro | | |
| `WP_HOME` / `WP_SITEURL` | Hardcode / env / BD | |
| `DISABLE_WP_CRON` | Sí / No | |
| `DISALLOW_FILE_MODS` (prod) | Sí / No | |
| Plugins (#) y críticos | | |
| Themes (#) | | |
| `wp-content/uploads` path | | |
| `object-cache.php` (Redis/Memcached) | Sí / No — backend: | |
| `.htaccess` / rewrite | | |
| Updates desde wp-admin en prod | Sí / No (evitar en contenedor) | |
| Extensiones PHP requeridas | mysqli, gd, intl, zip, … | |

**Topología WP propuesta:** ☐ Nginx+PHP-FPM+DB ☐ All-in-one (no recomendado) ☐ + Redis ☐ + cron sidecar

### 2.4 Angular 12

| Campo | Valor | Evidencia (pantalla) |
|-------|-------|----------------------|
| `@angular/core` exacta | 12.x.x | |
| Node engines / versión usada en CI | (típicamente 14.x) | |
| Package manager + lockfile | npm/yarn — lock Sí/No | |
| Tipo | ☐ SPA estática ☐ SSR/Universal ☐ Híbrido | |
| `outputPath` (`angular.json`) | | |
| `environment*.ts` — URLs API | Hardcode / fileReplacements / runtime config | |
| Secretos en environments | Sí / No | |
| Base href / deploy URL | | |
| i18n / múltiples proyectos en monorepo | | |
| Servidor estático destino | Nginx / IIS / Otro | |
| Dockerfile existente | Sí / No | |

**Topología Angular propuesta:** ☐ Multi-stage Node→Nginx ☐ Node SSR ☐ CDN + Nginx

### 2.5 .NET 5

| Campo | Valor | Evidencia (pantalla) |
|-------|-------|----------------------|
| Tipo proyecto | ASP.NET Core / Worker / Library / Desktop | |
| `TargetFramework` | net5.0 / multi-TFM: | |
| SDK (`global.json`) | | |
| Self-contained | Sí / No | |
| WinForms / WPF / RID `win-*` | Sí / No (bloqueante Linux) | |
| `appsettings*.json` — secretos | | |
| ConnectionStrings | | |
| `ASPNETCORE_URLS` / Kestrel ports | | |
| Health checks (`/health`) | Sí / No — path: | |
| System.Drawing / Win32 APIs | Sí / No | |
| Hosted services / BackgroundService | Sí / No | |
| Plan upgrade a .NET 8 LTS | Sí / No / En curso | |
| Imagen candidata | `mcr.microsoft.com/dotnet/aspnet:5.0` (EOL) / upgrade | |

**Topología .NET propuesta:** ☐ Multi-stage SDK→aspnet ☐ Self-contained ☐ Windows container (solo si aplica)

**Cambios mínimos de build previstos (todos los stacks):**

- [ ]
- [ ]

---

## 3. Configuración y secretos (Twelve-Factor)

| Ítem | ¿Dónde vive hoy? | ¿Externalizable a env/secret mount? | Riesgo |
|------|------------------|--------------------------------------|--------|
| URL/credenciales BD | | Sí / No / Parcial | Alto/Med/Bajo |
| LDAP/SSO | | | |
| URLs de APIs | | | |
| Mail/SMTP | | | |
| Feature flags | | | |
| Certificados / keystores | | | |
| WP salts / AUTH_KEY | | | |
| Angular API URL / keys | | | |
| .NET ConnectionStrings / ClientSecret | | | |
| Diferencias Dev vs Prod en el artefacto | Sí / No | — | |

| Campo | Valor |
|-------|-------|
| Mecanismo actual de secretos | Archivo / env SO / vault / BD / hardcode |
| ¿Misma imagen viable Dev→Prod solo con env? | Sí / No / Con cambios |
| Variables candidatas (lista borrador) | `DB_HOST`, `WORDPRESS_*`, `ASPNETCORE_*`, `API_URL`, … |

**Hallazgos de pantalla (config):**

>

**Cambios mínimos de configuración:**

- [ ] Externalizar datasources / connection strings / `DB_*`
- [ ] Eliminar secretos del artefacto (`wp-config`, `appsettings`, `environment.ts`)
- [ ] Overlay `standalone` / env subst / `.env` / `wp-config` docker / config.json runtime
- [ ] Otros:

---

## 4. Estado, filesystem y persistencia

| Path / recurso | Lectura/Escritura | ¿Debe persistir entre reinicios? | Estrategia contenedor |
|----------------|-------------------|----------------------------------|------------------------|
| | R / W | Sí / No | Volume / PVC / Object storage / Efímero |
| | | | |

| Campo | Valor |
|-------|-------|
| Sesiones en disco | Sí / No |
| Uploads / reportes / temp | |
| WildFly data/log/content como estado | Sí / No |
| PHP `storage/` / `var/` / `uploads/` | |
| WordPress `wp-content/uploads` (y ¿todo `wp-content`?) | |
| Angular: ¿estado en runtime? (normalmente no) | N/A / Sí — detalle: |
| .NET: paths de archivos / DataProtection keys | |
| Permisos UID/GID esperados | |
| Shared storage entre nodos (NFS/SMB) | Sí / No — detalle: |

**Pregunta decisiva — respuesta del cliente:**

> Si el contenedor se recrea vacío, ¿qué pérdida es inaceptable?

**Respuesta:**

>

---

## 5. Integraciones y datos

| Dependencia | Tecnología/versión | Endpoint/host (sin secretos) | Protocolo | Criticidad | Notas |
|-------------|--------------------|------------------------------|-----------|------------|-------|
| Base de datos | | | JDBC/PDO/mysqli/ADO.NET | | |
| Cola / JMS / Rabbit / Azure Service Bus | | | | | |
| Caché (Infinispan/Redis/Memcached/WP object-cache) | | | | | |
| LDAP/AD | | | | | |
| APIs REST/SOAP (Angular→backend) | | | | | |
| SMTP | | | | | |
| Otros | | | | | |

| Campo | Valor |
|-------|-------|
| ¿Migraciones de schema? ¿Quién las ejecuta? | |
| ¿Llamadas a localhost / procesos co-localizados en la VM? | Sí / No — lista: |
| ¿Dispositivos locales / impresoras / agentes en host? | Sí / No |

---

## 6. Sesión, clustering y HA

| Campo | Valor |
|-------|-------|
| Sticky session en LB | Sí / No / No aplica |
| Replicación de sesión (WildFly / .NET DataProtection / WP) | |
| Cluster WildFly / JGroups | Sí / No |
| EJB timers / singletons / .NET HostedService único | Sí / No — detalle: |
| Angular SSR sticky (si aplica) | Sí / No / N/A |
| Réplicas deseadas en contenedor | |
| Implicación para L&S | Affinity / DNS_PING / Single replica / Refactor |

---

## 7. Red, puertos y TLS

| Puerto / servicio | Protocolo | Expuesto hoy | ¿Exponer en contenedor? |
|-------------------|-----------|--------------|-------------------------|
| 8080 HTTP | | | Sí / No |
| 8443 HTTPS | | | |
| 80/443 (Nginx/Angular/WP) | | | |
| 9000 PHP-FPM (interno) | | | **No público** |
| 9990 Management WildFly | | | **No (recomendado)** |
| Kestrel (.NET) | | | |
| AJP / otros | | | |

| Campo | Valor |
|-------|-------|
| Terminación TLS | App / LB / Ambos |
| Context path / base href | |
| Reverse proxy actual | |
| Restricciones por IP | |

---

## 8. Observabilidad, health y ciclo de vida

| Campo | Valor |
|-------|-------|
| Destino de logs hoy | Archivo / Consola / Ambos — path: |
| Framework de logging | |
| ¿Viable redirigir a stdout/stderr? | Sí / No / Con cambio |
| Health endpoint existente | URL / No hay |
| Criterio actual de “arrancó OK” | |
| Graceful shutdown hoy | Sí / No / Desconocido |
| APM / JMX / agentes | |
| Métricas existentes | |

**Probes sugeridos (borrador):**

| Tipo | Método | Criterio | Timeout/arranque |
|------|--------|----------|------------------|
| Liveness | | | |
| Readiness | | | |
| HEALTHCHECK Docker | | | |

---

## 9. Seguridad y runtime del proceso

| Campo | Valor |
|-------|-------|
| Usuario OS actual del proceso | root / otro UID: |
| ¿Requiere root? | Sí / No — por qué: |
| UID/GID para volúmenes compartidos | |
| AuthN/AuthZ de la app | JAAS / Keycloak / LDAP / Session / WP users / JWT / Otro |
| Base image permitida | Pública / Solo registry interno |
| Escaneo CVE / SBOM obligatorio | Sí / No |
| Nota EOL | .NET 5 / Angular 12 / Node 14 — plan de upgrade |

---

## 10. Recursos y performance

### Java / JVM

| Campo | Valor actual | Propuesta contenedor |
|-------|--------------|----------------------|
| `-Xms` / `-Xmx` | | `%` RAM (`Initial/Max/MinRAMPercentage`) |
| GC / flags especiales | | |
| RAM/CPU VM actual | | requests/limits: |
| Tiempo arranque en frío | | |

### PHP-FPM / WordPress

| Campo | Valor actual | Propuesta |
|-------|--------------|-----------|
| `memory_limit` | | |
| `pm` / max children | | |
| OPcache memory | | |
| Workers / wp-cron aparte | | Sidecar / CronJob |

### Angular (build)

| Campo | Valor actual | Propuesta |
|-------|--------------|-----------|
| Memoria Node en CI (`NODE_OPTIONS`) | | |
| Tiempo `ng build --prod` | | |

### .NET

| Campo | Valor actual | Propuesta |
|-------|--------------|-----------|
| GC / Server GC | | |
| RAM/CPU | | requests/limits |
| ThreadPool / Kestrel limits | | |

---

## 11. Operación y CI/CD

| Campo | Valor |
|-------|-------|
| Pipeline actual | |
| Quién construye / despliega | |
| Promoción entre ambientes | |
| Rollback actual | |
| ¿Entregarán artefacto o build en su CI? | Artefacto / Dockerfile en su repo / Ambos |
| Operador post-handoff | |

---

## 12. Restricciones del cliente

| Restricción | Sí/No | Detalle |
|-------------|-------|---------|
| Prohibido retener código fuente | | |
| Permitido ver código en llamada | | |
| Comparten artefactos compilados | | |
| Comparten configs sanitizadas | | |
| Air-gapped / sin Docker Hub | | |
| Compliance / datos sensibles | | |
| Ventanas de cambio | | |

---

## 13. Clasificación y decisión de diseño

### Scorecard rápido (marcar)

| Criterio | OK L&S | Ajuste menor | Bloqueante |
|----------|--------|--------------|------------|
| Artefacto desplegable claro | ☐ | ☐ | ☐ |
| Config externalizable | ☐ | ☐ | ☐ |
| Sin domain/cluster/SSR/Win-desktop complejo | ☐ | ☐ | ☐ |
| Estado en disco acotado y mapeable | ☐ | ☐ | ☐ |
| Logs a stdout viable | ☐ | ☐ | ☐ |
| Health definible | ☐ | ☐ | ☐ |
| Proceso no-root viable | ☐ | ☐ | ☐ |
| Sin dependencia de host/local devices | ☐ | ☐ | ☐ |

### Clasificación final

| Campo | Valor |
|-------|-------|
| Resultado | ☐ Lift puro ☐ Lift + ajustes ☐ Refactor parcial ☐ No apto L&S |
| Justificación (3–5 líneas) | |
| Esfuerzo estimado (T-shirt) | S / M / L / XL |
| Riesgo go-live | Bajo / Medio / Alto |

### Arquitectura de contenedor propuesta

| Ítem | Decisión |
|------|----------|
| Topología | ☐ WildFly ☐ Nginx+PHP-FPM ☐ Nginx+WP+FPM ☐ Nginx(Angular dist) ☐ Node SSR ☐ ASP.NET Kestrel ☐ App+sidecars ☐ Otro: |
| Imagen base candidata | Temurin / WildFly / PHP-FPM Slim / nginx-unprivileged / node:14 / aspnet:5.0→8 / Distroless / Interna |
| Multi-stage | Sí / No |
| Usuario runtime | UID ___ (no-root) |
| Volúmenes nombrados | |
| Red / servicios dependientes | |
| Compose profiles | dev / prod |
| Variables de entorno mínimas | |
| Secrets | |
| HEALTHCHECK | |

**Diagrama textual (opcional):**

```text
[LB/Ingress] -> [Nginx?] -> [WildFly|PHP-FPM|Kestrel|SSR] -> [BD/Cola/LDAP/Redis]
                     |                    |
               volume:uploads         env/secrets
```

---

## 14. Backlog de modificaciones mínimas

> Solo cambios necesarios para contenerizar. Separar **app**, **servidor/runtime** y **plataforma**.

| ID | Cambio | Capa | Prioridad | Dueño | Bloquea imagen? | Validación |
|----|--------|------|-----------|-------|-----------------|------------|
| C-01 | | App / Runtime / Plataforma | Alta/Media/Baja | Cliente / Nosotros | Sí/No | |
| C-02 | | | | | | |
| C-03 | | | | | | |

### Fuera de alcance (explícito)

- 
- 

### Supuestos

- 
- 

### Riesgos residuales

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| | | |

---

## 15. Artefactos a solicitar post-entrevista

Sin código fuente completo; preferir sanitizado:

- [ ] WAR/EAR o build artifact reproducible
- [ ] `standalone.xml` / overlay datasources (sanitizado)
- [ ] Lista de env vars / properties por ambiente
- [ ] Lista de puertos e integraciones
- [ ] Paths de escritura y requisitos UID/GID
- [ ] Flags JVM o pool PHP-FPM actuales
- [ ] Script start/stop y criterio de salud operativo
- [ ] PHP: `composer.lock`, vhost, extensiones, crontab
- [ ] **WP:** `wp-config` sanitizado, lista plugins/themes, tamaño `uploads`
- [ ] **Angular:** `package-lock`/`yarn.lock`, `angular.json`, `environment*.ts` sanitizado
- [ ] **.NET:** `*.csproj`, `global.json`, `appsettings*.json` sanitizado, publish folder
- [ ] Política de imágenes base / registry
- [ ] Reporte `assess_containerization.py` (si se ejecutó en sitio)

---

## 16. Cierre de entrevista — guion (2 min)

Confirmaciones a leer en voz alta:

1. Clasificación provisional: **___**
2. Bloqueantes encontrados: **___**
3. Próximo entregable: diseño de imagen + Compose/K8s high-level + backlog C-xx
4. Próxima sesión (si falta evidencia en pantalla): **___**

**Firma / visto bueno verbal del interlocutor técnico:** Sí / No — nombre:

---

## Anexo A — Preguntas gatillo para la revisión en pantalla

Usar solo si la respuesta verbal es ambigua:

1. “Muéstrame dónde se define la conexión a BD y si cambia por ambiente.”
2. “Busquemos en el proyecto rutas absolutas (`C:\\`, `/opt/`, `\\\\server\\`).”
3. “¿Dónde se escriben uploads/temp y con qué usuario del SO?”
4. “¿El WAR asume módulos ya instalados en WildFly o trae todo?”
5. “¿Al hacer restart del servicio, la app cierra conexiones/colas limpio?”
6. “¿Existe algún URL que el LB use hoy para saber si está viva?”
7. “¿Hay timers, hilos daemon o procesos fuera del deployment?”
8. (PHP) “¿`storage` y `bootstrap/cache` son escribibles solo por el usuario del pool?”
9. (WP) “¿Instalan plugins desde wp-admin en producción? ¿Hay Multisite u object-cache?”
10. (WP) “¿`DISABLE_WP_CRON` está activo? ¿Quién dispara el cron hoy?”
11. (Angular) “¿Es SPA estática o Universal/SSR? ¿Las URLs de API viven en `environment.ts`?”
12. (Angular) “¿Qué versión exacta de Node usan en el pipeline de `ng build`?”
13. (.NET) “¿El TFM es solo `net5.0`? ¿Hay plan a .NET 8?”
14. (.NET) “¿Usan WinForms/WPF, `System.Drawing` o paths `C:\\`?”
15. (.NET) “¿Existe `MapHealthChecks` / readiness para el LB?”

## Anexo B — Leyenda de clasificación

| Clase | Significado | Ejemplo típico |
|-------|-------------|----------------|
| **Lift puro** | Imagen + env + volumen opcional; app casi intacta | WAR portable; Angular SPA con config runtime; WP con env |
| **Lift + ajustes** | Overlay config, entrypoint, volúmenes, logs stdout, non-root | Datasources en servidor; WP uploads; `appsettings` a env |
| **Refactor parcial** | Cambios acotados antes de prod | Domain mode; WP Multisite complejo; Angular SSR; .NET 5 + APIs Win32 |
| **No apto L&S** | Requiere rediseño | WinForms/WPF; dispositivos locales; acoplamiento fuerte a la VM |

## Anexo C — Mapeo rápido assess → ficha

| Prefijo hallazgo | Hoja / sección ficha |
|------------------|----------------------|
| `WF-*` / `JAVA-*` / `BUILD-*` | 2.1 Java/WildFly |
| `PHP-*` | 2.2 PHP |
| `WP-*` | 2.3 WordPress |
| `NG-*` | 2.4 Angular 12 |
| `DN-*` | 2.5 .NET 5 |
| `SRC-*` | Evidencia + Config/Persistencia |
| `CFG-*` / `SEC-*` / `OBS-*` | §§ 3, 8, 9 |
