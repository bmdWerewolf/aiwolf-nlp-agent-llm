"""Run postgame LLM-as-a-judge scoring from built packets."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from time import sleep
from typing import Any

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from evaluate.packet_builder import build_judge_bundle
from evaluate.prompting import render_judge_prompt


def _load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open(encoding="utf-8") as file:
        loaded = yaml.safe_load(file)
    if not isinstance(loaded, dict):
        raise TypeError("Configuration file did not load as a mapping.")
    return loaded


def _create_llm(config: dict[str, Any]) -> Any:
    llm_type = str(config["llm"]["type"])
    if llm_type == "google":
        api_key = os.environ.get("GOOGLE_API_KEY")
        return ChatGoogleGenerativeAI(
            model=str(config["google"]["model"]),
            temperature=float(config["google"]["temperature"]),
            api_key=api_key,
        )
    if llm_type == "openai":
        api_key = os.environ.get("OPENAI_API_KEY") or str(config["openai"].get("api_key", ""))
        kwargs: dict[str, Any] = {
            "model": str(config["openai"]["model"]),
            "temperature": float(config["openai"]["temperature"]),
            "api_key": api_key,
        }
        base_url = str(config["openai"].get("base_url", "")).strip()
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)
    if llm_type == "ollama":
        return ChatOllama(
            model=str(config["ollama"]["model"]),
            temperature=float(config["ollama"]["temperature"]),
            base_url=str(config["ollama"]["base_url"]),
        )
    raise ValueError(f"Unsupported llm.type: {llm_type}")


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_+-]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_json_text(text: str) -> str:
    cleaned = _strip_code_fences(text)
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Judge output does not contain a JSON object.")
    return cleaned[start : end + 1]


def _clamp_score(value: float) -> float:
    return max(0.0, min(5.0, round(value, 1)))


def _normalize_result(result: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    quality = result.setdefault("quality", {})
    validity = result.setdefault("validity", {})
    breakdown = quality.setdefault("teamplay_breakdown", {})

    teamplay_items = [
        float(breakdown.get("alignment_score", 0)),
        float(breakdown.get("coordination_signals_score", 0)),
        float(breakdown.get("vote_formation_score", 0)),
        float(breakdown.get("role_aware_teamplay_score", 0)),
    ]
    quality["teamplay_score"] = _clamp_score(sum(teamplay_items) / len(teamplay_items))

    strategy_quality = float(quality.get("strategy_quality_score", 0))
    role_consistency = float(quality.get("role_consistency_score", 0))
    anti_penalty = float(validity.get("anti_hallucination_penalty", 0))
    rules_penalty = float(validity.get("rules_compliance_penalty", 0))

    base_score = (strategy_quality + role_consistency + float(quality["teamplay_score"])) / 3
    result["final_judge_score"] = _clamp_score(base_score - anti_penalty - rules_penalty)
    result["agent"] = packet["agent"]["name"]
    result["agent_idx"] = packet["agent"]["idx"]
    result["role"] = packet["agent"]["role"]
    result["team"] = packet["agent"]["camp"]
    result["judge_scope"] = "postgame_full_info"
    result["used_private_info"] = bool(packet["private_record"]["available"])
    return result


def _invoke_judge(llm: Any, prompt: str, max_retries: int) -> str:
    messages = [
        SystemMessage(
            content=(
                "You are a strict postgame judge for AIWolf. "
                "Return JSON only. Do not use markdown fences."
            ),
        ),
        HumanMessage(content=prompt),
    ]
    for attempt in range(max_retries):
        try:
            return (llm | StrOutputParser()).invoke(messages)
        except Exception:
            if attempt == max_retries - 1:
                raise
            sleep(2)
    raise RuntimeError("Judge invocation failed unexpectedly.")


def main() -> None:
    """Run the judge pipeline from logs to scored JSON."""
    parser = argparse.ArgumentParser(description="Run postgame LLM-as-a-judge scoring.")
    parser.add_argument("--config", required=True, help="Path to config/*.yml")
    parser.add_argument("--log", required=True, help="Path to server/logs/game/*.log")
    parser.add_argument("--json", help="Optional path to server/logs/json/*.json")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write bundle and prompt files only, without calling any model.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle = build_judge_bundle(args.log, args.json)
    (out_dir / "judge_bundle.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")

    template_path = Path("evaluate/templates/postgame_judge_prompt.j2")
    rubric_path = Path("evaluate/rubric.md")
    schema_path = Path("evaluate/judge_schema.json")
    prompts_dir = out_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    rendered_prompts: dict[str, str] = {}
    for packet in bundle["player_packets"]:
        prompt = render_judge_prompt(
            template_path=template_path,
            rubric_path=rubric_path,
            schema_path=schema_path,
            game_summary=bundle["game_summary"],
            player_packet=packet,
        )
        agent_name = packet["agent"]["name"]
        rendered_prompts[agent_name] = prompt
        (prompts_dir / f"{agent_name}.prompt.md").write_text(prompt, encoding="utf-8")

    if args.dry_run:
        return

    config = _load_config(Path(args.config))
    llm = _create_llm(config)
    max_retries = int(config.get("llm", {}).get("max_retries", 3))

    results: list[dict[str, Any]] = []
    raw_outputs: dict[str, str] = {}
    for packet in bundle["player_packets"]:
        agent_name = packet["agent"]["name"]
        raw_output = _invoke_judge(llm, rendered_prompts[agent_name], max_retries=max_retries)
        raw_outputs[agent_name] = raw_output
        parsed = json.loads(_extract_json_text(raw_output))
        if not isinstance(parsed, dict):
            raise TypeError(f"Judge output for {agent_name} did not parse as a JSON object.")
        results.append(_normalize_result(parsed, packet))

    (out_dir / "judge_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "judge_raw_outputs.json").write_text(
        json.dumps(raw_outputs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
