# Plantilla de exposición — Estrategia de migración a contenedores

> **Uso:** deck o documento ejecutivo para presentar al cliente la estrategia Lift-and-Shift.  
> **Entrada:** ficha(s) técnica(s) + scorecard + backlog C-xx + (opcional) reporte `assess_containerization.py`.  
> **Salida de la reunión:** acuerdo de alcance, priorización de apps y aprobación para elaborar el **Plan de migración** detallado.  
> **Duración sugerida:** 30–45 min (portafolio) o 15–20 min (una app).

---

## Diapositiva 0 — Portada

| Campo | Valor |
|-------|-------|
| Título | Estrategia de migración a contenedores — [Cliente / Programa] |
| Subtítulo | Lift-and-Shift: WildFly / PHP / WordPress / Angular / .NET |
| Fecha | |
| Presenta | |
| Audiencia | ☐ Dirección ☐ Arquitectura ☐ Ops ☐ Desarrollo ☐ Seguridad |
| Clasificación del documento | Interno / Confidencial |

---

## 1. Objetivo y alcance (2 min)

**Mensaje clave (1 frase):**

> Migrar [N] aplicaciones a contenedores con el **mínimo cambio** necesario para operar de forma segura, reproducible y desacoplada (Twelve-Factor), sin rediseñar el negocio.

| Ítem | Contenido a completar |
|------|------------------------|
| Objetivo de negocio | p. ej. estandarizar despliegues, habilitar K8s/OCP, reducir drift Dev/Prod |
| Alcance IN | Apps, ambientes (Dev/QA/Prod), Compose y/o orquestador |
| Alcance OUT | Reescritura funcional, upgrade mayor de framework (salvo bloqueantes), data migration masiva |
| Premisa | Sin retención de código fuente fuera del cliente; evidencia vía entrevista + assess in-situ |
| Criterio de éxito | Imagen inmutable + config por env + health + non-root + rollback documentado |

**No digas en esta slide:** detalle de Dockerfile, flags JVM, listados de plugins.

---

## 2. Método de descubrimiento (2 min)

```text
Entrevista + pantalla  →  Ficha técnica v2  →  Scorecard + clasificación
         ↓                        ↓
   assess.py (opcional)     Backlog C-xx (cambios mínimos)
         ↓
   Estrategia (esta exposición)  →  Plan de migración (entregable)
```

| Artefacto | Para qué sirve |
|-----------|----------------|
| Ficha técnica | Hechos por app (build, config, estado, red, seguridad) |
| Assess script | Evidencia automatizable (WP/NG/DN/WF/SRC) |
| Matriz multi-app | Priorización del portafolio |
| Plan de migración | Pasos ejecutables (siguiente entregable) |

---

## 3. Principios de la estrategia (3 min)

Presentar como **no negociables** (salvo excepción firmada):

1. **Lift-and-Shift con ajustes mínimos** — no big-bang de arquitectura.
2. **Una unidad de despliegue = una imagen versionada**.
3. **Config y secretos fuera de la imagen** (env / secret mount).
4. **Contenedor efímero** — estado solo en volúmenes explícitos.
5. **Proceso no-root** + superficie mínima (Alpine/Slim/Distroless cuando aplique).
6. **Logs a stdout/stderr** + health (liveness/readiness).
7. **Dev ≠ Prod por overlay/compose profiles**, no por rebuild con secretos distintos.

**Frase de cierre del bloque:**

> Si un hallazgo viola estos principios, la app pasa de “Lift puro” a “Lift + ajustes” o “Refactor parcial” — no se fuerza el contenedor a costa de estabilidad.

---

## 4. Clasificación del portafolio (5–8 min)

### 4.1 Leyenda (mostrar siempre)

| Clase | Significado para el cliente | Implicación |
|-------|----------------------------|-------------|
| **Lift puro** | Contenerizar con cambios casi nulos | Rápido; bajo riesgo |
| **Lift + ajustes** | Config, volúmenes, entrypoint, probes | Caso más frecuente |
| **Refactor parcial** | Cambios acotados de app/runtime antes de prod | Ventana + dueño de app |
| **No apto L&S** | Rediseño (persistencia/OS/desktop) | Fuera de este wave o proyecto aparte |

### 4.2 Matriz ejecutiva (copiar desde `99_Matriz_MultiApp`)

