#!/usr/bin/env python3
"""Genera la ficha técnica de contenerización en Excel."""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

OUT = Path(__file__).with_name("ficha-tecnica-contenorizacion.xlsx")

# Styles
HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
SECTION_FILL = PatternFill("solid", fgColor="2E75B6")
SECTION_FONT = Font(bold=True, color="FFFFFF", name="Calibri", size=12)
LABEL_FILL = PatternFill("solid", fgColor="D6E3F0")
LABEL_FONT = Font(bold=True, name="Calibri", size=10)
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
TITLE_FONT = Font(bold=True, name="Calibri", size=14, color="1F4E79")
NORMAL_FONT = Font(name="Calibri", size=10)
THIN = Border(
    left=Side(style="thin", color="B0B0B0"),
    right=Side(style="thin", color="B0B0B0"),
    top=Side(style="thin", color="B0B0B0"),
    bottom=Side(style="thin", color="B0B0B0"),
)
WRAP = Alignment(wrap_text=True, vertical="top")


def style_header_row(ws, row, cols):
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = WRAP
        cell.border = THIN


def style_section(ws, row, cols, title):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=cols)
    cell = ws.cell(row=row, column=1, value=title)
    cell.fill = SECTION_FILL
    cell.font = SECTION_FONT
    cell.alignment = Alignment(vertical="center")
    for c in range(1, cols + 1):
        ws.cell(row=row, column=c).fill = SECTION_FILL
        ws.cell(row=row, column=c).border = THIN


def add_kv_rows(ws, start_row, fields, cols=2):
    """fields: list of (label, placeholder optional). Returns next row."""
    r = start_row
    for item in fields:
        label = item[0]
        placeholder = item[1] if len(item) > 1 else ""
        ws.cell(row=r, column=1, value=label).font = LABEL_FONT
        ws.cell(row=r, column=1).fill = LABEL_FILL
        ws.cell(row=r, column=1).border = THIN
        ws.cell(row=r, column=1).alignment = WRAP
        val = ws.cell(row=r, column=2, value=placeholder)
        val.fill = INPUT_FILL
        val.border = THIN
        val.alignment = WRAP
        val.font = NORMAL_FONT
        if cols >= 3:
            for c in range(3, cols + 1):
                cell = ws.cell(row=r, column=c, value="")
                cell.fill = INPUT_FILL
                cell.border = THIN
        r += 1
    return r


def add_table(ws, start_row, headers, rows_data=None, empty_rows=0):
    """Write header + data/empty rows. Returns next row."""
    for i, h in enumerate(headers, 1):
        ws.cell(row=start_row, column=i, value=h)
    style_header_row(ws, start_row, len(headers))
    r = start_row + 1
    if rows_data:
        for row in rows_data:
            for i, v in enumerate(row, 1):
                cell = ws.cell(row=r, column=i, value=v)
                cell.border = THIN
                cell.alignment = WRAP
                cell.font = NORMAL_FONT
                if i > 1 or True:
                    cell.fill = INPUT_FILL
            r += 1
    for _ in range(empty_rows):
        for i in range(1, len(headers) + 1):
            cell = ws.cell(row=r, column=i, value="")
            cell.border = THIN
            cell.fill = INPUT_FILL
        r += 1
    return r


def set_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def add_yes_no_validation(ws, formula_range):
    dv = DataValidation(type="list", formula1='"Sí,No,Parcial,N/A"', allow_blank=True)
    dv.error = "Seleccione un valor de la lista"
    dv.errorTitle = "Valor inválido"
    ws.add_data_validation(dv)
    dv.add(formula_range)


def add_class_validation(ws, formula_range):
    dv = DataValidation(
        type="list",
        formula1='"Lift puro,Lift + ajustes,Refactor parcial,No apto L&S"',
        allow_blank=True,
    )
    ws.add_data_validation(dv)
    dv.add(formula_range)


def sheet_portada(wb):
    ws = wb.active
    ws.title = "00_Portada"
    ws["A1"] = "Ficha técnica v2.0 — Contenerización Lift-and-Shift"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:B1")
    ws["A3"] = (
        "Una ficha por aplicación. Stacks: WildFly/Java, PHP, WordPress, Angular 12, .NET 5. "
        "Fuente: entrevista + código en pantalla (sin copia local) + opcional assess_containerization.py. "
        "Objetivo: clasificar esfuerzo y diseñar contenedor mínimo."
    )
    ws["A3"].alignment = WRAP
    ws.merge_cells("A3:B3")
    ws.row_dimensions[3].height = 70

    r = add_kv_rows(
        ws,
        5,
        [
            ("Aplicación", ""),
            ("Código interno / alias", ""),
            ("Fecha entrevista", ""),
            ("Entrevistador(es)", ""),
            ("Interlocutores (rol)", ""),
            ("Duración (min)", ""),
            ("Medio (Meet/Teams/presencial)", ""),
            ("¿Código mostrado en pantalla?", "Sí / No / Parcial"),
            ("¿Se ejecutó assess_containerization.py?", "Sí / No"),
            ("Archivo reporte assess (si aplica)", ""),
            ("Grabación / acta autorizada", "Sí / No"),
            ("Clasificación preliminar", ""),
            ("Confianza de la clasificación", "Alta / Media / Baja"),
            (
                "Stack principal",
                "WildFly+Java17 / PHP / WordPress / Angular12 / .NET5 / Híbrido",
            ),
            ("Objetivo contenedor", "Solo local / QA / Producción"),
            ("Orquestación destino", "Compose / K8s / Otro"),
        ],
    )
    add_yes_no_validation(ws, "B12")
    add_yes_no_validation(ws, "B13")
    add_yes_no_validation(ws, "B15")
    add_class_validation(ws, "B16")

    conf = DataValidation(type="list", formula1='"Alta,Media,Baja"', allow_blank=True)
    ws.add_data_validation(conf)
    conf.add("B17")

    r += 1
    style_section(ws, r, 2, "Instrucciones de uso")
    r += 1
    instructions = [
        "1. Completar 00_Portada y 01_Identificacion al inicio de la entrevista.",
        "2. Pedir compartir pantalla y registrar evidencia en 02_Evidencia_Pantalla (sin pegar código).",
        "3. Completar hojas de build según stack: 03 Java, 04 PHP, 05 WP, 06 Angular, 07 .NET.",
        "4. Completar 08–13 (config, FS, integraciones, red, obs, operación).",
        "5. Cerrar con 14_Clasificacion_Diseno y 15_Backlog_Cambios.",
        "6. Celdas amarillas = captura. Listas desplegables donde existan.",
        "7. Duplicar este archivo por cada aplicación.",
    ]
    for line in instructions:
        ws.cell(row=r, column=1, value=line).font = NORMAL_FONT
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        r += 1

    set_widths(ws, [42, 55])
    ws.freeze_panes = "A5"


