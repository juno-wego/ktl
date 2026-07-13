# 1. Go2 시스템 이해하기

이 문서는 현재 장비를 처음 다루는 사람이 **전원과 네트워크를 확인하고, ROS 2 노드와 토픽이 어떻게 연결되는지 이해하는 것**을 목표로 한다.

## 1.1 전체 구성

현재 시스템은 다음 네 부분으로 나뉜다.

```text
Unitree Go2 본체
  ├─ Go2 모션 컨트롤러 ── Unitree DDS ──┐
  └─ Go2 확장 컴퓨터                     ├─ 유선 네트워크(eno1)
                                         │
Jetson Orin(ROS 2) ── CycloneDDS ────────┘
       └─ Hesai XT16 ── UDP PointCloud2
```

- **Go2**: 보행, 자세, 관절, 배터리 상태를 생성하고 속도 명령을 실행한다.
- **Jetson Orin**: ROS 2, Go2 브리지, Hesai 드라이버, SLAM, Nav2를 실행한다.
- **Hesai XT16**: UDP로 3D 포인트를 Jetson에 전송한다.
- **RViz 2**: 센서·TF·지도·경로를 시각화한다.

이 시스템에서 ROS 2는 장치 자체가 아니라, 여러 프로그램을 토픽과 서비스로 연결하는 통신 계층이다.

## 1.2 네트워크 주소

| 장치 | 주소 | 역할 |
|---|---|---|
| Jetson ROS 호스트 | `192.168.123.222/24` | ROS 2, Hesai 수신, SLAM/Nav2 |
| Go2 모션 컨트롤러 | `192.168.123.161` | Unitree 보행 제어 |
| Go2 확장 Jetson | `192.168.123.18` | Go2 보조 컴퓨터 |
| Hesai XT16 | `192.168.123.20` | LiDAR 장치 |

모든 장비는 Jetson의 `eno1` 유선 인터페이스를 기준으로 연결한다.

```bash
ip addr show eno1
ping -c 3 192.168.123.20   # Hesai
ping -c 3 192.168.123.161 # Go2 모션 컨트롤러
```

Hesai의 기본 통신은 다음과 같다.

- UDP 데이터: Hesai → Jetson `192.168.123.222:2368`
- PTC 설정 통신: Hesai `192.168.123.20:9347`
- 웹 설정 화면: `http://192.168.123.20`

`eno1`에 링크가 없거나 로봇이 꺼져 있으면 CycloneDDS 노드가 종료될 수 있다. 이때는 ROS 2 에러보다 먼저 전원, 케이블, IP를 확인한다.

## 1.3 ROS 2와 DDS

ROS 2의 `publish/subscribe`는 내부적으로 DDS(Data Distribution Service)를 사용한다. 노드는 토픽 이름만 알고 서로의 IP를 직접 관리하지 않으며, DDS가 참여자 발견과 데이터 전달을 담당한다.

현재는 `rmw_cyclonedds_cpp`를 사용한다.

- **ROS 2**: 노드, 토픽, 서비스, 액션을 제공하는 응용 계층
- **RMW**: ROS 2와 DDS를 연결하는 어댑터
- **CycloneDDS**: 실제 DDS 발견·전송을 담당하는 구현체
- **`CYCLONEDDS_URI`**: DDS가 사용할 네트워크 인터페이스를 지정하는 설정

Bringup에서 `network_interface:=eno1`을 주면 다음과 같이 CycloneDDS를 설정한다.

```bash
ros2 launch go2_base go2_bringup.launch.py network_interface:=eno1 rviz:=false
```

여러 네트워크가 연결된 환경에서 `eno1`을 명시하는 이유는 DDS가 Wi-Fi나 가상 인터페이스를 통해 잘못된 네트워크를 선택하지 않도록 하기 위해서다.

## 1.4 Unitree 통신과 ROS 2 통신의 경계

Unitree 쪽 데이터는 Unitree가 정의한 DDS 메시지로 들어온다. `go2_state_bridge`가 이 데이터를 받아 표준 ROS 2 메시지로 변환한다.

