\# Windows VM + Sysmon + Wazuh 에이전트 연동



\## 환경

\- Windows 10 64-bit

\- VMware Workstation Pro

\- Sysmon (Sysinternals)

\- Wazuh Agent 4.9.0



\## 설치 순서



\### 1. Sysmon 설치

PowerShell 관리자 권한으로

Expand-Archive -Path C:\\Users\\yhc\\Downloads\\Sysmon.zip -DestinationPath C:\\Users\\yhc\\Downloads\\Sysmon

cd C:\\Users\\yhc\\Downloads\\Sysmon

.\\Sysmon64.exe -accepteula -i



\### 2. Wazuh 에이전트 설치

\- wazuh-agent-4.9.0-1.msi 다운로드

\- Manager IP: 192.168.190.128 설정

\- 설치 완료 후 서비스 시작



\### 3. Sysmon 로그 Wazuh 연동

C:\\Program Files (x86)\\ossec-agent\\ossec.conf 에 추가

<localfile>

&#x20; <location>Microsoft-Windows-Sysmon/Operational</location>

&#x20; <log\_format>eventchannel</log\_format>

</localfile>



Restart-Service WazuhSvc



\## 결과

\- ID: 004, Name: DESKTOP-5408CBA, Active

\- Sysmon 이벤트 27건 탐지

\- Discovery activity executed

\- net.exe account discovery command 탐지



\## 배운 것

\- Sysmon은 Windows 시스템 활동을 상세히 기록

\- Wazuh 에이전트가 호스트명으로 자동 등록됨

\- eventchannel 형식으로 Windows 이벤트 로그 수집

