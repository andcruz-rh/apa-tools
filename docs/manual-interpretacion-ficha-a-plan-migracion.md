# Manual de interpretación — De la ficha técnica al Plan de migración

> **Propósito:** traducir de forma sistemática la información de la **Ficha técnica v2.0** (y del assess opcional) en el entregable **Plan de migración a contenedores** (pasos ejecutables).  
> **Audiencia:** arquitectos / DevOps que elaboran el plan tras la entrevista.  
> **Documentos relacionados:**  
> - `ficha-tecnica-contenorizacion.md` / `.xlsx`  
> - `plantilla-exposicion-estrategia-migracion.md`  
> - `plantilla-plan-migracion-contenedores.md` ← entregable final  

---

## 1. Flujo de trabajo

```text
Ficha completa (+ assess.md/json)
        │
        ▼
[1] Validar completitud mínima
        │
        ▼
[2] Leer clasificación y scorecard (§13)
        │
        ▼
[3] Mapear hallazgos → tipos de cambio (tabla §3)
        │
        ▼
[4] Seleccionar plantilla de pasos por stack (§4)
        │
        ▼
[5] Redactar Plan de migración (usar plantilla)
        │
        ▼
[6] Revisar con dueño app/ops → baseline para build
```

**Regla de oro:** la ficha describe el *as-is* y los *gaps*; el plan describe el *to-be* y la *secuencia de trabajo*. No copiar la ficha al plan: **interpretar**.

---

## 2. Completitud mínima antes de redactar el plan

No iniciar el Plan de migración si falta algo de esta lista (salvo excepción firmada):

| # | Campo ficha | ¿Por qué bloquea el plan? |
|---|-------------|---------------------------|
| 1 | Stack + versiones runtime | Define imagen base y stages |
| 2 | Clasificación final (§13) | Define profundidad de pasos |
| 3 | Scorecard con al menos 6/8 criterios marcados | Evita planes genéricos |
| 4 | Inventario de paths de escritura (§4) o respuesta a “contenedor vacío” | Define volúmenes |
| 5 | Dónde viven secretos/BD (§3) | Define externalización |
| 6 | Puertos / TLS / context path (§7) | Define exposición |
| 7 | Backlog C-xx con dueños (§14) | Define dependencias y orden |
| 8 | Restricciones registry/air-gap (§12) | Define origen de bases |

Si hay reporte assess: adjuntar IDs `WP-*` / `NG-*` / `DN-*` / `WF-*` / `SRC-*` como evidencia en el plan (Anexo).

---

## 3. Cómo leer la clasificación

### 3.1 Clase → profundidad del plan

| Clasificación | Qué debe contener el plan | Qué NO debe prometer |
|---------------|---------------------------|----------------------|
| **Lift puro** | Dockerfile/Compose, env map, health, non-root, CI básico, prueba smoke | Refactors de código |
| **Lift + ajustes** | Todo lo anterior + overlay config, volúmenes, entrypoint, logs stdout, cambios C-xx de config/runtime | Reescritura de módulos de negocio |
| **Refactor parcial** | Fases previas (código/runtime) **antes** del go-live contenedor; criterios de salida por fase | “Solo Docker” sin tocar app |
| **No apto L&S** | Documento de *no go* + alternativas (rediseño, Windows containers, diferir) | Un Dockerfile “a ver si corre” |

### 3.2 Scorecard → secciones obligatorias del plan

| Criterio ficha | Si está **OK L&S** | Si **Ajuste menor** | Si **Bloqueante** |
|----------------|--------------------|---------------------|-------------------|
| Artefacto desplegable claro | Paso “obtener artefacto/CI build” corto | Definir pipeline de build en el plan | Parar: sin unidad empaquetable no hay imagen |
| Config externalizable | Tabla env mínima | Fase “externalizar config/secretos” | Bloqueante: no promover a prod hasta remediar |
| Sin domain/cluster/SSR/Win complejo | Topología simple | Diseño HA/affinity o single-replica documentado | Fase refactor o reclasificar No apto |
| Estado en disco mapeable | Volúmenes listados | Inventario + migrate data path | Definir almacenamiento o rediseño |
| Logs a stdout viable | Config logging en imagen | Cambio de appenders/handlers en backlog | No cerrar go-live sin stdout o sidecar acordado |
| Health definible | Probes concretos | Crear endpoint o TCP probe temporal | Definir health antes de prod multi-réplica |
| Proceso no-root viable | `USER` en Dockerfile | Ajuste UID/GID volúmenes | Excepción de seguridad firmada o remediar |
| Sin dependencia host/devices | — | Sidecar/servicio sustituto | Candidato No apto L&S |

