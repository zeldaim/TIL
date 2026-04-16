# Troubleshooting — 2026-04-16

---

## 1. ossec.conf log_format 누락

### 증상
`/var/log/secure`에 로그가 찍히는데 Wazuh 알럿이 발생하지 않음.

### 원인
localfile 블록에 `<log_format>` 태그 누락. 형식을 인식하지 못해 파싱 실패.

```xml
<!-- 문제 있는 설정 -->
<localfile>
  <location>/var/log/secure</location>
</localfile>
```

### 해결
```xml
<localfile>
  <log_format>syslog</log_format>
  <location>/var/log/secure</location>
</localfile>
```

```bash
sudo systemctl restart wazuh-agent
```

---

## 2. curl URL 파싱 에러

### 증상
```
curl: (3) URL rejected: Malformed input to a URL function
```

### 원인
싱글쿼트(`'`)와 공백이 포함된 URL을 쌍따옴표로 감쌌을 때, `--"` 에서 쌍따옴표가 닫혀버려 URL이 깨짐.

```bash
# 잘못된 예시
curl "http://192.168.190.128/?id=1' union select 1,2,3--"
```

### 해결
URL 인코딩 적용:

```bash
curl "http://192.168.190.128/?id=1%27%20union%20select%201%2C2%2C3--"
```

| 문자 | 인코딩 |
|---|---|
| `'` | `%27` |
| 공백 | `%20` |
| `,` | `%2C` |
| `=` | `%3D` |

---

## 3. Wazuh alerts.log 파일 없음 (호스트에서 접근 시)

### 증상
```
tail: cannot open '/var/ossec/logs/alerts/alerts.log' for reading: 그런 파일이나 디렉터리가 없습니다
```

### 원인
Wazuh Manager가 Docker 컨테이너로 구동 중. alerts.log는 컨테이너 내부에 존재.

### 해결
```bash
docker exec -it single-node-wazuh.manager-1 tail -f /var/ossec/logs/alerts/alerts.log
```

---

## 4. Rule 100005가 Manager에 없음 (SQLi 탐지 안 됨)

### 증상
`wazuh-logtest`에서 rule 매칭 안 됨. alerts.log에 SQLi alert 미생성.

### 원인
custom rule을 Rocky Linux 호스트의 `/var/ossec/etc/rules/`에만 작성.  
Wazuh Manager는 Docker 컨테이너이므로 **컨테이너 내부**에 rule이 있어야 함.

### 확인
```bash
docker exec -it single-node-wazuh.manager-1 find /var/ossec/ruleset -name "*.xml" | xargs grep -l "100005"
# → 결과 없음
```

### 해결
```bash
cat > /tmp/sqli_rule.xml << 'EOF'
<group name="web,sqli,">
  <rule id="100005" level="10">
    <if_sid>31103</if_sid>
    <url>union|select|insert|drop|delete|update|cast|exec|declare|--|%27|%3B</url>
    <description>SQL Injection attempt detected</description>
    <mitre>
      <id>T1190</id>
    </mitre>
  </rule>
</group>
EOF

docker cp /tmp/sqli_rule.xml single-node-wazuh.manager-1:/tmp/sqli_rule.xml
docker exec single-node-wazuh.manager-1 bash -c "cat /tmp/sqli_rule.xml >> /var/ossec/etc/rules/local_rules.xml"
docker exec single-node-wazuh.manager-1 /var/ossec/bin/wazuh-control restart
```

---

## 5. Manager 재시작 후 Agent 연결 끊김

### 증상
```
wazuh-agentd: ERROR: (1137): Lost connection with manager. Setting lock.
```

### 원인
Manager 재시작 시 Agent 연결이 끊김. 자동 재연결이 안 된 상태.

### 해결
```bash
sudo systemctl restart wazuh-agent

# 연결 확인
sudo tail -f /var/ossec/logs/ossec.log
# → "Analyzing file: '/var/log/httpd/access_log'" 확인
```

---

## 핵심 교훈 요약

| # | 교훈 |
|---|---|
| 1 | `log_format` 없으면 Wazuh가 로그를 읽어도 파싱 못함 |
| 2 | curl SQLi 페이로드는 반드시 URL 인코딩 필요 |
| 3 | Wazuh가 Docker이면 alerts.log는 컨테이너 내부 기준 |
| 4 | Custom rule은 Manager 컨테이너의 `local_rules.xml`에 넣어야 적용됨 |
| 5 | Manager 재시작 후 반드시 Agent 재시작 및 연결 확인 |
