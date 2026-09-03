from pathlib import Path

from .prompts import build_prompt

_DESCRIPTIONS = {
    "create": (
        "Use when asked to build, generate, or create the .wiki knowledge base for this "
        "repository from scratch. Runs wiki_cli's create workflow directly in the current "
        "session instead of the headless CLI."
    ),
    "update": (
        "Use when asked to update, refresh, or sync the .wiki knowledge base with recent "
        "code changes. Runs wiki_cli's update workflow directly in the current session "
        "instead of the headless CLI."
    ),
}


def render_skill_md(mode: str) -> str:
    return (
        f"---\nname: wiki-{mode}\ndescription: {_DESCRIPTIONS[mode]}\n---\n\n"
        f"# wiki-{mode}\n\n{build_prompt(mode)}"
    )


def write_skill_files(target_dir: str = ".claude/skills") -> list[Path]:
    root = Path(target_dir)
    written = []
    for mode in ("create", "update"):
        dest = root / f"wiki-{mode}" / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render_skill_md(mode))
        written.append(dest)
    return written