def sheet_identificacion(wb):
    ws = wb.create_sheet("01_Identificacion")
    ws["A1"] = "1. Identificación y alcance"
    ws["A1"].font = TITLE_FONT
    r = add_kv_rows(
        ws,
        3,
        [
            ("Descripción funcional (1–2 líneas)", ""),
            ("Criticidad", "P1 / P2 / P3"),
            ("Dueño funcional", ""),
            ("Dueño técnico", ""),
            (
                "Stack",
                "WildFly+Java17 / PHP / WordPress / Angular12 / .NET5 / Híbrido / Otro",
            ),
            ("Versión exacta WildFly", ""),
            ("Versión exacta Java + vendor", ""),
            ("Versión exacta PHP", ""),
            ("Versión WordPress", ""),
            ("Versión Angular / Node", ""),
            ("Versión .NET / SDK", ""),
            (
                "Tipo de empaquetado",
                "WAR / EAR / JAR / PHP / WP / SPA dist / DLL / Otro",
            ),
            ("Modo WildFly", "Standalone / Domain / N/A"),
            ("Nº instancias Dev / QA / Prod", ""),
            ("Restricción: sin código fuera del cliente", "Sí"),
            ("Notas de alcance", ""),
        ],
    )
    crit = DataValidation(type="list", formula1='"P1,P2,P3"', allow_blank=True)
    ws.add_data_validation(crit)
    crit.add("B4")
    modo = DataValidation(
        type="list", formula1='"Standalone,Domain,N/A"', allow_blank=True
    )
    ws.add_data_validation(modo)
    modo.add("B15")
    set_widths(ws, [45, 60])
    ws.row_dimensions[3].height = 40
    ws.row_dimensions[r - 1].height = 50


def sheet_evidencia(wb):
    ws = wb.create_sheet("02_Evidencia_Pantalla")
    ws["A1"] = "Evidencia vista en pantalla (sin retener código)"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (
        "Anotar qué se vio y el hallazgo. No pegar código fuente. "
        "Ruta/módulo solo como referencia verbal."
    )
    ws["A2"].alignment = WRAP
    ws.merge_cells("A2:E2")
    ws.row_dimensions[2].height = 35

    style_section(ws, 4, 5, "Registro de evidencia")
    add_table(
        ws,
        5,
        [
            "#",
            "Artefacto visto",
            "Ruta/módulo (solo referencia)",
            "Hallazgo clave",
            "Captura/nota autorizada (Sí/No)",
        ],
        rows_data=[[str(i), "", "", "", ""] for i in range(1, 11)],
    )
    add_yes_no_validation(ws, "E6:E15")

    style_section(ws, 17, 5, "Checklist de revisión en llamada")
    checklist = [
        "Build (pom/gradle/composer/package.json/csproj + lock)",
        "Artefacto despliegue (WAR/EAR/dist/publish/WP)",
        "Config por ambiente (props/XML/.env/wp-config/appsettings/environment.ts)",
        "Datasources / ConnectionStrings / DB_*",
        "Logging (log4j/jboss/monolog/serilog/WP debug)",
        "Paths escritura (uploads/storage/wp-content/uploads/data)",
        "Scripts start/stop/CLI / wp-cron / HostedService",
        "Health / readiness si existe",
        "Docker/CI existente (si hay)",
        "(WP) plugins/themes, Multisite, object-cache",
        "(Angular) SPA vs SSR, lockfile, Node engines",
        "(.NET) TFM net5.0, WinForms/WPF, health checks",
    ]
    add_table(
        ws,
        18,
        ["#", "Ítem a revisar en pantalla", "Revisado (Sí/No/Parcial)", "Notas"],
        rows_data=[[str(i + 1), item, "", ""] for i, item in enumerate(checklist)],
    )
    for r in range(19, 31):
        ws.cell(row=r, column=2).fill = PatternFill()
        ws.cell(row=r, column=1).fill = PatternFill()
    add_yes_no_validation(ws, "C19:C30")

    style_section(ws, 32, 5, "Anexo — Preguntas gatillo")
    triggers = [
        "Muéstrame dónde se define la conexión a BD y si cambia por ambiente.",
        "Busquemos en el proyecto rutas absolutas (C:\\, /opt/, \\\\server\\).",
        "¿Dónde se escriben uploads/temp y con qué usuario del SO?",
        "¿El WAR asume módulos ya instalados en WildFly o trae todo?",
        "¿Al reiniciar el servicio, la app cierra conexiones/colas limpio?",
        "¿Existe algún URL que el LB use hoy para saber si está viva?",
        "¿Hay timers, hilos daemon o procesos fuera del deployment?",
        "(PHP) ¿storage y bootstrap/cache escribibles solo por el usuario del pool?",
        "(WP) ¿Instalan plugins desde wp-admin en prod? ¿Multisite u object-cache?",
        "(WP) ¿DISABLE_WP_CRON activo? ¿Quién dispara el cron?",
        "(Angular) ¿SPA estática o SSR? ¿URLs API en environment.ts?",
        "(Angular) ¿Qué versión de Node usan en ng build?",
        "(.NET) ¿TFM solo net5.0? ¿Plan a .NET 8?",
        "(.NET) ¿WinForms/WPF, System.Drawing o paths C:\\?",
        "(.NET) ¿Existe MapHealthChecks / readiness para el LB?",
    ]
    add_table(
        ws,
        33,
        ["#", "Pregunta gatillo", "Usada", "Resumen respuesta"],
        rows_data=[[str(i + 1), t, "", ""] for i, t in enumerate(triggers)],
    )
    for r in range(34, 49):
        ws.cell(row=r, column=2).fill = PatternFill()
        ws.cell(row=r, column=1).fill = PatternFill()
    add_yes_no_validation(ws, "C34:C48")
    set_widths(ws, [5, 62, 35, 40, 28])


