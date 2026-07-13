# 1. 시스템 개요와 통신 구조

이 문서는 Go2, Hesai XT16, Jetson Orin으로 구성된 ROS 2 시스템의 구조와 기본 점검 방법을 설명한다. 실습 전에는 [명령어 모음](cmd_manuals.md)의 네트워크 확인부터 수행한다.

## 시스템 구성

```text
Go2 모션 컨트롤러 ── Unitree DDS ─┐
Go2 확장 컴퓨터                   ├─ eno1 유선망 ─ Jetson Orin (ROS 2)
Hesai XT16 ─────────── UDP ───────┘                    │
                                                       ├─ SLAM Toolbox
                                                       ├─ Nav2
                                                       └─ RViz 2
```

| 구성요소 | 역할 |
|---|---|
| Go2 | 보행 제어와 로봇 상태 제공 |
| Jetson Orin | ROS 2 노드, 센서 처리, SLAM, Navigation 실행 |
| Hesai XT16 | 3D 포인트클라우드 전송 |
| RViz 2 | TF, 센서, 지도, 경로 시각화 |

## 네트워크

모든 장치는 Jetson의 `eno1` 유선 인터페이스를 사용한다.

| 장치 | IP | 용도 |
|---|---|---|
| Jetson ROS 호스트 | `192.168.123.222/24` | ROS 2와 LiDAR 수신 |
| Go2 모션 컨트롤러 | `192.168.123.161` | Unitree 보행 제어 |
| Go2 확장 컴퓨터 | `192.168.123.18` | Go2 보조 컴퓨터 |
| Hesai XT16 | `192.168.123.20` | LiDAR |

Hesai는 UDP `2368`으로 포인트를 보내고 PTC는 `9347` 포트를 사용한다. 로봇이나 LiDAR가 꺼져 있으면 ROS 2 에러를 먼저 해석하지 말고 전원, 케이블, IP를 확인한다.

```bash
ip link show eno1
ping -c 3 192.168.123.20   # Hesai
ping -c 3 192.168.123.161 # Go2
```

## ROS 2, DDS, CycloneDDS

ROS 2 노드는 토픽·서비스·액션으로 데이터를 주고받는다. 실제 발견과 전송은 DDS가 담당하며, 이 시스템은 `rmw_cyclonedds_cpp`를 사용한다.

| 계층 | 역할 |
|---|---|
| ROS 2 | 노드, 토픽, 서비스, 액션 인터페이스 |
| RMW | ROS 2와 DDS 구현을 연결 |
| CycloneDDS | 노드 발견과 실제 네트워크 전송 |

Bringup의 `network_interface:=eno1`은 CycloneDDS가 유선망만 사용하도록 제한한다. Wi-Fi·VPN·Docker 인터페이스를 잘못 선택하는 문제를 예방한다.

```bash
ros2 launch go2_base go2_bringup.launch.py \
  network_interface:=eno1 rviz:=false
```

### DDS 설정 확인과 직접 실행

평소에는 launch가 `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`와 `CYCLONEDDS_URI`를 자동 설정하므로 별도 설정 파일을 수정할 필요가 없다. 단독 노드 시험이나 통신 문제 분석 시에는 현재 환경을 확인한다.

```bash
printenv RMW_IMPLEMENTATION
printenv CYCLONEDDS_URI
ip link show eno1
```

직접 실행해야 할 때의 최소 설정 예시다.

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="eno1" priority="default" multicast="default" /></Interfaces></General></Domain></CycloneDDS>'
```

이 설정은 현재 터미널에만 적용된다. 인터페이스 이름이 틀렸거나 링크가 내려가 있으면 Unitree DDS를 구독하는 노드가 데이터를 받지 못한다.

## Unitree와 ROS 2의 연결

`go2_state_bridge`는 Unitree DDS 상태를 표준 ROS 2 메시지로 변환한다. `go2_cmd_vel_bridge`는 ROS 2 속도 명령을 Unitree 제어 요청으로 변환한다.

```text
Unitree DDS 상태                         ROS 2 상태
/lf/sportmodestate, /lowstate ──→ go2_state_bridge ──→ /go2/odom, /go2/imu
                                                        /joint_states, /go2/battery_state