### 3.3 Esfuerzo T-shirt → horizonte del plan

| T-shirt | Horizontes típicos (orientativo) | Estructura del plan |
|---------|----------------------------------|---------------------|
| **S** | Días–1 semana | 1 fase técnica + go-live |
| **M** | 1–3 semanas | Foundation app + build + deploy + piloto |
| **L** | 3–6 semanas | + remediación config/estado + pruebas no funcionales |
| **XL** | +6 semanas | Tratar como programa; partir en fases con gates |

---

## 4. Mapeo campo ficha → contenido del plan

### 4.1 Identificación (§1)

| Campo ficha | Va al plan como… |
|-------------|------------------|
| Criticidad P1–P3 | Ventana de cambio, nivel de hypercare, réplicas mínimas |
| Stack / versiones | “Arquitectura destino” + tags de imagen |
| Objetivo contenedor (local/QA/prod) | Ambientes del plan y criterios de aceptación por ambiente |
| Orquestación (Compose/K8s) | Manifiestos a entregar (compose vs Deployment/Service/Ingress) |

### 4.2 Build por stack (§2)

#### Java / WildFly

| Hallazgo típico | Paso de migración a redactar |
|-----------------|------------------------------|
| WAR + standalone | Multi-stage o copy WAR sobre imagen WildFly/JRE; overlay datasource |
| Módulos custom | Capa `COPY modules/`; documentar en imagen |
| Domain mode | **Gate:** migrar a standalone antes de contenedor prod |
| Paths absolutos | Sustituir por env + volumen; pruebas de path |
| `-Xmx` fijo | Cambiar a `% RAM` en `JAVA_OPTS` |
| Management 0.0.0.0 | Cerrar 9990; no publicar Service |

#### PHP (no WP)

| Hallazgo | Paso |
|----------|------|
| mod_php | Separar Nginx + PHP-FPM |
| Sin composer.lock | Generar lock en CI o fijar versiones |
| OPcache validate_timestamps=1 | Ajuste prod en imagen |
| storage/uploads | Volumen + UID www-data |

#### WordPress

| Hallazgo (ficha / WP-*) | Paso |
|-------------------------|------|
| Secretos en wp-config | Template wp-config desde env; no copiar secretos |
| DB_HOST=localhost | Nombre servicio Compose/K8s |
| uploads | PVC/volume dedicado |
| wp-cron HTTP | DISABLE_WP_CRON + CronJob |
| Updates admin | DISALLOW_FILE_MODS; plugins en imagen/CI |
| Multisite | Diseño de dominios/cookies/proxy (fase propia) |
| object-cache | Servicio Redis + config |
| .htaccess | Traducir a Nginx `try_files` |

#### Angular 12

| Hallazgo | Paso |
|----------|------|
| SPA | Multi-stage Node 14 → Nginx sirve `outputPath` |
| SSR | Contenedor Node + probes; no solo Nginx |
| environment.ts hardcode | Runtime `config.json` o replacements por ambiente en CI |
| Sin lockfile | Introducir lock antes de imagen reproducible |
| EOL NG12/Node14 | Contenerizar + ítem explícito de upgrade en backlog |

#### .NET 5

| Hallazgo | Paso |
|----------|------|
| net5.0 | Imagen aspnet:5.0 **o** (preferible) upgrade a 8 en fase previa |
| appsettings secretos | env / secrets; quitar del publish |
| localhost en ConnectionString | DNS de servicio |
| /health | HEALTHCHECK + readiness |
| WinForms/WPF/win-RID | No go Linux; alternativa Windows container o rediseño |
| System.Drawing | Validar libs nativas o reemplazo |

