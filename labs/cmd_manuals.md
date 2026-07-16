# 실습 명령어 모음

이 문서는 실습에 필요한 명령만 모아 둔 요약본이다. 자세한 설명은 [시스템 구성](1_system.md), [SLAM](2_slam.md), [Navigation](3_nav.md)을 참고한다.

## 1. ROS 2 기본 확인 명령어

노드 확인:

```bash
ros2 node list                 # 실행 중인 노드 목록 확인
ros2 node info /노드_이름      # 노드의 구독·발행 토픽과 서비스 확인
```

토픽 확인:

```bash
ros2 topic list                # 현재 사용 중인 토픽 목록 확인
ros2 topic list -t             # 토픽 목록과 메시지 타입 함께 확인
ros2 topic info /토픽_이름     # 토픽 타입과 발행·구독 노드 수 확인
ros2 topic echo /토픽_이름     # 토픽에서 발행되는 메시지 내용 출력
ros2 topic hz /토픽_이름       # 토픽의 초당 발행 주기(Hz) 확인
```

노드와 토픽 연결 관계를 그래프로 확인:

```bash
rqt_graph                      # 노드와 토픽의 연결 관계를 그래프로 표시
```

두 TF 프레임 사이의 변환 확인:

```bash
ros2 run tf2_ros tf2_echo 기준_프레임 대상_프레임  # 두 프레임 사이의 위치·회전 변환을 계속 출력

# 예: map에서 base_link까지의 변환 확인
ros2 run tf2_ros tf2_echo map base_link
```

전체 TF 트리를 파일로 생성:

```bash
ros2 run tf2_tools view_frames  # 전체 TF 트리를 분석해 frames.pdf로 저장
```

명령을 실행한 현재 디렉터리에 `frames.pdf`가 생성된다.

## 2. 환경 불러오기

새 터미널에서 실행한다.

```bash
source /opt/ros/humble/setup.bash
source ~/ktl_ws/install/setup.bash
```

## 3. 장비 연결 확인

```bash
ip link show eno1
ping -c 3 192.168.123.20   # Hesai LiDAR
ping -c 3 192.168.123.161 # Go2 모션 컨트롤러 PC
ping -c 3 192.168.123.18  # Go2 확장 PC
```

## 4. 빌드

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

## 5. Go2와 LiDAR 확인

Go2와 LiDAR만 확인할 때 실행한다.

```bash
ros2 launch go2_base go2_bringup.launch.py \
  network_interface:=eno1 rviz:=true
```

## 6. 지도 만들기

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

## 7. 자율주행

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

## 8. 수동 이동과 정지

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