ROS 2 제어                              Unitree 제어
/cmd_vel ──→ go2_cmd_vel_bridge ──→ /api/sport/request 또는 /lowcmd
```

`/cmd_vel`은 표준 `geometry_msgs/msg/Twist` 토픽이다. 제어 브리지는 기본적으로 명령이 약 0.5초 동안 끊기면 정지 명령을 보낸다.

### 실행 모드와 odom 기준점

같은 `go2_bringup.launch.py`라도 어떤 launch에서 포함하느냐에 따라 제어와 odom의 사용 목적이 달라진다.

| 실행 방식 | 제어 브리지 | `rebase_odom_on_start` | 사용 목적 |
|---|---|---:|---|
| 단독 bringup | 기본 `true` | 기본 `false` | 센서·상태·수동 제어 점검 |
| Mapping launch | 기본 `false` | `true` | 매핑 시작 위치를 odom 원점으로 사용 |
| Navigation launch | 기본 `true` | 기본 `false` | AMCL이 기존 map 기준 위치를 보정 |

`rebase_odom_on_start:=true`이면 첫 Go2 Sport 상태의 위치와 yaw를 원점으로 삼아 이후 `/go2/odom`을 발행한다. 그래서 매핑을 새로 시작할 때는 작은 좌표에서 지도를 만들 수 있다. 반면 저장된 지도로 주행할 때는 AMCL이 `map → odom`을 추정하므로, Navigation에서 매번 odom을 다시 기준화할 필요가 없다.

Navigation launch는 현재 Go2 bringup의 기본값을 그대로 사용하므로 제어 브리지가 활성화된다. 실로봇 시험 전에는 주변을 비우고 `/cmd_vel`이 어떤 노드에서 발행되는지 확인한다.

## 좌표계와 URDF

```text
map → odom → base_link → hesai_lidar
```

| TF | 발행 주체 | 의미 |
|---|---|---|
| `map → odom` | SLAM Toolbox 또는 AMCL | 지도 기준 위치 보정 |
| `odom → base_link` | `go2_state_bridge` | Go2 주행 추정 |
| `base_link → hesai_lidar` | URDF / robot_state_publisher | LiDAR 장착 위치와 방향 |

LiDAR의 물리적 위치나 방향은 [go2_description.urdf](../../go2_driver/go2_description/urdf/go2_description.urdf)에서 관리한다. LaserScan에 포함할 높이 범위는 [go2_pointcloud_to_laserscan.yaml](../config/laser_scan/go2_pointcloud_to_laserscan.yaml)에서 관리한다.

## 핵심 노드와 토픽

| 노드 | 역할 |
|---|---|
| `go2_state_bridge` | Go2 상태, odom, IMU, 배터리 발행 |
| `go2_cmd_vel_bridge` | `/cmd_vel`을 Go2 명령으로 변환 |
| `hesai_ros_driver_node` | Hesai UDP를 PointCloud2로 변환 |
| `pointcloud_to_laserscan_node` | PointCloud2를 2D LaserScan으로 변환 |
| `slam_toolbox` | 지도 생성과 pose graph 관리 |
| Nav2 | 위치 추정, 경로 계획, 장애물 회피, 속도 제어 |

| 토픽 | 용도 |
|---|---|
| `/go2/odom` | 로봇 위치·속도 추정 |
| `/go2/imu` | Go2 IMU 상태 |
| `/go2/battery_state` | 배터리 상태 |
| `/hesai/lidar_points` | Hesai 3D 포인트클라우드 |
| `/scan` | SLAM·Nav2가 사용하는 2D LaserScan |
| `/cmd_vel` | 로봇 속도 명령 |
| `/map`, `/plan` | 지도와 전역 경로 |

```bash
ros2 topic info /go2/odom
ros2 topic echo /go2/battery_state --once
ros2 topic hz /hesai/lidar_points
ros2 node list
```

### 상태 점검 순서

문제가 생겼을 때는 토픽을 무작정 많이 보기보다 데이터 흐름 순서대로 확인한다.

| 순서 | 확인 대상 | 정상 판단 |
|---:|---|---|
| 1 | `eno1`, Go2·Hesai ping | 링크가 있고 각 장치가 응답 |
| 2 | `/go2/odom`, `/go2/imu` | 상태가 계속 발행되고 값이 갱신 |
| 3 | `/hesai/lidar_points` | PointCloud 주기가 유지 |
| 4 | `/scan` | `frame_id`, 거리값, timestamp가 유효 |
| 5 | TF | `odom → base_link`, `base_link → hesai_lidar` 존재 |
| 6 | `/map` 또는 `/amcl_pose` | 매핑·위치추정 상태가 갱신 |

`/go2/battery_state`는 `voltage`(V), `current`(A), `soc`(0~100%), `is_charging` 필드를 제공한다. 이 토픽은 Unitree LowState를 그대로 쓰는 것이 아니라 상태 브리지가 ROS 메시지로 변환한 결과다.

## 저장소와 설정 파일

```text
src/
├─ go2_driver/
│  ├─ go2_base/          Go2 상태·제어 브리지와 bringup
│  └─ go2_description/   URDF, TF, RViz 설정
├─ hesai_lidar/          Hesai XT16 드라이버 소스
├─ ktl/
│  ├─ config/            LiDAR, SLAM, Nav2 설정
│  ├─ launch/            매핑·내비게이션 launch
│  ├─ maps/              지도와 pose graph
│  └─ labs/              교육 자료
└─ unitree_ros2/         Unitree DDS 메시지·SDK
```

`hesai_lidar`는 소스 폴더명이다. 실제 ROS 패키지와 실행 파일 이름은 다음과 같다.

```text
패키지: hesai_ros_driver
실행 파일: hesai_ros_driver_node
```

실제 LiDAR 설정은 [config.yaml](../../hesai_lidar/config/config.yaml)에서 확인한다. 현재는 `source_type: 1`의 실시간 UDP 모드이며, PointCloud 토픽은 `/hesai/lidar_points`다.

XT16에서는 `firetimes_path`도 확인한다. 이 파일은 채널별 발사 시점 보정에 사용되며, 경로가 틀리면 드라이버가 보정 파일 오류를 내거나 포인트 시간 보정이 기대와 다르게 동작할 수 있다. `correction_file_path`는 PTC 연결로 장치 보정을 받는 현재 구성에서는 비어 있을 수 있다.

## 설치·빌드·장비 정보

주요 ROS 의존성은 `ros-humble-desktop`, `ros-humble-rmw-cyclonedds-cpp`, `ros-humble-slam-toolbox`, `ros-humble-navigation2`, `ros-humble-nav2-bringup`, `ros-humble-pointcloud-to-laserscan`이다. Hesai GPU 빌드에는 CUDA 12.6과 Orin용 아키텍처 `87`이 필요하다.

새 Jetson에서 동일한 실습 환경을 준비할 때의 핵심 의존성 설치 명령은 다음과 같다.

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

```bash
cd ~/ktl_ws
colcon build --packages-select hesai_ros_driver --symlink-install \
  --cmake-clean-cache \
  --cmake-args -DFIND_CUDA=ON \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda-12.6/bin/nvcc \
  -DCMAKE_CUDA_ARCHITECTURES=87
colcon build --symlink-install --packages-skip hesai_ros_driver
source install/setup.bash
```

Jetson은 50W 전력 모드를 권장한다. 이미지마다 모드 번호가 다르므로 먼저 확인한 후 설정한다.

```bash
sudo nvpmodel -q
sudo nvpmodel -m <50W_모드번호>
```

## Credentials
- id : ktl
- password : ktl1234

### 설정 변경의 적용 범위

| 변경 대상 | 적용 방법 |
|---|---|
| `ktl/config/*.yaml` | 실행 중인 launch를 종료하고 다시 실행 |
| launch Python 파일 | launch를 종료하고 다시 실행. 설치 공간이 symlink가 아니면 재빌드 필요 |
| C++ 브리지·드라이버 코드 | 해당 패키지 재빌드 후 `source ~/ktl_ws/install/setup.bash` |
| URDF | robot_state_publisher를 포함한 bringup 재실행 |

현재 워크스페이스는 `--symlink-install` 빌드를 권장한다. 그래도 실행 중인 노드는 파일 변경을 자동으로 읽지 않으므로, 설정값을 바꾼 뒤에는 반드시 해당 launch를 재시작한다.
