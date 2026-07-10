# scripts

설치, 네트워크 설정, 실행 환경 적용을 돕는 스크립트를 둔다.

- `configure_go2_eth.bash`: PC 유선 NIC를 Go2 기본 대역으로 설정
- `setup_go2_cyclonedds.bash`: ROS2/CycloneDDS 환경 변수를 적용하고 runtime XML을 생성

환경 적용 스크립트는 실행이 아니라 `source`로 불러와야 현재 터미널에 변수들이 남는다.
