# [Wazuh] MITRE ATT\&CK 기반 SSH Brute Force 탐지 구현 



 ## 📅 작성일: 2026-04-09

 ## 📝 요약

Wazuh Docker 환경에서 커스텀 룰을 정의하여 SSH 무차별 대입 공격(Brute Force)을 탐지하고, 분석 과정 중 발생한 리소스 부족 및 가상 디스크 에러를 해결한 과정을 기록합니다.



---



 ## 1. 실험 환경

\- \*\*Target OS:\*\* Rocky Linux 9 (Docker Container 기반 Wazuh Agent)

\- \*\*Attacker OS:\*\* Kali Linux (Hydra 사용)

\- \*\*SIEM:\*\* Wazuh Manager (Single-node Docker deployment)



---



 ## 2. 구현 단계



 ### 2.1 Wazuh 커스텀 룰 설정

Wazuh Manager가 Docker 컨테이너 내부에서 구동 중이므로, 컨테이너 내 `local_rules.xml` 파일을 수정해야 합니다.



```bash

 # 1. Wazuh Manager 컨테이너 접속

sudo docker exec -it single-node-wazuh.manager-1 bash



 # 2. 커스텀 룰(ID: 100001) 작성

 # if_matched_sid를 5760(sshd: authentication failed)으로 설정하여 탐지 트리거 생성

cat > /var/ossec/etc/rules/local_rules.xml << 'EOF'

<group name="custom_rules">

  <rule id="100001" level="10" frequency="5" timeframe="60">

    <if_matched_sid>5760</if_matched_sid>

    <same_source_ip />

    <description>SSH Brute Force Attack Detected - MITRE T1110</description>

    <mitre>

      <id>T1110</id>

    </mitre>

  </rule>

</group>

EOF



 # 3. 설정 적용을 위한 컨테이너 재시작

exit

sudo docker restart single-node-wazuh.manager-1
2.2 공격 시뮬레이션 및 검증
Kali Linux에서 Hydra 도구를 사용하여 SSH 로그인 시도를 반복 수행했습니다.

Bash
# SSH 공격 수행
hydra -l testuser -P /usr/share/wordlists/rockyou.txt ssh://[Target_IP] -t 4


