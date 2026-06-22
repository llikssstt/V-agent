from datetime import datetime
from zoneinfo import ZoneInfo


def get_current_time():
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    return {
        "ok": True,
        "timezone": "Asia/Shanghai",
        "iso": now.isoformat(timespec="seconds"),
        "text": now.strftime("%Y-%m-%d %H:%M:%S"),
    }