### 4.3 Config y secretos (§3)

| Señal | Traducción al plan |
|-------|-------------------|
| Misma imagen Dev→Prod = Sí | Un pipeline; promoción por tag + env |
| = No / Con cambios | Fase 0 de externalización **antes** de “docker build prod” |
| Variables candidatas | Tabla “Mapa de configuración” del plan (obligatoria) |
| Vault vs archivo | Mecanismo de inyección en cada ambiente |

### 4.4 Persistencia (§4)

| Respuesta a “contenedor vacío” | Acción en el plan |
|--------------------------------|-------------------|
| Nada crítico | Sin PVC (o solo tmp) |
| Uploads / reportes | Volumen nombrado + backup/restore |
| Data dir WildFly / sesiones disco | Rediseñar a store externo o sticky + volumen (documentar riesgo) |
| Desconocido | **Gate de discovery** antes del build prod |

### 4.5 Integraciones (§5)

Cada dependencia → fila en “Contratos de integración” del plan:

- DNS/nombre servicio  
- Puerto  
- Secretos asociados  
- Health dependencia (¿el readiness debe esperar BD?)  
- Quién migra connection string  

### 4.6 HA / red / TLS (§6–7)

| Señal | Paso |
|-------|------|
| Sticky sí | Anotar en Ingress/LB; probar con 2 réplicas |
| Cluster JGroups multicast | DNS_PING/KUBE_PING o single replica en W1 |
| TLS en app | Montar certs o terminar en LB (decidir una) |
| Context path / base href | Config Ingress + app/`baseHref` |

### 4.7 Observabilidad y seguridad (§8–9)

| Señal | Paso |
|-------|------|
| Logs a archivo | Cambio a CONSOLE / stdout en fase runtime |
| Sin health | Definir TCP o endpoint mínimo en backlog C-xx |
| Corre como root | USER no-root + chown volúmenes |
| APM | Cómo se inyecta agente (capa imagen vs sidecar) |

### 4.8 Recursos (§10)

Pasar “valor actual” → “requests/limits” y flags runtime en la sección “Sizing” del plan. Si no hay datos: sizing provisional + prueba de carga como criterio de aceptación.

### 4.9 Ops / restricciones (§11–12)

| Señal | Paso |
|-------|------|
| Pipeline existente | Extender job “docker build/push” |
| Air-gapped | Mirror de bases; sin Docker Hub directo |
| No retener código | Build en CI del cliente; nosotros entregamos Dockerfiles |

### 4.10 Backlog C-xx (§14)

**Orden canónico de ejecución en el plan:**

1. C-xx que **bloquean imagen** (secretos, paths, domain mode, Win desktop)  
2. C-xx de **runtime** (logs, health, non-root, cron)  
3. C-xx de **plataforma** (registry, red, PVC, Ingress)  
4. C-xx de **nice-to-have** (upgrade EOL, optimizaciones)  

Cada C-xx del backlog debe aparecer como tarea numerada o como dependencia explícita de una fase.

---

## 5. Traducción assess → severidad en el plan

| Severidad assess | Tratamiento en el Plan de migración |
|------------------|-------------------------------------|
| `ok` / `info` | Mencionar en “estado actual” o omitir |
| `low` / `medium` | Tarea en fase de ajustes; no bloquea spike técnico |
| `high` | Tarea con dueño y fecha; gate antes de prod |
| `blocker` | Gate duro: no build/promote prod hasta cerrado |

**Ejemplos:**

| ID | Interpretación para el plan |
|----|-----------------------------|
| `WP-003` / `DN-010` / `SRC-011` | Fase “Remediación de secretos” obligatoria |
| `WF-011` domain | Fase previa “Standalone migration” |
| `NG-005` SSR | Topología Node, no solo Nginx |
| `DN-002` WinForms | Reclasificar; no seguir plantilla Linux |
| `SRC-020` timers | Single-replica o diseño de líder |

