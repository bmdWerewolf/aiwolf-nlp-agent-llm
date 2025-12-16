"""Merge and sort COT logs from all agents by timestamp.

合并所有玩家的 COT 日志，按时间排序，方便分析 AI 决策过程。

Usage:
    python src/utils/merge_cot_logs.py ./log/cot_log/20251216124818996
    python src/utils/merge_cot_logs.py ./log/cot_log/20251216124818996 -o merged.log
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, TypedDict, Union

class CotEntry(TypedDict):
    timestamp: datetime
    agent: str
    type: str
    request: str
    content: str

def parse_cot_log(file_path: Path) -> list[CotEntry]:
    """Parse a single COT log file and extract entries.
    
    Args:
        file_path: Path to the COT log file
        
    Returns:
        List of parsed log entries with timestamp, agent, type, and content
    """
    entries: list[CotEntry] = []
    current_entry: Optional[CotEntry] = None
    agent_name = file_path.stem.replace("_cot", "")  # e.g., kanolab_11
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            # Match log line: 2025-12-16 12:48:38,934 - kanolab_12_cot - [THINKING] Request.VOTE
            match = re.match(
                r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - \S+ - \[(\w+)\] (.+)",
                line.strip()
            )
            
            if match:
                # Save previous entry
                if current_entry and current_entry["type"] in ("THINKING", "ACTION"):
                    entries.append(current_entry)
                
                timestamp_str, entry_type, request = match.groups()
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
                
                current_entry = {
                    "timestamp": timestamp,
                    "agent": agent_name,
                    "type": entry_type,
                    "request": request,
                    "content": ""
                }
            elif line.strip() == "=" * 50:
                # End of FULL_RESPONSE block, skip
                if current_entry and current_entry["type"] in ("THINKING", "ACTION"):
                    entries.append(current_entry)
                current_entry = None
            elif current_entry and current_entry["type"] in ("THINKING", "ACTION"):
                # Append content lines
                current_entry["content"] += line
    
    # Don't forget the last entry
    if current_entry and current_entry["type"] in ("THINKING", "ACTION"):
        entries.append(current_entry)
    
    return entries


def merge_cot_logs(cot_log_dir: Path, output_file: Optional[Path] = None) -> str:
    """Merge all COT logs from a directory, sorted by timestamp.
    
    Args:
        cot_log_dir: Directory containing *_cot.log files
        output_file: Optional output file path
        
    Returns:
        Merged log content as string
    """
    all_entries: list[CotEntry] = []
    
    # Read all COT log files
    for log_file in cot_log_dir.glob("*_cot.log"):
        entries = parse_cot_log(log_file)
        all_entries.extend(entries)
    
    # Sort by timestamp
    all_entries.sort(key=lambda x: x["timestamp"])
    
    # Format output
    output_lines: list[str] = []
    output_lines.append("=" * 80)
    output_lines.append("MERGED COT LOG - All Players Timeline")
    output_lines.append(f"Source: {cot_log_dir}")
    output_lines.append("=" * 80)
    output_lines.append("")
    
    current_request: Optional[str] = None
    for entry in all_entries:
        # Add separator when request type changes
        if entry["request"] != current_request:
            current_request = entry["request"]
            output_lines.append("")
            output_lines.append("-" * 60)
            output_lines.append(f">>> {entry['request']}")
            output_lines.append("-" * 60)
        
        # Format entry
        time_str = entry["timestamp"].strftime("%H:%M:%S")
        type_marker = "[THINK]" if entry["type"] == "THINKING" else "[SAY]"
        
        output_lines.append("")
        output_lines.append(f"[{time_str}] {type_marker} {entry['agent']} ({entry['type']})")
        output_lines.append(entry["content"].strip())
    
    result = "\n".join(output_lines)
    
    # Write to file if specified
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Merged log saved to: {output_file}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Merge COT logs from all agents, sorted by timestamp"
    )
    parser.add_argument(
        "cot_log_dir",
        type=Path,
        help="Directory containing *_cot.log files (e.g., ./log/cot_log/20251216124818996)"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output file path (default: prints to stdout)"
    )
    
    args = parser.parse_args()
    
    if not args.cot_log_dir.exists():
        print(f"Error: Directory not found: {args.cot_log_dir}")
        return 1
    
    # Default output file in the same directory
    if args.output is None:
        args.output = args.cot_log_dir / "merged_timeline.log"
    
    result = merge_cot_logs(args.cot_log_dir, args.output)
    
    # Also print to stdout (with encoding error handling for Windows)
    import sys
    try:
        print(result)
    except UnicodeEncodeError:
        # Fallback for Windows console encoding issues
        print(result.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
    
    return 0


if __name__ == "__main__":
    exit(main())