```text
/lf/sportmodestate ─┐
/lowstate           ├─ go2_state_bridge ─→ /go2/odom
Unitree DDS         │                    ├→ /go2/imu
                    │                    ├→ /joint_states
                    │                    └→ /go2/battery_state
```

반대로 이동 명령은 다음 경로를 따른다.

```text
Nav2/DWB ─→ /cmd_vel (geometry_msgs/Twist)
              └─ go2_cmd_vel_bridge
                    └─ /api/sport/request 또는 /lowcmd
                         └─ Unitree Go2
```

즉 `/cmd_vel`은 ROS 2 표준 속도 명령이고, `/api/sport/request`와 `/lowcmd`는 Go2 쪽 제어 인터페이스다. `go2_cmd_vel_bridge`는 명령 주기와 timeout을 관리하며, 기본 timeout은 0.5초이고 시간이 지나면 정지 명령을 보낸다.

## 1.5 주요 노드 구조

```text
go2_bringup.launch.py
├─ robot_state_publisher       URDF로 link 간 TF 발행
├─ go2_state_bridge             Unitree 상태 → ROS 2 상태/odom/imu
├─ go2_cmd_vel_bridge           ROS 2 cmd_vel → Unitree 속도 명령
├─ hesai_ros_driver_node        Hesai UDP → PointCloud2
└─ rviz2                       시각화(선택)
```

SLAM을 실행하면 여기에 다음 노드가 추가된다.

```text
pointcloud_to_laserscan_node    PointCloud2 → LaserScan
restamp_laserscan.py             scan timestamp 보정(매핑 launch에서 사용)
slam_toolbox                     LaserScan + odom/TF → map
```

Nav2를 실행하면 AMCL, map server, planner server, controller server, costmap 등이 추가된다.

## 1.6 URDF와 TF

URDF는 로봇의 링크, 관절, 센서 위치와 좌표계 관계를 표현한다. 관련 파일은 다음과 같다.

- `go2_driver/go2_description/urdf/go2_description.urdf`: 로봇 링크·센서 위치
- `go2_driver/go2_description/launch/`: `robot_state_publisher`, RViz 관련 실행
- `go2_driver/go2_base/src/go2_state_bridge.cpp`: `odom → base_link` 동적 TF

현재 주요 TF 흐름은 다음과 같다.

```text
map → odom → base_link → ... → hesai_lidar
```

- `map → odom`: SLAM Toolbox 또는 AMCL
- `odom → base_link`: Go2 상태 브리지
- `base_link → hesai_lidar`: URDF/robot_state_publisher

센서 높이나 방향을 바꾸려면 PointCloud 설정이 아니라 먼저 URDF의 Hesai 고정 관절과 TF를 확인한다. LaserScan의 높이 필터는 `ktl/config/laser_scan/go2_pointcloud_to_laserscan.yaml`에서 별도로 결정한다.

## 1.7 주요 토픽 분류

### Unitree 입력 토픽

| 토픽 | 의미 |
|---|---|
| `/lf/sportmodestate` | 보행·자세·속도 등 Sport 상태 |
| `/lowstate` | 관절, IMU, 배터리 등 저수준 상태 |

### ROS 2로 변환된 Go2 상태

| 토픽 | 타입/의미 |
|---|---|
| `/go2/odom` | `nav_msgs/Odometry`, 주행 추정 위치·속도 |
| `/go2/imu` | `sensor_msgs/Imu`, Go2 IMU |
| `/joint_states` | 관절 상태 |
| `/go2/foot_force` | 발 접촉/힘 상태 |
| `/go2/battery_state` | 배터리 상태 |
| `/go2/sport_state` | ROS 2로 변환된 Sport 상태 |

### 센서·내비게이션 토픽

| 토픽 | 의미 |
|---|---|
| `/hesai/lidar_points` | Hesai 원본 3D `PointCloud2` |
| `/hesai/scan_raw` | 매핑 중 PointCloud를 투영한 원본 LaserScan |
| `/scan` | SLAM/Nav2가 사용하는 LaserScan |
| `/cmd_vel` | ROS 2 표준 이동 명령 |
| `/map` | 현재 지도 |
| `/plan` | 전역 경로 |
| `/local_plan` | 로컬 제어기가 선택한 경로 |
| `/local_costmap/costmap` | 주변 장애물 비용 지도 |
| `/global_costmap/costmap` | 전체 지도 기반 비용 지도 |

