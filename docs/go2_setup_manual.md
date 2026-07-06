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

## 4. 사전 준비

### 4.1 필수 패키지

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  cmake \
  git \
  python3-colcon-common-extensions \
  python3-pip
```

### 4.2 ROS2 환경 확인

```bash
source /opt/ros/humble/setup.bash
ros2 --version
```

### 4.3 워크스페이스 구조

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws
```

## 5. 네트워크 설정

### 5.1 연결 방식

- 유선 LAN
- Wi-Fi
- 로봇 내부 네트워크 직접 연결

### 5.2 IP 확인

```bash
ip addr
ping <GO2_IP>
```

### 5.3 체크리스트

- [ ] 호스트 PC와 Go2가 같은 네트워크 대역에 있는지 확인
- [ ] 로봇 IP 주소 확인
- [ ] 방화벽 또는 VPN으로 DDS 통신이 막히지 않는지 확인
- [ ] `ping` 응답 확인

## 6. CycloneDDS 설치 및 설정

### 6.1 설치

```bash
sudo apt install -y ros-humble-rmw-cyclonedds-cpp
```

### 6.2 환경 변수 설정

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

`~/.bashrc`에 추가:

```bash
echo 'export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp' >> ~/.bashrc
```

### 6.3 CycloneDDS 설정 파일

파일 위치 예시:

```bash
mkdir -p ~/.ros
nano ~/.ros/cyclonedds.xml
```

설정 템플릿:

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<CycloneDDS>
  <Domain>
    <General>
      <Interfaces>
        <NetworkInterface name="<NETWORK_INTERFACE_NAME>" priority="default" multicast="default" />
      </Interfaces>
      <AllowMulticast>true</AllowMulticast>
    </General>
  </Domain>
</CycloneDDS>
```

환경 변수 추가:

```bash
export CYCLONEDDS_URI=file://$HOME/.ros/cyclonedds.xml
echo 'export CYCLONEDDS_URI=file://$HOME/.ros/cyclonedds.xml' >> ~/.bashrc
```

### 6.4 확인

```bash
ros2 doctor --report
```

## 7. Unitree SDK 설치

### 7.1 소스 다운로드

```bash
cd ~/ros2_ws/src
git clone <UNITREE_SDK_REPOSITORY_URL>
```

### 7.2 빌드

```bash
cd ~/ros2_ws
colcon build --symlink-install
source install/setup.bash
```

### 7.3 확인 항목

- [ ] SDK 저장소 URL 확인
- [ ] ROS2 Humble 호환 브랜치 확인
- [ ] 빌드 에러 없음
- [ ] 실행 예제 또는 샘플 노드 확인

## 8. Go2 ROS2 패키지 설치

### 8.1 소스 다운로드

```bash
cd ~/ros2_ws/src
git clone <GO2_ROS2_REPOSITORY_URL>
```

### 8.2 의존성 설치

```bash
cd ~/ros2_ws
rosdep update
rosdep install --from-paths src --ignore-src -r -y
```

### 8.3 빌드

```bash
colcon build --symlink-install
source install/setup.bash
```

## 9. 로봇 연결 확인

### 9.1 토픽 확인

```bash
ros2 topic list
```

### 9.2 노드 확인

```bash
ros2 node list
```

### 9.3 데이터 확인

```bash
ros2 topic echo <TOPIC_NAME>
```

체크리스트:

- [ ] Go2 관련 노드가 보이는지 확인
- [ ] 상태 토픽이 수신되는지 확인
- [ ] 명령 토픽 publish 가능 여부 확인
- [ ] 통신 지연 또는 끊김 여부 확인

## 10. 기본 제어 테스트

주의: 제어 테스트 전 로봇 주변 안전 공간을 확보한다.

### 10.1 Stand Up / Stand Down

```bash
ros2 service call <SERVICE_NAME> <SERVICE_TYPE> "<REQUEST>"
```

### 10.2 속도 명령 테스트

```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.1}, angular: {z: 0.0}}" --once
```

확인 항목:

- [ ] 비상 정지 수단 준비
- [ ] 로봇 상태 정상
- [ ] 명령 토픽 이름 확인
- [ ] 실제 이동 방향 확인

## 11. 센서 및 TF 확인

### 11.1 TF 트리 확인

```bash
ros2 run tf2_tools view_frames
```

### 11.2 센서 토픽 확인

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

## 12. SLAM 실행

### 12.1 SLAM 패키지 설치

```bash
sudo apt install -y ros-humble-slam-toolbox
```

### 12.2 실행 예시

```bash
ros2 launch slam_toolbox online_async_launch.py
```

### 12.3 RViz 확인

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

## 13. Navigation 실행

### 13.1 Nav2 설치

```bash
sudo apt install -y ros-humble-navigation2 ros-humble-nav2-bringup
```

### 13.2 실행 예시

```bash
ros2 launch nav2_bringup navigation_launch.py use_sim_time:=false
```

### 13.3 확인 항목

- [ ] 저장된 맵 로드
- [ ] AMCL 또는 localization 노드 실행
- [ ] Costmap 정상 생성
- [ ] Goal pose 전송 가능
- [ ] 장애물 회피 확인
- [ ] 로봇 정지 및 복구 동작 확인

## 14. SLAMNav 통합 실행

최종 목표는 Go2 bringup, 센서, TF, SLAM 또는 Localization, Nav2를 하나의 절차로 실행하는 것이다.

### 14.1 실행 순서 초안

1. Go2 네트워크 연결
2. CycloneDDS 환경 변수 적용
3. Go2 bringup 실행
4. 센서 및 TF 확인
5. SLAM 또는 저장된 맵 기반 localization 실행
6. Nav2 실행
7. RViz에서 목표 지점 전송

### 14.2 통합 launch 후보

```bash
ros2 launch <GO2_SLAMNAV_PACKAGE> <LAUNCH_FILE>.launch.py
```

정리 필요 항목:

- [ ] 실제 패키지명
- [ ] 실제 launch 파일명
- [ ] 파라미터 파일 경로
- [ ] 맵 파일 경로
- [ ] RViz 설정 파일 경로

## 15. 트러블슈팅

| 증상 | 확인할 것 | 조치 |
| --- | --- | --- |
| ROS2 토픽이 안 보임 | DDS, 네트워크 인터페이스, 방화벽 | CycloneDDS 설정 및 IP 대역 확인 |
| `ping` 실패 | 네트워크 연결, 로봇 IP | 케이블/Wi-Fi/IP 설정 확인 |
| 빌드 실패 | 의존성, 브랜치, ROS2 버전 | `rosdep install` 재실행 및 호환 브랜치 확인 |
| TF 에러 | frame id, static transform | URDF/TF broadcaster 확인 |
| SLAM 맵이 흔들림 | odom, scan, TF timestamp | 센서 주기와 TF timestamp 확인 |
| Nav2가 움직이지 않음 | lifecycle, costmap, cmd_vel | Nav2 lifecycle 상태와 토픽 확인 |

## 16. 남은 작성 항목

- [ ] 실제 Go2 IP 및 네트워크 구성 기록
- [ ] Unitree SDK 공식 저장소 및 브랜치 확정
- [ ] Go2 ROS2 패키지 저장소 및 브랜치 확정
- [ ] 실제 토픽/서비스 이름 기록
- [ ] CycloneDDS 인터페이스 이름 예시 추가
- [ ] SLAM 파라미터 파일 추가
- [ ] Nav2 파라미터 파일 추가
- [ ] 통합 launch 파일 작성
- [ ] 현장 테스트 결과 기록
