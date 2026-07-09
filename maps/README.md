# maps

SLAM으로 생성한 map 파일을 둔다.

일반적으로 함께 관리하는 파일:

- `<map_name>.yaml`
- `<map_name>.pgm`
- `<map_name>.png`

맵 저장 예시:

```bash
ros2 run nav2_map_server map_saver_cli -f maps/go2_map
```

