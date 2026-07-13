# 실습 명령어 모음

## 공통 준비

새 터미널에서는 항상 환경을 불러온다.

```bash
source /opt/ros/humble/setup.bash
source ~/ktl_ws/install/setup.bash
```

## 1. 장비 확인

```bash
ip link show eno1
ping -c 3 192.168.123.20   # Hesai
ping -c 3 192.168.123.161 # Go2
sudo nvpmodel -q
```

## 2. 빌드

Hesai 드라이버를 먼저 빌드한 뒤 나머지 패키지를 빌드한다.

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

## 3. Go2·LiDAR bringup

```bash
ros2 launch go2_base go2_bringup.launch.py \
  network_interface:=eno1 rviz:=true
```

상태 확인:

```bash
ros2 topic echo /go2/battery_state --once
ros2 topic echo /go2/odom --once
ros2 topic hz /hesai/lidar_points
ros2 node list
```

## 4. 지도 생성

```bash
ros2 launch ktl go2_mapping.launch.py \
  network_interface:=eno1 rviz:=true
```

입력 확인:

```bash
ros2 topic hz /hesai/lidar_points
ros2 topic hz /scan
ros2 topic echo /scan --once
```

Pose graph 저장:

```bash
ros2 service call /slam_toolbox/serialize_map \
  slam_toolbox/srv/SerializePoseGraph \
  "{filename: '/home/ktl/ktl_ws/src/ktl/maps/map_practice'}"
```

Navigation용 지도 저장:

```bash
ros2 run nav2_map_server map_saver_cli \
  -f /home/ktl/ktl_ws/src/ktl/maps/map_practice
```

## 5. 자율주행

```bash
ros2 launch ktl go2_navigation.launch.py \
  map:=/home/ktl/ktl_ws/src/ktl/maps/map_practice.yaml \
  rviz:=true
```

RViz 순서:

1. Fixed Frame을 `map`으로 설정
2. `2D Pose Estimate`로 현재 위치·방향 지정
3. AMCL 포즈가 맞으면 `Nav2 Goal`로 목표 전송

```bash
ros2 topic echo /amcl_pose --once
ros2 topic echo /plan --once
ros2 topic echo /cmd_vel
```

## 6. 안전한 수동 주행

낮은 속도에서만 시험하고, 즉시 정지할 수 있는 상태에서 실행한다.

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.10, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

정지:

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

## 7. 에러 찾기

```bash
ros2 launch ktl go2_navigation.launch.py \
  map:=/home/ktl/ktl_ws/src/ktl/maps/map_practice.yaml \
  rviz:=false 2>&1 | tee /tmp/go2_navigation.log
```

다른 터미널에서 경고와 에러만 확인한다.

```bash
rg -n -i 'error|fatal|warn|failed|abort|timeout|exception' \
  /tmp/go2_navigation.log
```

| 증상 | 먼저 확인할 것 |
|---|---|
| LiDAR 토픽 없음 | LiDAR 전원, `eno1`, `192.168.123.20`, UDP 2368 |
| `/scan` 없음 | PointCloud 변환 노드, TF, 높이 필터 |
| 지도 생성 안 됨 | `/scan`, `/go2/odom`, `odom → base_link` |
| AMCL 오차 | 2D Pose Estimate, `/scan`, TF |
| 경로 생성 실패 | global costmap, 목표가 장애물인지 여부 |
| 도착 후 회전 지속 | goal tolerance, DWB, odom |
