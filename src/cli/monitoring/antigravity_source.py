import os
import time
from pathlib import Path
from constants.source_files import ANTIGRAVITY_BASE_DIR

class AntigravitySource:
    def __init__(self):
        self.base_dir = Path(ANTIGRAVITY_BASE_DIR).expanduser()
        self.brain_dir = self.base_dir / "brain"
        self.conv_dir = self.base_dir / "conversations"

    def parse_antigravity_sessions(self) -> tuple:
        sessions = []
        totals = {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0}
        
        if not self.conv_dir.exists():
            return sessions, totals

        try:
            # We look at .pb files in conversations
            pb_files = list(self.conv_dir.glob("*.pb"))
            # Sort by modification time
            pb_files = sorted(pb_files, key=os.path.getmtime, reverse=True)[:10]

            for pb_file in pb_files:
                session_id = pb_file.stem
                mtime = os.path.getmtime(pb_file)
                
                # Estimate tokens: 1KB ~ 150 tokens (conservative estimate for binary PB)
                file_size_kb = pb_file.stat().st_size / 1024
                estimated_tokens = int(file_size_kb * 150)
                
                # Add to global totals (rough distribution: 80% input, 10% output, 10% cache)
                totals["input"] += int(estimated_tokens * 0.7)
                totals["output"] += int(estimated_tokens * 0.15)
                totals["cacheR"] += int(estimated_tokens * 0.15)
                
                # Find summary from brain artifacts
                summary = self._get_summary_from_brain(session_id)
                
                # Status
                status = "Wait"
                if time.time() - mtime < 60:
                    status = "Work"
                
                sessions.append({
                    "AI": "AG",
                    "Project": "mathtools", # Default for this env
                    "ProjectPath": "/root/mathtools",
                    "SessionId": session_id,
                    "Summary": summary,
                    "Model": "antigravity",
                    "Status": status,
                    "TurnCount": "-", 
                    "LastContext": int(estimated_tokens * 0.6), 
                    "ContextWindow": 2000000, 
                    "TotalTokens": estimated_tokens,
                    "InputTokens": int(estimated_tokens * 0.7),
                    "OutputTokens": int(estimated_tokens * 0.15),
                    "CacheR": int(estimated_tokens * 0.15),
                    "CacheW": 0,
                    "Quota": None,
                    "mtime": mtime
                })
        except Exception:
            pass
            
        return sessions, totals

    def _get_summary_from_brain(self, session_id: str) -> str:
        session_brain = self.brain_dir / session_id
        if not session_brain.exists():
            return "Antigravity Session"
            
        # Try walkthrough, then task, then plan
        for filename in ["walkthrough.md", "task.md", "implementation_plan.md"]:
            file_path = session_brain / filename
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            clean = line.lstrip("# \t").strip()
                            if clean:
                                return clean[:60] + ("..." if len(clean) > 60 else "")
                except:
                    continue
        return f"Session {session_id[:8]}"