def sheet_build_java(wb):
    ws = wb.create_sheet("03_Build_Java_WildFly")
    ws["A1"] = "2.1 Empaquetado y build — Java / WildFly"
    ws["A1"].font = TITLE_FONT
    add_kv_rows(
        ws,
        3,
        [
            ("Herramienta de build", "Maven / Gradle / Ant / Manual"),
            ("¿Build reproducible en CI?", ""),
            ("Artefacto final y nombre", ""),
            ("Context path / nombre deployment", ""),
            ("Módulos custom en $JBOSS_HOME/modules", "Sí/No — lista:"),
            ("Perfil standalone*.xml usado", ""),
            (
                "Subsystems críticos",
                "datasources, messaging, mail, security…",
            ),
            ("Scripts JBoss CLI / post-deploy", "Sí/No — cuándo:"),
            ("Paths absolutos en config o código", "Sí/No — ejemplos:"),
            ("Evidencia en pantalla (resumen)", ""),
        ],
        cols=2,
    )
    add_yes_no_validation(ws, "B4")
    style_section(ws, 15, 2, "Cambios mínimos de build previstos")
    add_table(
        ws,
        16,
        ["#", "Cambio previsto"],
        empty_rows=5,
    )
    set_widths(ws, [48, 65])


def sheet_build_php(wb):
    ws = wb.create_sheet("04_Build_PHP")
    ws["A1"] = "2.2 Empaquetado y runtime — PHP"
    ws["A1"].font = TITLE_FONT
    add_kv_rows(
        ws,
        3,
        [
            ("Framework", "Laravel / Symfony / CI / Legacy / Otro"),
            ("SAPI actual", "Apache mod_php / PHP-FPM+Nginx / Otro"),
            ("Composer + lock en prod", ""),
            ("Extensiones requeridas", ""),
            ("Document root", ""),
            ("Rewrite / .htaccess / vhost", ""),
            ("OPcache en prod", ""),
            ("opcache.validate_timestamps", ""),
            ("Crons / queues / workers", ""),
            ("Evidencia en pantalla (resumen)", ""),
        ],
    )
    add_yes_no_validation(ws, "B5")
    add_yes_no_validation(ws, "B9")
    style_section(ws, 15, 2, "Cambios mínimos de build previstos")
    add_table(ws, 16, ["#", "Cambio previsto"], empty_rows=5)
    set_widths(ws, [42, 65])


def sheet_build_wordpress(wb):
    ws = wb.create_sheet("05_Build_WordPress")
    ws["A1"] = "2.3 Empaquetado y runtime — WordPress"
    ws["A1"].font = TITLE_FONT
    add_kv_rows(
        ws,
        3,
        [
            ("Versión WordPress (core)", ""),
            ("Multisite", ""),
            ("SAPI actual", "Apache mod_php / PHP-FPM+Nginx / Otro"),
            ("wp-config usa getenv/env", ""),
            ("DB_HOST / secretos en claro", ""),
            ("WP_HOME / WP_SITEURL", "Hardcode / env / BD"),
            ("DISABLE_WP_CRON", ""),
            ("DISALLOW_FILE_MODS (prod)", ""),
            ("Plugins (#) y críticos", ""),
            ("Themes (#)", ""),
            ("wp-content/uploads path", ""),
            ("object-cache.php (Redis/Memcached)", "Sí/No — backend:"),
            (".htaccess / rewrite", ""),
            ("Updates desde wp-admin en prod", ""),
            ("Extensiones PHP requeridas", "mysqli, gd, intl, zip, …"),
            (
                "Topología propuesta",
                "Nginx+PHP-FPM+DB / +Redis / +cron sidecar",
            ),
            ("Evidencia en pantalla (resumen)", ""),
        ],
    )
    for cell in ("B4", "B5", "B6", "B9", "B10", "B14", "B16"):
        add_yes_no_validation(ws, cell)
    style_section(ws, 22, 2, "Cambios mínimos WordPress")
    add_table(
        ws,
        23,
        ["#", "Cambio previsto"],
        rows_data=[
            ["1", "Externalizar DB_* y salts a env"],
            ["2", "Volumen solo uploads; DISALLOW_FILE_MODS"],
            ["3", "DISABLE_WP_CRON + CronJob/WP-CLI"],
            ["4", ""],
            ["5", ""],
        ],
    )
    set_widths(ws, [48, 65])


