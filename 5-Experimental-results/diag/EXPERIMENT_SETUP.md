# Thiết lập thực nghiệm GCS–Bézier trên năm dạng bản đồ 2D

Tài liệu này quy định thiết lập tái lập được cho thực nghiệm so sánh phân hoạch không gian tự do và lập kế hoạch GCS–Bézier. Nội dung phản ánh implementation hiện tại trong `map_generators.py`, `run_benchmark.py`, `configs/benchmark_config.json`, cùng các nguyên tắc thiết kế/diễn giải trong `codex.md`, `decomp.md` và `TRAJECTORY_CORNER_ANALYSIS.md`.

## 1. Mục tiêu và phạm vi

Thực nghiệm dùng **cùng một `MapInstance`** cho ACD và VCC, sau đó chạy cùng cấu hình GCS–Bézier. Vì vậy khác biệt giữa các phương pháp phải được hiểu là ảnh hưởng của phân hoạch, không phải do thay đổi map. Năm map chính là:

| Mã map | Loại khó chính | Vai trò trong benchmark |
|---|---|---|
| `clustering` | nhiều vật cản nhỏ theo cụm, nhiều kênh đi vòng | kiểm tra độ nhạy với phân bố obstacle không đều |
| `narrows` | chuỗi cửa hẹp bắt buộc | kiểm tra bottleneck và liên thông region graph |
| `rooms` | các phòng và cửa nối tuần tự | kiểm tra lựa chọn qua topology kiểu floorplan |
| `flappy` | các vách xen kẽ, buộc đổi hướng nhiều lần | kiểm tra chuỗi chuyển region dài |
| `u_shaped` | obstacle lõm dạng chữ U/bẫy cục bộ | kiểm tra cách phân hoạch xử lý concavity và đường vòng |

`blobs` không thuộc bộ này: generator đó đang bị vô hiệu hóa có chủ đích vì polygon hóa biên cong có thể sinh quá nhiều mảnh ACD mỏng. Các map `map1_*`, `map3_*`… là các map mở rộng/stress, không thay thế năm map chính trong tài liệu này.

## 2. Không gian làm việc và quy ước chung

Mỗi map được sinh trước trong hệ chuẩn hóa `[0,1]^2` rồi scale theo cạnh workspace `L`. Thiết lập chính dùng `L = 5`; CLI cũng cho phép `L ∈ {5, 10, 20}`. Start và goal không ngẫu nhiên:

```text
start = (0.04L, 0.04L)       goal = (0.96L, 0.96L)
```

Tất cả obstacle được cắt vào workspace, làm sạch polygon, gộp các primitive chạm nhau khi cần (`merge_connected_primitives=true`), và loại polygon quá nhỏ/hỏng. Hai obstacle rời phải cách nhau ít nhất `max(min_obstacle_separation, 10^-4 L)`. Trong config hiện tại, ngưỡng passage tối thiểu đưa vào generator là `0.08` (đồng thời không nhỏ hơn `10^-3 L`).

Sau khi sinh, hệ thống kiểm tra theo thứ tự: (1) semantic contract của map, (2) không overlap/không quá gần, (3) start–goal không nằm trong obstacle, và (4) tồn tại đường đi BFS trên occupancy grid **không inflate obstacle**. Độ phân giải grid là `ceil(30L)`; với `L=5` là `150 × 150`. Một map không đạt bị sinh lại tối đa 50 lần; nếu vẫn thất bại, `feasible_grid=false` và benchmark ghi một dòng lỗi thay vì đổi sang loại map khác.

## 3. Minh họa và cấu hình từng map

Trong sơ đồ, `S` là start, `G` là goal, `█` là obstacle/vách, và khoảng trống là free space. Đây là minh họa topology, không phải ảnh hình học theo tỉ lệ tuyệt đối.

### 3.1 `clustering` — các cụm obstacle

```text
+-------------------------+
|       █ █     █ █       |
|     █ █ █   █ █ █       |
|           █             |
|  S      █ █ █       G   |
|    █ █         █ █      |
|    █ █   █ █   █ █      |
+-------------------------+
```

