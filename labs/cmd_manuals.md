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

데이터 흐름을 한 단계씩 점검할 때:

```bash
ros2 topic info /go2/odom
ros2 topic info /hesai/lidar_points
ros2 topic echo /go2/battery_state --once
ros2 run tf2_ros tf2_echo odom base_link
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

현재 costmap을 비우고 다시 관측하려면:

```bash
ros2 service call /local_costmap/clear_entirely_local_costmap \
  nav2_msgs/srv/ClearEntireCostmap '{}'
ros2 service call /global_costmap/clear_entirely_global_costmap \
  nav2_msgs/srv/ClearEntireCostmap '{}'
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

Nav2 목표 전체 취소:

```bash
ros2 service call /navigate_to_pose/_action/cancel_goal \
  action_msgs/srv/CancelGoal \
  "{goal_info: {goal_id: {uuid: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}, stamp: {sec: 0, nanosec: 0}}}"
```

종료 순서:

1. Nav2 목표를 취소한다.
2. 0 속도 명령을 한 번 발행한다.
3. 실행 중인 launch 터미널에서 `Ctrl+C`로 노드를 종료한다.

0 속도 명령은 소프트웨어 정지다. 비상 상황에서는 현장 안전 절차와 로봇의 안전 상태 전환 방법을 우선한다.

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

## 8. 설정 수정 후 재실행

| 수정한 항목 | 필요한 작업 |
|---|---|
| `ktl/config` YAML | 해당 launch 종료 후 재실행 |
| launch 파일 | launch 재실행, symlink가 아니면 패키지 재빌드 |
| C++ 코드 | 패키지 재빌드 후 `source ~/ktl_ws/install/setup.bash` |
| URDF | bringup 재실행 |

### 데이터 흐름별 진단

| 단계 | 확인 명령 | 다음 단계로 넘어갈 조건 |
|---|---|---|
| 네트워크 | `ping -c 3 <장치_IP>` | Go2·Hesai 응답 |
| Go2 상태 | `ros2 topic echo /go2/odom --once` | pose와 twist가 수신됨 |
| LiDAR | `ros2 topic hz /hesai/lidar_points` | PointCloud가 지속 발행됨 |
| 2D scan | `ros2 topic echo /scan --once` | frame, range, stamp가 유효 |
| TF | `ros2 run tf2_ros tf2_echo odom base_link` | transform이 계속 출력됨 |
| 위치·경로 | `ros2 topic echo /amcl_pose --once`, `ros2 topic echo /plan --once` | AMCL pose·전역 경로 수신 |