def sheet_build_angular(wb):
    ws = wb.create_sheet("06_Build_Angular12")
    ws["A1"] = "2.4 Empaquetado y build — Angular 12"
    ws["A1"].font = TITLE_FONT
    add_kv_rows(
        ws,
        3,
        [
            ("@angular/core exacta", "12.x.x"),
            ("Node engines / versión en CI", "típicamente 14.x"),
            ("Package manager + lockfile", "npm/yarn — lock Sí/No"),
            ("Tipo", "SPA estática / SSR-Universal / Híbrido"),
            ("outputPath (angular.json)", ""),
            ("environment*.ts — URLs API", "Hardcode / fileReplacements / runtime config"),
            ("Secretos en environments", ""),
            ("Base href / deploy URL", ""),
            ("i18n / monorepo multi-project", ""),
            ("Servidor estático destino", "Nginx / IIS / Otro"),
            ("Dockerfile existente", ""),
            (
                "Topología propuesta",
                "Multi-stage Node→Nginx / Node SSR / CDN+Nginx",
            ),
            ("Evidencia en pantalla (resumen)", ""),
        ],
    )
    add_yes_no_validation(ws, "B9")
    add_yes_no_validation(ws, "B13")
    style_section(ws, 18, 2, "Cambios mínimos Angular")
    add_table(
        ws,
        19,
        ["#", "Cambio previsto"],
        rows_data=[
            ["1", "Fijar Node 14 en stage de build + npm ci"],
            ["2", "Externalizar API URL (runtime config.json)"],
            ["3", "Nginx unprivileged sirve dist/ + HEALTHCHECK"],
            ["4", ""],
            ["5", ""],
        ],
    )
    set_widths(ws, [42, 65])


def sheet_build_dotnet(wb):
    ws = wb.create_sheet("07_Build_DotNet5")
    ws["A1"] = "2.5 Empaquetado y runtime — .NET 5"
    ws["A1"].font = TITLE_FONT
    add_kv_rows(
        ws,
        3,
        [
            ("Tipo proyecto", "ASP.NET Core / Worker / Library / Desktop"),
            ("TargetFramework", "net5.0 / multi-TFM"),
            ("SDK (global.json)", ""),
            ("Self-contained", ""),
            ("WinForms / WPF / RID win-*", ""),
            ("appsettings — secretos", ""),
            ("ConnectionStrings", ""),
            ("ASPNETCORE_URLS / Kestrel ports", ""),
            ("Health checks (/health)", ""),
            ("System.Drawing / Win32 APIs", ""),
            ("Hosted services / BackgroundService", ""),
            ("Plan upgrade a .NET 8 LTS", "Sí / No / En curso"),
            (
                "Imagen candidata",
                "mcr.microsoft.com/dotnet/aspnet:5.0 (EOL) / upgrade 8",
            ),
            (
                "Topología propuesta",
                "Multi-stage SDK→aspnet / Self-contained / Windows container",
            ),
            ("Evidencia en pantalla (resumen)", ""),
        ],
    )
    for cell in ("B6", "B7", "B11", "B12", "B13"):
        add_yes_no_validation(ws, cell)
    style_section(ws, 20, 2, "Cambios mínimos .NET")
    add_table(
        ws,
        21,
        ["#", "Cambio previsto"],
        rows_data=[
            ["1", "Externalizar ConnectionStrings a env/secrets"],
            ["2", "ASPNETCORE_URLS=http://0.0.0.0:8080 + USER no-root"],
            ["3", "HEALTHCHECK a /health; plan upgrade net8.0"],
            ["4", ""],
            ["5", ""],
        ],
    )
    set_widths(ws, [48, 65])


