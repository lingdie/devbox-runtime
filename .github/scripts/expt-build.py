#!/usr/bin/env python3

import argparse
import json
import os
import re
import sys
from pathlib import Path


ROOT = Path.cwd()
EXPERIMENTAL_ROOT = ROOT / "experimental"
INTERNAL_FROM_RE = re.compile(r"^FROM \$\{REGISTRY\}/\$\{REPO\}/([^:\s]+):")


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def normalize_bool(value: object) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    fail(f"unsupported boolean value '{value}'")


def relative_posix(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def write_outputs(values: dict[str, str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    lines = [f"{key}={value}" for key, value in values.items()]
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
            handle.write("\n")
        return
    print("\n".join(lines))


def append_summary(text: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(text)
            if not text.endswith("\n"):
                handle.write("\n")
        return
    print(text)


def find_dockerfiles(root: Path) -> list[str]:
    return sorted(relative_posix(path) for path in root.rglob("Dockerfile"))


def select_dockerfiles(build_root: str, kind: str, name: str) -> list[str]:
    target_root = EXPERIMENTAL_ROOT / build_root / kind
    if name:
        target_root = target_root / name
    if not target_root.exists():
        fail(f"target path '{relative_posix(target_root)}' does not exist")
    return find_dockerfiles(target_root)


def dockerfile_to_image_name(dockerfile: str) -> str:
    dockerfile_path = Path(dockerfile)
    return f"{dockerfile_path.parent.parent.name}-{dockerfile_path.parent.name}"


def build_image_map() -> dict[str, str]:
    image_map: dict[str, str] = {}
    for dockerfile in find_dockerfiles(EXPERIMENTAL_ROOT / "images"):
        image_map[dockerfile_to_image_name(dockerfile)] = dockerfile
    return image_map


def list_internal_dependencies(dockerfile: str) -> list[str]:
    dependencies: list[str] = []
    with open(ROOT / dockerfile, "r", encoding="utf-8") as handle:
        for line in handle:
            match = INTERNAL_FROM_RE.match(line.strip())
            if match:
                dependencies.append(match.group(1))
    return dependencies


def finalize_stage_name(stage_names: set[str], fallback_name: str) -> str:
    if len(stage_names) == 1:
        return next(iter(stage_names))
    if fallback_name:
        return fallback_name
    return ""


def handle_define_matrix(args: argparse.Namespace) -> int:
    tag = args.tag or args.github_sha[:7]
    tools_version = args.tools_version or tag
    os_version = args.os_version or tag
    framework_image_version = args.framework_image_version or tag

    l10n_map = {
        "en_US": [{"display": "en_US", "normalized": "en-us"}],
        "zh_CN": [{"display": "zh_CN", "normalized": "zh-cn"}],
        "both": [
            {"display": "en_US", "normalized": "en-us"},
            {"display": "zh_CN", "normalized": "zh-cn"},
        ],
    }
    if args.l10n not in l10n_map:
        fail(f"unknown l10n option '{args.l10n}'")

    arch_map = {
        "amd64": (["amd64"], "linux/amd64", "true"),
        "arm64": (["arm64"], "linux/arm64", "false"),
        "both": (["amd64", "arm64"], "linux/amd64,linux/arm64", "true"),
    }
    if args.arch not in arch_map:
        fail(f"unknown arch option '{args.arch}'")

    arch_values, platforms, platforms_include_amd64 = arch_map[args.arch]
    packages = select_dockerfiles(args.build_type, args.kind, args.name)
    if args.name and not packages:
        fail(f"No Dockerfile found for package '{args.name}' in kind '{args.kind}'")

    print(f"Resolved tag: {tag}")
    print(f"Found {len(packages)} packages to build")

    write_outputs(
        {
            "tag": tag,
            "framework_image_version": framework_image_version,
            "tools_version": tools_version,
            "os_version": os_version,
            "l10n_matrix": json.dumps(l10n_map[args.l10n], separators=(",", ":")),
            "arch_matrix": json.dumps(arch_values, separators=(",", ":")),
            "platforms": platforms,
            "platforms_include_amd64": platforms_include_amd64,
            "aliyun_enabled": "true" if normalize_bool(args.aliyun_enabled) else "false",
            "packages": json.dumps(packages, separators=(",", ":")),
        }
    )
    return 0


def handle_resolve_plan(args: argparse.Namespace) -> int:
    target_kind = args.target_kind
    target_name = args.target_name
    target_build_type = args.target_build_type
    include_prerequisites = normalize_bool(args.include_prerequisites)

    flags = {
        "build_tools": False,
        "build_os_base": False,
        "build_language_base": False,
        "build_framework_base": False,
        "build_os_runtime": False,
        "build_language_runtime": False,
        "build_framework_runtime": False,
    }
    fallback_names = {
        "os_base": "",
        "language_base": "",
        "framework_base": "",
        "os_runtime": "",
        "language_runtime": "",
        "framework_runtime": "",
    }
    stage_names = {
        "os_base": set(),
        "language_base": set(),
        "framework_base": set(),
    }
    image_map = build_image_map()
    seen_dockerfiles: set[str] = set()

    def mark_selected_image_stage() -> None:
        if target_kind == "operating-systems":
            flags["build_os_base"] = True
            fallback_names["os_base"] = target_name
        elif target_kind == "languages":
            flags["build_language_base"] = True
            fallback_names["language_base"] = target_name
        elif target_kind == "frameworks":
            flags["build_framework_base"] = True
            fallback_names["framework_base"] = target_name
        else:
            fail(f"unsupported target kind '{target_kind}'")

    def mark_selected_runtime_stage() -> None:
        if target_kind == "operating-systems":
            flags["build_os_runtime"] = True
            fallback_names["os_runtime"] = target_name
        elif target_kind == "languages":
            flags["build_language_runtime"] = True
            fallback_names["language_runtime"] = target_name
        elif target_kind == "frameworks":
            flags["build_framework_runtime"] = True
            fallback_names["framework_runtime"] = target_name
        else:
            fail(f"unsupported target kind '{target_kind}'")

    def mark_base_stage_for_image(dockerfile: str) -> None:
        relative = dockerfile.removeprefix("experimental/images/")
        kind, package_path = relative.split("/", 1)
        package_path = package_path.removesuffix("/Dockerfile")
        if kind == "operating-systems":
            flags["build_os_base"] = True
            stage_names["os_base"].add(package_path)
        elif kind == "languages":
            flags["build_language_base"] = True
            stage_names["language_base"].add(package_path)
        elif kind == "frameworks":
            flags["build_framework_base"] = True
            stage_names["framework_base"].add(package_path)
        else:
            fail(f"unsupported image kind '{kind}' while resolving {dockerfile}")

    def resolve_image_dependencies(dockerfile: str) -> None:
        if dockerfile in seen_dockerfiles:
            return
        seen_dockerfiles.add(dockerfile)
        mark_base_stage_for_image(dockerfile)
        for dependency in list_internal_dependencies(dockerfile):
            if dependency == "base-tools":
                flags["build_tools"] = True
                continue
            dependency_dockerfile = image_map.get(dependency)
            if not dependency_dockerfile:
                fail(f"could not resolve internal dependency '{dependency}' referenced by {dockerfile}")
            resolve_image_dependencies(dependency_dockerfile)

    if target_name and target_kind == "all":
        fail("target_name can only be used when target_kind is operating-systems, languages, or frameworks.")

    if target_name:
        selected_images: list[str] = []
        selected_runtime_base_images: list[str] = []

        if target_build_type in {"images", "all"}:
            selected_images = select_dockerfiles("images", target_kind, target_name)

        if target_build_type in {"runtimes", "all"}:
            select_dockerfiles("runtimes", target_kind, target_name)
            selected_runtime_base_images = select_dockerfiles("images", target_kind, target_name)

        if include_prerequisites:
            for dockerfile in selected_images:
                resolve_image_dependencies(dockerfile)
            for dockerfile in selected_runtime_base_images:
                resolve_image_dependencies(dockerfile)
        elif target_build_type in {"images", "all"}:
            mark_selected_image_stage()

        if target_build_type in {"all", "runtimes"}:
            mark_selected_runtime_stage()

        if target_build_type != "runtimes" or include_prerequisites:
            if target_kind == "operating-systems":
                fallback_names["os_base"] = target_name
            elif target_kind == "languages":
                fallback_names["language_base"] = target_name
            elif target_kind == "frameworks":
                fallback_names["framework_base"] = target_name
    elif target_kind == "all":
        if target_build_type == "all":
            for key in flags:
                flags[key] = True
        elif target_build_type == "images":
            flags["build_tools"] = True
            flags["build_os_base"] = True
            flags["build_language_base"] = True
            flags["build_framework_base"] = True
        elif target_build_type == "runtimes":
            if include_prerequisites:
                flags["build_tools"] = True
                flags["build_os_base"] = True
                flags["build_language_base"] = True
                flags["build_framework_base"] = True
            flags["build_os_runtime"] = True
            flags["build_language_runtime"] = True
            flags["build_framework_runtime"] = True
        else:
            fail(f"unsupported target_build_type '{target_build_type}'")
    else:
        if target_kind == "operating-systems":
            if target_build_type in {"all", "images"}:
                if include_prerequisites:
                    flags["build_tools"] = True
                flags["build_os_base"] = True
            if target_build_type in {"all", "runtimes"}:
                if include_prerequisites:
                    flags["build_tools"] = True
                    flags["build_os_base"] = True
                flags["build_os_runtime"] = True
        elif target_kind == "languages":
            if include_prerequisites:
                flags["build_tools"] = True
                flags["build_os_base"] = True
            if target_build_type in {"all", "images"}:
                flags["build_language_base"] = True
            if target_build_type in {"all", "runtimes"}:
                if include_prerequisites:
                    flags["build_language_base"] = True
                flags["build_language_runtime"] = True
        elif target_kind == "frameworks":
            if include_prerequisites:
                flags["build_tools"] = True
                flags["build_os_base"] = True
                flags["build_language_base"] = True
            if target_build_type in {"all", "images"}:
                flags["build_framework_base"] = True
            if target_build_type in {"all", "runtimes"}:
                if include_prerequisites:
                    flags["build_framework_base"] = True
                flags["build_framework_runtime"] = True
        else:
            fail(f"unsupported target kind '{target_kind}'")

    os_base_name = finalize_stage_name(stage_names["os_base"], fallback_names["os_base"])
    language_base_name = finalize_stage_name(stage_names["language_base"], fallback_names["language_base"])
    framework_base_name = finalize_stage_name(stage_names["framework_base"], fallback_names["framework_base"])

    write_outputs(
        {
            "build_tools": "true" if flags["build_tools"] else "false",
            "effective_tools_version": args.effective_tools_version,
            "build_os_base": "true" if flags["build_os_base"] else "false",
            "os_base_name": os_base_name,
            "build_language_base": "true" if flags["build_language_base"] else "false",
            "language_base_name": language_base_name,
            "build_framework_base": "true" if flags["build_framework_base"] else "false",
            "framework_base_name": framework_base_name,
            "build_os_runtime": "true" if flags["build_os_runtime"] else "false",
            "os_runtime_name": fallback_names["os_runtime"],
            "build_language_runtime": "true" if flags["build_language_runtime"] else "false",
            "language_runtime_name": fallback_names["language_runtime"],
            "build_framework_runtime": "true" if flags["build_framework_runtime"] else "false",
            "framework_runtime_name": fallback_names["framework_runtime"],
        }
    )

    def stage_line(label: str, enabled: bool, scope: str) -> str:
        if enabled:
            if scope:
                return f"- {label}: `{scope}`"
            return f"- {label}: all"
        return f"- {label}: skipped"

    summary_lines = [
        "## Requested Build Plan",
        f"- Target kind: `{target_kind}`",
        f"- Target name: `{target_name}`" if target_name else "- Target name: all",
        f"- Target build type: `{target_build_type}`",
        f"- Include prerequisites: `{'true' if include_prerequisites else 'false'}`",
        f"- Effective tools version when reused: `{args.effective_tools_version}`",
    ]
    if target_name and target_build_type == "runtimes" and not include_prerequisites:
        summary_lines.append("- Note: prerequisites are disabled, so the required base images must already exist in the registry.")
    summary_lines.extend(
        [
            "",
            stage_line("Tools Image", flags["build_tools"], ""),
            stage_line("Base Images (OS)", flags["build_os_base"], os_base_name),
            stage_line("Base Images (Languages)", flags["build_language_base"], language_base_name),
            stage_line("Base Images (Frameworks)", flags["build_framework_base"], framework_base_name),
            stage_line("Runtime Images (OS)", flags["build_os_runtime"], fallback_names["os_runtime"]),
            stage_line("Runtime Images (Languages)", flags["build_language_runtime"], fallback_names["language_runtime"]),
            stage_line("Runtime Images (Frameworks)", flags["build_framework_runtime"], fallback_names["framework_runtime"]),
        ]
    )
    append_summary("\n".join(summary_lines) + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Helpers for experimental image/runtime GitHub Actions workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    define_matrix = subparsers.add_parser("define-matrix", help="Resolve build versions, matrices, and package list.")
    define_matrix.add_argument("--tag", default="")
    define_matrix.add_argument("--tools-version", default="")
    define_matrix.add_argument("--os-version", default="")
    define_matrix.add_argument("--framework-image-version", default="")
    define_matrix.add_argument("--l10n", required=True)
    define_matrix.add_argument("--arch", required=True)
    define_matrix.add_argument("--kind", required=True)
    define_matrix.add_argument("--name", default="")
    define_matrix.add_argument("--build-type", required=True)
    define_matrix.add_argument("--aliyun-enabled", default="false")
    define_matrix.add_argument("--github-sha", default=os.environ.get("GITHUB_SHA", ""))
    define_matrix.set_defaults(handler=handle_define_matrix)

    resolve_plan = subparsers.add_parser("resolve-plan", help="Plan which experimental stages need to run.")
    resolve_plan.add_argument("--target-kind", required=True)
    resolve_plan.add_argument("--target-name", default="")
    resolve_plan.add_argument("--target-build-type", required=True)
    resolve_plan.add_argument("--include-prerequisites", default="true")
    resolve_plan.add_argument("--effective-tools-version", required=True)
    resolve_plan.set_defaults(handler=handle_resolve_plan)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
