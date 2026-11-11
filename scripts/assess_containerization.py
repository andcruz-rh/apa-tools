#!/usr/bin/env python3
"""
Evaluador de readiness para contenerización Lift-and-Shift.

Diseñado para ejecutarse EN EL ENTORNO DEL CLIENTE (servidor de app, bastion
o workstation con acceso al deployment/código). No requiere dependencias
externas (solo Python 3.9+ stdlib).

Puede evaluar:
  - Artefactos WAR/EAR, standalone.xml, JBOSS_HOME, PHP runtime
  - WordPress, Angular (12.x) y .NET (5.x / net5.0)
  - Código fuente (vía --source) cuando el cliente lo permita en sitio

Ejemplos:
  python3 assess_containerization.py --app MiApp \\
    --war /opt/wildfly/standalone/deployments/app.war \\
    --jboss-home /opt/wildfly

  python3 assess_containerization.py --app PortalWP \\
    --wordpress-root /var/www/html \\
    --source /var/www/html

  python3 assess_containerization.py --app FrontAngular \\
    --angular-root /repo/frontend \\
    --source /repo/frontend

  python3 assess_containerization.py --app ApiNet \\
    --dotnet-root /repo/api \\
    --source /repo/api

IMPORTANTE:
  - No imprime secretos en claro (redacta password/user/secret/token/key).
  - No copia código fuente; solo analiza y reporta hallazgos (ruta relativa + snippet redactado).
  - Los puntos que requieren juicio humano quedan como "manual".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import zipfile
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "1.2.0"

SECRET_KEYS = re.compile(
    r"(password|passwd|pwd|secret|token|api[_-]?key|private[_-]?key|credential)",
    re.I,
)
ABS_PATH = re.compile(
    r"(?:(?:[A-Za-z]:\\|\\\\\\\\[^\\]+\\)|(?:/(?:opt|var|usr|home|data|apps|srv|mnt)/)[^\s\"'<>]+)"
)
LOCALHOST = re.compile(r"\b(localhost|127\.0\.0\.1|0\.0\.0\.0)\b", re.I)
JDBC_URL = re.compile(r"jdbc:[a-z0-9:+]+://[^\s\"'<>]+", re.I)
ENV_PLACEHOLDER = re.compile(
    r"\$\{?[A-Z0-9_]+\}?|%env\(|getenv\s*\(|env\s*\(|os\.environ|System\.getenv|"
    r"@ConfigProperty|config\.get\(|ConfigurationProvider",
    re.I,
)
HARDCODED_SECRET = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key)\s*[=:]\s*['\"]?([^'\"\s\$\{][^'\"\s]{2,})"
)
JAVA_ABS_FILE = re.compile(
    r"""(?:new\s+File\s*\(\s*|Paths\.get\s*\(\s*|Path\.of\s*\(\s*|Files\.(?:new|read|write|copy|move)\w*\s*\(\s*|File(?:Input|Output)Stream\s*\(\s*)['"]([A-Za-z]:\\|/)[^'"]+['"]"""
)
JAVA_TIMER = re.compile(
    r"@(?:Schedule|Schedules|Timeout|Startup)\b|TimerService|@Singleton\b",
    re.M,
)
JAVA_EXEC = re.compile(r"Runtime\.getRuntime\(\)\.exec\s*\(|ProcessBuilder\s*\(")
JAVA_STATEFUL = re.compile(r"@Stateful\b|HttpSession|javax\.servlet\.http\.HttpSession|jakarta\.servlet\.http\.HttpSession")
PHP_ABS_FILE = re.compile(
    r"""(?:fopen|file_get_contents|file_put_contents|readfile|move_uploaded_file|mkdir|chmod|unlink|rename|copy|SplFileObject|new\s+File)\s*\(\s*['"]([A-Za-z]:\\|/[^'"]+)['"]"""
)
PHP_EXEC = re.compile(r"\b(?:exec|shell_exec|system|passthru|proc_open|popen)\s*\(")
PHP_CHMOD_WORLD = re.compile(r"chmod\s*\([^,]+,\s*0?777\s*\)")
HEALTH_HINT = re.compile(
    r"@Readiness|@Liveness|@Health|/health|microprofile\.health|HealthCheck\b|actuator/health",
    re.I,
)

SKIP_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".idea",
    ".vscode",
    ".settings",
    "node_modules",
    "target",
    "build",
    "dist",
    "out",
    "bin",
    "obj",
    "__pycache__",
    ".tox",
    ".venv",
    "venv",
    "coverage",
    ".scannerwork",
    "bower_components",
}
SKIP_DIRS_OPTIONAL_VENDOR = {"vendor"}  # Composer vendor; omitido salvo --include-vendor

SOURCE_SUFFIXES = {
    ".java",
    ".php",
    ".phtml",
    ".jsp",
    ".jspx",
    ".xhtml",
    ".xml",
    ".properties",
    ".yml",
    ".yaml",
    ".json",
    ".env",
    ".conf",
    ".config",
    ".gradle",
    ".kts",
    ".sql",
    ".ini",
    ".cfg",
    ".txt",
    ".md",
    ".cs",
    ".csproj",
    ".fsproj",
    ".vbproj",
    ".ts",
    ".tsx",
    ".js",
}
SOURCE_BASENAMES = {
    "dockerfile",
    "containerfile",
    "makefile",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "composer.json",
    "composer.lock",
    "application.properties",
    "application.yml",
    "application.yaml",
    "persistence.xml",
    "beans.xml",
    "web.xml",
    "jboss-web.xml",
    "jboss-deployment-structure.xml",
    ".env",
    ".env.example",
    ".env.local",
    ".env.production",
    "wp-config.php",
    "wp-config-sample.php",
    "angular.json",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "global.json",
    "nuget.config",
    "appsettings.json",
    "appsettings.development.json",
    "appsettings.production.json",
}


@dataclass
class Finding:
    id: str
    area: str  # build|config|persistence|network|runtime|security|obs|php|java
    severity: str  # ok|info|low|medium|high|blocker
    title: str
    detail: str
    evidence: str = ""
    ficha_field: str = ""
    automated: bool = True


@dataclass
class Report:
    app_name: str
    generated_at: str
    tool_version: str
    host: str
    classification: str = "Sin datos suficientes"
    confidence: str = "Baja"
    effort_tshirt: str = "?"
    risk: str = "?"
    scorecard: dict[str, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    inventory: dict[str, Any] = field(default_factory=dict)
    manual_checklist: list[str] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)


def redact(text: str, limit: int = 240) -> str:
    if not text:
        return ""
    redacted = SECRET_KEYS.sub(lambda m: m.group(0), text)
    # Mask values after secret-like keys in key=value or XML attrs
    redacted = re.sub(
        r'(?i)(password|passwd|pwd|secret|token|api[_-]?key)\s*([=:])\s*([^\s"\'<>]+)',
        r"\1\2***REDACTED***",
        redacted,
    )
    redacted = re.sub(
        r'(?i)(password|secret|token)("\s*value\s*=\s*")([^"]*)(")',
        r"\1\2***REDACTED***\4",
        redacted,
    )
    redacted = re.sub(r"(?i)(password\s*=\s*)([^\s;]+)", r"\1***REDACTED***", redacted)
    if len(redacted) > limit:
        return redacted[: limit - 3] + "..."
    return redacted


def run_cmd(cmd: list[str], timeout: int = 15) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"comando no encontrado: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def read_text(path: Path, max_bytes: int = 2_000_000) -> str | None:
    try:
        data = path.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace")
    except OSError:
        return None


def iter_zip_text_members(
    zpath: Path, suffixes: tuple[str, ...] = (".xml", ".properties", ".yml", ".yaml", ".json", ".conf", ".env", ".txt")
) -> Iterable[tuple[str, str]]:
    try:
        with zipfile.ZipFile(zpath) as zf:
            for info in zf.infolist():
                if info.is_dir() or info.file_size > 1_500_000:
                    continue
                name = info.filename
                lower = name.lower()
                if not lower.endswith(suffixes):
                    continue
                try:
                    raw = zf.read(info)[:1_000_000]
                    yield name, raw.decode("utf-8", errors="replace")
                except Exception:
                    continue
    except zipfile.BadZipFile:
        return


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_host_runtime(report: Report) -> None:
    report.inventory["python"] = sys.version.split()[0]
    report.inventory["platform"] = sys.platform
    report.inventory["cwd"] = os.getcwd()
    uid = os.geteuid() if hasattr(os, "geteuid") else None
    report.inventory["scanner_uid"] = uid
    if uid == 0:
        report.add(
            Finding(
                id="SEC-001",
                area="security",
                severity="medium",
                title="El escáner corre como root",
                detail=(
                    "Si el proceso de la app también corre como root, habrá que "
                    "definir USER no-root en la imagen. Confirmar UID del servicio."
                ),
                ficha_field="09_Obs_Seguridad_Recursos / Usuario OS",
            )
        )
    else:
        report.add(
            Finding(
                id="SEC-001",
                area="security",
                severity="ok",
                title="Escáner no corre como root",
                detail=f"UID actual: {uid}",
                ficha_field="09_Obs_Seguridad_Recursos / Usuario OS",
            )
        )


def check_java(report: Report) -> None:
    code, out, err = run_cmd(["java", "-version"])
    text = (err or out)
    report.inventory["java_version_raw"] = text.splitlines()[:3]
    if code == 127:
        report.add(
            Finding(
                id="JAVA-001",
                area="java",
                severity="info",
                title="Java no disponible en PATH",
                detail="No se pudo ejecutar java -version en este host.",
                ficha_field="01_Identificacion / Versión Java",
            )
        )
        return

    m = re.search(r'version\s+"([^"]+)"', text)
    ver = m.group(1) if m else "desconocida"
    report.inventory["java_version"] = ver
    major = None
    if ver.startswith("1."):
        major = int(ver.split(".")[1])
    else:
        try:
            major = int(ver.split(".")[0])
        except ValueError:
            major = None

    if major is None:
        sev, title = "info", f"Java detectado: {ver}"
    elif major >= 11:
        sev, title = "ok", f"Java {ver} compatible con UseContainerSupport"
    else:
        sev, title = "high", f"Java {ver} antiguo para contenedores modernos"

    report.add(
        Finding(
            id="JAVA-001",
            area="java",
            severity=sev,
            title=title,
            detail="OpenJDK 11+ detecta cgroup limits (-XX:+UseContainerSupport por defecto).",
            evidence=redact(text),
            ficha_field="01_Identificacion / Versión Java",
        )
    )

    # JAVA_OPTS / common env
    for key in ("JAVA_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "JAVA_OPTIONS"):
        val = os.environ.get(key)
        if not val:
            continue
        report.inventory.setdefault("jvm_env", {})[key] = redact(val, 400)
        if re.search(r"-Xm[sx]\d", val):
            report.add(
                Finding(
                    id="JAVA-002",
                    area="runtime",
                    severity="medium",
                    title=f"{key} usa -Xms/-Xmx absolutos",
                    detail=(
                        "En contenedor preferir -XX:InitialRAMPercentage / "
                        "MaxRAMPercentage / MinRAMPercentage."
                    ),
                    evidence=redact(val),
                    ficha_field="09_Obs_Seguridad_Recursos / Recursos JVM",
                )
            )
        if "MaxRAMPercentage" in val or "UseContainerSupport" in val:
            report.add(
                Finding(
                    id="JAVA-003",
                    area="runtime",
                    severity="ok",
                    title=f"{key} ya contempla flags de contenedor",
                    detail="Se detectaron flags orientados a cgroup/RAM porcentual.",
                    evidence=redact(val),
                    ficha_field="09_Obs_Seguridad_Recursos / Recursos JVM",
                )
            )


def check_war_ear(report: Report, artifact: Path) -> None:
    if not artifact.exists():
        report.add(
            Finding(
                id="BUILD-001",
                area="build",
                severity="blocker",
                title="Artefacto WAR/EAR no encontrado",
                detail=str(artifact),
                ficha_field="03_Build_Java_WildFly / Artefacto",
            )
        )
        return

    report.inventory["artifact"] = {
        "path": str(artifact),
        "size_bytes": artifact.stat().st_size,
        "suffix": artifact.suffix.lower(),
    }
    report.add(
        Finding(
            id="BUILD-001",
            area="build",
            severity="ok",
            title="Artefacto desplegable presente",
            detail=f"{artifact.name} ({artifact.stat().st_size} bytes)",
            ficha_field="03_Build_Java_WildFly / Artefacto",
        )
    )

    abs_hits = []
    localhost_hits = []
    jdbc_hits = []
    file_log_hits = []
    env_hits = 0
    hardcoded_secret_hits = 0
    members_scanned = 0

    for name, content in iter_zip_text_members(artifact):
        members_scanned += 1
        for m in ABS_PATH.finditer(content):
            abs_hits.append((name, redact(m.group(0))))
        for m in LOCALHOST.finditer(content):
            localhost_hits.append((name, m.group(0)))
        for m in JDBC_URL.finditer(content):
            jdbc_hits.append((name, redact(m.group(0))))
        if re.search(r"(FileAppender|RollingFileAppender|file\s*Name\s*=\s*[\"']?/)", content, re.I):
            file_log_hits.append(name)
        if ENV_PLACEHOLDER.search(content):
            env_hits += 1
        # crude secret assignment detection (with or without quotes)
        if re.search(
            r"(?i)(password|passwd|secret|token)\s*[=:]\s*['\"]?([^'\"\s\$\{][^'\"\s]*)",
            content,
        ):
            hardcoded_secret_hits += 1

    report.inventory["artifact_scan"] = {
        "members_scanned": members_scanned,
        "absolute_paths": len(abs_hits),
        "localhost_refs": len(localhost_hits),
        "jdbc_urls": len(jdbc_hits),
        "file_log_configs": len(file_log_hits),
        "env_placeholder_files": env_hits,
        "possible_hardcoded_secrets": hardcoded_secret_hits,
    }

    if abs_hits:
        samples = "; ".join(f"{n}: {p}" for n, p in abs_hits[:5])
        report.add(
            Finding(
                id="CFG-001",
                area="config",
                severity="high",
                title="Rutas absolutas dentro del artefacto",
                detail="Riesgo alto en contenedor; externalizar paths o usar rutas relativas/volúmenes.",
                evidence=samples,
                ficha_field="03_Build_Java_WildFly / Paths absolutos",
            )
        )
    else:
        report.add(
            Finding(
                id="CFG-001",
                area="config",
                severity="ok",
                title="No se detectaron rutas absolutas obvias en el artefacto",
                detail=f"Archivos de texto escaneados: {members_scanned}",
                ficha_field="03_Build_Java_WildFly / Paths absolutos",
            )
        )

    if jdbc_hits:
        samples = "; ".join(f"{n}: {u}" for n, u in jdbc_hits[:5])
        # if looks externalized via ${}
        externalized = any("${" in u or "%" in u for _, u in jdbc_hits)
        report.add(
            Finding(
                id="CFG-002",
                area="config",
                severity="medium" if not externalized else "info",
                title="JDBC embebido en el artefacto",
                detail=(
                    "Preferible datasource en servidor/env. "
                    + ("Parece usar placeholders." if externalized else "Parece hardcodeado.")
                ),
                evidence=samples,
                ficha_field="05_Config_Secretos / URL BD",
            )
        )

    if hardcoded_secret_hits:
        report.add(
            Finding(
                id="CFG-003",
                area="config",
                severity="blocker",
                title="Posibles secretos hardcodeados en el artefacto",
                detail="Eliminar secretos del WAR/EAR y usar env/secret mount.",
                evidence=f"Archivos sospechosos: {hardcoded_secret_hits}",
                ficha_field="05_Config_Secretos",
            )
        )

    if localhost_hits:
        samples = "; ".join(f"{n}:{h}" for n, h in localhost_hits[:5])
        report.add(
            Finding(
                id="NET-001",
                area="network",
                severity="medium",
                title="Referencias a localhost dentro del artefacto",
                detail="En Compose/K8s localhost no alcanza otros servicios; usar nombres de servicio DNS.",
                evidence=samples,
                ficha_field="07_Integraciones / localhost",
            )
        )

    if file_log_hits:
        report.add(
            Finding(
                id="OBS-001",
                area="obs",
                severity="medium",
                title="Logging a archivo detectado en el artefacto",
                detail="Para contenedores, redirigir a stdout/stderr (CONSOLE appender).",
                evidence=", ".join(file_log_hits[:8]),
                ficha_field="09_Obs_Seguridad_Recursos / Logs",
            )
        )
    elif members_scanned:
        report.add(
            Finding(
                id="OBS-001",
                area="obs",
                severity="info",
                title="No se detectó FileAppender obvio en el artefacto",
                detail="Confirmar en llamada la config real de logging del servidor.",
                ficha_field="09_Obs_Seguridad_Recursos / Logs",
            )
        )

    if env_hits:
        report.add(
            Finding(
                id="CFG-004",
                area="config",
                severity="ok",
                title="Indicios de configuración externalizable",
                detail=f"Se vieron placeholders/env en {env_hits} archivo(s) del artefacto.",
                ficha_field="05_Config_Secretos / Externalizable",
            )
        )


def check_standalone_xml(report: Report, path: Path) -> None:
    text = read_text(path)
    if text is None:
        report.add(
            Finding(
                id="WF-001",
                area="java",
                severity="high",
                title="No se pudo leer standalone.xml",
                detail=str(path),
                ficha_field="03_Build_Java_WildFly / standalone.xml",
            )
        )
        return

    report.inventory["standalone_xml"] = str(path)
    report.add(
        Finding(
            id="WF-001",
            area="java",
            severity="ok",
            title="standalone.xml legible",
            detail=path.name,
            ficha_field="03_Build_Java_WildFly / standalone.xml",
        )
    )

    # Datasources
    ds_count = len(re.findall(r"<datasource\b", text, re.I))
    xa_count = len(re.findall(r"<xa-datasource\b", text, re.I))
    connection_urls = JDBC_URL.findall(text)
    has_vault_expr = bool(re.search(r"\$\{.*password|vault::|credential-reference", text, re.I))
    plaintext_pwd = bool(
        re.search(r'<password>[^$<{][^<]*</password>', text, re.I)
        or re.search(r'password="[^"$\{][^"]*"', text, re.I)
    )

    report.inventory["datasources"] = {
        "datasource_count": ds_count,
        "xa_datasource_count": xa_count,
        "jdbc_urls_found": [redact(u) for u in connection_urls[:10]],
        "credential_reference_or_expr": has_vault_expr,
        "plaintext_password_suspected": plaintext_pwd,
    }

    if ds_count or xa_count:
        sev = "blocker" if plaintext_pwd else "medium"
        report.add(
            Finding(
                id="WF-002",
                area="config",
                severity=sev,
                title=f"Datasources en servidor ({ds_count} + XA {xa_count})",
                detail=(
                    "Lift+ajustes: externalizar vía env/overlay/secret. "
                    + ("Posible password en claro." if plaintext_pwd else "Sin password en claro obvio.")
                ),
                evidence="; ".join(redact(u) for u in connection_urls[:5]) or "sin JDBC URL parseable",
                ficha_field="05_Config_Secretos / Datasources",
            )
        )

    # Logging to file
    if re.search(r'periodic-rotating-file-handler|size-rotating-file-handler|file\s+path=', text, re.I):
        report.add(
            Finding(
                id="WF-003",
                area="obs",
                severity="medium",
                title="Handlers de log a archivo en WildFly",
                detail="Configurar CONSOLE handler y recoger logs del contenedor.",
                ficha_field="09_Obs_Seguridad_Recursos / Logs",
            )
        )

    # Management interface
    if re.search(r'inet-address\s+value="\$\{jboss\.bind\.address\.management:0\.0\.0\.0\}"', text):
        report.add(
            Finding(
                id="WF-004",
                area="security",
                severity="high",
                title="Management bind potencialmente 0.0.0.0",
                detail="En contenedor no exponer 9990; bind a localhost o deshabilitar exposición.",
                ficha_field="08_HA_Red_TLS / Management",
            )
        )

    # Clustering / JGroups
    if re.search(r"<subsystem\s+xmlns=\"urn:jboss:domain:jgroups", text) or "jgroups" in text.lower():
        if re.search(r"UDP|MPING|multicast", text, re.I):
            report.add(
                Finding(
                    id="WF-005",
                    area="network",
                    severity="high",
                    title="JGroups/multicast detectado",
                    detail="Clustering en K8s suele requerir DNS_PING/KUBE_PING; no es lift puro.",
                    ficha_field="08_HA_Red_TLS / Cluster",
                )
            )
        else:
            report.add(
                Finding(
                    id="WF-005",
                    area="network",
                    severity="info",
                    title="Subsistema JGroups presente",
                    detail="Verificar si el cluster está realmente activo en prod.",
                    ficha_field="08_HA_Red_TLS / Cluster",
                )
            )

    # MicroProfile Health
    if re.search(r"microprofile-health|urn:wildfly:microprofile-health", text, re.I):
        report.add(
            Finding(
                id="WF-006",
                area="obs",
                severity="ok",
                title="MicroProfile Health presente en configuración",
                detail="Candidato a HEALTHCHECK/readiness (/health).",
                ficha_field="09_Obs_Seguridad_Recursos / Health",
            )
        )
    else:
        report.add(
            Finding(
                id="WF-006",
                area="obs",
                severity="medium",
                title="No se detectó MicroProfile Health en standalone.xml",
                detail="Habrá que definir health HTTP propio o probe TCP al puerto HTTP.",
                ficha_field="09_Obs_Seguridad_Recursos / Health",
            )
        )

    # Messaging
    if re.search(r"urn:jboss:domain:messaging-activemq", text):
        report.add(
            Finding(
                id="WF-007",
                area="network",
                severity="info",
                title="Messaging ActiveMQ/Artemis en WildFly",
                detail="Confirmar si el broker es embebido o externo; impacta topología de contenedores.",
                ficha_field="07_Integraciones / Cola JMS",
            )
        )


def check_jboss_home(report: Report, jboss_home: Path) -> None:
    if not jboss_home.exists():
        report.add(
            Finding(
                id="WF-010",
                area="java",
                severity="high",
                title="JBOSS_HOME no existe",
                detail=str(jboss_home),
                ficha_field="03_Build_Java_WildFly",
            )
        )
        return

    report.inventory["jboss_home"] = str(jboss_home)
    domain = jboss_home / "domain"
    standalone = jboss_home / "standalone"
    modules = jboss_home / "modules"

    if (domain / "configuration" / "domain.xml").exists() and not (standalone / "configuration").exists():
        report.add(
            Finding(
                id="WF-011",
                area="java",
                severity="blocker",
                title="Instalación orientada a domain mode",
                detail="Domain mode no es idóneo para contenedores; preferir standalone o refactor.",
                ficha_field="01_Identificacion / Modo WildFly",
            )
        )
    elif (standalone / "configuration").exists():
        report.add(
            Finding(
                id="WF-011",
                area="java",
                severity="ok",
                title="Standalone configuration presente",
                detail=str(standalone / "configuration"),
                ficha_field="01_Identificacion / Modo WildFly",
            )
        )

    # Custom modules (approx): modules with non-system paths that look custom
    custom_modules = []
    if modules.exists():
        for path in modules.rglob("module.xml"):
            rel = str(path.relative_to(modules))
            # Heuristic: org/jboss, org/wildfly, javax, com/sun often stock; flag others lightly
            if any(
                rel.startswith(p)
                for p in (
                    "org/jboss/",
                    "org/wildfly/",
                    "org/infinispan/",
                    "org/hibernate/",
                    "javax/",
                    "javaee/",
                    "io/undertow/",
                    "com/fasterxml/",
                    "org/apache/",
                    "org/glassfish/",
                    "org/slf4j/",
                    "org/jboss/as/",
                )
            ):
                continue
            custom_modules.append(rel)
            if len(custom_modules) >= 25:
                break

    report.inventory["custom_modules_suspect"] = custom_modules
    if custom_modules:
        report.add(
            Finding(
                id="WF-012",
                area="build",
                severity="medium",
                title=f"Posibles módulos custom ({len(custom_modules)})",
                detail="Deben copiarse a la imagen o empaquetarse; aumenta complejidad del Dockerfile.",
                evidence="; ".join(custom_modules[:8]),
                ficha_field="03_Build_Java_WildFly / Módulos custom",
            )
        )
    else:
        report.add(
            Finding(
                id="WF-012",
                area="build",
                severity="ok",
                title="No se detectaron módulos custom obvios",
                detail="Heurística sobre modules/; validar en entrevista.",
                ficha_field="03_Build_Java_WildFly / Módulos custom",
            )
        )

    # Writable / stateful dirs
    for rel in ("standalone/data", "standalone/log", "standalone/tmp", "standalone/deployments"):
        p = jboss_home / rel
        if p.exists():
            writable = os.access(p, os.W_OK)
            report.add(
                Finding(
                    id=f"FS-WF-{rel.replace('/', '-')}",
                    area="persistence",
                    severity="info" if writable else "low",
                    title=f"Directorio WildFly: {rel}",
                    detail=f"exists=True writable={writable}. En contenedor: volumen solo si debe persistir.",
                    ficha_field="06_Persistencia_FS",
                )
            )


def check_php(report: Report, php_root: Path | None, document_root: Path | None) -> None:
    code, out, err = run_cmd(["php", "-v"])
    if code == 127:
        report.add(
            Finding(
                id="PHP-001",
                area="php",
                severity="info",
                title="PHP no disponible en PATH",
                detail="Omitiendo checks de runtime PHP.",
                ficha_field="04_Build_PHP",
            )
        )
    else:
        first = (out or err).splitlines()[0] if (out or err) else "php"
        report.inventory["php_version_raw"] = first
        report.add(
            Finding(
                id="PHP-001",
                area="php",
                severity="ok",
                title=f"PHP detectado: {first}",
                detail="Usar imagen base alineada a esta versión mayor.",
                evidence=redact(first),
                ficha_field="04_Build_PHP / Versión",
            )
        )
        c2, mods, _ = run_cmd(["php", "-m"])
        if c2 == 0:
            mod_list = [m.strip() for m in mods.splitlines() if m.strip() and not m.startswith("[")]
            report.inventory["php_modules"] = mod_list
            report.add(
                Finding(
                    id="PHP-002",
                    area="php",
                    severity="ok",
                    title=f"Extensiones PHP cargadas: {len(mod_list)}",
                    detail="Mapear a install-php-extensions / docker-php-ext-*.",
                    evidence=", ".join(mod_list[:40]),
                    ficha_field="04_Build_PHP / Extensiones",
                )
            )
        c3, info, _ = run_cmd(["php", "-i"])
        if c3 == 0:
            opcache = "opcache.enable => On" in info or re.search(
                r"opcache\.enable\s*=>\s*On", info
            )
            validate = re.search(r"opcache\.validate_timestamps\s*=>\s*(\w+)", info)
            report.inventory["opcache_enable"] = bool(opcache)
            report.inventory["opcache_validate_timestamps"] = (
                validate.group(1) if validate else None
            )
            if opcache:
                vt = validate.group(1) if validate else "?"
                sev = "ok" if vt.lower() in {"off", "0"} else "medium"
                report.add(
                    Finding(
                        id="PHP-003",
                        area="php",
                        severity=sev,
                        title=f"OPcache enable; validate_timestamps={vt}",
                        detail="En producción: validate_timestamps=0.",
                        ficha_field="04_Build_PHP / OPcache",
                    )
                )
            else:
                report.add(
                    Finding(
                        id="PHP-003",
                        area="php",
                        severity="medium",
                        title="OPcache no aparece habilitado",
                        detail="Habilitar y tunear OPcache en imagen prod.",
                        ficha_field="04_Build_PHP / OPcache",
                    )
                )

    root = php_root or document_root
    if not root:
        return
    if not root.exists():
        report.add(
            Finding(
                id="PHP-010",
                area="php",
                severity="high",
                title="php-root/document-root no existe",
                detail=str(root),
                ficha_field="04_Build_PHP",
            )
        )
        return

    report.inventory["php_root"] = str(php_root) if php_root else None
    report.inventory["document_root"] = str(document_root) if document_root else None

    composer = None
    for base in filter(None, [php_root, document_root, (document_root.parent if document_root else None)]):
        cand = base / "composer.json"
        if cand.exists():
            composer = cand
            break
        cand2 = base.parent / "composer.json" if base else None
        if cand2 and cand2.exists():
            composer = cand2
            break

    if composer:
        report.inventory["composer_json"] = str(composer)
        lock = composer.with_name("composer.lock")
        report.add(
            Finding(
                id="PHP-011",
                area="php",
                severity="ok",
                title="composer.json encontrado",
                detail=str(composer),
                ficha_field="04_Build_PHP / Composer",
            )
        )
        if lock.exists():
            report.add(
                Finding(
                    id="PHP-012",
                    area="php",
                    severity="ok",
                    title="composer.lock presente",
                    detail="Builds reproducibles posibles (--no-dev --optimize-autoloader).",
                    ficha_field="04_Build_PHP / Composer lock",
                )
            )
        else:
            report.add(
                Finding(
                    id="PHP-012",
                    area="php",
                    severity="medium",
                    title="Falta composer.lock",
                    detail="Sin lock, el build de imagen no es reproducible.",
                    ficha_field="04_Build_PHP / Composer lock",
                )
            )
        raw = read_text(composer)
        if raw:
            if "laravel/framework" in raw:
                report.inventory["php_framework"] = "Laravel"
            elif "symfony/framework-bundle" in raw or "symfony/symfony" in raw:
                report.inventory["php_framework"] = "Symfony"
            elif "codeigniter4/framework" in raw:
                report.inventory["php_framework"] = "CodeIgniter"
    else:
        report.add(
            Finding(
                id="PHP-011",
                area="php",
                severity="info",
                title="No se encontró composer.json",
                detail="Puede ser legacy sin Composer; confirmar en entrevista.",
                ficha_field="04_Build_PHP / Composer",
            )
        )

    # .env secrets / config (dedupe by resolved path)
    env_candidates: list[Path] = []
    seen_env: set[str] = set()
    for base in filter(None, [php_root, document_root, (document_root.parent if document_root else None)]):
        for name in (".env", ".env.local", ".env.production", "application.properties"):
            p = base / name
            if not p.exists():
                continue
            key = str(p.resolve())
            if key in seen_env:
                continue
            seen_env.add(key)
            env_candidates.append(p)
    for env_path in env_candidates[:5]:
        content = read_text(env_path) or ""
        if SECRET_KEYS.search(content):
            report.add(
                Finding(
                    id="PHP-013",
                    area="config",
                    severity="high",
                    title=f"Archivo de config con secretos: {env_path.name}",
                    detail="No copiar a la imagen; inyectar por env/secret en runtime.",
                    evidence=str(env_path),
                    ficha_field="05_Config_Secretos",
                )
            )
        abs_m = ABS_PATH.search(content)
        if abs_m:
            report.add(
                Finding(
                    id="PHP-014",
                    area="config",
                    severity="medium",
                    title=f"Rutas absolutas en {env_path.name}",
                    detail=redact(abs_m.group(0)),
                    ficha_field="06_Persistencia_FS",
                )
            )

    # Writable dirs typical
    writable_targets = []
    bases = [b for b in [php_root, document_root, document_root.parent if document_root else None] if b]
    for base in bases:
        for rel in ("storage", "var", "var/cache", "var/log", "bootstrap/cache", "uploads", "public/uploads"):
            p = base / rel
            if p.exists():
                writable_targets.append(p)
    seen = set()
    for p in writable_targets:
        rp = str(p.resolve()) if p.exists() else str(p)
        if rp in seen:
            continue
        seen.add(rp)
        wr = os.access(p, os.W_OK)
        report.add(
            Finding(
                id=f"FS-PHP-{p.name}",
                area="persistence",
                severity="info",
                title=f"Directorio app: {p}",
                detail=f"writable={wr}. En prod debe pertenecer al UID no-root del contenedor (www-data).",
                ficha_field="06_Persistencia_FS",
            )
        )


def _looks_like_wordpress(root: Path) -> bool:
    return (root / "wp-config.php").exists() or (root / "wp-includes").is_dir() or (
        root / "wp-content"
    ).is_dir()


def _looks_like_angular(root: Path) -> bool:
    return (root / "angular.json").exists()


def _find_csproj_files(root: Path, limit: int = 30) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".csproj"):
                found.append(Path(dirpath) / name)
                if len(found) >= limit:
                    return found
    return found


def _looks_like_dotnet(root: Path) -> bool:
    return bool(_find_csproj_files(root, limit=1)) or (root / "global.json").exists()


def check_wordpress(report: Report, root: Path) -> None:
    """Checks específicos de portal WordPress."""
    if not root.exists():
        report.add(
            Finding(
                id="WP-000",
                area="php",
                severity="blocker",
                title="wordpress-root no existe",
                detail=str(root),
                ficha_field="04_Build_PHP / WordPress",
            )
        )
        return

    report.inventory["wordpress_root"] = str(root.resolve())
    report.add(
        Finding(
            id="WP-000",
            area="php",
            severity="ok",
            title="Árbol WordPress detectado",
            detail=str(root.resolve()),
            ficha_field="04_Build_PHP / WordPress",
        )
    )

    version_file = root / "wp-includes" / "version.php"
    ver_txt = read_text(version_file) if version_file.exists() else None
    wp_ver = None
    if ver_txt:
        m = re.search(r"\$wp_version\s*=\s*'([^']+)'", ver_txt)
        if m:
            wp_ver = m.group(1)
            report.inventory["wordpress_version"] = wp_ver
            report.add(
                Finding(
                    id="WP-001",
                    area="php",
                    severity="info",
                    title=f"WordPress version {wp_ver}",
                    detail="Fijar la misma versión en la imagen (no auto-update en prod).",
                    ficha_field="04_Build_PHP / Versión WP",
                )
            )

    cfg = root / "wp-config.php"
    sample = root / "wp-config-sample.php"
    cfg_text = read_text(cfg) if cfg.exists() else (read_text(sample) if sample.exists() else None)
    if cfg.exists():
        report.add(
            Finding(
                id="WP-002",
                area="config",
                severity="ok",
                title="wp-config.php presente",
                detail="Revisar secretos y DB_HOST para externalizar a env.",
                ficha_field="05_Config_Secretos",
            )
        )
    else:
        report.add(
            Finding(
                id="WP-002",
                area="config",
                severity="medium",
                title="Sin wp-config.php (solo sample o ausente)",
                detail="En contenedor generar desde env en entrypoint.",
                ficha_field="05_Config_Secretos",
            )
        )

    if cfg_text:
        if re.search(r"define\s*\(\s*['\"]DB_PASSWORD['\"]\s*,\s*['\"][^'\"]+['\"]", cfg_text):
            if "getenv" not in cfg_text and "$_ENV" not in cfg_text:
                report.add(
                    Finding(
                        id="WP-003",
                        area="config",
                        severity="blocker",
                        title="DB_PASSWORD hardcodeado en wp-config",
                        detail="Usar getenv/WORDPRESS_DB_PASSWORD o secret mount.",
                        evidence="wp-config.php",
                        ficha_field="05_Config_Secretos / BD",
                    )
                )
        if re.search(r"define\s*\(\s*['\"]DB_HOST['\"]\s*,\s*['\"]localhost['\"]", cfg_text, re.I):
            report.add(
                Finding(
                    id="WP-004",
                    area="network",
                    severity="medium",
                    title="DB_HOST=localhost en wp-config",
                    detail="En Compose/K8s usar el nombre del servicio de BD.",
                    ficha_field="07_Integraciones / BD",
                )
            )
        if "getenv(" in cfg_text or "$_ENV" in cfg_text or "$_SERVER[" in cfg_text:
            report.add(
                Finding(
                    id="WP-005",
                    area="config",
                    severity="ok",
                    title="wp-config usa variables de entorno",
                    detail="Buena señal Twelve-Factor.",
                    ficha_field="05_Config_Secretos",
                )
            )
        disable_cron = re.search(
            r"define\s*\(\s*['\"]DISABLE_WP_CRON['\"]\s*,\s*(true|false)", cfg_text, re.I
        )
        if disable_cron and disable_cron.group(1).lower() == "true":
            report.add(
                Finding(
                    id="WP-006",
                    area="runtime",
                    severity="ok",
                    title="DISABLE_WP_CRON=true",
                    detail="Complementar con CronJob/WP-CLI en contenedor sidecar.",
                    ficha_field="04_Build_PHP / Cron",
                )
            )
        else:
            report.add(
                Finding(
                    id="WP-006",
                    area="runtime",
                    severity="medium",
                    title="wp-cron por HTTP probablemente activo",
                    detail="En contenedores preferir DISABLE_WP_CRON + cron real.",
                    ficha_field="04_Build_PHP / Cron",
                )
            )
        if re.search(r"define\s*\(\s*['\"]MULTISITE['\"]\s*,\s*true", cfg_text, re.I):
            report.add(
                Finding(
                    id="WP-007",
                    area="network",
                    severity="high",
                    title="WordPress Multisite detectado",
                    detail="Requiere cuidado con dominios, cookies y reverse proxy.",
                    ficha_field="08_HA_Red_TLS",
                )
            )
        for const in ("WP_HOME", "WP_SITEURL"):
            if re.search(rf"define\s*\(\s*['\"]{const}['\"]\s*,\s*['\"]https?://", cfg_text):
                report.add(
                    Finding(
                        id="WP-008",
                        area="config",
                        severity="medium",
                        title=f"{const} hardcodeado",
                        detail="Externalizar URL pública por env (proxy/TLS).",
                        ficha_field="05_Config_Secretos / URL",
                    )
                )

    uploads = root / "wp-content" / "uploads"
    if uploads.exists():
        report.add(
            Finding(
                id="WP-010",
                area="persistence",
                severity="info",
                title="wp-content/uploads presente",
                detail=f"writable={os.access(uploads, os.W_OK)}. Debe ser volumen persistente.",
                ficha_field="06_Persistencia_FS",
            )
        )
    else:
        report.add(
            Finding(
                id="WP-010",
                area="persistence",
                severity="medium",
                title="No existe wp-content/uploads",
                detail="Crear y montar volumen en contenedor.",
                ficha_field="06_Persistencia_FS",
            )
        )

    object_cache = root / "wp-content" / "object-cache.php"
    if object_cache.exists():
        report.add(
            Finding(
                id="WP-011",
                area="network",
                severity="info",
                title="object-cache.php presente",
                detail="Probable Redis/Memcached externo; declarar servicio en Compose/K8s.",
                ficha_field="07_Integraciones / Caché",
            )
        )

    plugins = root / "wp-content" / "plugins"
    themes = root / "wp-content" / "themes"
    plugin_count = len([p for p in plugins.iterdir() if p.is_dir()]) if plugins.is_dir() else 0
    theme_count = len([p for p in themes.iterdir() if p.is_dir()]) if themes.is_dir() else 0
    report.inventory["wordpress_plugins"] = plugin_count
    report.inventory["wordpress_themes"] = theme_count
    report.add(
        Finding(
            id="WP-012",
            area="build",
            severity="info",
            title=f"Plugins={plugin_count}, Themes={theme_count}",
            detail="En prod fijar en imagen/CI; evitar instalar desde wp-admin.",
            ficha_field="04_Build_PHP / WordPress",
        )
    )

    htaccess = root / ".htaccess"
    if htaccess.exists():
        report.add(
            Finding(
                id="WP-013",
                area="network",
                severity="info",
                title=".htaccess presente",
                detail="Si se usa Nginx, traducir rewrite rules (try_files → index.php).",
                ficha_field="08_HA_Red_TLS / Reverse proxy",
            )
        )


def check_angular(report: Report, root: Path) -> None:
    """Checks Angular (enfoque 12.x) — SPA estática vs SSR."""
    if not root.exists():
        report.add(
            Finding(
                id="NG-000",
                area="build",
                severity="blocker",
                title="angular-root no existe",
                detail=str(root),
                ficha_field="Build / Angular",
            )
        )
        return

    report.inventory["angular_root"] = str(root.resolve())
    angular_json = root / "angular.json"
    package_json = root / "package.json"

    if not angular_json.exists():
        report.add(
            Finding(
                id="NG-000",
                area="build",
                severity="high",
                title="Sin angular.json en la raíz indicada",
                detail=str(root),
                ficha_field="Build / Angular",
            )
        )
        return

    report.add(
        Finding(
            id="NG-000",
            area="build",
            severity="ok",
            title="Proyecto Angular detectado",
            detail=str(root.resolve()),
            ficha_field="Build / Angular",
        )
    )

    pkg = {}
    pkg_raw = read_text(package_json) if package_json.exists() else None
    if pkg_raw:
        try:
            pkg = json.loads(pkg_raw)
        except json.JSONDecodeError:
            report.add(
                Finding(
                    id="NG-001",
                    area="build",
                    severity="medium",
                    title="package.json no parseable",
                    detail=str(package_json),
                    ficha_field="Build / Angular",
                )
            )

    deps = {}
    deps.update(pkg.get("dependencies") or {})
    deps.update(pkg.get("devDependencies") or {})
    ng_core = str(deps.get("@angular/core", ""))
    report.inventory["angular_core"] = ng_core

    major = None
    m = re.search(r"(\d+)\.", ng_core.lstrip("^~>=< "))
    if m:
        major = int(m.group(1))

    if major == 12:
        report.add(
            Finding(
                id="NG-002",
                area="build",
                severity="ok",
                title="Angular 12 detectado",
                detail="Imagen de build: Node 14.x (compatible típico). Runtime: Nginx estático.",
                evidence=f"@angular/core={ng_core}",
                ficha_field="Build / Angular 12",
            )
        )
    elif major is not None:
        sev = "info" if major > 12 else "high"
        report.add(
            Finding(
                id="NG-002",
                area="build",
                severity=sev,
                title=f"Angular {major} (no 12)",
                detail="Ajustar versión de Node en multi-stage según la major.",
                evidence=f"@angular/core={ng_core}",
                ficha_field="Build / Angular",
            )
        )
    else:
        report.add(
            Finding(
                id="NG-002",
                area="build",
                severity="medium",
                title="No se pudo determinar versión de @angular/core",
                detail="Revisar package.json / package-lock.json",
                ficha_field="Build / Angular",
            )
        )

    engines = pkg.get("engines") or {}
    if engines:
        report.add(
            Finding(
                id="NG-003",
                area="build",
                severity="ok",
                title=f"engines definidos: {engines}",
                detail="Respetar en stage de build (nvm/Node image tag).",
                ficha_field="Build / Node",
            )
        )
    else:
        report.add(
            Finding(
                id="NG-003",
                area="build",
                severity="info",
                title="Sin campo engines en package.json",
                detail="Angular 12 suele requerir Node 14.15+ / 14.20; fijarlo en Dockerfile.",
                ficha_field="Build / Node",
            )
        )

    if (root / "package-lock.json").exists() or (root / "yarn.lock").exists():
        report.add(
            Finding(
                id="NG-004",
                area="build",
                severity="ok",
                title="Lockfile presente",
                detail="Builds reproducibles (npm ci / yarn --frozen-lockfile).",
                ficha_field="Build / Angular",
            )
        )
    else:
        report.add(
            Finding(
                id="NG-004",
                area="build",
                severity="medium",
                title="Sin package-lock.json ni yarn.lock",
                detail="El build de imagen no será reproducible.",
                ficha_field="Build / Angular",
            )
        )

    # SSR?
    if "@nguniversal/express-engine" in deps or "@angular/ssr" in deps or (
        root / "server.ts"
    ).exists():
        report.add(
            Finding(
                id="NG-005",
                area="runtime",
                severity="high",
                title="SSR / Universal detectado",
                detail="No es solo Nginx estático: contenedor Node + health + no-root.",
                ficha_field="Runtime / Angular SSR",
            )
        )
    else:
        report.add(
            Finding(
                id="NG-005",
                area="runtime",
                severity="ok",
                title="SPA sin SSR aparente",
                detail="Lift típico: multi-stage Node build → Nginx unprivileged sirve /dist.",
                ficha_field="Runtime / Angular",
            )
        )

    # environment files with hardcoded API URLs
    env_hits = []
    env_dir = root / "src" / "environments"
    if env_dir.is_dir():
        for p in sorted(env_dir.glob("environment*.ts")):
            text = read_text(p) or ""
            if LOCALHOST.search(text) or re.search(r"https?://", text):
                env_hits.append(_rel(root, p))
            if HARDCODED_SECRET.search(text):
                report.add(
                    Finding(
                        id="NG-006",
                        area="config",
                        severity="blocker",
                        title=f"Posible secreto en {p.name}",
                        detail="No versionar secretos en environments; usar env de CI o runtime config.json",
                        evidence=_rel(root, p),
                        ficha_field="05_Config_Secretos",
                    )
                )
    if env_hits:
        report.add(
            Finding(
                id="NG-007",
                area="config",
                severity="medium",
                title="URLs en environment*.ts",
                detail="Para contenedores: fileReplacements por env o config.json cargado en runtime.",
                evidence=", ".join(env_hits[:6]),
                ficha_field="05_Config_Secretos / API URL",
            )
        )

    # angular.json output path
    aj = read_text(angular_json) or ""
    try:
        aj_data = json.loads(aj)
        projects = aj_data.get("projects") or {}
        outs = []
        for name, proj in projects.items():
            arch = (proj.get("architect") or {}).get("build") or {}
            options = arch.get("options") or {}
            out = options.get("outputPath")
            if out:
                outs.append(f"{name}:{out}")
        report.inventory["angular_output_paths"] = outs
        if outs:
            report.add(
                Finding(
                    id="NG-008",
                    area="build",
                    severity="ok",
                    title="outputPath detectado",
                    detail="Usar esa ruta como COPY --from=build en Nginx.",
                    evidence="; ".join(outs[:6]),
                    ficha_field="Build / Angular dist",
                )
            )
    except json.JSONDecodeError:
        report.add(
            Finding(
                id="NG-008",
                area="build",
                severity="medium",
                title="angular.json no parseable",
                detail=str(angular_json),
                ficha_field="Build / Angular",
            )
        )

    if (root / "Dockerfile").exists() or (root / "docker-compose.yml").exists():
        report.add(
            Finding(
                id="NG-009",
                area="runtime",
                severity="info",
                title="Ya hay Docker en el frontend",
                detail="Validar multi-stage, non-root y HEALTHCHECK.",
                ficha_field="10_Operacion",
            )
        )


def check_dotnet(report: Report, root: Path) -> None:
    """Checks .NET (enfoque net5.0 / .NET 5)."""
    if not root.exists():
        report.add(
            Finding(
                id="DN-000",
                area="runtime",
                severity="blocker",
                title="dotnet-root no existe",
                detail=str(root),
                ficha_field="Build / .NET",
            )
        )
        return

    report.inventory["dotnet_root"] = str(root.resolve())
    csprojs = _find_csproj_files(root)
    if not csprojs:
        report.add(
            Finding(
                id="DN-000",
                area="runtime",
                severity="high",
                title="No se encontraron .csproj",
                detail=str(root),
                ficha_field="Build / .NET",
            )
        )
        return

    report.add(
        Finding(
            id="DN-000",
            area="runtime",
            severity="ok",
            title=f"Proyecto(s) .NET detectados ({len(csprojs)})",
            detail=", ".join(_rel(root, p) for p in csprojs[:8]),
            ficha_field="Build / .NET",
        )
    )

    frameworks = []
    windows_hints = 0
    self_contained_hints = 0
    for proj in csprojs:
        text = read_text(proj) or ""
        for m in re.finditer(
            r"<TargetFramework(s)?>([^<]+)</TargetFramework(s)?>", text, re.I
        ):
            frameworks.append(m.group(2).strip())
        if re.search(r"net5\.0|netcoreapp5", text, re.I):
            pass
        if re.search(r"UseWindowsForms|UseWPF|RuntimeIdentifier>win", text, re.I):
            windows_hints += 1
        if re.search(r"<SelfContained>true</SelfContained>", text, re.I):
            self_contained_hints += 1
        if re.search(r"Microsoft\.AspNetCore", text) or (proj.parent / "Program.cs").exists():
            pass

    report.inventory["dotnet_target_frameworks"] = frameworks
    tfm_join = ", ".join(sorted(set(frameworks))) or "desconocido"
    has_net5 = any("net5.0" in f.replace(" ", "") for f in frameworks)
    has_eol_only = has_net5 and not any(
        re.search(r"net(?:6|7|8|9)\.0", f) for f in frameworks
    )

    if has_net5:
        report.add(
            Finding(
                id="DN-001",
                area="runtime",
                severity="high" if has_eol_only else "info",
                title="TargetFramework net5.0 detectado",
                detail=(
                    ".NET 5 está fuera de soporte. Contenerizable con "
                    "mcr.microsoft.com/dotnet/aspnet:5.0, pero planificar upgrade a 8 LTS."
                ),
                evidence=tfm_join,
                ficha_field="Build / .NET 5",
            )
        )
    else:
        report.add(
            Finding(
                id="DN-001",
                area="runtime",
                severity="info",
                title=f"TFM(s): {tfm_join}",
                detail="Ajustar SDK/runtime tags de la imagen multi-stage.",
                ficha_field="Build / .NET",
            )
        )

    if windows_hints:
        report.add(
            Finding(
                id="DN-002",
                area="runtime",
                severity="blocker",
                title="Dependencias Windows (WinForms/WPF/win-RID)",
                detail="No apto para contenedor Linux sin rediseño; evaluar Windows containers.",
                ficha_field="Runtime / .NET",
            )
        )
    else:
        report.add(
            Finding(
                id="DN-002",
                area="runtime",
                severity="ok",
                title="Sin indicios WinForms/WPF/win-RID",
                detail="Candidato a imagen Linux (aspnet/runtime).",
                ficha_field="Runtime / .NET",
            )
        )

    if self_contained_hints:
        report.add(
            Finding(
                id="DN-003",
                area="build",
                severity="info",
                title="SelfContained=true en algún csproj",
                detail="Imagen más pesada; alternativa: framework-dependent + aspnet base.",
                ficha_field="Build / .NET",
            )
        )

    # appsettings
    for name in (
        "appsettings.json",
        "appsettings.Development.json",
        "appsettings.Production.json",
    ):
        # search shallow + one level
        candidates = list(root.glob(name)) + list(root.glob(f"*/{name}"))
        for cfg in candidates[:6]:
            text = read_text(cfg) or ""
            rel = _rel(root, cfg)
            if HARDCODED_SECRET.search(text) or re.search(
                r'"(Password|ClientSecret|ApiKey)"\s*:\s*"[^"$\{][^"]+"', text
            ):
                report.add(
                    Finding(
                        id="DN-010",
                        area="config",
                        severity="blocker",
                        title=f"Posibles secretos en {rel}",
                        detail="Usar env vars / user-secrets (dev) / montaje de secrets (prod).",
                        evidence=rel,
                        ficha_field="05_Config_Secretos",
                    )
                )
            if LOCALHOST.search(text):
                report.add(
                    Finding(
                        id="DN-011",
                        area="network",
                        severity="medium",
                        title=f"localhost en {rel}",
                        detail="ConnectionStrings/URLs deben apuntar a servicios DNS del compose.",
                        evidence=rel,
                        ficha_field="07_Integraciones",
                    )
                )
            if ABS_PATH.search(text):
                report.add(
                    Finding(
                        id="DN-012",
                        area="config",
                        severity="high",
                        title=f"Ruta absoluta en {rel}",
                        detail="Usar paths bajo /app o volúmenes.",
                        evidence=redact(ABS_PATH.search(text).group(0)),
                        ficha_field="06_Persistencia_FS",
                    )
                )

    # Program.cs / Startup hints
    for prog in list(root.glob("**/Program.cs"))[:15]:
        text = read_text(prog) or ""
        rel = _rel(root, prog)
        if re.search(r"Listen\(.*80|UseUrls\(|ASPNETCORE_URLS", text):
            report.add(
                Finding(
                    id="DN-020",
                    area="network",
                    severity="info",
                    title=f"Binding Kestrel referenciado en {rel}",
                    detail="En contenedor preferir ASPNETCORE_URLS=http://0.0.0.0:8080 y USER no-root.",
                    evidence=rel,
                    ficha_field="08_HA_Red_TLS",
                )
            )
        if re.search(r"MapHealthChecks\s*\(|AddHealthChecks\s*\(", text):
            report.add(
                Finding(
                    id="DN-021",
                    area="obs",
                    severity="ok",
                    title="Health checks ASP.NET detectados",
                    detail="Usar /health en HEALTHCHECK/readiness.",
                    evidence=rel,
                    ficha_field="09_Obs / Health",
                )
            )
        if re.search(r"System\.Drawing|Microsoft\.Win32|Directory\.GetCurrentDirectory", text):
            if "System.Drawing" in text or "Microsoft.Win32" in text:
                report.add(
                    Finding(
                        id="DN-022",
                        area="runtime",
                        severity="high",
                        title=f"API Windows-specific en {rel}",
                        detail="Puede fallar en contenedor Linux (libgdiplus / Win32).",
                        evidence=rel,
                        ficha_field="Runtime / .NET",
                    )
                )

    # Runtime check
    code, out, err = run_cmd(["dotnet", "--list-runtimes"])
    if code == 0 and (out or err):
        report.inventory["dotnet_runtimes_host"] = (out or err).splitlines()[:12]
        report.add(
            Finding(
                id="DN-030",
                area="runtime",
                severity="info",
                title="dotnet runtime(s) en el host del escáner",
                detail="Solo informativo; la imagen debe traer su propio runtime.",
                evidence=redact((out or err)[:300]),
                ficha_field="Build / .NET",
            )
        )

    global_json = root / "global.json"
    if global_json.exists():
        gj = read_text(global_json) or ""
        report.add(
            Finding(
                id="DN-031",
                area="build",
                severity="ok",
                title="global.json presente",
                detail="Fijar la misma SDK en el stage de build.",
                evidence=redact(gj, 200),
                ficha_field="Build / .NET SDK",
            )
        )


def check_ports(report: Report, ports: list[int]) -> None:
    open_ports = []
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            try:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    open_ports.append(port)
            except OSError:
                pass
    report.inventory["local_open_ports"] = open_ports
    if open_ports:
        report.add(
            Finding(
                id="NET-010",
                area="network",
                severity="info",
                title=f"Puertos locales abiertos: {open_ports}",
                detail="Mapear exposición mínima en contenedor; 9990 no debe publicarse.",
                ficha_field="08_HA_Red_TLS / Puertos",
            )
        )
        if 9990 in open_ports:
            report.add(
                Finding(
                    id="NET-011",
                    area="security",
                    severity="high",
                    title="Puerto management 9990 abierto en localhost",
                    detail="No publicar en la imagen/orquestación de producción.",
                    ficha_field="08_HA_Red_TLS / Management",
                )
            )


def check_docker_presence(report: Report, roots: list[Path]) -> None:
    found = []
    for root in roots:
        if not root or not root.exists():
            continue
        for name in ("Dockerfile", "docker-compose.yml", "compose.yml", "docker-compose.yaml"):
            p = root / name
            if p.exists():
                found.append(str(p))
        # shallow search
        try:
            for p in root.glob("**/Dockerfile"):
                found.append(str(p))
                if len(found) >= 10:
                    break
        except OSError:
            pass
    found = sorted(set(found))
    report.inventory["docker_files"] = found
    if found:
        report.add(
            Finding(
                id="OPS-001",
                area="runtime",
                severity="info",
                title="Ya existen artefactos Docker",
                detail="Revisar si cumplen multi-stage, non-root, HEALTHCHECK.",
                evidence="; ".join(found[:8]),
                ficha_field="10_Operacion_Restricciones",
            )
        )


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _sample(hits: list[str], n: int = 5) -> str:
    return "; ".join(hits[:n])


def iter_source_files(
    root: Path,
    *,
    include_vendor: bool,
    max_files: int,
    max_file_bytes: int,
) -> Iterable[Path]:
    skip = set(SKIP_DIRS)
    if not include_vendor:
        skip |= SKIP_DIRS_OPTIONAL_VENDOR

    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # prune in-place
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".gradle")]
        for name in filenames:
            path = Path(dirpath) / name
            lower = name.lower()
            suffix = path.suffix.lower()
            interesting = suffix in SOURCE_SUFFIXES or lower in SOURCE_BASENAMES
            if not interesting:
                continue
            try:
                if path.stat().st_size > max_file_bytes:
                    continue
            except OSError:
                continue
            yield path
            count += 1
            if count >= max_files:
                return


def check_source_tree(
    report: Report,
    source_root: Path,
    *,
    include_vendor: bool = False,
    max_files: int = 4000,
    max_file_bytes: int = 750_000,
) -> None:
    """Analiza código fuente Java/PHP/config sin copiarlo."""
    if not source_root.exists() or not source_root.is_dir():
        report.add(
            Finding(
                id="SRC-000",
                area="build",
                severity="blocker",
                title="--source no es un directorio válido",
                detail=str(source_root),
                ficha_field="02_Evidencia_Pantalla / Código fuente",
            )
        )
        return

    report.inventory["source_root"] = str(source_root.resolve())
    report.add(
        Finding(
            id="SRC-000",
            area="build",
            severity="ok",
            title="Código fuente disponible para análisis",
            detail=str(source_root.resolve()),
            ficha_field="02_Evidencia_Pantalla / Código fuente",
        )
    )

    # Build descriptors
    build_hits = []
    for name in (
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "composer.json",
        "package.json",
    ):
        p = source_root / name
        if p.exists():
            build_hits.append(name)
        else:
            # one-level modules
            for child in source_root.iterdir() if source_root.is_dir() else []:
                if child.is_dir() and (child / name).exists():
                    build_hits.append(f"{child.name}/{name}")
    report.inventory["source_build_files"] = build_hits
    if build_hits:
        report.add(
            Finding(
                id="SRC-001",
                area="build",
                severity="ok",
                title="Descriptores de build en el árbol fuente",
                detail="Útiles para multi-stage y caché de dependencias.",
                evidence=", ".join(build_hits[:12]),
                ficha_field="03_Build_Java_WildFly / 04_Build_PHP",
            )
        )
    else:
        report.add(
            Finding(
                id="SRC-001",
                area="build",
                severity="medium",
                title="No se halló pom/gradle/composer en la raíz (ni 1er nivel)",
                detail="Confirmar cómo se construye el artefacto.",
                ficha_field="03_Build_Java_WildFly / Build",
            )
        )

    buckets: dict[str, list[str]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    files_scanned = 0
    java_files = 0
    php_files = 0
    truncated = False

    for path in iter_source_files(
        source_root,
        include_vendor=include_vendor,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
    ):
        files_scanned += 1
        if files_scanned >= max_files:
            truncated = True
        rel = _rel(source_root, path)
        suffix = path.suffix.lower()
        if suffix == ".java":
            java_files += 1
        elif suffix in {".php", ".phtml"}:
            php_files += 1

        content = read_text(path, max_bytes=max_file_bytes)
        if content is None:
            continue

        def add_hit(key: str, line_hint: str) -> None:
            counts[key] += 1
            if len(buckets[key]) < 8:
                buckets[key].append(f"{rel}: {redact(line_hint, 120)}")

        # Absolute paths (generic + language helpers)
        for m in ABS_PATH.finditer(content):
            # skip common false positives in docs/licenses briefly
            if suffix == ".md" and "http" in m.group(0).lower():
                continue
            add_hit("abs_path", m.group(0))
        for m in JAVA_ABS_FILE.finditer(content):
            add_hit("java_abs_io", m.group(0)[:160])
        for m in PHP_ABS_FILE.finditer(content):
            add_hit("php_abs_io", m.group(0)[:160])

        for m in LOCALHOST.finditer(content):
            add_hit("localhost", m.group(0))
        for m in JDBC_URL.finditer(content):
            add_hit("jdbc", m.group(0))
        for m in HARDCODED_SECRET.finditer(content):
            # ignore placeholders / obvious non-secrets
            val = m.group(2)
            if val.lower() in {"null", "true", "false", "changeme", "xxx", "***", "password", "secret"}:
                continue
            if val.startswith("${") or val.startswith("%") or val.startswith("env("):
                continue
            add_hit("secret", m.group(0))
        if ENV_PLACEHOLDER.search(content):
            counts["env_usage"] += 1
            if len(buckets["env_usage"]) < 8:
                buckets["env_usage"].append(rel)

        if re.search(
            r"(FileAppender|RollingFileAppender|periodic-rotating-file-handler|"
            r"fileName\s*=\s*[\"']?/|logging\.file\s*=|log_file\s*=)",
            content,
            re.I,
        ):
            add_hit("file_log", rel)

        if JAVA_TIMER.search(content):
            add_hit("java_timer", rel)
        if JAVA_EXEC.search(content):
            add_hit("java_exec", rel)
        if JAVA_STATEFUL.search(content) and suffix == ".java":
            add_hit("java_stateful", rel)
        if PHP_EXEC.search(content):
            add_hit("php_exec", rel)
        if PHP_CHMOD_WORLD.search(content):
            add_hit("php_chmod777", rel)
        if HEALTH_HINT.search(content):
            add_hit("health", rel)

        # PHP world-writable intent / storage writes are informational via abs paths already

    report.inventory["source_scan"] = {
        "files_scanned": files_scanned,
        "java_files": java_files,
        "php_files": php_files,
        "truncated_by_max_files": truncated,
        "include_vendor": include_vendor,
        "counts": dict(counts),
    }

    if truncated:
        report.add(
            Finding(
                id="SRC-002",
                area="build",
                severity="info",
                title=f"Escaneo truncado en {max_files} archivos",
                detail="Aumentar --max-files si el monorepo es grande.",
                ficha_field="02_Evidencia_Pantalla",
            )
        )

    report.add(
        Finding(
            id="SRC-003",
            area="build",
            severity="info",
            title=f"Archivos fuente escaneados: {files_scanned}",
            detail=f"Java={java_files}, PHP={php_files}",
            ficha_field="02_Evidencia_Pantalla / Código fuente",
        )
    )

    # Emit findings by bucket
    if counts.get("abs_path") or counts.get("java_abs_io") or counts.get("php_abs_io"):
        total = counts.get("abs_path", 0) + counts.get("java_abs_io", 0) + counts.get("php_abs_io", 0)
        samples = _sample(
            buckets["java_abs_io"] + buckets["php_abs_io"] + buckets["abs_path"]
        )
        report.add(
            Finding(
                id="SRC-010",
                area="config",
                severity="high",
                title=f"Rutas absolutas / I/O a path fijo en fuente ({total})",
                detail="Rompe portabilidad del contenedor; externalizar paths o usar volúmenes.",
                evidence=samples,
                ficha_field="03_Build / Paths absolutos",
            )
        )
    else:
        report.add(
            Finding(
                id="SRC-010",
                area="config",
                severity="ok",
                title="Sin rutas absolutas obvias en el código escaneado",
                detail=f"Archivos revisados: {files_scanned}",
                ficha_field="03_Build / Paths absolutos",
            )
        )

    if counts.get("secret"):
        report.add(
            Finding(
                id="SRC-011",
                area="config",
                severity="blocker",
                title=f"Posibles secretos hardcodeados en fuente ({counts['secret']})",
                detail="Mover a env/secret manager antes de imagen de prod.",
                evidence=_sample(buckets["secret"]),
                ficha_field="05_Config_Secretos",
            )
        )

    if counts.get("jdbc"):
        report.add(
            Finding(
                id="SRC-012",
                area="config",
                severity="medium",
                title=f"URLs JDBC en código/config fuente ({counts['jdbc']})",
                detail="Preferible datasource/env externalizado.",
                evidence=_sample(buckets["jdbc"]),
                ficha_field="05_Config_Secretos / BD",
            )
        )

    if counts.get("localhost"):
        report.add(
            Finding(
                id="SRC-013",
                area="network",
                severity="medium",
                title=f"Referencias a localhost/127.0.0.1 en fuente ({counts['localhost']})",
                detail="En Compose/K8s usar nombres DNS de servicio.",
                evidence=_sample(buckets["localhost"]),
                ficha_field="07_Integraciones / localhost",
            )
        )

    if counts.get("env_usage"):
        report.add(
            Finding(
                id="SRC-014",
                area="config",
                severity="ok",
                title=f"Uso de env/config externalizada ({counts['env_usage']} archivos)",
                detail="Buen señal Twelve-Factor; mapear variables a la ficha.",
                evidence=_sample(buckets["env_usage"]),
                ficha_field="05_Config_Secretos / Externalizable",
            )
        )
    elif files_scanned:
        report.add(
            Finding(
                id="SRC-014",
                area="config",
                severity="medium",
                title="Poco o ningún uso detectable de env/config externa",
                detail="Riesgo de config embebida; validar en entrevista.",
                ficha_field="05_Config_Secretos / Externalizable",
            )
        )

    if counts.get("file_log"):
        report.add(
            Finding(
                id="SRC-015",
                area="obs",
                severity="medium",
                title=f"Logging a archivo en fuente/config ({counts['file_log']})",
                detail="Redirigir a stdout/stderr en contenedor.",
                evidence=_sample(buckets["file_log"]),
                ficha_field="09_Obs_Seguridad_Recursos / Logs",
            )
        )

    if counts.get("health"):
        report.add(
            Finding(
                id="SRC-016",
                area="obs",
                severity="ok",
                title="Indicios de health endpoint en fuente",
                detail="Candidato a HEALTHCHECK/readiness.",
                evidence=_sample(buckets["health"]),
                ficha_field="09_Obs_Seguridad_Recursos / Health",
            )
        )
    elif java_files or php_files:
        report.add(
            Finding(
                id="SRC-016",
                area="obs",
                severity="info",
                title="Sin indicios claros de /health en fuente",
                detail="Definir probe TCP/HTTP o endpoint dedicado.",
                ficha_field="09_Obs_Seguridad_Recursos / Health",
            )
        )

    if counts.get("java_timer"):
        report.add(
            Finding(
                id="SRC-020",
                area="java",
                severity="high",
                title=f"Timers/Schedule/Singleton detectados ({counts['java_timer']})",
                detail="Puede impedir multi-réplica ingenua; validar afinidad o single-replica.",
                evidence=_sample(buckets["java_timer"]),
                ficha_field="08_HA_Red_TLS / EJB timers",
            )
        )

    if counts.get("java_stateful"):
        report.add(
            Finding(
                id="SRC-021",
                area="java",
                severity="info",
                title=f"Uso de sesión/stateful en Java ({counts['java_stateful']})",
                detail="Confirmar sticky session o replicación al diseñar réplicas.",
                evidence=_sample(buckets["java_stateful"]),
                ficha_field="08_HA_Red_TLS / Sesión",
            )
        )

    if counts.get("java_exec") or counts.get("php_exec"):
        total = counts.get("java_exec", 0) + counts.get("php_exec", 0)
        report.add(
            Finding(
                id="SRC-022",
                area="security",
                severity="high",
                title=f"Ejecución de procesos OS desde la app ({total})",
                detail="En contenedor distroless/minimal puede fallar; revisar binarios necesarios.",
                evidence=_sample(buckets["java_exec"] + buckets["php_exec"]),
                ficha_field="09_Obs_Seguridad_Recursos / Runtime",
            )
        )

    if counts.get("php_chmod777"):
        report.add(
            Finding(
                id="SRC-023",
                area="security",
                severity="medium",
                title=f"chmod 777 en código PHP ({counts['php_chmod777']})",
                detail="Evitar; fijar UID no-root y permisos mínimos en volúmenes.",
                evidence=_sample(buckets["php_chmod777"]),
                ficha_field="06_Persistencia_FS / Permisos",
            )
        )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

SEVERITY_WEIGHT = {
    "ok": 0,
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 4,
    "blocker": 8,
}


def classify(report: Report) -> None:
    findings = report.findings
    blockers = [f for f in findings if f.severity == "blocker"]
    highs = [f for f in findings if f.severity == "high"]
    mediums = [f for f in findings if f.severity == "medium"]
    score = sum(SEVERITY_WEIGHT.get(f.severity, 0) for f in findings)

    # Scorecard aligned to ficha 11
    def status(ok_ids: list[str], bad_sevs: set[str], area_pred) -> str:
        relevant = [f for f in findings if area_pred(f)]
        if not relevant:
            return "Sin datos"
        if any(f.severity in bad_sevs for f in relevant):
            if any(f.severity == "blocker" for f in relevant):
                return "Bloqueante"
            return "Ajuste menor" if all(f.severity != "high" for f in relevant) else "Ajuste menor"
        if any(f.severity in {"high", "medium"} for f in relevant):
            return "Ajuste menor"
        return "OK L&S"

    report.scorecard = {
        "Artefacto desplegable claro": status(
            [], {"blocker"}, lambda f: f.id.startswith("BUILD-")
        ),
        "Config externalizable": status(
            [],
            {"blocker", "high"},
            lambda f: f.id
            in {
                "CFG-001",
                "CFG-002",
                "CFG-003",
                "WF-002",
                "PHP-013",
                "SRC-010",
                "SRC-011",
                "SRC-012",
                "SRC-014",
                "WP-003",
                "WP-005",
                "WP-008",
                "NG-006",
                "NG-007",
                "DN-010",
                "DN-012",
            },
        ),
        "Sin domain mode / cluster complejo": status(
            [],
            {"blocker", "high"},
            lambda f: f.id in {"WF-011", "WF-005", "SRC-020", "WP-007", "NG-005", "DN-002"},
        ),
        "Estado en disco acotado y mapeable": status(
            [],
            {"blocker"},
            lambda f: f.area == "persistence" or f.id in {"SRC-010", "SRC-023", "WP-010", "DN-012"},
        ),
        "Logs a stdout viable": status(
            [],
            {"high"},
            lambda f: f.id in {"OBS-001", "WF-003", "SRC-015"},
        ),
        "Health definible": status(
            [],
            {"blocker"},
            lambda f: f.id in {"WF-006", "SRC-016", "DN-021"},
        ),
        "Proceso no-root viable": status(
            [],
            {"blocker"},
            lambda f: f.id.startswith("SEC-")
            or f.id in {"SRC-022", "SRC-023", "DN-002", "DN-022"},
        ),
        "Sin dependencia localhost/host": status(
            [],
            {"high"},
            lambda f: f.id in {"NET-001", "SRC-013", "WP-004", "DN-011", "NG-007"},
        ),
    }

    # Refine scorecard cells more precisely
    def set_card(key: str, value: str) -> None:
        report.scorecard[key] = value

    if any(f.id == "BUILD-001" and f.severity == "ok" for f in findings):
        set_card("Artefacto desplegable claro", "OK L&S")
    if any(f.id == "BUILD-001" and f.severity == "blocker" for f in findings):
        set_card("Artefacto desplegable claro", "Bloqueante")

    if any(f.id in {"CFG-003", "SRC-011", "WP-003", "NG-006", "DN-010"} for f in findings) or any(
        f.id == "WF-002" and f.severity == "blocker" for f in findings
    ):
        set_card("Config externalizable", "Bloqueante")
    elif any(
        f.id
        in {
            "CFG-001",
            "CFG-002",
            "WF-002",
            "PHP-013",
            "SRC-010",
            "SRC-012",
            "SRC-014",
            "WP-008",
            "NG-007",
            "DN-012",
        }
        and f.severity in {"high", "medium"}
        for f in findings
    ):
        set_card("Config externalizable", "Ajuste menor")
    elif any(f.id in {"CFG-004", "SRC-014", "WP-005"} and f.severity == "ok" for f in findings):
        set_card("Config externalizable", "OK L&S")

    if any(f.id == "WF-011" and f.severity == "blocker" for f in findings):
        set_card("Sin domain mode / cluster complejo", "Bloqueante")
    elif any(f.id == "DN-002" and f.severity == "blocker" for f in findings):
        set_card("Sin domain mode / cluster complejo", "Bloqueante")
    elif any(f.id in {"WF-005", "SRC-020", "WP-007", "NG-005"} and f.severity == "high" for f in findings):
        set_card("Sin domain mode / cluster complejo", "Bloqueante")
    elif any(f.id == "WF-011" and f.severity == "ok" for f in findings):
        set_card("Sin domain mode / cluster complejo", "OK L&S")

    if any(f.id in {"OBS-001", "WF-003", "SRC-015"} and f.severity == "medium" for f in findings):
        set_card("Logs a stdout viable", "Ajuste menor")
    elif any(f.id in {"OBS-001", "SRC-015"} and f.severity in {"ok", "info"} for f in findings):
        set_card("Logs a stdout viable", "OK L&S")

    if any(f.id in {"WF-006", "SRC-016", "DN-021"} and f.severity == "ok" for f in findings):
        set_card("Health definible", "OK L&S")
    elif any(f.id in {"WF-006", "SRC-016"} and f.severity in {"medium", "info"} for f in findings):
        set_card("Health definible", "Ajuste menor")

    if any(f.id in {"NET-001", "SRC-013", "WP-004", "DN-011", "NG-007"} for f in findings):
        set_card("Sin dependencia localhost/host", "Ajuste menor")
    else:
        set_card("Sin dependencia localhost/host", "OK L&S" if findings else "Sin datos")

    if any(f.id in {"SRC-010", "SRC-023", "WP-010", "DN-012"} and f.severity in {"high", "medium"} for f in findings):
        set_card("Estado en disco acotado y mapeable", "Ajuste menor")

    source_scanned = any(
        f.id in {"SRC-000", "WP-000", "NG-000", "DN-000"} and f.severity == "ok" for f in findings
    )
    conf_boost = "Alta" if source_scanned else "Media"

    if blockers or any(v == "Bloqueante" for v in report.scorecard.values()):
        report.classification = "Refactor parcial" if any(
            f.id in {"WF-011", "WF-005", "SRC-020", "DN-002", "DN-022", "NG-005", "WP-007"}
            and f.severity in {"blocker", "high"}
            for f in findings
        ) else "Lift + ajustes"
        if any(f.id in {"WF-011", "DN-002"} and f.severity == "blocker" for f in findings):
            report.classification = "Refactor parcial"
        elif any(
            f.id in {"WF-005", "SRC-020", "DN-022", "NG-005", "WP-007"} and f.severity == "high"
            for f in findings
        ):
            report.classification = "Refactor parcial"
        elif blockers:
            report.classification = "Lift + ajustes"
        report.risk = "Alto"
        report.effort_tshirt = "L" if report.classification.startswith("Refactor") else "M"
        report.confidence = conf_boost
    elif len(highs) >= 2 or len(mediums) >= 3 or score >= 8:
        report.classification = "Lift + ajustes"
        report.risk = "Medio"
        report.effort_tshirt = "M"
        report.confidence = conf_boost
    elif findings:
        report.classification = "Lift puro"
        report.risk = "Bajo" if not mediums else "Medio"
        report.effort_tshirt = "S" if not mediums else "M"
        report.confidence = conf_boost
    else:
        report.classification = "Sin datos suficientes"
        report.risk = "?"
        report.effort_tshirt = "?"
        report.confidence = "Baja"

    report.manual_checklist = [
        "Confirmar sticky sessions / replicación de sesión WildFly en llamada",
        "Validar EJB timers / singletons detectados (SRC-020) con el equipo funcional",
        "Confirmar quién ejecuta migraciones de BD",
        "Validar política de imágenes base / registry interno",
        "Revisar paths de uploads de negocio no estándar no capturados por heurística",
        "Confirmar graceful shutdown y timeouts del LB",
        "PHP/WP: confirmar SAPI real (mod_php vs PHP-FPM) y vhost/nginx",
        "WordPress: inventario de plugins incompatibles con contenedor / object cache",
        "Angular: confirmar SPA estática vs SSR y estrategia de config por ambiente",
        ".NET 5: plan de upgrade a 8 LTS; validar System.Drawing / librerías nativas",
        "Acordar UID/GID de volúmenes compartidos con el equipo de ops",
        "Si hubo --source: validar falsos positivos de secretos/localhost en tests",
    ]


def report_to_dict(report: Report) -> dict[str, Any]:
    return {
        "app_name": report.app_name,
        "generated_at": report.generated_at,
        "tool_version": report.tool_version,
        "host": report.host,
        "classification": report.classification,
        "confidence": report.confidence,
        "effort_tshirt": report.effort_tshirt,
        "risk": report.risk,
        "scorecard": report.scorecard,
        "inventory": report.inventory,
        "findings": [asdict(f) for f in report.findings],
        "manual_checklist": report.manual_checklist,
    }


def to_markdown(report: Report) -> str:
    lines = [
        f"# Evaluación contenerización — {report.app_name}",
        "",
        f"- Generado: `{report.generated_at}`",
        f"- Host: `{report.host}`",
        f"- Tool: `assess_containerization.py v{report.tool_version}`",
        f"- **Clasificación sugerida:** {report.classification}",
        f"- Confianza: {report.confidence}",
        f"- Esfuerzo: {report.effort_tshirt} | Riesgo: {report.risk}",
        "",
        "## Scorecard (ficha 11)",
        "",
        "| Criterio | Resultado |",
        "|----------|-----------|",
    ]
    for k, v in report.scorecard.items():
        lines.append(f"| {k} | {v} |")

    lines += ["", "## Hallazgos", ""]
    order = {"blocker": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "ok": 5}
    for f in sorted(report.findings, key=lambda x: (order.get(x.severity, 9), x.id)):
        lines.append(f"### [{f.severity.upper()}] {f.id} — {f.title}")
        lines.append("")
        lines.append(f"- Área: `{f.area}`")
        if f.ficha_field:
            lines.append(f"- Ficha: `{f.ficha_field}`")
        lines.append(f"- Detalle: {f.detail}")
        if f.evidence:
            lines.append(f"- Evidencia: `{f.evidence}`")
        lines.append("")

    lines += ["## Checklist manual (entrevista)", ""]
    for item in report.manual_checklist:
        lines.append(f"- [ ] {item}")

    lines += ["", "## Inventario (extracto)", "", "```json"]
    lines.append(json.dumps(report.inventory, indent=2, ensure_ascii=False)[:4000])
    lines += ["```", ""]
    lines.append(
        "> Este reporte no reemplaza la ficha técnica; alimenta las hojas "
        "02/03/04/05/06/08/09/11 con evidencia automatizable."
    )
    return "\n".join(lines)


def to_csv_matrix_row(report: Report) -> str:
    """Una línea CSV compatible con 99_Matriz_MultiApp."""
    sc = report.scorecard
    def yn(key: str) -> str:
        v = sc.get(key, "")
        if v == "OK L&S":
            return "Sí"
        if v == "Sin datos":
            return "N/A"
        if v == "Bloqueante":
            return "No"
        return "Parcial"

    blockers = sum(1 for f in report.findings if f.severity == "blocker")
    cols = [
        report.app_name,
        str(report.inventory.get("java_version") or report.inventory.get("php_version_raw") or ""),
        report.classification,
        report.effort_tshirt,
        report.risk,
        yn("Config externalizable"),
        yn("Estado en disco acotado y mapeable"),
        "No" if sc.get("Sin domain mode / cluster complejo") == "OK L&S" else "Sí",
        "Sí" if sc.get("Health definible") == "OK L&S" else "No",
        str(blockers),
        "",
        "Completar ficha + revisar hallazgos high/blocker",
    ]
    def q(s: str) -> str:
        s = s.replace('"', '""')
        return f'"{s}"'
    return ",".join(q(c) for c in cols)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Evalúa readiness de contenerización Lift-and-Shift "
            "(WildFly/Java/PHP/WordPress/Angular/.NET)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--app", required=True, help="Nombre de la aplicación")
    p.add_argument("--war", type=Path, help="Ruta a WAR/EAR/JAR")
    p.add_argument("--standalone", type=Path, help="Ruta a standalone.xml")
    p.add_argument("--jboss-home", type=Path, help="JBOSS_HOME / WildFly home")
    p.add_argument("--php-root", type=Path, help="Raíz del proyecto PHP")
    p.add_argument("--document-root", type=Path, help="DocumentRoot PHP")
    p.add_argument("--wordpress-root", type=Path, help="Raíz de instalación WordPress")
    p.add_argument("--angular-root", type=Path, help="Raíz del proyecto Angular (angular.json)")
    p.add_argument("--dotnet-root", type=Path, help="Raíz del proyecto .NET (.csproj)")
    p.add_argument(
        "--source",
        type=Path,
        help="Raíz del código fuente para análisis estático (+ auto-detect WP/Angular/.NET)",
    )
    p.add_argument(
        "--include-vendor",
        action="store_true",
        help="Incluir vendor/ (Composer) en el escaneo de fuente",
    )
    p.add_argument(
        "--max-files",
        type=int,
        default=4000,
        help="Máximo de archivos fuente a escanear (default: 4000)",
    )
    p.add_argument(
        "--max-file-bytes",
        type=int,
        default=750000,
        help="Ignorar archivos mayores a N bytes (default: 750000)",
    )
    p.add_argument(
        "--ports",
        default="8080,8443,9990,80,443,9000",
        help="Puertos a probar en localhost (csv)",
    )
    p.add_argument("--json-out", type=Path, help="Salida JSON")
    p.add_argument("--md-out", type=Path, help="Salida Markdown")
    p.add_argument("--csv-out", type=Path, help="Append/escribe fila matriz CSV")
    p.add_argument(
        "--fail-on",
        choices=["never", "blocker", "high"],
        default="never",
        help="Exit code !=0 si hay hallazgos de ese nivel o peor",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = Report(
        app_name=args.app,
        generated_at=datetime.now(timezone.utc).isoformat(),
        tool_version=VERSION,
        host=socket.gethostname(),
    )

    check_host_runtime(report)

    # Java/WildFly path (solo si el escaneo es relevante)
    if args.war or args.standalone or args.jboss_home:
        check_java(report)
    elif args.source and shutil.which("java"):
        # Fuente genérica: informar runtime Java del host si existe
        check_java(report)

    if args.war:
        check_war_ear(report, args.war)
    if args.standalone:
        check_standalone_xml(report, args.standalone)
    if args.jboss_home:
        check_jboss_home(report, args.jboss_home)
        auto_standalone = args.jboss_home / "standalone/configuration/standalone.xml"
        if not args.standalone and auto_standalone.exists():
            check_standalone_xml(report, auto_standalone)

    if args.php_root or args.document_root or shutil.which("php"):
        if args.php_root or args.document_root:
            check_php(report, args.php_root, args.document_root)
        elif not (args.war or args.standalone or args.jboss_home or args.source):
            check_php(report, None, None)

    if args.source:
        check_source_tree(
            report,
            args.source,
            include_vendor=args.include_vendor,
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
        )

    # Stacks explícitos + auto-detect (una sola pasada por stack)
    checked_wp: set[str] = set()
    checked_ng: set[str] = set()
    checked_dn: set[str] = set()

    def _run_wp(path: Path) -> None:
        key = str(path.resolve())
        if key in checked_wp:
            return
        checked_wp.add(key)
        check_wordpress(report, path)

    def _run_ng(path: Path) -> None:
        key = str(path.resolve())
        if key in checked_ng:
            return
        checked_ng.add(key)
        check_angular(report, path)

    def _run_dn(path: Path) -> None:
        key = str(path.resolve())
        if key in checked_dn:
            return
        checked_dn.add(key)
        check_dotnet(report, path)

    if args.wordpress_root:
        _run_wp(args.wordpress_root)
    if args.angular_root:
        _run_ng(args.angular_root)
    if args.dotnet_root:
        _run_dn(args.dotnet_root)

    for candidate in (args.source, args.php_root, args.document_root):
        if not candidate or not candidate.exists():
            continue
        if _looks_like_wordpress(candidate):
            _run_wp(candidate)
        if _looks_like_angular(candidate):
            _run_ng(candidate)
        if _looks_like_dotnet(candidate):
            _run_dn(candidate)

    ports = []
    for part in args.ports.split(","):
        part = part.strip()
        if part.isdigit():
            ports.append(int(part))
    if ports:
        check_ports(report, ports)

    roots = [
        p
        for p in [
            args.php_root,
            args.document_root,
            args.jboss_home,
            args.source,
            args.wordpress_root,
            args.angular_root,
            args.dotnet_root,
            Path.cwd(),
        ]
        if p
    ]
    if args.war:
        roots.append(args.war.parent)
    check_docker_presence(report, roots)

    classify(report)

    # stdout summary
    print(f"App: {report.app_name}")
    print(f"Clasificación: {report.classification} (confianza {report.confidence})")
    print(f"Esfuerzo: {report.effort_tshirt} | Riesgo: {report.risk}")
    print("Scorecard:")
    for k, v in report.scorecard.items():
        print(f"  - {k}: {v}")
    print("Hallazgos:")
    order = {"blocker": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "ok": 5}
    for f in sorted(report.findings, key=lambda x: (order.get(x.severity, 9), x.id)):
        print(f"  [{f.severity}] {f.id} {f.title}")

    data = report_to_dict(report)
    if args.json_out:
        args.json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON: {args.json_out}")
    if args.md_out:
        args.md_out.write_text(to_markdown(report), encoding="utf-8")
        print(f"Markdown: {args.md_out}")
    if args.csv_out:
        header = (
            "App,Stack,Clasificación,Esfuerzo,Riesgo,Config externalizable,"
            "Estado en disco,Cluster/HA complejo,Health existente,Bloqueantes (#),"
            "Dueño técnico,Próximo paso\n"
        )
        row = to_csv_matrix_row(report) + "\n"
        if not args.csv_out.exists():
            args.csv_out.write_text(header + row, encoding="utf-8")
        else:
            with args.csv_out.open("a", encoding="utf-8") as fh:
                fh.write(row)
        print(f"CSV matriz: {args.csv_out}")

    if args.fail_on == "blocker" and any(f.severity == "blocker" for f in report.findings):
        return 2
    if args.fail_on == "high" and any(f.severity in {"blocker", "high"} for f in report.findings):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