def sheet_config(wb):
    ws = wb.create_sheet("08_Config_Secretos")
    ws["A1"] = "3. Configuración y secretos (Twelve-Factor)"
    ws["A1"].font = TITLE_FONT
    style_section(ws, 3, 4, "Inventario de configuración")
    items = [
        "URL/credenciales BD",
        "LDAP/SSO",
        "URLs de APIs",
        "Mail/SMTP",
        "Feature flags",
        "Certificados / keystores",
        "WP salts / AUTH_KEY",
        "Angular API URL / keys",
        ".NET ConnectionStrings / ClientSecret",
        "Diferencias Dev vs Prod en el artefacto",
    ]
    add_table(
        ws,
        4,
        [
            "Ítem",
            "¿Dónde vive hoy?",
            "¿Externalizable a env/secret mount?",
            "Riesgo (Alto/Med/Bajo)",
        ],
        rows_data=[[i, "", "", ""] for i in items],
    )
    for r in range(5, 15):
        ws.cell(row=r, column=1).fill = PatternFill()
    ext = DataValidation(
        type="list", formula1='"Sí,No,Parcial"', allow_blank=True
    )
    ws.add_data_validation(ext)
    ext.add("C5:C14")
    risk = DataValidation(
        type="list", formula1='"Alto,Medio,Bajo"', allow_blank=True
    )
    ws.add_data_validation(risk)
    risk.add("D5:D14")

    r = 16
    style_section(ws, r, 4, "Resumen")
    add_kv_rows(
        ws,
        r + 1,
        [
            ("Mecanismo actual de secretos", "Archivo / env SO / vault / BD / hardcode"),
            ("¿Misma imagen Dev→Prod solo con env?", ""),
            (
                "Variables candidatas (lista)",
                "DB_HOST, WORDPRESS_*, ASPNETCORE_*, API_URL, …",
            ),
            ("Hallazgos de pantalla (config)", ""),
        ],
    )
    add_yes_no_validation(ws, "B18")
    style_section(ws, 23, 4, "Cambios mínimos de configuración")
    add_table(
        ws,
        24,
        ["Hecho", "Cambio"],
        rows_data=[
            ["", "Externalizar datasources / connection strings / DB_*"],
            ["", "Eliminar secretos (wp-config / appsettings / environment.ts)"],
            ["", "Overlay standalone / env / wp-config docker / config.json runtime"],
            ["", "Otros:"],
        ],
    )
    done = DataValidation(type="list", formula1='"☐,☑"', allow_blank=True)
    ws.add_data_validation(done)
    done.add("A25:A28")
    set_widths(ws, [42, 40, 35, 22])


def sheet_persistencia(wb):
    ws = wb.create_sheet("09_Persistencia_FS")
    ws["A1"] = "4. Estado, filesystem y persistencia"
    ws["A1"].font = TITLE_FONT
    style_section(ws, 3, 4, "Inventario de paths")
    add_table(
        ws,
        4,
        [
            "Path / recurso",
            "Lectura/Escritura (R/W)",
            "¿Persiste entre reinicios?",
            "Estrategia contenedor",
        ],
        empty_rows=8,
    )
    rw = DataValidation(type="list", formula1='"R,W,R/W"', allow_blank=True)
    ws.add_data_validation(rw)
    rw.add("B5:B12")
    add_yes_no_validation(ws, "C5:C12")
    strat = DataValidation(
        type="list",
        formula1='"Volume,PVC,Object storage,Efímero,Shared NFS/SMB"',
        allow_blank=True,
    )
    ws.add_data_validation(strat)
    strat.add("D5:D12")

    style_section(ws, 14, 4, "Resumen de estado")
    add_kv_rows(
        ws,
        15,
        [
            ("Sesiones en disco", ""),
            ("Uploads / reportes / temp", ""),
            ("WildFly data/log/content como estado", ""),
            ("PHP storage/ / var/ / uploads/", ""),
            ("WordPress wp-content/uploads (¿todo wp-content?)", ""),
            ("Angular: ¿estado en runtime? (normalmente N/A)", ""),
            (".NET: paths de archivos / DataProtection keys", ""),
            ("Permisos UID/GID esperados", ""),
            ("Shared storage entre nodos (NFS/SMB)", ""),
            (
                "Si el contenedor se recrea vacío, ¿qué pérdida es inaceptable?",
                "",
            ),
        ],
    )
    add_yes_no_validation(ws, "B15")
    add_yes_no_validation(ws, "B17")
    set_widths(ws, [58, 22, 28, 28])
    ws.row_dimensions[24].height = 45


def sheet_integraciones(wb):
    ws = wb.create_sheet("10_Integraciones")
    ws["A1"] = "5. Integraciones y datos"
    ws["A1"].font = TITLE_FONT
    style_section(ws, 3, 6, "Dependencias externas")
    deps = [
        "Base de datos",
        "Cola / JMS / Rabbit / Service Bus",
        "Caché (Infinispan/Redis/WP object-cache)",
        "LDAP/AD",
        "APIs REST/SOAP (Angular→backend)",
        "SMTP",
        "Otro",
        "Otro",
    ]
    add_table(
        ws,
        4,
        [
            "Dependencia",
            "Tecnología/versión",
            "Endpoint/host (sin secretos)",
            "Protocolo",
            "Criticidad",
            "Notas",
        ],
        rows_data=[[d, "", "", "", "", ""] for d in deps],
    )
    for r in range(5, 13):
        ws.cell(row=r, column=1).fill = PatternFill()
    crit = DataValidation(
        type="list", formula1='"Alta,Media,Baja"', allow_blank=True
    )
    ws.add_data_validation(crit)
    crit.add("E5:E12")

    style_section(ws, 14, 6, "Preguntas clave")
    add_kv_rows(
        ws,
        15,
        [
            ("¿Migraciones de schema? ¿Quién las ejecuta?", ""),
            ("¿Llamadas a localhost / procesos co-localizados?", ""),
            ("¿Dispositivos locales / impresoras / agentes en host?", ""),
        ],
    )
    set_widths(ws, [28, 22, 32, 14, 12, 30])


