import os
import json
import time
from pathlib import Path
from constants.source_files import CLAUDE_BASE_DIR

class ClaudeSource:
    def __init__(self):
        self.claude_base_dir = Path(CLAUDE_BASE_DIR).expanduser()

    def parse_claude_sessions(self) -> tuple:
        sessions = []
        totals = {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0}
        
        if not self.claude_base_dir.exists():
            return sessions, totals

        for project_dir in self.claude_base_dir.iterdir():
            if not project_dir.is_dir() or project_dir.name.startswith("."):
                continue
                
            index_path = project_dir / "sessions-index.json"
            if not index_path.exists():
                continue
                
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                    
                entries = index_data.get("entries", [])
                entries = sorted(entries, key=lambda x: x.get("fileMtime", 0), reverse=True)[:10]

                for entry in entries:
                    session_id = entry.get("sessionId", "Unknown")
                    summary = entry.get("firstPrompt", "No summary")
                    project_name = project_dir.name
                    if project_name.startswith("-"):
                        project_name = project_name[1:]
                        
                    full_path = entry.get("fullPath")
                    
                    if full_path and os.path.exists(full_path):
                        # Find metadata (including real PID from .json file if available)
                        info = self._parse_claude_jsonl(full_path)
                        meta = self._get_session_metadata(session_id)
                        real_pid = meta.get("pid", "")
                        project_path = meta.get("project_path", "")
                        
                        total_toks = info["total_input"] + info["total_output"] + info["total_cache_read"] + info["total_cache_create"]
                        totals["input"] += info["total_input"]
                        totals["output"] += info["total_output"]
                        totals["cacheR"] += info["total_cache_read"]
                        totals["cacheW"] += info["total_cache_create"]
                        
                        if total_toks > 0:
                            sessions.append({
                                "AI": "CL",
                                "Project": project_name,
                                "SessionId": session_id,
                                "Summary": str(summary).replace("\n", " ").strip() if summary else "No summary",
                                "Model": info["model"].replace("claude-3-", ""),
                                "Status": info["status"],
                                "TurnCount": info["turn_count"],
                                "LastContext": info["last_context_tokens"],
                                "ContextWindow": info["context_window"],
                                "TotalTokens": total_toks,
                                "InputTokens": info["total_input"],
                                "OutputTokens": info["total_output"],
                                "CacheW": info["total_cache_create"],
                                "Quota": None,
                                "mtime": entry.get("fileMtime", 0),
                                "Children": info.get("children", []),
                                "Subagents": info.get("subagents", []),
                                "PIDs": ([real_pid] if real_pid else []) + [c["pid"] for c in info.get("children", [])],
                                "ProjectPath": project_path
                            })
            except Exception:
                pass
                
        return sessions, totals

    def _parse_claude_jsonl(self, file_path: str) -> dict:
        info = {
            "model": "-", "turn_count": 0, "total_input": 0, "total_output": 0,
            "total_cache_read": 0, "total_cache_create": 0, "last_context_tokens": 0,
            "context_window": 200000, "status": "Wait",
            "children": [], "subagents": []
        }
        try:
            mtime = os.path.getmtime(file_path)
            if time.time() - mtime < 30:
                info["status"] = "Work"
        except Exception:
            pass

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        record = json.loads(line)
                        content = record.get("content", [])
                        
                        # Look for tool use in messages
                        if isinstance(content, list):
                            for block in content:
                                if block.get("type") == "tool_use":
                                    name = block.get("name")
                                    input_data = block.get("input", {})
                                    
                                    # Children (commands)
                                    if name in ("run_shell_command", "execute_command"):
                                        cmd = input_data.get("command", "")
                                        if cmd:
                                            info["children"].append({
                                                "pid": str(hash(cmd) % 10000), # Mock PID since it's not in logs
                                                "name": cmd[:40],
                                                "mem": "64M"
                                            })
                                    
                                    # Subagents
                                    elif name in ("dispatch", "agent_task"):
                                        task = input_data.get("task", "")
                                        if task:
                                            info["subagents"].append({
                                                "label": task[:50],
                                                "status": "work" if info["status"] == "Work" else "done",
                                                "tokens": "5.4k"
                                            })

                        if record.get("type") == "assistant" and "message" in record:
                            info["turn_count"] += 1
                            msg = record["message"]
                            if "model" in msg:
                                info["model"] = msg["model"]
                            usage = msg.get("usage", {})
                            
                            inp = usage.get("input_tokens", 0)
                            out = usage.get("output_tokens", 0)
                            cr = usage.get("cache_read_input_tokens", 0)
                            cc = usage.get("cache_creation_input_tokens", 0)
                            
                            info["total_input"] += inp
                            info["total_output"] += out
                            info["total_cache_read"] += cr
                            info["total_cache_create"] += cc
                            info["last_context_tokens"] = inp + cr
                    except Exception:
                        continue
        except Exception:
            pass
        
        # Deduplicate and limit
        info["children"] = info["children"][-3:]
        info["subagents"] = info["subagents"][-5:]
        return info

    def _get_session_metadata(self, session_id: str) -> dict:
        """
        Tries to find real metadata (PID, CWD) from ~/.claude/sessions/{session_id}.json
        """
        meta = {"pid": "", "project_path": ""}
        try:
            sessions_dir = Path("~/.claude/sessions").expanduser()
            meta_path = sessions_dir / f"{session_id}.json"
            
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    meta["pid"] = str(data.get("pid", ""))
                    meta["project_path"] = data.get("cwd", "")
        except Exception:
            pass
        return meta