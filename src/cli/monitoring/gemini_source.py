import os
import json
import time
from pathlib import Path
from constants.source_files import GEMINI_BASE_DIR

class GeminiSource:
    def __init__(self):
        self.gemini_base_dir = Path(GEMINI_BASE_DIR).expanduser()
        self.tmp_dir = self.gemini_base_dir / "tmp"

    def parse_gemini_sessions(self) -> tuple:
        sessions = []
        totals = {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0}
        
        if not self.tmp_dir.exists():
            return sessions, totals

        try:
            # Gemini stores sessions in ~/.gemini/tmp/<project>/chats/session-*.json
            for project_dir in self.tmp_dir.iterdir():
                if not project_dir.is_dir():
                    continue
                
                chats_dir = project_dir / "chats"
                if not chats_dir.exists():
                    continue
                
                # Get latest session files
                session_files = list(chats_dir.glob("session-*.json"))
                # Sort by modification time
                session_files = sorted(session_files, key=os.path.getmtime, reverse=True)[:10]

                for session_file in session_files:
                    try:
                        with open(session_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        
                        messages = data.get("messages", [])
                        if not messages:
                            continue
                            
                        session_id = session_file.stem.split("-")[-1]
                        project_name = project_dir.name
                        
                        info = self._extract_session_info(data)
                        
                        mtime = os.path.getmtime(session_file)
                        status = "Wait"
                        if time.time() - mtime < 45:
                            status = "Work"
                        
                        total_toks = info["total_input"] + info["total_output"] + info["total_cache_read"]
                        totals["input"] += info["total_input"]
                        totals["output"] += info["total_output"]
                        totals["cacheR"] += info["total_cache_read"]
                        
                        sessions.append({
                            "AI": "GE",
                            "Project": project_name,
                            "SessionId": session_id,
                            "Summary": info["summary"],
                            "Model": info["model"].replace("gemini-3-", ""),
                            "Status": status,
                            "TurnCount": info["turn_count"],
                            "LastContext": info["last_context_tokens"],
                            "ContextWindow": info["context_window"],
                            "TotalTokens": total_toks,
                            "InputTokens": info["total_input"],
                            "OutputTokens": info["total_output"],
                            "CacheR": info["total_cache_read"],
                            "CacheW": 0,
                            "mtime": mtime,
                            "Subagents": info["subagents"],
                            "PIDs": self._get_pids_for_project(project_name),
                            "ProjectPath": f"/root/{project_name}" # Heuristic
                        })
                    except Exception:
                        continue
        except Exception:
            pass
            
        return sessions, totals

    def _extract_session_info(self, data: dict) -> dict:
        info = {
            "model": "-", "turn_count": 0, "total_input": 0, "total_output": 0,
            "total_cache_read": 0, "last_context_tokens": 0,
            "context_window": 2000000, "summary": "Gemini Session",
            "subagents": []
        }
        
        user_summary = None
        gemini_summary = None
        
        messages = data.get("messages", [])
        for msg in messages:
            msg_type = msg.get("type")
            
            if msg_type == "gemini":
                # Tokens
                tokens = msg.get("tokens")
                if tokens:
                    info["turn_count"] += 1
                    inp = tokens.get("input", 0)
                    out = tokens.get("output", 0)
                    cached = tokens.get("cached", 0)
                    
                    info["total_input"] += inp
                    info["total_output"] += out
                    info["total_cache_read"] += cached
                    info["last_context_tokens"] = inp + cached
                
                # Model
                if "model" in msg:
                    info["model"] = msg["model"]
                
                # Thoughts -> Summary (Prefer the latest subject)
                thoughts = msg.get("thoughts", [])
                if thoughts:
                    for thought in reversed(thoughts):
                        subject = thought.get("subject")
                        if subject:
                            gemini_summary = subject
                            break
            
            elif msg_type == "user" and not user_summary:
                # Fallback to first user message
                content = msg.get("content", [])
                if isinstance(content, list) and content:
                    text = content[0].get("text")
                    if text:
                        user_summary = text[:60] + ("..." if len(text) > 60 else "")
        
        info["summary"] = gemini_summary or user_summary or "Gemini Session"
        return info

    def _get_pids_for_project(self, project_name: str) -> list:
        pids = []
        import subprocess
        try:
            cmd = ["pgrep", "-f", "gemini"]
            raw_pids = subprocess.check_output(cmd).decode().splitlines()
            for pid in raw_pids:
                try:
                    cwd = os.readlink(f"/proc/{pid}/cwd")
                    if project_name in cwd:
                        pids.append(pid)
                except:
                    continue
        except:
            pass
        return pids
