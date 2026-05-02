#!/usr/bin/env python3
"""
Migration : déplacer les fichiers chatbot du core Frappe vers l'app custom_dashboard.

Source (à nettoyer) :
    apps/frappe/frappe/
        chatbot_api.py, chatbot_logger.py, intent_classifier.py,
        accounting_api.py, vente_api.py, purchase_api.py,
        stock_api.py, hr_api.py, project_api.py
        public/js/chatbot.js
        public/css/chatbot.css

Destination :
    apps/custom_dashboard/custom_dashboard/
        chatbot/<modules>.py
        public/js/chatbot.js
        public/css/chatbot.css

Le script :
  - Détecte automatiquement la racine du bench
  - Sauvegarde tous les fichiers concernés avant toute modification
  - Réécrit les imports Python (from frappe.X → from custom_dashboard.chatbot.X)
  - Réécrit les chemins JS (frappe.X.method → custom_dashboard.chatbot.X.method)
  - Met à jour custom_dashboard/hooks.py pour inclure JS/CSS
  - Signale (sans modifier) les pollutions dans apps/frappe/frappe/hooks.py
  - Idempotent : peut être relancé sans casser l'état

Usage :
    python migrate_chatbot_to_app.py              # dry-run (par défaut)
    python migrate_chatbot_to_app.py --apply      # exécution réelle
    python migrate_chatbot_to_app.py --apply --yes
    python migrate_chatbot_to_app.py --rollback   # restaure depuis le dernier backup
    python migrate_chatbot_to_app.py --bench-root /chemin/vers/my-bench
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Force UTF-8 sur la console Windows (cp1252 par défaut casse les emojis)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# ────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────────────────────────────────

PYTHON_MODULES = [
    "chatbot_api.py",
    "chatbot_logger.py",
    "intent_classifier.py",
    "accounting_api.py",
    "vente_api.py",
    "purchase_api.py",
    "stock_api.py",
    "hr_api.py",
    "project_api.py",
]

JS_FILES = ["chatbot.js", "lottie.min.js", "ai-animation-flow-1.json"]
CSS_FILES = ["chatbot.css"]

# URLs d'assets à réécrire dans chatbot.js (et autres JS) :
#   /assets/frappe/js/<fichier_migré>  →  /assets/custom_dashboard/js/<fichier_migré>
ASSET_URL_FILES = JS_FILES  # tous les fichiers JS référencés via /assets/frappe/js/...

# DocTypes à déplacer depuis apps/frappe/frappe/core/doctype/
DOCTYPES = ["chatbot_conversation", "chatbot_message", "chatbot_trace"]
FRAPPE_DOCTYPE_PARENT_REL = Path("apps/frappe/frappe/core/doctype")

FRAPPE_REL = Path("apps/frappe/frappe")
DEST_REL = Path("apps/custom_dashboard/custom_dashboard")
TARGET_SUBPACKAGE = "chatbot"
# Sous-dossier module Frappe dans l'app destination (lu depuis modules.txt)
DEST_MODULE_DIR = "custom_dashboard"  # dossier physique
DEST_MODULE_NAME = "Custom Dashboard"  # nom logique (champ "module" dans le JSON)

MIGRATED_MODULE_NAMES = [Path(m).stem for m in PYTHON_MODULES]

# ────────────────────────────────────────────────────────────────────────────
# UTILITAIRES
# ────────────────────────────────────────────────────────────────────────────


def die(msg: str) -> None:
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg: str) -> None:
    print(f"   {msg}")


def section(title: str) -> None:
    print(f"\n━━━ {title} ━━━")


def read_dest_module_name(dest: Path) -> str:
    """Lit le premier module déclaré dans modules.txt — autoritatif."""
    modules_txt = dest / "modules.txt"
    if not modules_txt.exists():
        return DEST_MODULE_NAME
    for line in modules_txt.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            return line
    return DEST_MODULE_NAME


def detect_bench_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).resolve()
        if not (root / "apps").is_dir() or not (root / "sites").is_dir():
            die(f"Le chemin {root} ne ressemble pas à un bench (pas de apps/ + sites/)")
        return root

    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "apps").is_dir() and (parent / "sites").is_dir():
            return parent
    die("Bench introuvable. Utilise --bench-root /chemin/vers/my-bench")


# ────────────────────────────────────────────────────────────────────────────
# RÉÉCRITURE DES IMPORTS / CHEMINS
# ────────────────────────────────────────────────────────────────────────────


def rewrite_python_imports(content: str) -> tuple[str, int]:
    """
    Réécrit uniquement les imports vers les modules migrés.
    NE TOUCHE PAS aux imports légitimes du framework (frappe.utils, frappe.db, etc.).
    """
    count = 0
    new_content = content

    for module in MIGRATED_MODULE_NAMES:
        # from frappe.MODULE import X
        pattern = rf"\bfrom\s+frappe\.{re.escape(module)}\s+import\b"
        replacement = f"from custom_dashboard.{TARGET_SUBPACKAGE}.{module} import"
        new_content, n = re.subn(pattern, replacement, new_content)
        count += n

        # import frappe.MODULE [as alias]
        pattern = rf"\bimport\s+frappe\.{re.escape(module)}\b"
        replacement = f"import custom_dashboard.{TARGET_SUBPACKAGE}.{module}"
        new_content, n = re.subn(pattern, replacement, new_content)
        count += n

    return new_content, count


def rewrite_js_method_paths(content: str) -> tuple[str, int]:
    """
    Réécrit dans le JS :
      "frappe.chatbot_api.send_message"        →  "custom_dashboard.chatbot.chatbot_api.send_message"
      "/api/method/frappe.chatbot_api.X"       →  "/api/method/custom_dashboard.chatbot.chatbot_api.X"
      "/assets/frappe/js/lottie.min.js"        →  "/assets/custom_dashboard/js/lottie.min.js"
      "/assets/frappe/js/ai-animation-...json" →  "/assets/custom_dashboard/js/ai-animation-...json"
    """
    count = 0
    new_content = content

    # 1) Méthodes whitelistées : "frappe.MODULE."
    for module in MIGRATED_MODULE_NAMES:
        pattern = rf"""(["'`])frappe\.{re.escape(module)}(\.)"""
        replacement = rf"\1custom_dashboard.{TARGET_SUBPACKAGE}.{module}\2"
        new_content, n = re.subn(pattern, replacement, new_content)
        count += n

    # 2) URLs d'assets : "/assets/frappe/js/<fichier_migré>"
    for asset in ASSET_URL_FILES:
        pattern = rf"/assets/frappe/js/{re.escape(asset)}\b"
        replacement = f"/assets/custom_dashboard/js/{asset}"
        new_content, n = re.subn(pattern, replacement, new_content)
        count += n

    return new_content, count


# ────────────────────────────────────────────────────────────────────────────
# MISE A JOUR HOOKS.PY DE CUSTOM_DASHBOARD
# ────────────────────────────────────────────────────────────────────────────


def update_custom_dashboard_hooks(dest: Path) -> None:
    """
    Ajoute (sans dupliquer) les includes JS/CSS dans custom_dashboard/hooks.py.
    """
    hooks = dest / "hooks.py"
    if not hooks.exists():
        info(f"⚠️  hooks.py introuvable : {hooks}")
        return

    content = hooks.read_text(encoding="utf-8")
    js_path = "/assets/custom_dashboard/js/chatbot.js"
    css_path = "/assets/custom_dashboard/css/chatbot.css"

    changed = False

    # app_include_js : déjà présent sous forme de liste -> on ajoute si absent
    if js_path in content:
        info("hooks.py : app_include_js déjà à jour")
    else:
        m = re.search(r"app_include_js\s*=\s*\[([^\]]*)\]", content, re.DOTALL)
        if m:
            inside = m.group(1).rstrip()
            sep = ", " if inside.strip() else ""
            new_block = f"app_include_js = [{inside}{sep}\"{js_path}\"]"
            content = content[: m.start()] + new_block + content[m.end():]
            changed = True
            info("hooks.py : ajout dans app_include_js")
        else:
            content += f"\n\napp_include_js = [\"{js_path}\"]\n"
            changed = True
            info("hooks.py : déclaration app_include_js")

    # app_include_css
    if css_path in content:
        info("hooks.py : app_include_css déjà à jour")
    else:
        m = re.search(r"app_include_css\s*=\s*\[([^\]]*)\]", content, re.DOTALL)
        if m:
            inside = m.group(1).rstrip()
            sep = ", " if inside.strip() else ""
            new_block = f"app_include_css = [{inside}{sep}\"{css_path}\"]"
            content = content[: m.start()] + new_block + content[m.end():]
            changed = True
            info("hooks.py : ajout dans app_include_css")
        else:
            content += f"\napp_include_css = [\"{css_path}\"]\n"
            changed = True
            info("hooks.py : déclaration app_include_css")

    if changed:
        hooks.write_text(content, encoding="utf-8")


# ────────────────────────────────────────────────────────────────────────────
# DÉTECTION POLLUTION FRAPPE CORE
# ────────────────────────────────────────────────────────────────────────────


def detect_frappe_core_pollution(bench_root: Path) -> list[tuple[int, str]]:
    """
    Repère les lignes ajoutées par l'utilisateur dans apps/frappe/frappe/hooks.py.
    Ne modifie rien — laisse l'utilisateur nettoyer manuellement.
    """
    hooks = bench_root / FRAPPE_REL / "hooks.py"
    if not hooks.exists():
        return []

    pollutants = [
        "chatbot.js", "chatbot.css", "chatbot_api", "chatbot_logger",
        "lottie", "ai-animation",
    ]
    found = []
    for i, line in enumerate(hooks.read_text(encoding="utf-8").splitlines(), 1):
        if any(p in line for p in pollutants):
            found.append((i, line.rstrip()))
    return found


# ────────────────────────────────────────────────────────────────────────────
# MIGRATION
# ────────────────────────────────────────────────────────────────────────────


def collect_files(src: Path) -> tuple[list[Path], list[Path], list[Path]]:
    py_files = [src / m for m in PYTHON_MODULES if (src / m).is_file()]
    js_files = [src / "public/js" / m for m in JS_FILES if (src / "public/js" / m).is_file()]
    css_files = [src / "public/css" / m for m in CSS_FILES if (src / "public/css" / m).is_file()]
    return py_files, js_files, css_files


def make_backup(files: list[Path], src: Path, backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        rel = f.relative_to(src)
        target = backup_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)


def migrate_python(py_files: list[Path], target_pkg: Path, dry_run: bool) -> None:
    if not py_files:
        info("aucun module Python à migrer")
        return

    if not dry_run:
        target_pkg.mkdir(parents=True, exist_ok=True)
        init_py = target_pkg / "__init__.py"
        if not init_py.exists():
            init_py.write_text("", encoding="utf-8")

    for f in py_files:
        new_path = target_pkg / f.name
        content = f.read_text(encoding="utf-8")
        new_content, n = rewrite_python_imports(content)

        if dry_run:
            info(f"[DRY] {f.name}  →  {new_path}  ({n} imports à réécrire)")
        else:
            new_path.write_text(new_content, encoding="utf-8")
            f.unlink()
            info(f"✅ {f.name}  →  chatbot/{f.name}  ({n} imports réécrits)")


def migrate_assets(
    asset_files: list[Path], target_dir: Path, kind: str, dry_run: bool
) -> None:
    if not asset_files:
        info(f"aucun fichier {kind} à migrer")
        return

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    for f in asset_files:
        new_path = target_dir / f.name
        content = f.read_text(encoding="utf-8")

        if kind == "js":
            new_content, n = rewrite_js_method_paths(content)
            label = f"{n} chemins réécrits"
        else:
            new_content, n = content, 0
            label = "copie"

        if dry_run:
            info(f"[DRY] {f.name}  →  {new_path}  ({label})")
        else:
            new_path.write_text(new_content, encoding="utf-8")
            f.unlink()
            info(f"✅ {f.name}  →  public/{kind}/{f.name}  ({label})")


def collect_doctype_dirs(bench_root: Path) -> list[Path]:
    src_parent = bench_root / FRAPPE_DOCTYPE_PARENT_REL
    return [src_parent / name for name in DOCTYPES if (src_parent / name).is_dir()]


def _doctype_files(src_dir: Path) -> list[Path]:
    """Tous les fichiers à migrer pour un DocType (skip __pycache__ et :Zone.Identifier)."""
    files = []
    for f in src_dir.iterdir():
        if f.is_dir():
            continue
        if f.name.endswith(":Zone.Identifier"):
            continue
        files.append(f)
    return files


def _patch_doctype_json(content: str, target_module: str) -> tuple[str, int]:
    """Réécrit le champ "module" : "Core" → "<target_module>". Idempotent."""
    pattern = r'("module"\s*:\s*")[^"]+(")'
    new_content, n = re.subn(
        pattern, lambda m: f'{m.group(1)}{target_module}{m.group(2)}', content, count=1
    )
    return new_content, n


def migrate_doctypes(
    src_dirs: list[Path],
    dest_doctype_parent: Path,
    target_module: str,
    dry_run: bool,
) -> None:
    if not src_dirs:
        info("aucun DocType à migrer")
        return

    if not dry_run:
        dest_doctype_parent.mkdir(parents=True, exist_ok=True)
        # __init__.py du dossier doctype/ s'il manque
        init = dest_doctype_parent / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")

    for src_dir in src_dirs:
        dest_dir = dest_doctype_parent / src_dir.name
        files = _doctype_files(src_dir)

        if dry_run:
            info(f"[DRY] {src_dir.name}/  →  {dest_dir}")
            for f in files:
                target_name = f.name
                # Correction du typo Frappe : _init_.py → __init__.py
                if f.name == "_init_.py":
                    target_name = "__init__.py"
                    info(f"   • {f.name}  →  {target_name}  (correction typo)")
                elif f.suffix == ".json":
                    content = f.read_text(encoding="utf-8")
                    _, n = _patch_doctype_json(content, target_module)
                    info(f"   • {f.name}  →  module rewrite ({n} change)")
                else:
                    info(f"   • {f.name}")
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            target_name = "__init__.py" if f.name == "_init_.py" else f.name
            target_path = dest_dir / target_name

            if f.suffix == ".json":
                content = f.read_text(encoding="utf-8")
                new_content, n = _patch_doctype_json(content, target_module)
                target_path.write_text(new_content, encoding="utf-8")
                info(f"✅ {src_dir.name}/{f.name}  →  module: {target_module} ({n} change)")
            else:
                shutil.copy2(f, target_path)
                if target_name != f.name:
                    info(f"✅ {src_dir.name}/{f.name}  →  {target_name} (typo corrigé)")
                else:
                    info(f"✅ {src_dir.name}/{f.name}")
            f.unlink()

        # Supprimer le dossier source (et __pycache__ et Zone.Identifier résiduels)
        for residual in src_dir.iterdir():
            try:
                if residual.is_dir():
                    shutil.rmtree(residual, ignore_errors=True)
                else:
                    residual.unlink()
            except OSError:
                pass
        try:
            src_dir.rmdir()
            info(f"🧹 dossier source supprimé : core/doctype/{src_dir.name}/")
        except OSError as e:
            info(f"⚠️  impossible de supprimer {src_dir} ({e})")


def cleanup_zone_identifier(src: Path, dry_run: bool) -> None:
    candidates = list(src.glob("*.py:Zone.Identifier")) + list(
        src.glob("public/**/*:Zone.Identifier")
    )
    if not candidates:
        return

    for f in candidates:
        if dry_run:
            info(f"[DRY] supprimerait {f.name}")
        else:
            try:
                f.unlink()
                info(f"🧹 supprimé {f.name}")
            except OSError:
                pass


# ────────────────────────────────────────────────────────────────────────────
# ROLLBACK
# ────────────────────────────────────────────────────────────────────────────


def find_latest_backup(bench_root: Path) -> Path | None:
    backups = sorted(bench_root.glob("chatbot_migration_backup_*"))
    return backups[-1] if backups else None


def rollback(bench_root: Path) -> None:
    backup = find_latest_backup(bench_root)
    if not backup:
        die("Aucun backup trouvé.")

    src = bench_root / FRAPPE_REL
    src_doctypes = bench_root / FRAPPE_DOCTYPE_PARENT_REL
    section(f"ROLLBACK depuis {backup.name}")

    # Restaurer fichiers Python/JS/CSS dans frappe/
    for f in backup.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(backup)
        # Les DocTypes sont sous core_doctype/<name>/...
        if rel.parts and rel.parts[0] == "core_doctype":
            sub = Path(*rel.parts[1:])
            target = src_doctypes / sub
        else:
            target = src / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        info(f"↩️  restauré {target.relative_to(bench_root)}")

    # Supprimer ce qui a été créé dans custom_dashboard/chatbot/
    dest_pkg = bench_root / DEST_REL / TARGET_SUBPACKAGE
    if dest_pkg.exists():
        for m in PYTHON_MODULES:
            p = dest_pkg / m
            if p.exists():
                p.unlink()
                info(f"🗑️  supprimé {p.relative_to(bench_root)}")
        init_py = dest_pkg / "__init__.py"
        if init_py.exists() and not any(dest_pkg.iterdir()):
            pass
        elif init_py.exists():
            try:
                init_py.unlink()
            except OSError:
                pass
        try:
            dest_pkg.rmdir()
        except OSError:
            info("ℹ️  custom_dashboard/chatbot/ n'est pas vide — laissé tel quel")

    # Supprimer les DocTypes migrés
    dest_doctype_parent = bench_root / DEST_REL / DEST_MODULE_DIR / "doctype"
    for name in DOCTYPES:
        d = dest_doctype_parent / name
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            info(f"🗑️  supprimé {DEST_MODULE_DIR}/doctype/{name}/")

    for name in JS_FILES:
        p = bench_root / DEST_REL / "public/js" / name
        if p.exists():
            p.unlink()
            info(f"🗑️  supprimé public/js/{name}")
    for name in CSS_FILES:
        p = bench_root / DEST_REL / "public/css" / name
        if p.exists():
            p.unlink()
            info(f"🗑️  supprimé public/css/{name}")

    print("\n✅ Rollback terminé. Vérifie tes fichiers et relance bench build/restart.")


# ────────────────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Migration chatbot : apps/frappe/frappe → apps/custom_dashboard"
    )
    p.add_argument("--bench-root", help="Racine du bench (auto-détectée par défaut)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="Aperçu sans modification (défaut)")
    g.add_argument("--apply", action="store_true", help="Applique réellement la migration")
    g.add_argument("--rollback", action="store_true", help="Restaure depuis le dernier backup")
    p.add_argument("--yes", "-y", action="store_true", help="Pas de confirmation interactive")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    bench_root = detect_bench_root(args.bench_root)
    print(f"🔧 Bench détecté : {bench_root}")

    if args.rollback:
        rollback(bench_root)
        return

    src = bench_root / FRAPPE_REL
    dest = bench_root / DEST_REL

    if not src.is_dir():
        die(f"Source introuvable : {src}")
    if not dest.is_dir():
        die(f"App destination introuvable : {dest}")

    py_files, js_files, css_files = collect_files(src)
    doctype_dirs = collect_doctype_dirs(bench_root)
    target_module = read_dest_module_name(dest)

    section("PLAN")
    info(f"Source      : {src.relative_to(bench_root)}")
    info(f"Destination : {dest.relative_to(bench_root)}/{TARGET_SUBPACKAGE}/")
    info(f"Module cible (DocType) : '{target_module}'")
    info(f"Modules Py  : {len(py_files)} fichier(s)")
    for f in py_files:
        info(f"   • {f.name}")
    info(f"JS          : {len(js_files)} fichier(s)")
    for f in js_files:
        info(f"   • {f.name}")
    info(f"CSS         : {len(css_files)} fichier(s)")
    for f in css_files:
        info(f"   • {f.name}")
    info(f"DocTypes    : {len(doctype_dirs)} dossier(s)")
    for d in doctype_dirs:
        info(f"   • {d.name}/")

    if not py_files and not js_files and not css_files and not doctype_dirs:
        print("\n✅ Rien à migrer — tout semble déjà à jour.")
        return

    dry_run = not args.apply
    if dry_run:
        print("\n⚠️  Mode DRY-RUN (aucune modification). Utilise --apply pour exécuter.")
    else:
        if not args.yes:
            try:
                resp = input("\nContinuer la migration ? [y/N] ").strip().lower()
            except EOFError:
                resp = ""
            if resp not in ("y", "yes", "o", "oui"):
                die("Annulé par l'utilisateur.")

    backup_dir = bench_root / f"chatbot_migration_backup_{datetime.now():%Y%m%d_%H%M%S}"
    if not dry_run:
        section("BACKUP")
        info(f"Destination backup : {backup_dir}")
        make_backup(py_files + js_files + css_files, src, backup_dir)

        # Backup des dossiers DocType (sous une racine "doctype/<name>/")
        if doctype_dirs:
            doctype_backup_root = backup_dir / "core_doctype"
            doctype_backup_root.mkdir(parents=True, exist_ok=True)
            for src_dir in doctype_dirs:
                target = doctype_backup_root / src_dir.name
                shutil.copytree(src_dir, target, dirs_exist_ok=True)
        info("✅ Backup terminé")

    section("MIGRATION PYTHON")
    target_pkg = dest / TARGET_SUBPACKAGE
    migrate_python(py_files, target_pkg, dry_run)

    section("MIGRATION JS")
    migrate_assets(js_files, dest / "public/js", "js", dry_run)

    section("MIGRATION CSS")
    migrate_assets(css_files, dest / "public/css", "css", dry_run)

    section("MIGRATION DOCTYPES")
    dest_doctype_parent = dest / DEST_MODULE_DIR / "doctype"
    migrate_doctypes(doctype_dirs, dest_doctype_parent, target_module, dry_run)

    if not dry_run:
        section("MISE À JOUR custom_dashboard/hooks.py")
        update_custom_dashboard_hooks(dest)

        section("NETTOYAGE Zone.Identifier (Windows)")
        cleanup_zone_identifier(src, dry_run=False)

    section("DÉTECTION POLLUTION FRAPPE CORE")
    pollution = detect_frappe_core_pollution(bench_root)
    if pollution:
        info("⚠️  Lignes suspectes dans apps/frappe/frappe/hooks.py :")
        for ln, line in pollution:
            info(f"   L{ln}: {line}")
        info("⛔ Le script NE TOUCHE PAS au core Frappe — supprime ces lignes à la main.")
    else:
        info("✅ aucune pollution détectée")

    section("ÉTAPES SUIVANTES")
    if dry_run:
        print("   1. Re-lance avec --apply pour exécuter")
        print("   2. Inspecte la sortie ci-dessus avant de valider")
    else:
        print("   1. Nettoie manuellement les lignes signalées dans frappe/hooks.py")
        print("   2. Vérifie que apps/frappe/ est revenu à l'état du upstream :")
        print("        cd apps/frappe && git status   (si .git existe encore)")
        print("   3. Mets à jour les lignes tabDocType en base (le module a changé) :")
        print('        bench --site <ton-site> mariadb -e "UPDATE tabDocType '
              "SET module='" + target_module + "' "
              "WHERE name IN ('Chatbot Conversation','Chatbot Message','Chatbot Trace');\"")
        print("   4. Lance les commandes bench :")
        print("        bench build --app custom_dashboard")
        print("        bench --site <ton-site> migrate")
        print("        bench --site <ton-site> clear-cache")
        print("        bench restart")
        print(f"   5. Backup conservé ici : {backup_dir}")
        print("      (rollback possible avec : python migrate_chatbot_to_app.py --rollback)")


if __name__ == "__main__":
    main()
