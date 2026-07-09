# Unitree Go2 CycloneDDS 셋업 매뉴얼

## 1. 목적

이 문서는 Unitree Go2를 ROS2 Humble PC에서 CycloneDDS로 연결하기 위한 설정 절차를 정리한다.
Go2 유선 연결 기준으로 작성하며, 로컬 테스트용 설정도 함께 제공한다.

## 2. 기준 환경

| 항목 | 값 |
| --- | --- |
| 로봇 | Unitree Go2 |
| PC OS | Ubuntu 22.04 LTS |
| ROS2 | Humble |
| DDS/RMW | CycloneDDS / `rmw_cyclonedds_cpp` |
| PC 유선 IP | `192.168.123.99/24` |
| Go2 기본 IP | `192.168.123.161` |

Unitree 공식 ROS2 패키지는 Go2, B2, H1 통신을 CycloneDDS 기반으로 사용한다.
Humble 환경에서는 apt로 제공되는 `rmw_cyclonedds_cpp`를 우선 사용한다.

## 3. repo 파일 구성

```text
config/
├── cyclonedds/
│   ├── go2_eth.template.xml
│   └── go2_local.xml
└── go2/
    └── go2_network.env

scripts/
├── configure_go2_eth.bash
└── setup_go2_cyclonedds.bash
```

| 파일 | 역할 |
| --- | --- |
| `config/go2/go2_network.env` | Go2 기본 IP, PC IP, ROS distro 값 |
| `config/cyclonedds/go2_eth.template.xml` | 실제 NIC 이름을 주입해서 사용할 CycloneDDS XML 템플릿 |
| `config/cyclonedds/go2_local.xml` | 로봇 없이 local loopback 테스트용 XML |
| `scripts/configure_go2_eth.bash` | PC 유선 NIC를 Go2 대역 IP로 설정 |
| `scripts/setup_go2_cyclonedds.bash` | ROS2 환경, CycloneDDS XML, RMW 환경 변수 적용 |

## 4. 패키지 설치

```bash
sudo apt update
sudo apt install -y \
  ros-humble-rmw-cyclonedds-cpp \
  ros-humble-rosidl-generator-dds-idl \
  libyaml-cpp-dev
```

`unitree_go` 빌드에서 `Could not find rosidl_generator_dds_idl`가 나오면 위 패키지가 설치되지 않은 상태다.
설치 후 workspace를 clean build한다.

```bash
cd ~/ros2_ws
rm -rf build install log
colcon build --symlink-install --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
```

설치 확인:

```bash
ros2 doctor --report | grep -i rmw
```

## 5. Go2 유선 네트워크 설정

### 5.1 인터페이스 이름 확인

Go2와 PC를 Ethernet으로 연결한 뒤 인터페이스 이름을 확인한다.

```bash
ip -o -4 addr show
```

예시:

```text
enp3s0  192.168.123.99/24
```

### 5.2 기본 IP 값 확인

기본값은 [config/go2/go2_network.env](../config/go2/go2_network.env)에 들어 있다.

```bash
GO2_ROBOT_IP=192.168.123.161
GO2_HOST_IP=192.168.123.99
GO2_NETMASK_CIDR=24
ROS_DISTRO=humble
```

현장 로봇 IP가 다르면 이 파일을 수정한다.

### 5.3 PC 유선 NIC에 IP 부여

예시에서 `enp3s0`는 실제 인터페이스 이름으로 바꾼다.

```bash
./scripts/configure_go2_eth.bash enp3s0
```

내부에서 실행하는 핵심 설정:

```bash
sudo ip link set enp3s0 up
sudo ip addr flush dev enp3s0
sudo ip addr add 192.168.123.99/24 dev enp3s0
```

연결 확인:

```bash
ping 192.168.123.161
```

## 6. CycloneDDS 환경 적용

### 6.1 유선 Go2 연결

반드시 `source`로 적용한다.

```bash
source scripts/setup_go2_cyclonedds.bash enp3s0
```

인터페이스를 생략하면 스크립트가 `192.168.123.161`로 가는 route 또는 `192.168.123.x` 주소가 붙은 NIC를 탐색한다.

```bash
source scripts/setup_go2_cyclonedds.bash
```

적용 후 확인:

```bash
echo $RMW_IMPLEMENTATION
echo $CYCLONEDDS_URI
```

기대값:

