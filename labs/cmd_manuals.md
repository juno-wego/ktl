# 실습 명령어 모음

이 문서는 실습에 필요한 명령만 모아 둔 요약본이다. 자세한 설명은 [시스템 구성](1_system.md), [SLAM](2_slam.md), [Navigation](3_nav.md)을 참고한다.

## 1. 환경 불러오기

새 터미널에서 실행한다.

```bash
source /opt/ros/humble/setup.bash
source ~/ktl_ws/install/setup.bash
```

## 2. 장비 연결 확인

```bash
ip link show eno1
ping -c 3 192.168.123.20   # Hesai LiDAR
ping -c 3 192.168.123.161 # Go2 모션 컨트롤러 PC
ping -c 3 192.168.123.18  # Go2 확장 PC
```

## 3. 빌드

Hesai 드라이버를 먼저 빌드한 뒤 나머지 패키지를 빌드한다.

```bash
source /opt/ros/humble/setup.bash
cd ~/ktl_ws

colcon build --packages-select hesai_ros_driver --symlink-install \
  --cmake-clean-cache \
  --cmake-args -DFIND_CUDA=ON \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda-12.6/bin/nvcc \
  -DCMAKE_CUDA_ARCHITECTURES=87

colcon build --symlink-install --packages-skip hesai_ros_driver
source ~/ktl_ws/install/setup.bash
```

## 4. Go2와 LiDAR 확인

Go2와 LiDAR만 확인할 때 실행한다.

```bash
ros2 launch go2_base go2_bringup.launch.py \
  network_interface:=eno1 rviz:=true
```

## 5. 지도 만들기

아래 명령 하나로 Go2·LiDAR와 SLAM을 함께 실행한다. 이때는 위의 기본 bringup을 따로 실행하지 않는다.

```bash
ros2 launch ktl go2_mapping.launch.py \
  network_interface:=eno1 rviz:=true
```

주행을 마친 뒤 Pose graph와 Navigation용 지도를 저장한다.

아래 두 명령은 같은 기본 이름 `map_practice`를 사용한다. 첫 번째 명령은
`map_practice.posegraph`, `map_practice.data`를 만들고, 두 번째 명령은
`map_practice.pgm`, `map_practice.yaml`을 만든다.

```bash
ros2 service call /slam_toolbox/serialize_map \
  slam_toolbox/srv/SerializePoseGraph \
  "{filename: '/home/ktl/ktl_ws/src/ktl/maps/map_practice'}"

ros2 run nav2_map_server map_saver_cli \
  -f /home/ktl/ktl_ws/src/ktl/maps/map_practice
```

저장한 pose graph를 이어서 매핑할 때는 `.posegraph`와 `.data` 파일을 함께 둔다.

```bash
ros2 launch ktl go2_mapping.launch.py \
  network_interface:=eno1 \
  posegraph:=/home/ktl/ktl_ws/src/ktl/maps/map_practice \
  map_start_pose:='[0.0, 0.0, 0.0]' \
  rviz:=true
```

## 6. 자율주행

아래 명령 하나로 Go2·LiDAR·Navigation을 함께 실행한다. 이때는 기본 bringup을 따로 실행하지 않는다.

```bash
ros2 launch ktl go2_navigation.launch.py \
  map:=/home/ktl/ktl_ws/src/ktl/maps/map_practice.yaml \
  rviz:=true
```

RViz에서 순서대로 한다.

1. Fixed Frame을 `map`으로 설정
2. `2D Pose Estimate`로 현재 위치와 방향 지정
3. `Nav2 Goal`로 목표 전송

## 7. 수동 이동과 정지

낮은 속도에서만 사용한다.

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.10, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

정지:

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```
