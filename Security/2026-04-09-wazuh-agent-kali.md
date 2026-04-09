\# Wazuh 에이전트 Kali Linux 연동



\## 환경

\- Wazuh Manager: Rocky Linux Docker (v4.9.0)

\- Kali Linux IP: 192.168.190.130



\## 설치 명령어

curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | sudo gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import \&\& sudo chmod 644 /usr/share/keyrings/wazuh.gpg



echo "deb \[signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" | sudo tee /etc/apt/sources.list.d/wazuh.list



sudo apt update

sudo apt install -y wazuh-agent



sudo sed -i 's/MANAGER\_IP/192.168.190.128/' /var/ossec/etc/ossec.conf



sudo systemctl enable wazuh-agent

sudo systemctl start wazuh-agent



\## 트러블슈팅



\### 문제 1 - Never connected

\- 원인: Manager에 에이전트 등록은 됐지만 키 교환 안됨

\- 해결: Manager에서 키 추출 후 Kali에서 키 등록



\### 문제 2 - 버전 불일치

\- 오류: Agent version must be lower or equal to manager version

\- 원인: Kali 에이전트가 Manager(4.9.0)보다 높은 버전

\- 해결: 에이전트 4.9.0으로 다운그레이드



\### 문제 3 - MANAGER\_IP 미치환

\- 오류: Invalid server address found: 'MANAGER\_IP'

\- 원인: 다운그레이드 후 재설치로 설정 초기화

\- 해결: sed 명령어로 MANAGER\_IP → 192.168.190.128 변경



\### 문제 4 - 새 에이전트 자동 생성

\- 현상: yhc 이름으로 새 에이전트 자동 등록

\- 원인: 재설치 후 호스트명으로 자동 등록되는 정상 동작

\- 결과: ID:004 yhc → Active (정상)



\## 배운 것

\- systemctl status는 프로세스 실행 여부만 확인

\- 실제 연결 오류는 ossec.log에서 확인

\- Wazuh 에이전트 삭제해도 Manager 등록 정보는 유지됨

\- 에이전트 정상 동작 시 호스트명으로 자동 등록됨

\- 에이전트 버전은 Manager 버전보다 낮거나 같아야 함



\## 결과

\- ID: 002 RockyLinux → Active ✅

\- ID: 004 yhc (Kali) → Active ✅

\- Wazuh 대시보드에서 2개 에이전트 확인 ✅