Generator đặt 3/4/5/6 cluster cores tương ứng `sparse/medium/dense/very_dense`; tâm core được jitter Gaussian với độ lệch chuẩn `0.025L`. Mỗi core có lần lượt 6/9/12/14 hình chữ nhật xoay nhẹ; kích thước lấy theo `obstacle_size_level`. Một blocker trung tâm được thêm để chặn hướng đi thẳng. Các block trong một cụm được lấy quanh core với độ lệch chuẩn `(0.040 + 0.012 × rank)L` và chỉ được chấp nhận nếu không chồng lấn.

Độ khó tăng theo số cụm, số block trong cụm và độ lan cụm; metadata lưu `num_clusters`, `target_cluster_obstacles`, tọa độ core và số transition được thiết kế.

### 3.2 `narrows` — chuỗi hành lang hẹp

```text
+-------------------------+
|       ███     ███       |
|       ███     ███       |
|  S    ███     ███   G   |
|       ███     ███       |
|       ███     ███       |
|             ███         |
+-------------------------+
```

Map gồm các vách dọc gần phủ chiều cao workspace; mỗi vách có đúng một gap. Số vách là 2/3/4/4, còn gap được chọn ngẫu nhiên theo các khoảng chuẩn hóa: `0.10–0.14`, `0.04–0.06`, `0.02–0.03`, `0.005–0.015` lần `L`. Độ dày vách được lấy trong `0.022–0.040L`; vị trí vách và tâm gap có jitter nhỏ. Các gap xen kẽ cao/thấp để buộc đổi hướng. Metadata quan trọng: `num_barriers`, `designed_bottleneck_width`, `gateway_centers_normalized` và `designed_forced_transitions`.

### 3.3 `rooms` — đồ thị phòng và cửa

```text
+---------+---------+-----+
|    S    |         |     |
|         |    o    |     |
+----o----+----+----+-----+
|         |    |          |
|         o    |       G  |
+---------+----+----------+
```

`rooms` tạo skeleton dạng lưới phòng: `2×2`, `2×3`, `3×3`, `3×3` theo bốn mức density. Các vách trong được tạo bằng các đoạn vách có cửa; route chính nối phòng chứa `S` đến phòng chứa `G` luôn được bảo toàn. Ở density cao hơn, một số cạnh phụ có thể mở cửa ngẫu nhiên để tạo lựa chọn/nhánh phụ. Độ dày vách là `0.014–0.024L`; độ rộng cửa lần lượt là `0.145`, `0.115`, `0.090`, `0.075L` (và không nhỏ hơn ngưỡng passage).

Metadata: `room_grid`, `num_rooms`, `num_doors`, `room_graph_edges`, `start_goal_room_hops`, `num_dead_end_rooms`, `designed_bottleneck_width`.

### 3.4 `flappy` — vách neo xen kẽ

```text
+-------------------------+
|   ███       ███         |
|   ███       ███         |
| S ███   ███ ███   ███ G |
|       ███       ███     |
|       ███       ███     |
+-------------------------+
```

Map có các vách dài neo luân phiên từ mép trên và dưới; đường đi phải luồn qua gap của từng vách. Số flap là 4/6/12/16. Gap lần lượt thuộc `0.24–0.30L`, `0.18–0.23L`, `0.13–0.17L`, `0.10–0.14L`; độ dày danh nghĩa là `0.028/0.023/0.015/0.012L` và có nhiễu ±10%. Vị trí x trải từ `0.10L` đến `0.90L`, jitter nhưng bị chặn theo khoảng cách flap để không đảo thứ tự. Góc quay tối đa giảm theo density: 6°, 4°, 2°, 1.25°.

Mỗi flap có retry cục bộ để tránh overlap. Map chỉ qua semantic validation khi số flap đặt được đúng mục tiêu và anchor xen kẽ. Metadata ghi đầy đủ `flap_data`, `flap_anchors`, `min_tip_gap`, `min_center_spacing`, `forced_turn_count` và `flap_angle_limit_deg`.