---

## 6. Estructura recomendada del entregable (resumen)

Usar íntegramente `plantilla-plan-migracion-contenedores.md`. Mínimos:

1. Resumen ejecutivo (clase, esfuerzo, riesgo, decisión)  
2. As-is → to-be (diagrama)  
3. Mapa de configuración (env/secrets)  
4. Volúmenes y datos  
5. Pasos por fases (con gates)  
6. Pruebas de aceptación  
7. Rollback  
8. Runbook operativo breve  
9. Anexos (ficha, assess, C-xx)

---

## 7. Plantillas de “pasos” por clasificación

### 7.1 Lift puro (esqueleto)

1. Acordar imagen base y tags  
2. Crear Dockerfile multi-stage / runtime  
3. Mapear env mínimos  
4. HEALTHCHECK + non-root  
5. Compose/K8s smoke en Dev  
6. Pipeline build-scan-push  
7. QA → Prod con tag inmutable  

### 7.2 Lift + ajustes (esqueleto)

1. Cerrar bloqueantes de secretos/paths (C-xx)  
2. Externalizar config (overlay/env/wp-config/appsettings)  
3. Definir volúmenes y UID/GID  
4. Ajustar logs → stdout  
5. Definir probes  
6. Construir imagen  
7. Prueba destroy/recreate del contenedor  
8. Piloto QA  
9. Go-live + hypercare  

### 7.3 Refactor parcial (esqueleto)

**Fase A — Remediación app/runtime** (sin prod contenedor)  
**Gate A:** scorecard sin bloqueantes críticos  
**Fase B — Contenerización** (igual que Lift+)  
**Gate B:** aceptación QA  
**Fase C — Prod + hypercare**

### 7.4 No apto L&S

1. Declarar no-go con evidencia del scorecard  
2. Opciones: rediseño / Windows containers / diferir wave  
3. No generar Dockerfile “experimental” como compromiso de entrega  

---

## 8. Checklist de calidad del Plan (antes de enviar al cliente)

- [ ] La clasificación del plan coincide con la ficha (§13)  
- [ ] Cada **bloqueante** del scorecard tiene un gate o tarea  
- [ ] Toda variable de la ficha §3 aparece en el mapa env o se marca N/A  
- [ ] Toda path de escritura §4 tiene estrategia (volumen/efímero/object storage)  
- [ ] Topología coincide con el stack (no mezclar patrones)  
- [ ] Hay criterios de aceptación **medibles** por ambiente  
- [ ] Rollback es técnico (tag anterior), no “llamar al proveedor”  
- [ ] No hay secretos en claro en el documento  
- [ ] Dueños (RACI) asignados a C-xx que bloquean imagen  
- [ ] Si hay EOL (NET5/NG12), el plan lo nombra (contenerizar ≠ olvidar upgrade)

---

## 9. Ejemplo rápido de traducción (ilustrativo)

**Ficha (extracto):** WordPress 6.4, `DB_PASSWORD` hardcode, `DB_HOST=localhost`, uploads en disco, clasificación **Lift + ajustes**, esfuerzo **M**.

**Interpretación:**

| Hecho | Paso en el plan |
|-------|-----------------|
| Secretos hardcode | Fase 1: wp-config desde env; rotar password |
| localhost | Fase 1: `WORDPRESS_DB_HOST=db` |
| uploads | Volumen `wp_uploads`; backup previo |
| Lift+ / M | Nginx+FPM+DB; piloto 2 semanas; sin Multisite |

**No interpretar como:** “subir la carpeta WP a un contenedor Apache all-in-one y listo”.

---

## 10. Glosario breve

| Término | Significado en este programa |
|---------|------------------------------|
| Gate | Condición que debe cumplirse para pasar de fase |
| Wave | Lote de apps priorizadas en la exposición de estrategia |
| C-xx | Ítem del backlog de cambios mínimos de la ficha |
| Lift | Contenerizar preservando comportamiento funcional |
| Overlay | Config externa montada o inyectada sin rebuild del artefacto de negocio |
