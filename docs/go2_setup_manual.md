# Unitree Go2 세팅 매뉴얼

## 1. 문서 목적

이 문서는 Unitree Go2를 ROS2 환경에서 사용하기 위한 기본 세팅 절차를 정리한다.
초기 네트워크 설정부터 CycloneDDS, Unitree SDK, ROS2 패키지 빌드, SLAM 및 Navigation 실행까지 단계별로 관리한다.

## 2. 대상 환경

| 항목 | 내용 |
| --- | --- |
| 로봇 | Unitree Go2 |
| 호스트 OS | Ubuntu 22.04 LTS |
| ROS2 배포판 | Humble |
| DDS | CycloneDDS |
| 최종 목표 | Go2 기반 SLAM/Navigation 실행 |

## 3. 전체 진행 순서

1. 사전 준비
2. 네트워크 설정
3. CycloneDDS 설치 및 설정
4. Unitree SDK 설치 및 빌드
5. Go2 ROS2 패키지 설치 및 빌드
6. 로봇 연결 확인
7. 기본 제어 테스트
8. 센서 및 TF 확인
9. SLAM 실행
10. Navigation 실행
11. 트러블슈팅

## 4. 폴더 구조

```text
ktl/
├── config/
│   ├── cyclonedds/
│   ├── go2/
│   └── nav2/
├── docs/
│   ├── assets/
│   └── checklists/
├── launch/
├── maps/
├── rviz/
├── scripts/
└── logs/
```

| 경로 | 용도 |
| --- | --- |
| `config/cyclonedds/` | CycloneDDS XML 설정 파일 및 템플릿 |
| `config/go2/` | Go2 SDK, bringup, 로봇별 네트워크 설정 |
| `config/nav2/` | Nav2 파라미터 파일 |
| `docs/assets/` | 매뉴얼용 이미지, 캡처, 네트워크 구성도 |
| `docs/checklists/` | 현장 설치/테스트 체크리스트 |
| `launch/` | Go2 bringup, SLAM, Navigation 통합 launch 파일 |
| `maps/` | SLAM 결과 map 파일 |
| `rviz/` | RViz 설정 파일 |
| `scripts/` | 설치, 환경 설정, 실행 보조 스크립트 |
| `logs/` | 테스트 로그, 현장 이슈 기록 |

## 5. 사전 준비

### 5.1 필수 패키지

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  cmake \
  git \
  python3-catkin-pkg \
  python3-colcon-common-extensions \
  python3-pip \
  ros-humble-rosidl-generator-dds-idl
```

### 5.2 ROS2 환경 확인

```bash
source /opt/ros/humble/setup.bash
ros2 --version
```

### 5.3 워크스페이스 구조

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws
```

## 6. 네트워크 설정

### 6.1 연결 방식

- 유선 LAN
- Wi-Fi
- 로봇 내부 네트워크 직접 연결

### 6.2 IP 확인

```bash
ip addr
ping <GO2_IP>
```

### 6.3 체크리스트

- [ ] 호스트 PC와 Go2가 같은 네트워크 대역에 있는지 확인
- [ ] 로봇 IP 주소 확인
- [ ] 방화벽 또는 VPN으로 DDS 통신이 막히지 않는지 확인
- [ ] `ping` 응답 확인

## 7. CycloneDDS 설치 및 설정

상세 절차는 [Unitree Go2 CycloneDDS 셋업 매뉴얼](cyclonedds_go2_setup.md)을 기준으로 한다.

### 7.1 설치

```bash
sudo apt update
sudo apt install -y \
  ros-humble-rmw-cyclonedds-cpp \
  ros-humble-rosidl-generator-dds-idl \
  libyaml-cpp-dev
```

### 7.2 Go2 유선 네트워크 설정

Go2 유선 연결 기본값:

| 항목 | 값 |
| --- | --- |
| PC IP | `192.168.123.99/24` |
| Go2 IP | `192.168.123.161` |

인터페이스 이름 확인:

```bash
ip -o -4 addr show
```

PC 유선 NIC 설정:

```bash
./scripts/configure_go2_eth.bash enp3s0
```

