# Plan de migración a contenedores — [NOMBRE_APP]

| Campo | Valor |
|-------|-------|
| Versión del documento | 0.1 |
| Fecha | |
| Autor | |
| Revisores | |
| Estado | ☐ Borrador ☐ En revisión ☐ Aprobado |
| App / código | |
| Stack | ☐ WildFly/Java ☐ PHP ☐ WordPress ☐ Angular 12 ☐ .NET 5 ☐ Híbrido |
| Clasificación (ficha §13) | ☐ Lift puro ☐ Lift + ajustes ☐ Refactor parcial ☐ No apto L&S |
| Esfuerzo / Riesgo | _ / _ |
| Ficha técnica ref. | `ficha-…` fecha: |
| Assess ref. (opcional) | archivo / N/A |
| Exposición estrategia ref. | |

> **Cómo usar:** completar tras interpretar la ficha con el `manual-interpretacion-ficha-a-plan-migracion.md`.  
> **No incluir secretos en claro.**

---

## 1. Resumen ejecutivo

**Situación actual (2–3 líneas):**

>

**Objetivo de la migración:**

>

**Decisión / alcance:**

| Ítem | Valor |
|------|-------|
| Resultado esperado | App operando en contenedor en [Dev/QA/Prod] |
| Enfoque | Lift-and-Shift / Lift + ajustes / Refactor parcial |
| Orquestación | Compose / K8s / OCP / Otro |
| Fuera de alcance | |
| Dependencias externas (gates) | |

**Recomendación:**

> ☐ Proceder  
> ☐ Proceder tras cerrar bloqueantes: ___  
> ☐ No proceder (No apto L&S) — ver §12  

---

## 2. As-is → To-be

### 2.1 As-is (desde ficha §§1–2, 5–7)

| Aspecto | Estado actual |
|---------|---------------|
| Empaquetado / artefacto | |
| Runtime | |
| Config / secretos | |
| Persistencia | |
| Integraciones clave | |
| Exposición HTTP/TLS | |
| Operación / CI | |

### 2.2 To-be (arquitectura destino)

```text
[Completar diagrama textual]

[LB/Ingress] --> [ ] --> [ ] --> [ ]
                      |
                 volumes / secrets
```

| Componente | Imagen / servicio | Réplicas | Notas |
|------------|-------------------|----------|-------|
| | | | |
| | | | |

| Decisión de diseño | Valor | Origen en ficha |
|--------------------|-------|-----------------|
| Imagen base | | §13 / §2 |
| Usuario no-root (UID) | | §9 |
| Multi-stage | Sí/No | §13 |
| Health | | §8 |
| JVM/FPM/Node/.NET flags | | §10 |

---

## 3. Scorecard y bloqueantes

Copiar interpretación de ficha §13:

| Criterio | Resultado ficha | Impacto en este plan |
|----------|-----------------|----------------------|
| Artefacto desplegable claro | | |
| Config externalizable | | |
| Sin domain/cluster/SSR/Win complejo | | |
| Estado en disco acotado | | |
| Logs a stdout | | |
| Health definible | | |
| Non-root viable | | |
| Sin dependencia host/devices | | |

**Bloqueantes a cerrar antes de imagen/prod:**

| ID (C-xx / assess) | Descripción | Dueño | Gate |
|--------------------|-------------|-------|------|
| | | | Antes de build / Antes de QA / Antes de Prod |
| | | | |

---

## 4. Mapa de configuración (Twelve-Factor)

| Variable / secreto | Usado por | Origen actual (ficha §3) | Destino (env/secret) | Ambiente |
|--------------------|-----------|--------------------------|----------------------|----------|
| | | | | Dev |
| | | | | QA |
| | | | | Prod |

**Archivos de config a modificar o sustituir:**

| Archivo / recurso | Acción | Responsable |
|-------------------|--------|-------------|
| p. ej. standalone overlay / wp-config / appsettings / environment.ts | Externalizar / eliminar secreto / generar en entrypoint | |

---

## 5. Persistencia y datos

| Path / recurso | ¿Persiste? | Mecanismo (volume/PVC/S3/NFS) | Backup / restore | UID/GID |
|----------------|------------|-------------------------------|------------------|---------|
| | | | | |

**Prueba obligatoria:** destroy/recreate del contenedor sin pérdida de datos críticos.

| Dato crítico | Cómo se valida |
|--------------|----------------|
| | |

---

## 6. Integraciones

| Dependencia | Endpoint lógico (sin secretos) | Cambio requerido | Readiness depende de ella |
|-------------|-------------------------------|------------------|---------------------------|
| BD | | | Sí/No |
| | | | |

---

## 7. Plan de pasos por fases

> Numerar tareas. Marcar dependencias. Toda tarea que venga de backlog C-xx debe citar el ID.

### Fase 0 — Preparación / remediación (omitir si Lift puro sin bloqueantes)

**Objetivo:** dejar scorecard sin bloqueantes de imagen/prod.

