#!/usr/bin/env python3
"""
Wazuh alerts.json Parser
Home SOC Lab - Week 3
Usage: python3 parse_alerts.py [alerts.json path]
"""

import json
import sys
import re
from collections import defaultdict, Counter
from datetime import datetime

# ── 경로 설정 ──────────────────────────────────────────────
ALERTS_FILE = sys.argv[1] if len(sys.argv) > 1 else "/var/ossec/logs/alerts/alerts.json"

# ── 데이터 수집용 구조 ──────────────────────────────────────
ip_counter      = Counter()          # 공격 IP 빈도
rule_counter    = Counter()          # Rule ID 발동 횟수
hour_counter    = Counter()          # 시간대 분포 (0~23시)
rule_desc       = {}                 # rule_id -> description 매핑
mitre_counter   = Counter()          # MITRE technique 빈도
level_counter   = Counter()          # 위협 레벨 분포
parse_errors    = 0
total           = 0

# ── 파싱 ───────────────────────────────────────────────────
with open(ALERTS_FILE, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            alert = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue

        total += 1

        # 1) 공격 IP 추출 (data.srcip 우선, 없으면 agent.ip)
        src_ip = (
            alert.get("data", {}).get("srcip")
            or alert.get("data", {}).get("src_ip")
            or alert.get("agent", {}).get("ip")
        )
        if src_ip and src_ip not in ("127.0.0.1", "::1", "unknown"):
            ip_counter[src_ip] += 1

        # 2) Rule 정보
        rule = alert.get("rule", {})
        rule_id   = str(rule.get("id", "unknown"))
        rule_lv   = rule.get("level", 0)
        rule_desc[rule_id] = rule.get("description", "")
        rule_counter[rule_id] += 1
        level_counter[rule_lv] += 1

        # 3) 시간대 추출
        ts = alert.get("timestamp", "")
        try:
            # 형식: 2026-04-22T02:45:11.031+0000
            hour = int(ts[11:13])
            hour_counter[hour] += 1
        except (ValueError, IndexError):
            pass

        # 4) MITRE technique
        mitre_ids = rule.get("mitre", {}).get("id", [])
        for mid in mitre_ids:
            mitre_counter[mid] += 1

# ── 출력 ───────────────────────────────────────────────────
SEP = "=" * 60

print(f"\n{SEP}")
print(f"  WAZUH ALERT ANALYSIS REPORT")
print(f"  파일: {ALERTS_FILE}")
print(f"  총 이벤트: {total:,}건  |  파싱 오류: {parse_errors}건")
print(SEP)

# 1) Top 10 공격 IP
print("\n[1] 공격 IP 빈도 Top 10")
print(f"  {'IP':<20} {'횟수':>8}")
print(f"  {'-'*20} {'-'*8}")
for ip, cnt in ip_counter.most_common(10):
    print(f"  {ip:<20} {cnt:>8,}")

# 2) Top 15 Rule 발동 횟수
print("\n[2] Rule 발동 횟수 Top 15")
print(f"  {'Rule ID':<10} {'횟수':>7}  설명")
print(f"  {'-'*10} {'-'*7}  {'-'*35}")
for rid, cnt in rule_counter.most_common(15):
    desc = rule_desc.get(rid, "")[:45]
    print(f"  {rid:<10} {cnt:>7,}  {desc}")

# 3) 시간대 분포
print("\n[3] 시간대별 이벤트 분포 (KST 기준 UTC+9 적용 필요)")
print(f"  {'시간':>4}  {'건수':>6}  {'바'}")
print(f"  {'-'*4}  {'-'*6}  {'-'*30}")
max_h = max(hour_counter.values()) if hour_counter else 1
for h in range(24):
    cnt = hour_counter.get(h, 0)
    bar = "█" * int(cnt / max_h * 30) if cnt else ""
    print(f"  {h:02d}시  {cnt:>6,}  {bar}")

# 4) MITRE ATT&CK 기법 분포
print("\n[4] MITRE ATT&CK Technique 발동 횟수")
print(f"  {'Technique':<12} {'횟수':>7}")
print(f"  {'-'*12} {'-'*7}")
for mid, cnt in mitre_counter.most_common(20):
    print(f"  {mid:<12} {cnt:>7,}")

# 5) 위협 레벨 분포
print("\n[5] 위협 레벨(Level) 분포")
print(f"  {'Level':<7} {'횟수':>7}  {'비율'}")
print(f"  {'-'*7} {'-'*7}  {'-'*10}")
for lv in sorted(level_counter.keys(), reverse=True):
    cnt = level_counter[lv]
    pct = cnt / total * 100 if total else 0
    print(f"  Lv {lv:<4} {cnt:>7,}  {pct:>5.1f}%")

print(f"\n{SEP}\n")