### 3.5 `u_shaped` — bẫy chữ U lõm

```text
+-------------------------+
|                 ███     |
|      ███████    █ █     |
|  S   █     █      █   G |
|      █     █             |
|      ███████             |
+-------------------------+
```

Map đặt một U-shape chính gần trung tâm, xoay quanh 45° với nhiễu Gaussian, sau đó thử thêm tối đa 20 U-shape nhỏ làm distractor tại các vị trí định sẵn có jitter. Số U thực tế phụ thuộc các lần placement không overlap; `num_u_traps` trong metadata là số obstacle đã đặt. Density làm thay đổi kích thước U chính: chiều rộng `(0.34 + 0.04 × rank)L`, chiều cao `(0.30 + 0.04 × rank)L`, và bề dày `(0.045 − 0.004 × min(rank,2))L`. Generator kiểm tra không overlap trước khi thêm từng U. Metadata gồm `num_u_traps`, `main_u_depth`, `main_u_mouth_width`, orientation, và số transition dự kiến.

Không nên xem việc trajectory cắt cạnh phân hoạch là va chạm: đó có thể là điểm chuyển hợp lệ giữa hai convex region. Ngược lại, point-only contact giữa region phải bị loại khỏi graph; đây là guardrail đã được nêu trong phân tích trajectory.

## 4. Mức density, kích thước obstacle và map seed

`density_level` điều khiển **tham số đúng với archetype** (số vách/phòng/flap, độ rộng gap/cửa…), chứ không chỉ tăng số obstacle. Dải target area coverage chung trong generator là: sparse `10–18%`, medium `18–30%`, dense `30–45%`, very_dense `45–55%`. Khi không truyền target riêng, giá trị trung bình dải được dùng. Với năm map cấu trúc, coverage thực tế được đo và log, nhưng không được dùng để phá skeleton.

`obstacle_size_level` quy định kích thước chuẩn hóa của block ngẫu nhiên: `tiny=0.008–0.020L`, `small=0.015–0.040L`, `medium=0.040–0.080L`, `large=0.080–0.180L`. Trong bộ CLI chính dùng `small/medium/large`; tham số này ảnh hưởng trực tiếp nhất đến `clustering`, còn map vách có kích thước được xác định bởi skeleton.

Map seed là seed geometry. Với một tổ hợp `(map_type, map_seed, L, density_level, obstacle_size_level, density_mode, target coverage/count)`, lần thử đầu sử dụng:

```python
rng = np.random.default_rng(map_seed)
```

Nếu cần regenerate, lần thử `a` dùng `np.random.default_rng(map_seed + 1_000_003*a)`. Do đó geometry tái lập được; `regeneration_attempts` trong CSV cho biết map có phải dùng seed dẫn xuất hay không. Seed map không được thay đổi theo phương pháp decomposition.

## 5. Thiết lập seed VCC và seed IRIS

VCC có nguồn ngẫu nhiên độc lập với map geometry. Với `vcc_seed_base=B`, `vcc_seeds_per_map=K` và `trial=t` (bắt đầu từ 0), seed VCC là:

```text
vcc_seed = B + map_seed × K + t
```

Thiết lập khuyến nghị/hiện hành là `B=0`, `K=10`, vì vậy map seed 0 dùng VCC seed 0–9, map seed 1 dùng 10–19, v.v. ACD chỉ chạy một lần trên mỗi `MapInstance`; VCC chạy K lần trên đúng map đó. `vcc_random_seed`, nếu được đặt trong config cũ, đóng vai trò base override; cờ `--vcc-seed-base` có ưu tiên cao hơn config. CSV phải giữ cả `seed`, `vcc_trial` và `vcc_seed`.

IRIS không dùng VCC seed. Start và goal là seed IRIS mặc định; seed thủ công chỉ là điểm mầm truyền vào Drake IRIS, **không phải convex region**. File seed lưu từ editor bị ràng buộc theo `map_type`, map seed, `L`, profile và fingerprint geometry; benchmark từ chối artifact không khớp. Một batch headless cần truyền `--iris-seed-points` hoặc `--no-interactive-iris-seeds`.