def sheet_ha_red(wb):
    ws = wb.create_sheet("11_HA_Red_TLS")
    ws["A1"] = "6–7. Sesión, clustering, HA, red y TLS"
    ws["A1"].font = TITLE_FONT
    style_section(ws, 3, 2, "Sesión / clustering / HA")
    add_kv_rows(
        ws,
        4,
        [
            ("Sticky session en LB", ""),
            ("Replicación de sesión (WildFly/.NET/WP)", ""),
            ("Cluster WildFly / JGroups", ""),
            ("EJB timers / singletons / .NET HostedService", ""),
            ("Angular SSR sticky (si aplica)", ""),
            ("Réplicas deseadas en contenedor", ""),
            (
                "Implicación para L&S",
                "Affinity / DNS_PING / Single replica / Refactor",
            ),
        ],
    )
    add_yes_no_validation(ws, "B4")
    add_yes_no_validation(ws, "B5")
    add_yes_no_validation(ws, "B6")
    add_yes_no_validation(ws, "B7")
    add_yes_no_validation(ws, "B8")

    style_section(ws, 13, 4, "Puertos")
    add_table(
        ws,
        14,
        [
            "Puerto / servicio",
            "Protocolo",
            "Expuesto hoy (Sí/No)",
            "¿Exponer en contenedor?",
        ],
        rows_data=[
            ["8080 HTTP", "HTTP", "", ""],
            ["8443 HTTPS", "HTTPS", "", ""],
            ["80/443 Nginx/Angular/WP", "HTTP/S", "", ""],
            ["9000 PHP-FPM", "FastCGI", "", "No público"],
            ["9990 Management WildFly", "HTTP", "", "No (recomendado)"],
            ["Kestrel (.NET)", "HTTP", "", ""],
            ["AJP / otros", "", "", ""],
        ],
    )
    add_yes_no_validation(ws, "C15:C21")

    style_section(ws, 23, 2, "TLS y exposición")
    add_kv_rows(
        ws,
        24,
        [
            ("Terminación TLS", "App / LB / Ambos"),
            ("Context path / base href", ""),
            ("Reverse proxy actual", ""),
            ("Restricciones por IP", ""),
        ],
    )
    set_widths(ws, [42, 40, 22, 28])


def sheet_obs_seg_res(wb):
    ws = wb.create_sheet("12_Obs_Seguridad_Recursos")
    ws["A1"] = "8–10. Observabilidad, seguridad y recursos"
    ws["A1"].font = TITLE_FONT

    style_section(ws, 3, 2, "Logs, health y ciclo de vida")
    add_kv_rows(
        ws,
        4,
        [
            ("Destino de logs hoy", "Archivo / Consola / Ambos — path:"),
            ("Framework de logging", ""),
            ("¿Viable redirigir a stdout/stderr?", ""),
            ("Health endpoint existente", "URL / No hay"),
            ("Criterio actual de “arrancó OK”", ""),
            ("Graceful shutdown hoy", ""),
            ("APM / JMX / agentes", ""),
            ("Métricas existentes", ""),
        ],
    )
    add_yes_no_validation(ws, "B6")
    add_yes_no_validation(ws, "B9")

    style_section(ws, 14, 4, "Probes sugeridos (borrador)")
    add_table(
        ws,
        15,
        ["Tipo", "Método", "Criterio", "Timeout / arranque"],
        rows_data=[
            ["Liveness", "", "", ""],
            ["Readiness", "", "", ""],
            ["HEALTHCHECK Docker", "", "", ""],
        ],
    )

    style_section(ws, 20, 2, "Seguridad y runtime")
    add_kv_rows(
        ws,
        21,
        [
            ("Usuario OS actual del proceso", "root / otro UID:"),
            ("¿Requiere root?", ""),
            ("UID/GID para volúmenes compartidos", ""),
            (
                "AuthN/AuthZ de la app",
                "JAAS / Keycloak / LDAP / Session / WP users / JWT / Otro",
            ),
            ("Base image permitida", "Pública / Solo registry interno"),
            ("Escaneo CVE / SBOM obligatorio", ""),
            ("Nota EOL (.NET 5 / Angular 12 / Node 14)", "Plan de upgrade:"),
        ],
    )
    add_yes_no_validation(ws, "B22")
    add_yes_no_validation(ws, "B26")

    style_section(ws, 30, 3, "Recursos JVM")
    add_table(
        ws,
        31,
        ["Campo", "Valor actual", "Propuesta contenedor"],
        rows_data=[
            ["-Xms / -Xmx", "", "% RAM (Initial/Max/MinRAMPercentage)"],
            ["GC / flags especiales", "", ""],
            ["RAM/CPU VM actual", "", "requests/limits:"],
            ["Tiempo arranque en frío", "", ""],
        ],
    )
    for r in range(32, 36):
        ws.cell(row=r, column=1).fill = PatternFill()

    style_section(ws, 37, 3, "Recursos PHP-FPM / WordPress")
    add_table(
        ws,
        38,
        ["Campo", "Valor actual", "Propuesta"],
        rows_data=[
            ["memory_limit", "", ""],
            ["pm / max children", "", ""],
            ["OPcache memory", "", ""],
            ["Workers / wp-cron aparte", "", "Sidecar / CronJob"],
        ],
    )
    for r in range(39, 43):
        ws.cell(row=r, column=1).fill = PatternFill()

    style_section(ws, 44, 3, "Recursos Angular (build)")
    add_table(
        ws,
        45,
        ["Campo", "Valor actual", "Propuesta"],
        rows_data=[
            ["NODE_OPTIONS / memoria CI", "", ""],
            ["Tiempo ng build --prod", "", ""],
        ],
    )
    for r in range(46, 48):
        ws.cell(row=r, column=1).fill = PatternFill()

    style_section(ws, 49, 3, "Recursos .NET")
    add_table(
        ws,
        50,
        ["Campo", "Valor actual", "Propuesta"],
        rows_data=[
            ["GC / Server GC", "", ""],
            ["RAM/CPU", "", "requests/limits"],
            ["Kestrel / ThreadPool limits", "", ""],
        ],
    )
    for r in range(51, 54):
        ws.cell(row=r, column=1).fill = PatternFill()
    set_widths(ws, [48, 40, 40, 22])