| # | Tarea | C-xx / evid. | Dueño | Entrada | Salida | Hecho |
|---|-------|--------------|-------|---------|--------|------|
| 0.1 | | | | | | ☐ |
| 0.2 | | | | | | ☐ |

**Gate 0:** ☐ Sin secretos en artefacto ☐ Paths portables ☐ Clasificación revalidada  

---

### Fase 1 — Empaquetado contenedor

**Objetivo:** Dockerfile (+ Nginx si aplica) construible de forma reproducible.

| # | Tarea | Dueño | Salida | Hecho |
|---|-------|-------|--------|------|
| 1.1 | Definir imagen(es) base aprobadas por seguridad | | Documentado | ☐ |
| 1.2 | Implementar Dockerfile multi-stage / runtime | | Dockerfile en repo CI cliente | ☐ |
| 1.3 | USER no-root + limpieza de capas | | Imagen local | ☐ |
| 1.4 | HEALTHCHECK / endpoints de salud | | Probe verificado | ☐ |
| 1.5 | (Stack) Ajustes específicos — ver §7.A | | | ☐ |

**Gate 1:** `docker build` OK + contenedor arranca en local/bastion con env de prueba.

---

### Fase 2 — Orquestación y config por ambiente

| # | Tarea | Dueño | Salida | Hecho |
|---|-------|-------|--------|------|
| 2.1 | Compose y/o manifiestos K8s (Deployment, Service, Ingress, PVC) | | YAML | ☐ |
| 2.2 | Inyectar secrets (sin valores en git) | | Procedimiento | ☐ |
| 2.3 | Volúmenes / PVC según §5 | | | ☐ |
| 2.4 | depends_on / probes / resources | | | ☐ |
| 2.5 | Profiles/overlays Dev vs Prod | | | ☐ |

**Gate 2:** stack completo arriba en Dev con `service_healthy` / ready.

---

### Fase 3 — CI/CD

| # | Tarea | Dueño | Salida | Hecho |
|---|-------|-------|--------|------|
| 3.1 | Pipeline build → scan → push registry | | Job CI | ☐ |
| 3.2 | Tagging inmutable (git sha / semver) | | Convención | ☐ |
| 3.3 | Promoción Dev→QA→Prod | | | ☐ |
| 3.4 | Rollback = redeploy tag anterior | | Probado en QA | ☐ |

**Gate 3:** imagen promovida a QA sin rebuild desde laptop.

---

### Fase 4 — Pruebas y endurecimiento

| # | Tarea | Dueño | Hecho |
|---|-------|-------|------|
| 4.1 | Smoke funcional (casos acordados) | | ☐ |
| 4.2 | Destroy/recreate + persistencia | | ☐ |
| 4.3 | Logs visibles en stdout / agregador | | ☐ |
| 4.4 | Probes bajo kill/restart | | ☐ |
| 4.5 | Non-root verificado | | ☐ |
| 4.6 | Prueba de carga / sizing (si P1 o riesgo alto) | | ☐ |

**Gate 4:** checklist §9 en verde para QA.

---

### Fase 5 — Go-live y hypercare

| # | Tarea | Dueño | Hecho |
|---|-------|-------|------|
| 5.1 | Ventana de cambio aprobada | | ☐ |
| 5.2 | Backup datos/volúmenes / punto de restauración | | ☐ |
| 5.3 | Despliegue Prod | | ☐ |
| 5.4 | Validación smoke Prod | | ☐ |
| 5.5 | Hypercare [N] días — contactos | | ☐ |
| 5.6 | Cierre: decommission VM legacy (si aplica) | | ☐ |

**Gate 5:** aceptación formal del dueño de la app.

---

### 7.A Pasos específicos por stack (completar solo el aplicable)

#### WildFly / Java

| # | Tarea | Hecho |
|---|-------|------|
| W.1 | Empaquetar WAR/EAR + módulos custom | ☐ |
| W.2 | Overlay datasources / system properties por env | ☐ |
| W.3 | JAVA_OPTS con `% RAM` | ☐ |
| W.4 | No publicar 9990 | ☐ |
| W.5 | Logging a CONSOLE | ☐ |

#### PHP

| # | Tarea | Hecho |
|---|-------|------|
| P.1 | Imagen PHP-FPM + extensiones | ☐ |
| P.2 | Nginx + document root / rewrites | ☐ |
| P.3 | Composer `--no-dev --optimize-autoloader` | ☐ |
| P.4 | OPcache prod | ☐ |
| P.5 | Volúmenes storage/uploads + UID | ☐ |

#### WordPress

| # | Tarea | Hecho |
|---|-------|------|
| WP.1 | Nginx + PHP-FPM + DB desacoplados | ☐ |
| WP.2 | wp-config desde env (sin secretos en imagen) | ☐ |
| WP.3 | Volumen `uploads` | ☐ |
| WP.4 | `DISABLE_WP_CRON` + CronJob | ☐ |
| WP.5 | `DISALLOW_FILE_MODS` en prod | ☐ |
| WP.6 | Plugins/themes fijados en imagen/CI | ☐ |
| WP.7 | (Si Multisite) diseño dominios/proxy | ☐ |

