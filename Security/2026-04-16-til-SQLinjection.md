# TIL — 2026-04-16

---

## 1. ossec.conf에서 log_format은 필수다

`log_format`이 없으면 Wazuh가 파일을 읽어도 파싱을 못한다.

```xml
<!-- 이렇게 하면 안 됨 -->
<localfile>
  <location>/var/log/secure</location>
</localfile>

<!-- 반드시 log_format 명시 -->
<localfile>
  <log_format>syslog</log_format>
  <location>/var/log/secure</location>
</localfile>
```

주요 log_format: `syslog`, `apache`, `audit`, `journald`

---

## 2. Wazuh Custom Rule은 Manager 컨테이너 안에 넣어야 한다

Rocky Linux 호스트의 `/var/ossec/`는 agent용 경로다.  
Rule은 **Manager 컨테이너 내부**의 `/var/ossec/etc/rules/local_rules.xml`에 있어야 적용된다.

```bash
# rule 적용 확인
docker exec single-node-wazuh.manager-1 grep -r "100005" /var/ossec/etc/rules/
```

XML 파일은 호스트에서 만들고 `docker cp`로 복사해야 한다.  
`docker exec ... bash -c 'cat > file << EOF'` 방식은 `<` 기호가 shell 리다이렉션으로 해석되어 태그가 깨진다.

```bash
cat > /tmp/rule.xml << 'EOF'
<group name="web,sqli,">
  ...
</group>
EOF

docker cp /tmp/rule.xml single-node-wazuh.manager-1:/var/ossec/etc/rules/local_rules.xml
```

---

## 3. wazuh-logtest로 rule 매칭을 미리 검증할 수 있다

실제 공격 트래픽 전에 로그 한 줄을 붙여넣어 rule 매칭 여부를 확인 가능.  
Phase 1 (pre-decoding) → Phase 2 (decoding) → Phase 3 (rule matching) 순서로 출력된다.

```bash
docker exec -it single-node-wazuh.manager-1 /var/ossec/bin/wazuh-logtest
# 로그 한 줄 입력 → Phase 3에서 rule id, level, description 확인
```

---

## 4. curl에서 SQLi 페이로드는 URL 인코딩이 필요하다

싱글쿼트와 공백이 포함된 URL을 그대로 쌍따옴표로 감싸면 curl이 파싱 에러를 낸다.

```bash
# 에러
curl "http://host/?id=1' union select 1,2,3--"

# 정상
curl "http://host/?id=1%27%20union%20select%201%2C2%2C3--"
```

---

## 5. Wazuh Manager 재시작 후 Agent도 재시작해야 한다

Manager를 재시작하면 Agent 연결이 끊긴다 (ERROR 1137).  
자동 재연결이 안 될 수 있으므로 수동으로 재시작해줘야 한다.

```bash
sudo systemctl restart wazuh-agent

# 연결 확인 — 아래 줄이 보이면 정상
# wazuh-logcollector: INFO: (1950): Analyzing file: '/var/log/httpd/access_log'
sudo tail -f /var/ossec/logs/ossec.log
```

---

## 6. HTTP 403이어도 Wazuh는 SQLi를 탐지할 수 있다

Apache가 요청을 403으로 막아도 access_log에는 요청이 기록된다.  
Wazuh는 access_log를 파싱하므로 실제 웹앱까지 요청이 닿지 않아도 탐지 가능하다.

```
Kali curl → Rocky Apache (403 응답) → access_log 기록 → Wazuh Agent → Rule 100005 매칭
```