| App | Stack | Clase | Esfuerzo | Riesgo | Bloqueantes (#) | Wave | Dueño |
|-----|-------|-------|----------|--------|-----------------|------|-------|
| | | | S/M/L/XL | B/M/A | | W1/W2/W3 | |
| | | | | | | | |

### 4.3 Distribución (opcional — 1 gráfico)

- % Lift puro / Lift+ / Refactor / No apto  
- Esfuerzo acumulado por wave  

**Recomendación de olas (completar):**

| Wave | Criterio | Apps | Meta |
|------|----------|------|------|
| W1 — Quick wins | Lift puro / Lift+ bajo riesgo | | Validar pipeline + patrones |
| W2 — Core | Lift+ con volúmenes/config | | Prod piloto |
| W3 — Complejas | Refactor parcial | | Tras lecciones W1–W2 |
| Parking | No apto L&S | | Rediseño / diferido |

---

## 5. Arquitectura destino por familia de stack (6–8 min)

Usar **una slide por familia presente en el portafolio** (omitir las que no apliquen).

### 5.1 WildFly 25 + Java 17

```text
[Ingress/LB] → [WildFly container] → [BD / LDAP / Cola]
                      ↑
              env + secrets + volume(uploads?)
```

| Decisión | Valor propuesto |
|----------|-----------------|
| Imagen | Temurin JRE / WildFly oficial + WAR |
| Modo | Standalone (no domain) |
| JVM | `% RAM` (MaxRAMPercentage), no `-Xmx` fijo |
| Management 9990 | No expuesto |
| Health | MicroProfile `/health` o HTTP app |

### 5.2 PHP / WordPress

```text
[Ingress] → [Nginx] → [PHP-FPM] → [MariaDB/MySQL]
                ↓           ↑
           static/uploads  env (WORDPRESS_* / DB_*)
```

| Decisión | Valor propuesto |
|----------|-----------------|
| Separación | Nginx ≠ PHP-FPM |
| Persistencia | `uploads` (WP); evitar `wp-content` completo en prod |
| Cron | `DISABLE_WP_CRON` + CronJob/WP-CLI |
| Admin updates | Off en prod (`DISALLOW_FILE_MODS`) |

### 5.3 Angular 12

```text
Build: Node 14 → dist/   |  Runtime: Nginx unprivileged → APIs backend
```

| Decisión | Valor propuesto |
|----------|-----------------|
| Runtime | Estático (salvo SSR) |
| Config | `config.json` runtime o fileReplacements en CI |
| Node 14 / NG 12 | EOL: plan de upgrade en backlog explícito |

### 5.4 .NET 5

```text
Build: SDK → publish  |  Runtime: aspnet (ideal net8) → BD/servicios
```

| Decisión | Valor propuesto |
|----------|-----------------|
| Binding | `ASPNETCORE_URLS=http://0.0.0.0:8080` |
| Health | `/health` |
| net5.0 | Contenerizable pero **EOL** → upgrade a 8 LTS recomendado |
| WinForms/WPF | No Linux containers → Windows container o rediseño |

---

## 6. Patrones transversales (3 min)

| Patrón | Cómo se aplica |
|--------|----------------|
| Multi-stage build | Dependencias en stage build; runtime mínimo |
| Secrets | No en imagen; vault/K8s secrets/Compose secrets |
| Health | Liveness ≠ Readiness; start-period según arranque |
| Recursos | requests/limits; JVM `%`; PHP-FPM `pm` |
| Observabilidad | stdout + correlation id; APM como sidecar/agente acordado |
| CI/CD | build image → scan → promote por tag inmutable |
| Rollback | redeploy tag anterior; DB migrations desacopladas si existen |

---

## 7. Roadmap y gobierno (3 min)

| Fase | Actividades | Salida |
|------|-------------|--------|
| 0. Discovery | Fichas + matriz | Clasificación acordada |
| 1. Foundation | Registry, bases aprobadas, pipeline plantilla, red/secrets | Landing zone contenedores |
| 2. Pilot (W1) | 1–2 apps Lift puro/Lift+ | Runbook + lecciones |
| 3. Scale (W2) | Resto Lift+ | Ops handover |
| 4. Complex (W3) | Refactor parcial | Apps con cambios de código |
| 5. Hypercare | Soporte post go-live | Cierre |

**RACI resumido (completar):**

| Actividad | Cliente App | Cliente Ops | Equipo migración | Seguridad |
|-----------|-------------|-------------|------------------|-----------|
| Cambios de código/config app | R/A | C | C | I |
| Dockerfile / Compose / manifiestos | C | C | R/A | C |
| Secrets / IAM | C | R | C | A |
| Go-live | A | R | C | C |

---

## 8. Riesgos y supuestos (2 min)

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Secretos en artefacto | Alto | Bloqueante en ficha; remediación antes de imagen prod |
| Estado no inventariado en disco | Alto | Pregunta decisiva de la ficha + prueba destroy/recreate |
| EOL (NET5 / NG12 / Node14) | Medio–Alto | Contenerizar + plan upgrade en paralelo |
| Sin acceso a código | Medio | Entrevista en pantalla + assess en bastion del cliente |
| Domain mode / Multisite / SSR / Win desktop | Alto | Clasificar Refactor o No apto; no forzar W1 |

**Supuestos a validar verbalmente:**

1.  
2.  
3.  

---

## 9. Próximos pasos y decisión pedida (2 min)

| # | Acción | Dueño | Fecha |
|---|--------|-------|-------|
| 1 | Aprobar clasificación y waves de la matriz | | |
| 2 | Autorizar Plan de migración detallado para apps Wave 1 | | |
| 3 | Confirmar registry / imágenes base permitidas | | |
| 4 | Nombrar interlocutores RACI por app piloto | | |
| 5 | Agendar sesión técnica de diseño (Dockerfile/Compose) | | |

**Decisión solicitada en esta reunión:**

> ☐ Aprobar estrategia y W1  
> ☐ Aprobar con cambios (anotar)  
> ☐ Requiere más discovery en apps: ___  

---

## Anexo — Guion del presentador (one-liner por bloque)

| Bloque | One-liner |
|--------|-----------|
| Objetivo | Mínimo cambio, máxima operabilidad en contenedor. |
| Método | Ficha → clasificación → plan; sin adivinar. |
| Principios | Efímero, env, non-root, health, logs stdout. |
| Portafolio | No todas las apps son iguales; olas por riesgo. |
| Arquitectura | Un patrón por stack; excepciones documentadas. |
| Transversal | Pipeline, secrets, probes, rollback. |
| Gobierno | Foundation → Pilot → Scale → Complex. |
| Cierre | Pedimos aprobación de W1 y dueños. |

---

## Checklist pre-exposición

- [ ] Matriz multi-app actualizada y validada con el interlocutor técnico  
- [ ] Al menos 1 diagrama por stack presente en el portafolio  
- [ ] Bloqueantes top 5 listos (sin secretos en claro)  
- [ ] Waves propuestas con esfuerzo T-shirt  
- [ ] Plantilla de Plan de migración lista para usar tras la aprobación  
- [ ] Material marcado como confidencial si aplica  
