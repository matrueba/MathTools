import os
import json
import sqlite3
import time
from pathlib import Path
from constants.source_files import OPENCODE_BASE_DIR, OPENCODE_DB_PATH

class OpenCodeSource:
    def __init__(self):
        self.opencode_base_dir = Path(OPENCODE_BASE_DIR).expanduser()
        self.opencode_db_path = Path(OPENCODE_DB_PATH).expanduser()
            
    def parse_opencode_sessions(self) -> tuple:
        sessions = []
        totals = {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0}
        
        try:
            # Use read-only connection to avoid blocking
            conn = sqlite3.connect(f"file:{self.opencode_db_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, title, directory, time_updated 
                FROM session 
                ORDER BY time_updated DESC 
                LIMIT 10
            """)
            rows = cursor.fetchall()

            for s_id, title, directory, time_updated in rows:
                cursor.execute("SELECT data FROM message WHERE session_id = ?", (s_id,))
                msg_rows = cursor.fetchall()
                
                info = {
                    "model": "-", "turn_count": 0, "total_input": 0, "total_output": 0,
                    "total_cache_read": 0, "total_cache_create": 0, "last_context_tokens": 0,
                    "context_window": 128000, "status": "Wait"
                }
                
                # Opencode stores timestamps in ms
                if (time.time() * 1000) - time_updated < 30000:
                    info["status"] = "Work"

                for (data_json,) in msg_rows:
                    try:
                        data = json.loads(data_json)
                        if data.get("role") == "assistant":
                            info["turn_count"] += 1
                            if "modelID" in data:
                                info["model"] = data["modelID"]
                            
                            toks = data.get("tokens", {})
                            inp = toks.get("input", 0)
                            out = toks.get("output", 0)
                            cache = toks.get("cache", {})
                            cr = cache.get("read", 0)
                            cw = cache.get("write", 0)

                            info["total_input"] += inp
                            info["total_output"] += out
                            info["total_cache_read"] += cr
                            info["total_cache_create"] += cw
                            info["last_context_tokens"] = inp + cr
                    except:
                        continue
                
                totals["input"] += info["total_input"]
                totals["output"] += info["total_output"]
                totals["cacheR"] += info["total_cache_read"]
                totals["cacheW"] += info["total_cache_create"]

                total_toks = info["total_input"] + info["total_output"] + info["total_cache_read"] + info["total_cache_create"]

                sessions.append({
                    "AI": "OC",
                    "Project": os.path.basename(directory) if directory else "Unknown",
                    "SessionId": s_id,
                    "Summary": title,
                    "Model": info["model"],
                    "Status": info["status"],
                    "TurnCount": info["turn_count"],
                    "LastContext": info["last_context_tokens"],
                    "ContextWindow": info["context_window"],
                    "TotalTokens": total_toks,
                    "Quota": None,
                    "mtime": time_updated / 1000
                })

            conn.close()
        except:
            pass
            
        return sessions, totals

    def parse_opencode_jsonl(self, file_path: Path) -> dict:
        info = {
            "session_id": file_path.stem, "project": "Unknown", "summary": "Opencode session",
            "model": "-", "turn_count": 0, "total_input": 0, "total_output": 0,
            "total_cache_read": 0, "total_cache_create": 0, "last_context_tokens": 0,
            "context_window": 128000, "status": "Wait", "quota": None
        }
        try:
            mtime = os.path.getmtime(file_path)
            if time.time() - mtime < 30:
                info["status"] = "Work"
        except Exception:
            pass

        summary_found = False
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        record = json.loads(line)
                        rtype = record.get("type")
                        
                        if rtype == "session_meta":
                            payload = record.get("payload", {})
                            if "id" in payload: info["session_id"] = payload["id"]
                            if "cwd" in payload:
                                cwd = payload["cwd"]
                                info["project"] = os.path.basename(cwd) if cwd else "Unknown"
                        
                        elif rtype == "event_msg":
                            payload = record.get("payload", {})
                            evt_type = payload.get("type")
                            
                            if evt_type == "user_message" and not summary_found:
                                msg = payload.get("message", "")
                                if msg:
                                    info["summary"] = msg.replace("\n", " ").strip()
                                    summary_found = True
                                    
                            elif evt_type == "agent_message":
                                info["turn_count"] += 1
                            
                            elif evt_type == "task_started":
                                cw = payload.get("model_context_window")
                                if cw: info["context_window"] = cw
                                
                            elif evt_type == "token_count":
                                p_info = payload.get("info", {})
                                
                                # Totals
                                tot = p_info.get("total_token_usage", {})
                                if tot:
                                    info["total_input"] = tot.get("input_tokens", 0)
                                    info["total_output"] = tot.get("output_tokens", 0)
                                    info["total_cache_read"] = tot.get("cached_input_tokens", 0) or tot.get("cache_read_input_tokens", 0)

                                # Last
                                last_usage = p_info.get("last_token_usage", {})
                                if last_usage:
                                    inp = last_usage.get("input_tokens", 0)
                                    cache = last_usage.get("cached_input_tokens", 0) or last_usage.get("cache_read_input_tokens", 0)
                                    info["last_context_tokens"] = inp + cache
                                    
                                # Rate limits
                                rl = payload.get("rate_limits", {})
                                if rl:
                                    parsed_rl = {}
                                    prim = rl.get("primary", {})
                                    if prim:
                                        if prim.get("window_minutes", 0) <= 300:
                                            parsed_rl["five_hour_pct"] = prim.get("used_percent")
                                        else:
                                            parsed_rl["seven_day_pct"] = prim.get("used_percent")
                                    sec = rl.get("secondary", {})
                                    if sec:
                                        if sec.get("window_minutes", 0) <= 300:
                                            parsed_rl["five_hour_pct"] = sec.get("used_percent")
                                        else:
                                            parsed_rl["seven_day_pct"] = sec.get("used_percent")
                                    if parsed_rl:
                                        info["quota"] = parsed_rl
                                        
                        elif rtype == "turn_context":
                            payload = record.get("payload", {})
                            if "model" in payload:
                                info["model"] = payload["model"]
                            if "model_context_window" in payload:
                                info["context_window"] = payload["model_context_window"]
                                
                    except Exception:
                        continue
        except Exception:
            pass
        return info