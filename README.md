# MTA — Metodología de Traslado a Contenedores (Lift-and-Shift)

Repositorio de **metodología, plantillas y herramientas** para descubrir, clasificar y planificar la contenerización de aplicaciones cuando el código fuente **no puede salir del entorno del cliente**.

Enfoque: **Lift-and-Shift con ajustes mínimos**, alineado a Twelve-Factor (config por entorno, logs a stdout/stderr, proceso no-root, healthchecks, imágenes mínimas / multi-stage).

## Stacks cubiertos

| Familia | Runtime típico | Notas |
|---------|----------------|-------|
| Java / WildFly | WildFly 25 + Java 17 | Standalone; datasources; JVM `% RAM` |
| PHP | PHP-FPM + Nginx/Apache | Composer, OPcache |
| WordPress | Nginx + PHP-FPM + MariaDB/MySQL | Uploads, cron, secrets en env |
| Angular 12 | Node 14 (build) → Nginx | SPA vs SSR; EOL a documentar |
| .NET 5 | ASP.NET Core (`net5.0`) | Preferible upgrade a 8 LTS; Win desktop ≠ Linux |

## Flujo del programa

```text
Entrevista + código en pantalla (+ assess in-situ)
                    │
                    ▼
           Ficha técnica v2.0
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
 Exposición estrategia     Interpretación (manual)
 (olas / aprobación)               │
                                   ▼
                        Plan de migración
                     (pasos, gates, runbook)
                                   │
                                   ▼
              Dockerfile / Compose / CI (p. ej. sample WP)
```

1. **Descubrir** — ficha + (opcional) `assess_containerization.py` en el bastion del cliente.  
2. **Clasificar** — Lift puro / Lift + ajustes / Refactor parcial / No apto L&S.  
3. **Acordar** — exposición de estrategia y waves (W1–W3).  
4. **Planear** — documento de pasos por app con gates y aceptación.  
5. **Ejecutar** — empaquetado contenedor según el plan (sample WordPress como referencia).

## Estructura del repositorio

```text
mta/
├── README.md                          ← este archivo
├── docs/                              ← metodología y plantillas
│   ├── ficha-tecnica-contenorizacion.md
│   ├── ficha-tecnica-contenorizacion.xlsx
│   ├── generate_ficha_excel.py
│   ├── plantilla-exposicion-estrategia-migracion.md
│   ├── manual-interpretacion-ficha-a-plan-migracion.md
│   └── plantilla-plan-migracion-contenedores.md
├── scripts/                           ← evaluación automatizable
│   ├── assess_containerization.py
│   └── README-assess.md
└── samples/
    └── wordpress/                     ← referencia Lift-and-Shift WP
        ├── Dockerfile
        ├── compose.yml
        ├── compose.prod.yml
        └── README.md
```

## Documentación (`docs/`)

| Documento | Para qué sirve |
|-----------|----------------|
| [Ficha técnica](docs/ficha-tecnica-contenorizacion.md) | Captura as-is por app (entrevista + pantalla). También en [Excel](docs/ficha-tecnica-contenorizacion.xlsx). |
| [Exposición de estrategia](docs/plantilla-exposicion-estrategia-migracion.md) | Plantilla ejecutiva: principios, matriz, olas, decisión W1. |
| [Manual de interpretación](docs/manual-interpretacion-ficha-a-plan-migracion.md) | Cómo traducir ficha/assess → plan (scorecard, mapeos por stack, gates). |
| [Plan de migración](docs/plantilla-plan-migracion-contenedores.md) | Entregable operativo: fases 0–5, env map, volúmenes, runbook, rollback. |

Regenerar el Excel de la ficha:

```bash
python3 -m venv .venv && .venv/bin/pip install openpyxl
.venv/bin/python docs/generate_ficha_excel.py
```

## Herramienta de assessment (`scripts/`)

`assess_containerization.py` (Python 3.9+, solo stdlib) evalúa readiness **sin copiar código**: WAR/EAR, WildFly, PHP, WordPress, Angular, .NET y árbol `--source`. Emite scorecard, clasificación y reportes JSON/Markdown/CSV (secretos redactados).

```bash
# Ejemplo WordPress
python3 scripts/assess_containerization.py --app PortalWP \
  --wordpress-root /var/www/html \
  --source /var/www/html \
  --md-out PortalWP.md --json-out PortalWP.json

# Angular / .NET
python3 scripts/assess_containerization.py --app Front --angular-root /repo/ui --md-out front.md
python3 scripts/assess_containerization.py --app Api --dotnet-root /repo/api --md-out api.md
```

Detalle de flags y hallazgos: [scripts/README-assess.md](scripts/README-assess.md).

Prefijos de hallazgos → sección de ficha: `WF-*`/`JAVA-*`, `PHP-*`, `WP-*`, `NG-*`, `DN-*`, `SRC-*`, `CFG-*`.

## Sample WordPress (`samples/wordpress/`)

Referencia de contenedorización: **Nginx (unprivileged) + PHP-FPM + MariaDB**, OPcache prod, healthchecks, config por env, volumen de `uploads`.

```bash
cd samples/wordpress
cp .env.example .env   # editar secretos
docker compose up -d --build
# Prod: docker compose -f compose.yml -f compose.prod.yml up -d --build
```

Guía local: [samples/wordpress/README.md](samples/wordpress/README.md).

## Clasificación Lift-and-Shift

| Clase | Significado | Acción típica |
|-------|-------------|----------------|
| **Lift puro** | Casi sin cambios de app | Imagen + env + health |
| **Lift + ajustes** | Config, volúmenes, entrypoint, logs | Caso más frecuente |
| **Refactor parcial** | Cambios acotados antes de prod | Fases A→B con gates |
| **No apto L&S** | Rediseño (p. ej. WinForms, devices) | No forzar contenedor Linux |

## Principios de diseño (no negociables salvo excepción)

- Imagen inmutable; **config/secretos fuera** del artefacto  
- Contenedor **efímero**; estado solo en volúmenes explícitos  
- **USER no-root**; superficie mínima (Slim/Alpine/Distroless cuando aplique)  
- **Logs a stdout/stderr**; liveness ≠ readiness  
- Builds **multi-stage** y caché de dependencias  
- Dev/Prod por overlay/profiles, no por secretos embebidos  

## Privacidad y uso con el cliente

- La metodología asume **prohibición de retener código fuente** fuera del cliente.  
- Evidencia: entrevista, pantalla compartida, artefactos sanitizados, assess ejecutado **en su red**.  
- Reportes del assess: el cliente debe revisarlos antes de compartirlos (redacción de secretos incluida, no infalible).

## Requisitos

| Uso | Requisito |
|-----|-----------|
| Plantillas Markdown | Editor / Git |
| Regenerar Excel ficha | Python 3 + `openpyxl` |
| Assess | Python 3.9+ (stdlib) |
| Sample WordPress | Docker / Docker Compose |

## Roadmap de uso sugerido

1. Duplicar ficha Excel/MD por aplicación.  
2. Completar entrevista; opcionalmente correr assess en sitio.  
3. Consolidar en matriz multi-app (hoja `99_Matriz_MultiApp`).  
4. Presentar estrategia y acordar Wave 1.  
5. Por cada app W1: interpretar ficha → rellenar Plan de migración → implementar.  

## Licencia / confidencialidad

Material de trabajo metodológico para el programa de contenerización. Tratar entregables del cliente como **confidenciales** según su política; no versionar secretos ni dumps de código.
