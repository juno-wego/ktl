# 실습 명령어 모음

아래 명령은 새 터미널마다 먼저 환경을 불러온다는 전제로 한다.

```bash
source /opt/ros/humble/setup.bash
source ~/ktl_ws/install/setup.bash
```

## 장비·네트워크 확인

```bash
ip addr show eno1
ping -c 3 192.168.123.20
ping -c 3 192.168.123.161
sudo nvpmodel -q
```

## 빌드

```bash
cd ~/ktl_ws
colcon build --packages-select hesai_ros_driver --symlink-install \
  --cmake-clean-cache \
  --cmake-args -DFIND_CUDA=ON \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda-12.6/bin/nvcc \
  -DCMAKE_CUDA_ARCHITECTURES=87
source install/setup.bash

colcon build --symlink-install --packages-skip hesai_ros_driver
source install/setup.bash
```

## Go2 bringup

```bash
ros2 launch go2_base go2_bringup.launch.py \
  network_interface:=eno1 rviz:=true
```

RViz 없이 실행:

```bash
ros2 launch go2_base go2_bringup.launch.py \
  network_interface:=eno1 rviz:=false
```

## 상태 확인

```bash
ros2 node list
ros2 topic list
ros2 topic echo /go2/battery_state --once
ros2 topic echo /go2/odom --once
ros2 topic echo /go2/imu --once
ros2 topic hz /go2/odom
ros2 topic hz /hesai/lidar_points
```

## 매핑

```bash
ros2 launch ktl go2_mapping.launch.py \
  network_interface:=eno1 rviz:=true
```

매핑 중 데이터 확인:

```bash
ros2 topic hz /hesai/lidar_points
ros2 topic hz /hesai/scan_raw
ros2 topic hz /scan
ros2 topic echo /scan --once
```

Pose graph 저장:

```bash
ros2 service call /slam_toolbox/serialize_map \
  slam_toolbox/srv/SerializePoseGraph \
  "{filename: '/home/ktl/ktl_ws/src/ktl/maps/map_practice'}"
```

점유 지도 저장:

```bash
ros2 run nav2_map_server map_saver_cli \
  -f /home/ktl/ktl_ws/src/ktl/maps/map_practice
```

## Navigation

```bash
ros2 launch ktl go2_navigation.launch.py \
  map:=/home/ktl/ktl_ws/src/ktl/maps/map_practice.yaml \
  rviz:=true
```

RViz에서 순서:

1. `Fixed Frame`을 `map`으로 설정
2. `2D Pose Estimate`로 현재 위치와 방향 지정
3. 위치가 수렴하면 `Nav2 Goal`로 목표 지정

## TF·Nav2 확인

```bash
ros2 topic echo /initialpose --once
ros2 topic echo /amcl_pose --once
ros2 topic echo /plan --once
ros2 topic echo /cmd_vel
ros2 topic echo /local_plan --once
ros2 topic echo /local_costmap/costmap --once
ros2 run tf2_tools view_frames
ros2 action list
ros2 service list | grep -E 'amcl|slam|costmap'
```

## 수동 속도 시험

작은 속도로 시험하고, 반드시 정지 명령을 준비한다.

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.10, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

## 로그 줄이기·에러 찾기

LiDAR 프레임 로그가 많을 때는 전체 화면에서 찾지 말고 로그를 파일로 저장한 뒤 경고·에러만 추린다.

```bash
ros2 launch ktl go2_navigation.launch.py \
  map:=/home/ktl/ktl_ws/src/ktl/maps/map_practice.yaml \
  rviz:=false 2>&1 | tee /tmp/go2_navigation.log
```

다른 터미널:

```bash
rg -n -i 'error|fatal|warn|failed|abort|timeout|exception' /tmp/go2_navigation.log
```

노드별 로그 위치:

```bash
ls -lt ~/.ros/log/latest/
rg -n -i 'error|fatal|warn|failed|timeout' ~/.ros/log/latest/
```

## 자주 확인하는 원인

| 증상 | 먼저 볼 것 |
|---|---|
| LiDAR 토픽 없음 | Hesai IP, `eno1`, `192.168.123.20`, UDP 2368 |
| `/scan` 없음 | PointCloud 변환 노드, TF, 높이 필터 |
| 지도 안 만들어짐 | `/scan`, `/go2/odom`, `odom→base_link` TF |
| AMCL이 틀어짐 | 2D Pose Estimate 방향, `/scan` frame, `map→odom` TF |
| 경로 생성 실패 | global costmap, 시작/목표가 장애물에 들어갔는지 |
| 도착 후 계속 움직임 | goal tolerance, DWB `RotateToGoal`, odom, `/cmd_vel` |
| 로봇이 꺼진 상태에서 종료 | 정상적인 통신 실패 가능성. 전원·케이블·IP부터 확인 |