## 6. Cấu hình decomposition và GCS–Bézier

Các giá trị dưới đây lấy từ `configs/benchmark_config.json`.

| Thành phần | Giá trị |
|---|---|
| Map validation | `grid_cells_per_unit=30`, `max_attempts=50`, `min_passage_width=0.08` |
| Geometry hygiene | `max_place_attempts_per_obstacle=200`, merge primitive chạm nhau, repair polygon, bỏ polygon tiny |
| ACD | `tau=0`, `alpha=0`, `beta=1`, measure `hybrid1`, timeout 30 s; bật repair và sliver filtering |
| VCC | 500 samples, coverage target 0.96, tối đa 500 iteration, clique tối thiểu 3 |
| Bézier/GCS | order 6, continuity 2, `hdot_min=0.1`, vận tốc mỗi trục `[-1,1]`, 500 samples đánh giá |
| Objective | time weight 1.0 + path-length proxy weight 1.0 + regularizer bậc 0/1 đều 0.1 |
| Solver | relaxation bật, Mosek time limit 3600 s, tắt log console |

Path-length term là cần thiết để tránh nghiệm rất mượt nhưng dài đi sát mép workspace như đã quan sát ở U-shape. Nó là convex proxy, vì vậy kết quả không được diễn giải là shortest path Euclid tuyệt đối. ACD/VCC/IRIS không được fallback chéo khi một phương pháp lỗi.

## 7. Protocol chạy và số lần lặp

Protocol chính: `L=5`, density `medium`, obstacle size `medium`, map seed 0–9, ACD một lần và VCC 10 lần trên mỗi map. Tổng số map geometry là `5 × 10 = 50`; tổng số decomposition run là `50 × (1 + 10) = 550`. Chỉ rõ cả năm map vì CLI hiện tại mặc định chỉ chọn `clustering`.

```bash
python3 run_benchmark.py \
  --profile quick \
  --map-types clustering narrows rooms flappy u_shaped \
  --seeds 0 1 2 3 4 5 6 7 8 9 \
  --workspace-sizes 5 \
  --density-levels medium \
  --obstacle-size-levels medium \
  --density-mode area_coverage \
  --decomp-methods acd vcc \
  --vcc-seeds-per-map 10 \
  --vcc-seed-base 0 \
  --max-instances 50 \
  --config configs/benchmark_config.json \
  --output results/five_maps_medium_L5.csv
```

Mở rộng có kiểm soát: chạy từng chiều biến thiên một (ví dụ `L=5,10`, hoặc `sparse,medium,dense`) trong khi giữ map seed và VCC schedule cố định. Không nên đồng thời thay đổi `L`, density, size và map family nếu mục tiêu là quy kết nguyên nhân.

## 8. Báo cáo và tiêu chí đọc kết quả

File CSV thô lưu geometry (`num_obstacles`, coverage, separation, feasibility, semantic metadata), decomposition (`num_regions`, `num_edges`, thời gian, chỉ số ACD/VCC), và nghiệm (`success`, `t_solve`, `path_length`, clearance, violation/certificate). File `_summary.csv` tổng hợp Q1, median, Q3 và population variance; với VCC, thống kê được thực hiện trên 10 VCC seeds của cùng map geometry.

Khi báo cáo, cần tách ba lớp kết quả:

1. **Map hợp lệ:** `grid_feasible`, `non_overlap_valid`, `semantic_validation_passed` đều đúng.
2. **Phân hoạch hợp lệ:** cover start/goal, start–goal connected, không safety/convexity violation vượt ngưỡng.
3. **Trajectory hợp lệ:** containment, clearance và velocity violation bằng 0; `active_edge_missing_count=0`.

Một failure ở bất kỳ lớp nào phải được giữ trong dữ liệu và ghi `stage`, `failed_reason`/`error_message`; không thay thế âm thầm bằng map, seed, hoặc decomposition method khác.
