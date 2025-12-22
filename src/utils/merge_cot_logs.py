"""Merge and sort COT logs from all agents by timestamp.

合并所有玩家的 COT 日志，按时间排序，方便分析 AI 决策过程。

Usage:
    python src/utils/merge_cot_logs.py ./log/cot_log/20251216124818996
    python src/utils/merge_cot_logs.py ./log/cot_log/20251216124818996 --html
    python src/utils/merge_cot_logs.py ./log/cot_log/20251216124818996 -o merged.log
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, TypedDict

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
            # Note: (.*)$ makes the request part optional (FULL_RESPONSE has no request)
            match = re.match(
                r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - \S+ - \[(\w+)\](.*)$",
                line.strip()
            )
            
            if match:
                # Save previous entry
                if current_entry and current_entry["type"] in ("THINKING", "ACTION"):
                    entries.append(current_entry)
                
                timestamp_str, entry_type, request_raw = match.groups()
                request = request_raw.strip() if request_raw else ""
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
    prev_agent: Optional[str] = None
    
    for entry in all_entries:
        # Add separator when request type changes
        if entry["request"] != current_request:
            current_request = entry["request"]
            prev_agent = None  # Reset agent tracking for new request
            output_lines.append("")
            output_lines.append("=" * 70)
            output_lines.append(f">>> {entry['request']}")
            output_lines.append("=" * 70)
        
        # Format entry
        time_str = entry["timestamp"].strftime("%H:%M:%S")
        
        # Add visual separator between different agents
        if prev_agent is not None and entry["agent"] != prev_agent:
            output_lines.append("")
            output_lines.append("-" * 40)
        
        prev_agent = entry["agent"]
        
        if entry["type"] == "THINKING":
            output_lines.append("")
            output_lines.append(f"[{time_str}] THINK >> {entry['agent']}")
            output_lines.append(entry["content"].strip())
        else:  # ACTION
            output_lines.append(f"[{time_str}] SAY   >> {entry['agent']}")
            output_lines.append(f"    {entry['content'].strip()}")
    
    result = "\n".join(output_lines)
    
    # Write to file if specified
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Merged log saved to: {output_file}")
    
    return result


# Agent color palette for HTML output
AGENT_COLORS = [
    "#4ecdc4",  # Teal
    "#ff6b6b",  # Coral
    "#95e1d3",  # Mint
    "#f9ca24",  # Yellow
    "#a29bfe",  # Purple
    "#fd79a8",  # Pink
    "#00b894",  # Green
    "#e17055",  # Orange
]


def merge_cot_logs_html(cot_log_dir: Path, output_file: Optional[Path] = None) -> str:
    """Merge all COT logs and output as HTML with styling.
    
    Args:
        cot_log_dir: Directory containing *_cot.log files
        output_file: Optional output file path
        
    Returns:
        HTML content as string
    """
    all_entries: list[CotEntry] = []
    
    # Read all COT log files
    for log_file in cot_log_dir.glob("*_cot.log"):
        entries = parse_cot_log(log_file)
        all_entries.extend(entries)
    
    # Sort by timestamp
    all_entries.sort(key=lambda x: x["timestamp"])
    
    # Assign colors to agents
    agents = list(set(e["agent"] for e in all_entries))
    agents.sort()
    agent_colors = {agent: AGENT_COLORS[i % len(AGENT_COLORS)] for i, agent in enumerate(agents)}
    
    # Build HTML
    html_parts: list[str] = []
    
    # HTML header with CSS
    html_parts.append(f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>COT Timeline - {cot_log_dir.name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', 'Hiragino Sans', 'Meiryo', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            padding: 30px 0;
            border-bottom: 2px solid #4ecdc4;
            margin-bottom: 30px;
        }}
        header h1 {{
            font-size: 2em;
            color: #4ecdc4;
            margin-bottom: 10px;
        }}
        header p {{
            color: #888;
            font-size: 0.9em;
        }}
        .legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            justify-content: center;
            margin-bottom: 30px;
            padding: 15px;
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.85em;
        }}
        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}
        .request-section {{
            margin-bottom: 40px;
        }}
        .request-header {{
            background: linear-gradient(90deg, #4ecdc4, transparent);
            padding: 12px 20px;
            border-radius: 8px 8px 0 0;
            font-weight: bold;
            font-size: 1.1em;
            color: #1a1a2e;
        }}
        .entry {{
            background: rgba(255,255,255,0.03);
            border-left: 4px solid;
            margin: 10px 0;
            border-radius: 0 8px 8px 0;
            overflow: hidden;
        }}
        .entry-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 15px;
            background: rgba(0,0,0,0.2);
            cursor: pointer;
        }}
        .entry-header:hover {{
            background: rgba(0,0,0,0.3);
        }}
        .time {{
            font-family: monospace;
            color: #888;
            font-size: 0.85em;
        }}
        .agent {{
            font-weight: bold;
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 0.85em;
        }}
        .type-badge {{
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
        }}
        .type-think {{
            background: #2d3436;
            color: #b2bec3;
        }}
        .type-say {{
            background: #00b894;
            color: white;
        }}
        .entry-content {{
            padding: 15px;
            white-space: pre-wrap;
            word-wrap: break-word;
            line-height: 1.6;
            font-size: 0.95em;
        }}
        .think-content {{
            color: #b2bec3;
            font-style: italic;
            border-top: 1px dashed rgba(255,255,255,0.1);
        }}
        .say-content {{
            color: #fff;
            background: rgba(0,184,148,0.1);
        }}
        details summary {{
            list-style: none;
        }}
        details summary::-webkit-details-marker {{
            display: none;
        }}
        details[open] .toggle-icon {{
            transform: rotate(90deg);
        }}
        .toggle-icon {{
            transition: transform 0.2s;
            color: #666;
        }}
        .pair-group {{
            margin: 15px 0;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🐺 AI Wolf COT Timeline</h1>
            <p>Source: {cot_log_dir}</p>
        </header>
        
        <div class="legend">
''')
    
    # Add legend
    for agent, color in agent_colors.items():
        html_parts.append(f'''            <div class="legend-item">
                <div class="legend-color" style="background: {color};"></div>
                <span>{agent}</span>
            </div>
''')
    
    html_parts.append('        </div>\n')
    
    # Group entries by request and then pair THINKING+ACTION
    current_request: Optional[str] = None
    i = 0
    
    while i < len(all_entries):
        entry = all_entries[i]
        
        # New request section
        if entry["request"] != current_request:
            if current_request is not None:
                html_parts.append('        </div>\n')  # Close previous section
            current_request = entry["request"]
            html_parts.append(f'''        <div class="request-section">
            <div class="request-header">📋 {entry["request"]}</div>
''')
        
        color = agent_colors[entry["agent"]]
        time_str = entry["timestamp"].strftime("%H:%M:%S")
        
        # Check if this is a THINKING entry followed by ACTION from same agent
        if entry["type"] == "THINKING" and i + 1 < len(all_entries):
            next_entry = all_entries[i + 1]
            if next_entry["type"] == "ACTION" and next_entry["agent"] == entry["agent"]:
                # Paired THINKING + ACTION
                next_time_str = next_entry["timestamp"].strftime("%H:%M:%S")
                html_parts.append(f'''            <div class="pair-group">
                <details>
                    <summary>
                        <div class="entry" style="border-color: {color};">
                            <div class="entry-header">
                                <span class="toggle-icon">▶</span>
                                <span class="time">{time_str}</span>
                                <span class="agent" style="background: {color}; color: #1a1a2e;">{entry["agent"]}</span>
                                <span class="type-badge type-think">💭 THINK</span>
                            </div>
                        </div>
                    </summary>
                    <div class="entry-content think-content">{_escape_html(entry["content"].strip())}</div>
                </details>
                <div class="entry" style="border-color: {color};">
                    <div class="entry-header">
                        <span style="width: 16px;"></span>
                        <span class="time">{next_time_str}</span>
                        <span class="agent" style="background: {color}; color: #1a1a2e;">{next_entry["agent"]}</span>
                        <span class="type-badge type-say">💬 SAY</span>
                    </div>
                    <div class="entry-content say-content">{_escape_html(next_entry["content"].strip())}</div>
                </div>
            </div>
''')
                i += 2
                continue
        
        # Single entry (not paired)
        type_class = "type-think" if entry["type"] == "THINKING" else "type-say"
        type_icon = "💭 THINK" if entry["type"] == "THINKING" else "💬 SAY"
        content_class = "think-content" if entry["type"] == "THINKING" else "say-content"
        
        html_parts.append(f'''            <div class="entry" style="border-color: {color};">
                <div class="entry-header">
                    <span class="time">{time_str}</span>
                    <span class="agent" style="background: {color}; color: #1a1a2e;">{entry["agent"]}</span>
                    <span class="type-badge {type_class}">{type_icon}</span>
                </div>
                <div class="entry-content {content_class}">{_escape_html(entry["content"].strip())}</div>
            </div>
''')
        i += 1
    
    # Close last section
    if current_request is not None:
        html_parts.append('        </div>\n')
    
    html_parts.append('''    </div>
</body>
</html>
''')
    
    result = "".join(html_parts)
    
    # Write to file if specified
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"HTML log saved to: {output_file}")
    
    return result


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


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
        help="Output file path (default: auto-generated in source directory)"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Output as HTML file with styling (recommended for readability)"
    )
    
    args = parser.parse_args()
    
    if not args.cot_log_dir.exists():
        print(f"Error: Directory not found: {args.cot_log_dir}")
        return 1
    
    if args.html:
        # HTML output
        if args.output is None:
            args.output = args.cot_log_dir / "merged_timeline.html"
        merge_cot_logs_html(args.cot_log_dir, args.output)
        print(f"\nOpen in browser: file:///{args.output.resolve()}")
    else:
        # Plain text output
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