`enp3s0`는 실제 Go2와 연결된 NIC 이름으로 바꾼다.

### 7.3 CycloneDDS 환경 변수 적용

반드시 `source`로 적용한다.

```bash
source scripts/setup_go2_cyclonedds.bash enp3s0
```

적용되는 값:

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file://<repo>/.runtime/cyclonedds/go2_<interface>.xml
```

### 7.4 설정 확인

```bash
echo $RMW_IMPLEMENTATION
echo $CYCLONEDDS_URI
ros2 doctor --report
```

### 7.5 Go2 topic 확인

```bash
ros2 daemon stop
ros2 daemon start
ros2 topic list
ros2 topic echo /sportmodestate
```

## 8. Unitree SDK 설치

### 8.1 소스 다운로드

```bash
cd ~/ros2_ws/src
git clone <UNITREE_SDK_REPOSITORY_URL>
```

### 8.2 빌드

ROS2 빌드는 conda 환경이 꺼진 터미널에서 진행한다.

```bash
conda deactivate
which python3
python3 -c "import sys; print(sys.executable)"
```

기대값은 `/usr/bin/python3`이다.

이미 conda Python으로 한 번 configure된 경우 `build/*/CMakeCache.txt`에 `/home/juno/anaconda3/bin/python3`가 남아 있을 수 있다.
그때는 affected package의 build cache를 지우고 다시 빌드한다.

```bash
cd ~/ros2_ws
rm -rf build/go2_description build/unitree_api build/unitree_go build/unitree_hg
colcon build --symlink-install --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
source install/setup.bash
```

### 8.3 확인 항목

- [ ] SDK 저장소 URL 확인
- [ ] ROS2 Humble 호환 브랜치 확인
- [ ] 빌드 에러 없음
- [ ] 실행 예제 또는 샘플 노드 확인

## 9. Go2 ROS2 패키지 설치

### 9.1 소스 다운로드

```bash
cd ~/ros2_ws/src
git clone <GO2_ROS2_REPOSITORY_URL>
```

### 9.2 의존성 설치

```bash
cd ~/ros2_ws
rosdep update
rosdep install --from-paths src --ignore-src -r -y
```

### 9.3 빌드

권장 빌드:

```bash
cd ~/ros2_ws
./src/ktl/scripts/build_go2_workspace.bash
source install/setup.bash
```

수동 빌드:

```bash
colcon build --symlink-install
source install/setup.bash
```

## 10. 로봇 연결 확인

### 10.1 토픽 확인

```bash
ros2 topic list
```

### 10.2 노드 확인

```bash
ros2 node list
```

### 10.3 데이터 확인

```bash
ros2 topic echo <TOPIC_NAME>
```

체크리스트:

- [ ] Go2 관련 노드가 보이는지 확인
- [ ] 상태 토픽이 수신되는지 확인
- [ ] 명령 토픽 publish 가능 여부 확인
- [ ] 통신 지연 또는 끊김 여부 확인

## 11. 기본 제어 테스트

주의: 제어 테스트 전 로봇 주변 안전 공간을 확보한다.

### 11.1 Stand Up / Stand Down

```bash
ros2 service call <SERVICE_NAME> <SERVICE_TYPE> "<REQUEST>"
```

### 11.2 속도 명령 테스트

```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.1}, angular: {z: 0.0}}" --once
```

확인 항목:

- [ ] 비상 정지 수단 준비
- [ ] 로봇 상태 정상
- [ ] 명령 토픽 이름 확인
- [ ] 실제 이동 방향 확인

## 12. 센서 및 TF 확인

### 12.1 TF 트리 확인

```bash
ros2 run tf2_tools view_frames
```

### 12.2 센서 토픽 확인

```bash
ros2 topic list
ros2 topic hz <SENSOR_TOPIC>
```

확인 항목:

- [ ] `base_link` 기준 프레임 확인
- [ ] LiDAR 또는 depth sensor 토픽 확인
- [ ] IMU 토픽 확인
- [ ] Odometry 토픽 확인
- [ ] RViz에서 TF와 센서 데이터 시각화 확인

## 13. SLAM 실행

### 13.1 SLAM 패키지 설치

```bash
sudo apt install -y ros-humble-slam-toolbox
```

### 13.2 실행 예시

```bash
ros2 launch slam_toolbox online_async_launch.py
```

### 13.3 RViz 확인

```bash
rviz2
```

확인 항목:

- [ ] `/scan` 또는 SLAM 입력 센서 토픽 확인
- [ ] `map -> odom -> base_link` TF 연결 확인
- [ ] 맵 생성 확인
- [ ] 맵 저장 확인

맵 저장 예시:

```bash
ros2 run nav2_map_server map_saver_cli -f maps/go2_map
```

## 14. Navigation 실행

### 14.1 Nav2 설치

```bash
sudo apt install -y ros-humble-navigation2 ros-humble-nav2-bringup
```

### 14.2 실행 예시

```bash
ros2 launch nav2_bringup navigation_launch.py use_sim_time:=false
```

### 14.3 확인 항목

- [ ] 저장된 맵 로드
- [ ] AMCL 또는 localization 노드 실행
- [ ] Costmap 정상 생성
- [ ] Goal pose 전송 가능
- [ ] 장애물 회피 확인
- [ ] 로봇 정지 및 복구 동작 확인

## 15. SLAMNav 통합 실행

최종 목표는 Go2 bringup, 센서, TF, SLAM 또는 Localization, Nav2를 하나의 절차로 실행하는 것이다.

### 15.1 실행 순서 초안

1. Go2 네트워크 연결
2. CycloneDDS 환경 변수 적용
3. Go2 bringup 실행
4. 센서 및 TF 확인
5. SLAM 또는 저장된 맵 기반 localization 실행
6. Nav2 실행
7. RViz에서 목표 지점 전송

### 15.2 통합 launch 후보

```bash
ros2 launch <GO2_SLAMNAV_PACKAGE> <LAUNCH_FILE>.launch.py
```

정리 필요 항목:

- [ ] 실제 패키지명
- [ ] 실제 launch 파일명
- [ ] 파라미터 파일 경로
- [ ] 맵 파일 경로
- [ ] RViz 설정 파일 경로

## 16. 트러블슈팅

| 증상 | 확인할 것 | 조치 |
| --- | --- | --- |
| ROS2 토픽이 안 보임 | DDS, 네트워크 인터페이스, 방화벽 | CycloneDDS 설정 및 IP 대역 확인 |
| `ping` 실패 | 네트워크 연결, 로봇 IP | 케이블/Wi-Fi/IP 설정 확인 |
| 빌드 실패 | 의존성, 브랜치, ROS2 버전 | `rosdep install` 재실행 및 호환 브랜치 확인 |
| `ModuleNotFoundError: No module named 'catkin_pkg'` | conda Python이 ROS2 빌드에 사용됨 또는 CMake cache에 남아 있음 | `conda deactivate`, `sudo apt install python3-catkin-pkg`, affected `build/<pkg>` 삭제 후 `-DPython3_EXECUTABLE=/usr/bin/python3`로 재빌드 |
| `Could not find rosidl_generator_dds_idl` | Unitree message IDL generator 의존성 미설치 | `sudo apt install ros-humble-rosidl-generator-dds-idl` 후 `rm -rf build install log` 재빌드 |
| TF 에러 | frame id, static transform | URDF/TF broadcaster 확인 |
| SLAM 맵이 흔들림 | odom, scan, TF timestamp | 센서 주기와 TF timestamp 확인 |
| Nav2가 움직이지 않음 | lifecycle, costmap, cmd_vel | Nav2 lifecycle 상태와 토픽 확인 |

## 17. 남은 작성 항목

- [ ] 실제 Go2 IP 및 네트워크 구성 기록
- [ ] Unitree SDK 공식 저장소 및 브랜치 확정
- [ ] Go2 ROS2 패키지 저장소 및 브랜치 확정
- [ ] 실제 토픽/서비스 이름 기록
- [ ] CycloneDDS 인터페이스 이름 예시 추가
- [ ] SLAM 파라미터 파일 추가
- [ ] Nav2 파라미터 파일 추가
- [ ] 통합 launch 파일 작성
- [ ] 현장 테스트 결과 기록
