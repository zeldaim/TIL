\# 🛡️ Troubleshooting: 가상 머신 디스크 풀(Errno 28) 장애 복구



\## 🚨 문제 상황

\- \*\*에러 메시지\*\*: `Errno 28: 장치에 남은 공간이 없음`

\- \*\*상태\*\*: Hydra 공격 실습 중 대량의 로그 발생으로 디스크 사용률 100% 도달.



\## 🔍 원인 분석

\- \*\*공격 로그 폭주\*\*: `/var/log/secure` 파일에 SSH 무차별 대입 공격 실패 기록이 초 단위로 누적됨.

\- \*\*자원 고갈\*\*: 할당된 가상 디스크 용량이 로그 생성 속도를 감당하지 못해 시스템 마비.



\## 🛠️ 해결 방법

\- \*\*로그 비우기\*\*: `truncate` 명령어를 사용하여 서비스 중단 없이 로그 용량 즉시 확보.

&#x20; ```bash

&#x20; sudo truncate -s 0 /var/log/secure

&#x20; sudo truncate -s 0 /var/log/messages

&#x20; sudo truncate -s 0 /var/ossec/logs/ossec.log

