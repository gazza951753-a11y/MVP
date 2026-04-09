from prometheus_client import Counter, Histogram

crawler_requests_total = Counter("crawler_requests_total", "Total crawler requests", ["source"])
crawler_http_429_total = Counter("crawler_http_429_total", "Total HTTP 429 responses", ["source"])
crawler_blocked_total = Counter("crawler_blocked_total", "Blocked/CAPTCHA events", ["source"])
crawler_latency_seconds = Histogram("crawler_latency_seconds", "Collector latency seconds", ["source"])

tasks_created_total = Counter("tasks_created_total", "Total created tasks", ["task_type"])