def sheet_ops(wb):
    ws = wb.create_sheet("13_Operacion_Restricciones")
    ws["A1"] = "11–12. Operación, CI/CD y restricciones del cliente"
    ws["A1"].font = TITLE_FONT
    style_section(ws, 3, 2, "Operación y CI/CD")
    add_kv_rows(
        ws,
        4,
        [
            ("Pipeline actual", ""),
            ("Quién construye / despliega", ""),
            ("Promoción entre ambientes", ""),
            ("Rollback actual", ""),
            (
                "¿Entregarán WAR/EAR o build en su CI?",
                "Artefacto / Dockerfile en su repo / Ambos",
            ),
            ("Operador post-handoff", ""),
        ],
    )
    style_section(ws, 12, 3, "Restricciones del cliente")
    add_table(
        ws,
        13,
        ["Restricción", "Sí/No/Parcial", "Detalle"],
        rows_data=[
            ["Prohibido retener código fuente", "", ""],
            ["Permitido ver código en llamada", "", ""],
            ["Comparten artefactos compilados", "", ""],
            ["Comparten configs sanitizadas", "", ""],
            ["Air-gapped / sin Docker Hub", "", ""],
            ["Compliance / datos sensibles", "", ""],
            ["Ventanas de cambio", "", ""],
        ],
    )
    for r in range(14, 21):
        ws.cell(row=r, column=1).fill = PatternFill()
    add_yes_no_validation(ws, "B14:B20")
    set_widths(ws, [48, 18, 50])


def sheet_clasificacion(wb):
    ws = wb.create_sheet("14_Clasificacion_Diseno")
    ws["A1"] = "13. Clasificación y decisión de diseño"
    ws["A1"].font = TITLE_FONT

    style_section(ws, 3, 4, "Scorecard rápido")
    criteria = [
        "Artefacto desplegable claro",
        "Config externalizable",
        "Sin domain/cluster/SSR/Win-desktop complejo",
        "Estado en disco acotado y mapeable",
        "Logs a stdout viable",
        "Health definible",
        "Proceso no-root viable",
        "Sin dependencia de host/local devices",
    ]
    add_table(
        ws,
        4,
        ["Criterio", "OK L&S", "Ajuste menor", "Bloqueante"],
        rows_data=[[c, "", "", ""] for c in criteria],
    )
    for r in range(5, 13):
        ws.cell(row=r, column=1).fill = PatternFill()
    mark = DataValidation(type="list", formula1='"X"', allow_blank=True)
    ws.add_data_validation(mark)
    mark.add("B5:D12")

    style_section(ws, 14, 2, "Clasificación final")
    add_kv_rows(
        ws,
        15,
        [
            ("Resultado", ""),
            ("Justificación (3–5 líneas)", ""),
            ("Esfuerzo estimado (T-shirt)", "S / M / L / XL"),
            ("Riesgo go-live", "Bajo / Medio / Alto"),
        ],
    )
    add_class_validation(ws, "B15")
    size = DataValidation(type="list", formula1='"S,M,L,XL"', allow_blank=True)
    ws.add_data_validation(size)
    size.add("B17")
    risk = DataValidation(
        type="list", formula1='"Bajo,Medio,Alto"', allow_blank=True
    )
    ws.add_data_validation(risk)
    risk.add("B18")
    ws.row_dimensions[16].height = 60

    style_section(ws, 20, 2, "Arquitectura de contenedor propuesta")
    add_kv_rows(
        ws,
        21,
        [
            (
                "Topología",
                "WildFly / Nginx+PHP-FPM / Nginx+WP / Nginx(Angular) / Node SSR / ASP.NET / sidecars",
            ),
            (
                "Imagen base candidata",
                "Temurin / WildFly / PHP-FPM Slim / nginx-unprivileged / node:14 / aspnet:5→8 / Distroless",
            ),
            ("Multi-stage", "Sí / No"),
            ("Usuario runtime (UID no-root)", ""),
            ("Volúmenes nombrados", ""),
            ("Red / servicios dependientes", ""),
            ("Compose profiles", "dev / prod"),
            ("Variables de entorno mínimas", ""),
            ("Secrets", ""),
            ("HEALTHCHECK", ""),
            ("Diagrama textual", "[LB] -> [Nginx?] -> [App] -> [BD/Redis]"),
        ],
    )
    add_yes_no_validation(ws, "B23")
    ws.row_dimensions[31].height = 50
    set_widths(ws, [48, 70, 16, 14])