```text
rmw_cyclonedds_cpp
file:///home/juno/ros2_ws/src/ktl/.runtime/cyclonedds/go2_enp3s0.xml
```

### 6.2 생성되는 CycloneDDS XML

스크립트는 [config/cyclonedds/go2_eth.template.xml](../config/cyclonedds/go2_eth.template.xml)의 `@NETWORK_INTERFACE@`에 실제 NIC 이름을 넣어 `.runtime/cyclonedds/` 아래 XML을 생성한다.

생성 예시:

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<CycloneDDS>
  <Domain id="any">
    <General>
      <Interfaces>
        <NetworkInterface name="enp3s0" priority="default" multicast="default" />
      </Interfaces>
      <AllowMulticast>true</AllowMulticast>
    </General>
  </Domain>
</CycloneDDS>
```

### 6.3 로컬 테스트

로봇 없이 ROS2 노드 간 통신만 확인할 때는 loopback 설정을 쓴다.

```bash
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file://$PWD/config/cyclonedds/go2_local.xml
```

터미널 1:

```bash
ros2 topic pub /ktl_cyclonedds_test std_msgs/msg/String "{data: hello_go2_dds}"
```

터미널 2:

```bash
ros2 topic echo /ktl_cyclonedds_test
```

## 7. Go2 ROS2 통신 확인

환경 적용 후 topic discovery를 확인한다.

```bash
source scripts/setup_go2_cyclonedds.bash enp3s0
ros2 daemon stop
ros2 daemon start
ros2 topic list
```

Unitree ROS2 예제에서 자주 확인하는 상태 토픽:

```bash
ros2 topic echo /sportmodestate
ros2 topic echo /lf/sportmodestate
ros2 topic echo /lowstate
ros2 topic echo /lf/lowstate
```

로봇/펌웨어/패키지 구성에 따라 topic namespace가 다를 수 있으므로 `ros2 topic list`를 먼저 확인한다.

## 8. Unitree ROS2 패키지와 함께 사용

Unitree 공식 ROS2 패키지를 `~/unitree_ros2`에 둔 경우 `setup_go2_cyclonedds.bash`가 아래 setup 파일을 자동으로 source한다.

```bash
~/unitree_ros2/cyclonedds_ws/install/setup.bash
```

다른 위치를 쓰는 경우:

```bash
export GO2_EXTRA_SETUP=/path/to/install/setup.bash
source scripts/setup_go2_cyclonedds.bash enp3s0
```

예제 실행 흐름:

```bash
cd ~/unitree_ros2/example
colcon build
source /home/juno/ros2_ws/src/ktl/scripts/setup_go2_cyclonedds.bash enp3s0
./install/unitree_ros2_example/bin/read_motion_state
```

## 9. 자동 적용 옵션

매 터미널마다 수동 적용하기 싫으면 `~/.bashrc`에 추가할 수 있다.
다만 여러 ROS2 프로젝트를 함께 쓰는 PC에서는 프로젝트별로 명시적으로 `source`하는 방식을 권장한다.

```bash
echo 'source /home/juno/ros2_ws/src/ktl/scripts/setup_go2_cyclonedds.bash enp3s0' >> ~/.bashrc
```

## 10. 트러블슈팅

| 증상 | 확인 | 조치 |
| --- | --- | --- |
| `ping` 실패 | IP 대역, 케이블, NIC 이름 | `configure_go2_eth.bash` 재실행, 케이블 재연결 |
| topic이 안 보임 | `RMW_IMPLEMENTATION`, `CYCLONEDDS_URI` | `source scripts/setup_go2_cyclonedds.bash <iface>` 재실행 |
| 일부 topic만 보임 | Wi-Fi/VPN/방화벽, multicast | VPN 해제, 유선 연결 우선 사용, 방화벽 확인 |
| XML parse warning | XML 경로, generated XML 내용 | `echo $CYCLONEDDS_URI` 후 파일 내용 확인 |
| 다른 ROS 환경과 충돌 | `.bashrc`, overlay workspace | 새 터미널에서 필요한 setup만 source |

## 11. 참고 자료

- Unitree ROS2 공식 저장소: https://github.com/unitreerobotics/unitree_ros2
- Unitree ROS2 Service 문서: https://support.unitree.com/home/en/developer/ROS2_service
- ROS2 RMW 구현체 문서: https://docs.ros.org/en/humble/How-To-Guides/Working-with-multiple-RMW-implementations.html