토픽의 실제 타입과 주기는 다음 명령으로 확인한다.

```bash
ros2 topic info /go2/odom
ros2 topic echo /go2/battery_state --once
ros2 topic hz /hesai/lidar_points
ros2 node list
```

## 1.8 전원과 상태 확인

교육용 장비에서는 Jetson 전력 모드를 **50W로 설정하는 것을 권장**한다. JetPack 이미지마다 `nvpmodel` 모드 번호가 다를 수 있으므로 먼저 현재 모드를 확인한다.

```bash
sudo nvpmodel -q
# 장비 이미지에서 50W에 해당하는 모드 번호를 확인한 뒤
sudo nvpmodel -m <50W_모드번호>
```

ROS 2 상태 확인:

```bash
ros2 topic echo /go2/battery_state --once
ros2 topic echo /go2/sport_state --once
ros2 topic echo /go2/odom --once
ros2 topic hz /go2/odom
```

로봇이 꺼진 상태에서 실행하면 상태 토픽이 나오지 않는 것이 정상이다. 장시간 `WARN`만 쌓이거나 노드가 종료되면 `ip link show eno1`, ping, Go2 전원을 순서대로 확인한다.

## 1.9 저장소 구조와 패키지

```text
src/
├─ go2_driver/
│  ├─ go2_base/          상태·제어 브리지와 bringup
│  ├─ go2_description/   URDF, TF, RViz
│  └─ go2_interface/     Go2 관련 ROS 메시지
├─ hesai_lidar/          Hesai XT16 드라이버 소스
├─ ktl/                  SLAM/Nav2 설정, launch, map
├─ unitree_ros2/         Unitree 메시지·DDS 관련 원본
└─ labs/                 이 교육 자료
```

주의할 점은 `hesai_lidar`가 소스 디렉터리 이름이고 실제 ROS 패키지 이름과 실행 이름은 각각 다음이라는 것이다.

```text
패키지: hesai_ros_driver
실행 파일: hesai_ros_driver_node
```

설정 파일은 `hesai_lidar/config/config.yaml`을 사용한다. 실제 라이다 모드에서는 UDP `source_type: 1`, Hesai 주소 `192.168.123.20`, 수신 포트 `2368`을 확인한다.

## 1.10 설치 패키지와 빌드

주요 의존 패키지:

```bash
sudo apt update
sudo apt install -y \
  build-essential cmake git ros-dev-tools \
  python3-colcon-common-extensions python3-rosdep \
  ros-humble-desktop ros-humble-rmw-cyclonedds-cpp \
  ros-humble-rosidl-generator-dds-idl \
  ros-humble-slam-toolbox ros-humble-navigation2 \
  ros-humble-nav2-bringup ros-humble-pointcloud-to-laserscan \
  libyaml-cpp-dev libboost-thread-dev libssl-dev libpcl-dev \
  cuda-nvcc-12-6
```

CUDA가 필요한 Hesai 드라이버는 먼저 별도로 빌드한다. 현재 패키지 이름에 맞춰 `hesai_ros_driver`를 선택한다.

```bash
source /opt/ros/humble/setup.bash
cd ~/ktl_ws
colcon build --packages-select hesai_ros_driver --symlink-install \
  --cmake-clean-cache \
  --cmake-args -DFIND_CUDA=ON \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda-12.6/bin/nvcc \
  -DCMAKE_CUDA_ARCHITECTURES=87
source install/setup.bash
```

그 다음 나머지를 빌드한다.

```bash
colcon build --symlink-install --packages-skip hesai_ros_driver
source install/setup.bash
```

빌드가 되었는지 확인:

```bash
ros2 pkg prefix go2_base
ros2 pkg prefix hesai_ros_driver
ros2 pkg executables go2_base
ros2 pkg executables hesai_ros_driver
```

## 1.11 장비 계정

교육용 장비 기준 계정 정보:

```text
id: ktl
pw: ktl1234
```

실제 운영 장비나 외부에 공유되는 문서에서는 반드시 비밀번호를 변경하거나 이 부분을 제거한다.