#### Angular 12

| # | Tarea | Hecho |
|---|-------|------|
| NG.1 | Build Node 14 + lockfile (`npm ci`) | ☐ |
| NG.2 | Copiar `outputPath` a Nginx unprivileged | ☐ |
| NG.3 | Externalizar API URL (runtime config o CI replacements) | ☐ |
| NG.4 | Si SSR: contenedor Node + probes (no solo estático) | ☐ |
| NG.5 | Registrar deuda EOL (upgrade Angular/Node) | ☐ |

#### .NET 5

| # | Tarea | Hecho |
|---|-------|------|
| DN.1 | Confirmar TFM; decidir 5.0 vs upgrade 8 | ☐ |
| DN.2 | Multi-stage SDK → aspnet; publish | ☐ |
| DN.3 | ConnectionStrings por env/secrets | ☐ |
| DN.4 | `ASPNETCORE_URLS=http://0.0.0.0:8080` + non-root | ☐ |
| DN.5 | Health checks en probes | ☐ |
| DN.6 | Si Win-only APIs: stop Linux path | ☐ |

---

## 8. Entregables técnicos

| Entregable | Ubicación / repo | Responsable |
|------------|------------------|-------------|
| Dockerfile(s) | | |
| Compose / overlays prod | | |
| Manifiestos K8s (si aplica) | | |
| Mapa env (sin secretos) | Este doc §4 | |
| Pipeline CI | | |
| Runbook (§10) | | |
| Resultados de prueba | | |

---

## 9. Criterios de aceptación

### Por ambiente

| Ambiente | Criterio | Evidencia |
|----------|----------|-----------|
| Dev | Stack healthy; smoke básico | |
| QA | Casos funcionales acordados; destroy/recreate OK | |
| Prod | Smoke + métricas/logs; rollback ensayado en QA | |

### Criterios transversales (marcar)

- [ ] Imagen sin secretos  
- [ ] Proceso no-root  
- [ ] Health liveness/readiness operativos  
- [ ] Logs en stdout/stderr  
- [ ] Config por env/secret mount  
- [ ] Volúmenes solo para estado declarado  
- [ ] Tag inmutable y rollback probado  

---

## 10. Runbook operativo (mínimo)

| Operación | Comando / procedimiento | Notas |
|-----------|-------------------------|-------|
| Desplegar versión | | |
| Rollback | | |
| Ver logs | | |
| Ver health | | |
| Escalar réplicas | | |
| Backup volumen | | |
| Rotar secreto | | |
| Contacto L1/L2 | | |

---

## 11. Rollback y contingencia

| Escenario | Acción | RTO orientativo |
|-----------|--------|-----------------|
| Fallo app post-deploy | Redeploy tag anterior | |
| Fallo de datos | Restore backup volumen/BD | |
| Fallo plataforma | | |
| Rollback a VM legacy (si aplica) | | Condiciones: |

---

## 12. No-go / excepciones (solo si aplica)

| Motivo (desde ficha) | Evidencia | Alternativa recomendada |
|----------------------|-----------|-------------------------|
| | | |

---

## 13. Riesgos residuales y supuestos

| Riesgo | Impacto | Mitigación | Estado |
|--------|---------|------------|--------|
| | | | Abierto/Cerrado |

**Supuestos:**

1.  
2.  

---

## 14. Cronograma orientativo

| Fase | Inicio | Fin | Hito |
|------|--------|-----|------|
| 0 Remediación | | | Gate 0 |
| 1 Empaquetado | | | Gate 1 |
| 2 Orquestación | | | Gate 2 |
| 3 CI/CD | | | Gate 3 |
| 4 Pruebas | | | Gate 4 |
| 5 Go-live | | | Gate 5 |

---

## 15. Aprobaciones

| Rol | Nombre | Fecha | Firma / OK |
|-----|--------|-------|------------|
| Dueño aplicación | | | |
| Ops / plataforma | | | |
| Seguridad (si aplica) | | | |
| Líder migración | | | |

---

## Anexo A — Trazabilidad ficha → plan

| Sección ficha | Sección de este plan |
|---------------|----------------------|
| §1 Identificación | §1, §14 |
| §2 Build | §2, §7 / §7.A |
| §3 Config | §4 |
| §4 Persistencia | §5 |
| §5 Integraciones | §6 |
| §6–7 HA/Red | §2, §2.2, §7 fase 2 |
| §8–10 Obs/Seg/Recursos | §2.2, §7, §9 |
| §11–12 Ops/Restricciones | §7 fase 3, §10 |
| §13 Clasificación | §1, §3 |
| §14 Backlog C-xx | §3, §7 |

## Anexo B — Extracto assess (IDs relevantes)

| ID | Severidad | Tratamiento en plan |
|----|-----------|---------------------|
| | | |

## Anexo C — Referencias

- Ficha técnica v2.0  
- Manual de interpretación ficha → plan  
- Plantilla exposición estrategia  
- Sample WP / scripts assess (si usados)  