def sheet_backlog(wb):
    ws = wb.create_sheet("15_Backlog_Cambios")
    ws["A1"] = "14. Backlog de modificaciones mínimas"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (
        "Solo cambios necesarios para contenerizar. Separar App / Runtime / Plataforma."
    )
    ws["A2"].alignment = WRAP
    ws.merge_cells("A2:G2")

    add_table(
        ws,
        4,
        [
            "ID",
            "Cambio",
            "Capa",
            "Prioridad",
            "Dueño",
            "¿Bloquea imagen?",
            "Validación",
        ],
        rows_data=[
            [f"C-{i:02d}", "", "", "", "", "", ""] for i in range(1, 16)
        ],
    )
    capa = DataValidation(
        type="list", formula1='"App,Runtime,Plataforma"', allow_blank=True
    )
    ws.add_data_validation(capa)
    capa.add("C5:C19")
    prio = DataValidation(
        type="list", formula1='"Alta,Media,Baja"', allow_blank=True
    )
    ws.add_data_validation(prio)
    prio.add("D5:D19")
    owner = DataValidation(
        type="list", formula1='"Cliente,Nosotros,Compartido"', allow_blank=True
    )
    ws.add_data_validation(owner)
    owner.add("E5:E19")
    add_yes_no_validation(ws, "F5:F19")

    style_section(ws, 21, 2, "Fuera de alcance (explícito)")
    add_table(ws, 22, ["#", "Ítem fuera de alcance"], empty_rows=5)

    style_section(ws, 29, 2, "Supuestos")
    add_table(ws, 30, ["#", "Supuesto"], empty_rows=5)

    style_section(ws, 37, 3, "Riesgos residuales")
    add_table(
        ws,
        38,
        ["Riesgo", "Impacto", "Mitigación"],
        empty_rows=5,
    )
    impact = DataValidation(
        type="list", formula1='"Alto,Medio,Bajo"', allow_blank=True
    )
    ws.add_data_validation(impact)
    impact.add("B39:B43")

    style_section(ws, 45, 3, "Artefactos a solicitar post-entrevista")
    arts = [
        "WAR/EAR o build artifact reproducible",
        "standalone.xml / overlay datasources (sanitizado)",
        "Lista de env vars / properties por ambiente",
        "Lista de puertos e integraciones",
        "Paths de escritura y requisitos UID/GID",
        "Flags JVM o pool PHP-FPM actuales",
        "Script start/stop y criterio de salud operativo",
        "PHP: composer.lock, vhost, extensiones, crontab",
        "WP: wp-config sanitizado, plugins/themes, tamaño uploads",
        "Angular: package-lock/yarn.lock, angular.json, environment*.ts sanitizado",
        ".NET: csproj, global.json, appsettings sanitizado, publish folder",
        "Política de imágenes base / registry",
        "Reporte assess_containerization.py (si aplica)",
    ]
    add_table(
        ws,
        46,
        ["Solicitado", "Artefacto", "Recibido"],
        rows_data=[["", a, ""] for a in arts],
    )
    for r in range(47, 60):
        ws.cell(row=r, column=2).fill = PatternFill()
    add_yes_no_validation(ws, "A47:A59")
    add_yes_no_validation(ws, "C47:C59")

    style_section(ws, 61, 2, "Cierre de entrevista")
    add_kv_rows(
        ws,
        62,
        [
            ("Clasificación provisional confirmada", ""),
            ("Bloqueantes encontrados", ""),
            ("Próximo entregable", "Diseño imagen + Compose/K8s + backlog C-xx"),
            ("Próxima sesión (si falta evidencia)", ""),
            ("Visto bueno verbal interlocutor técnico", "Sí/No — nombre:"),
        ],
    )
    add_class_validation(ws, "B62")
    set_widths(ws, [12, 55, 14, 12, 14, 16, 28])


def sheet_matriz(wb):
    """Hoja consolidada multi-app para portafolio."""
    ws = wb.create_sheet("99_Matriz_MultiApp")
    ws["A1"] = "Matriz consolidada multi-aplicación"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (
        "Copiar una fila por app tras cada entrevista. Útil para priorizar el portafolio."
    )
    ws.merge_cells("A2:L2")
    add_table(
        ws,
        4,
        [
            "App",
            "Stack",
            "Clasificación",
            "Esfuerzo",
            "Riesgo",
            "Config externalizable",
            "Estado en disco",
            "Cluster/HA complejo",
            "Health existente",
            "Bloqueantes (#)",
            "Dueño técnico",
            "Próximo paso",
        ],
        empty_rows=20,
    )
    add_class_validation(ws, "C5:C24")
    size = DataValidation(type="list", formula1='"S,M,L,XL"', allow_blank=True)
    ws.add_data_validation(size)
    size.add("D5:D24")
    risk = DataValidation(
        type="list", formula1='"Bajo,Medio,Alto"', allow_blank=True
    )
    ws.add_data_validation(risk)
    risk.add("E5:E24")
    yn = DataValidation(
        type="list", formula1='"Sí,No,Parcial,N/A"', allow_blank=True
    )
    ws.add_data_validation(yn)
    yn.add("F5:I24")
    set_widths(ws, [22, 18, 18, 10, 10, 18, 14, 16, 14, 12, 18, 28])


def main():
    wb = Workbook()
    sheet_portada(wb)
    sheet_identificacion(wb)
    sheet_evidencia(wb)
    sheet_build_java(wb)
    sheet_build_php(wb)
    sheet_build_wordpress(wb)
    sheet_build_angular(wb)
    sheet_build_dotnet(wb)
    sheet_config(wb)
    sheet_persistencia(wb)
    sheet_integraciones(wb)
    sheet_ha_red(wb)
    sheet_obs_seg_res(wb)
    sheet_ops(wb)
    sheet_clasificacion(wb)
    sheet_backlog(wb)
    sheet_matriz(wb)

    # print settings light touch
    for ws in wb.worksheets:
        ws.print_title_rows = "1:1"
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0

    wb.save(OUT)
    print(f"Generado: {OUT}")


if __name__ == "__main__":
    main()
