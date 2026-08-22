# Thiết lập kiểm nghiệm thống kê cho benchmark GCS–Bézier

Tài liệu này quy định cách phân tích thống kê cho benchmark được mô tả trong `EXPERIMENT_SETUP.md`. Mục tiêu là so sánh ACD và VCC công bằng trên cùng geometry, đo độ ổn định do ngẫu nhiên của VCC, và tránh coi nhiều lần chạy VCC trên một map là nhiều map độc lập.

## 1. Câu hỏi nghiên cứu và giả thuyết

Trên cùng một map geometry, ACD và VCC có khác nhau về:

1. tỷ lệ hoàn thành nghiệm hợp lệ;
2. thời gian phân hoạch (`t_decomp`) và thời gian solve (`t_solve`);
3. độ phức tạp graph/partition (`num_regions`, `num_edges`);
4. chất lượng trajectory (`path_length`, `traj_time`, `min_clearance`, `smoothness_proxy`);
5. độ ổn định giữa các VCC random seed?

Giả thuyết kiểm định hai phía là không có chênh lệch trung vị map-level giữa ACD và VCC. Mọi kiểm định đều hai phía, mức ý nghĩa gia đình `α = 0.05`; kết quả phải kèm effect size và khoảng tin cậy (CI), không chỉ báo p-value.

## 2. Thiết kế lấy mẫu và đơn vị phân tích

Thiết lập chính gồm năm map (`clustering`, `narrows`, `rooms`, `flappy`, `u_shaped`), map seed 0–9, `L=5`, density `medium`, obstacle size `medium`. Như vậy có 50 **map geometry độc lập theo seed**. Geometry không đổi khi chạy các method.

| Tầng dữ liệu | Đơn vị | Số lượng trong protocol chính | Vai trò |
|---|---|---:|---|
| Geometry | `(map_type, map_seed, L, density, size, mode)` | 50 | đơn vị độc lập cho suy luận giữa map |
| ACD run | 1 lần/geometry | 50 | phép đo xác định theo geometry và config |
| VCC run | 10 seed/geometry | 500 | đo độ nhạy của VCC với sampling/randomized clique cover |
| Method–geometry summary | 1 record/method/geometry | 100 | đơn vị dùng cho so sánh ACD–VCC |

VCC seed ở trial `t` là `base + map_seed × 10 + t`, với `base=0` và `t=0,…,9`. Map seed và VCC seed là hai nguồn ngẫu nhiên khác nhau. Không được đưa 500 lần chạy VCC vào một t-test cùng 50 ACD run: điều đó là pseudoreplication vì 10 VCC trial cùng dùng một map geometry.

## 3. Khóa cấu hình trước khi chạy

Trước lần chạy chính, lưu vào thư mục kết quả:

- commit Git, Python/Drake/Mosek version và OS;
- `configs/benchmark_config.json` nguyên vẹn;
- câu lệnh benchmark, map types, map seeds, VCC base và số VCC seeds;
- CSV raw, CSV summary, và manifest mô tả số run dự kiến;
- fingerprints/metadata map, gồm `regeneration_attempts`, `grid_feasible`, `non_overlap_valid`, `semantic_validation_passed`.

Không thay đổi config, seed schedule, timeout, hoặc rule hợp lệ sau khi xem kết quả. Nếu buộc phải thay đổi, đó là một experiment mới; giữ tách file output và báo cáo lý do.

## 4. Điều kiện đủ tư cách và xử lý failure

Một geometry chỉ được đưa vào so sánh hiệu năng nếu map hợp lệ: `grid_feasible=true`, `non_overlap_valid=true`, `semantic_validation_passed=true`, và start/goal hợp lệ. Không thay seed map để thay thế geometry thất bại.

Một run được tính **trajectory-valid success** khi `success=true` và các certificate sau không có vi phạm: `containment_violation_count=0`, `clearance_violation_count=0`, `velocity_violation_count=0`, `active_edge_missing_count=0`. Nếu một trường certificate bị trống do run dừng sớm, run đó không được dùng cho metric trajectory; vẫn được tính là failure cho success endpoint nếu không có nghiệm chứng nhận được.

Failure generation, decomposition, solver, timeout, hoặc certificate đều được giữ trong raw CSV cùng `stage`, `decomp_failed_reason` và `error_message`.

- **Success rate:** mẫu số là toàn bộ run được dự kiến trên geometry hợp lệ; không bỏ failure.
- **Runtime/trajectory metric:** chỉ phân tích các run trajectory-valid success; luôn báo thêm số eligible/success để tránh survivorship bias.
- **Timeout:** là failure cho success. Không thay bằng giá trị runtime 3600 s trong phân tích chính; có thể báo một sensitivity analysis với runtime bị censor tại 3600 s.

## 5. Tóm tắt map-level bắt buộc

ACD có một run trên mỗi geometry. Với mỗi metric liên tục `m`, summary ACD là giá trị duy nhất `m_ACD,g`. VCC phải được gộp trong phạm vi geometry `g` trước khi so sánh:

```text
success_VCC,g = (# VCC trajectory-valid success) / 10
m_VCC,g       = median(m của các VCC trajectory-valid success)
IQR_VCC,g     = Q3(m) − Q1(m), nếu có ít nhất 4 success
```

Median VCC là thống kê chính vì runtime và partition size thường lệch phải hoặc có outlier. Nếu một geometry không có VCC success, `m_VCC,g` là missing, không tự thay bằng timeout; geometry này vẫn góp vào endpoint success rate. `summary.csv` hiện có Q1/median/Q3/variance theo từng `map_type × seed × method`, nhưng phân tích phải dùng raw CSV để áp dụng rule trajectory-valid success ở trên.

## 6. Endpoints và thứ tự ưu tiên

Các endpoint được khóa trước khi phân tích:

| Nhóm | Endpoint chính | Cách báo cáo |
|---|---|---|
| Khả năng hoàn thành | ACD success rate; phân bố `success_VCC,g` | tỷ lệ, 95% CI, số failure theo `stage` |
| Chi phí tính toán | `t_decomp`, `t_solve` | median map-level, paired difference/ratio, 95% CI |
| Kích thước partition | `num_regions`, `num_edges` | median, IQR, paired difference |
| Chất lượng đường đi | `path_length` | median, paired difference; chỉ trên successful pairs |
| Ràng buộc an toàn | `min_clearance`, các violation count | distribution và tỷ lệ vi phạm; violation phải bằng 0 cho primary valid set |
| Ổn định VCC | `IQR_VCC,g`, variance, `success_VCC,g` | median qua geometry và biểu đồ phân bố |

`traj_time`, `smoothness_proxy`, `num_active_regions`, coverage/clique metrics VCC, và các diagnostic ACD là endpoint phụ/exploratory. Không kết luận method tốt hơn chỉ từ một metric phụ nếu endpoint chính không nhất quán.

## 7. Phương pháp kiểm định và effect size

### 7.1 So sánh ACD–VCC trên cặp geometry

Với mỗi geometry có cả ACD success và ít nhất một VCC success, tạo cặp:

```text
d_g = m_ACD,g − median(m_VCC,g)
r_g = log(m_ACD,g / median(m_VCC,g))     # chỉ cho metric dương
```

Thống kê chính là median của `d_g` (đơn vị gốc) và median của `r_g`/`exp(median(r_g))` (tỷ số geometric). Báo cáo paired bootstrap 95% CI bằng cách resample **50 geometry với replacement**, giữ nguyên cặp ACD–VCC trong từng geometry. Dùng tối thiểu 10 000 bootstrap replicate và seed phân tích được công bố.

Để có p-value bổ sung, dùng Wilcoxon signed-rank hai phía trên `d_g` khác 0, sau khi loại cặp thiếu theo rule đã khóa. Nếu số cặp quá nhỏ hoặc dữ liệu có nhiều tie, dùng paired sign/permutation test thay thế và nêu rõ. Không dùng independent-samples test.

Runtime có thể được phân tích thêm ở log scale (`r_g`) để giảm ảnh hưởng tail dài; bảng chính vẫn giữ đơn vị giây và ratio dễ diễn giải. Các count metric nên báo paired difference; chỉ dùng log-ratio khi cả hai giá trị dương.

### 7.2 Endpoint success

Success không được điều kiện hóa trên run thành công. Báo cáo:

- `ACD_success = successful ACD geometries / 50`;
- trung bình và median của `success_VCC,g` qua 50 geometry;
- số geometry với VCC success rate bằng 0, trong `(0,1)`, và bằng 1;
- bảng paired: ACD success/fail × VCC có ít nhất một success / không success.

Vì VCC có 10 lần lặp còn ACD có một, không diễn giải McNemar như một so sánh trial-level trực tiếp. Nếu cần một binary endpoint để kiểm định sensitivity, preregister rule `VCC robust success ⇔ success_VCC,g ≥ 0.8`, sau đó dùng exact McNemar test trên 50 cặp. Ngưỡng 0.8 chỉ dùng khi được khóa trước lần chạy; kết quả chính vẫn là các tỷ lệ và CI.

### 7.3 Điều chỉnh đa kiểm định

Gia đình xác nhận gồm `t_decomp`, `t_solve`, `num_regions`, `num_edges`, và `path_length`. Điều chỉnh p-value bằng Holm–Bonferroni trong gia đình này. Success và safety/validity được báo riêng là endpoint bảo đảm hệ thống, không gộp với các metric exploratory. Các phân tích theo từng map type là phân tích phân tầng/exploratory trừ khi mỗi tầng có đủ số geometry theo kế hoạch mở rộng.

## 8. Biểu đồ và bảng bắt buộc

1. **Bảng manifest:** số geometry hợp lệ, số ACD/VCC run kỳ vọng và thực tế, failure theo stage.
2. **Paired dot/line plot:** mỗi line là một geometry, nối ACD với median VCC cho `t_decomp`, `t_solve`, `num_regions`, `num_edges`, `path_length`.
3. **VCC stability plot:** box/violin của 10 VCC trial trong mỗi map type; hoặc heatmap `geometry × vcc_trial` cho success/runtime.
4. **Forest table:** median paired difference, ratio nếu phù hợp, bootstrap CI, test statistic, p thô và p Holm-adjusted, số cặp eligible.
5. **Failure table:** map type × method × stage với count và tỷ lệ trên số run dự kiến.

Không gộp tất cả map family vào một boxplot mà bỏ mất pairing. Nếu hình sử dụng log scale phải ghi rõ và không hiển thị zero/failed run như các giá trị runtime hữu hạn.

## 9. Phân tích sensitivity và mở rộng

Phân tích chính cố định ở `L=5`, `medium`, `medium`; do đó kết luận chỉ áp dụng cho phạm vi đó. Các sensitivity analysis được phép nhưng phải tách với bảng chính:

- thay statistic VCC từ median sang mean hoặc best-of-10 để định lượng ảnh hưởng chọn trial; **best-of-10 không dùng cho kết luận chính**;
- coi timeout là runtime censor ở 3600 s;
- chạy thêm VCC seed (ví dụ 30) nhưng vẫn aggregate trong mỗi geometry;
- mở rộng `L`, density hoặc size và fit mô hình mixed-effects exploratory: `metric ~ method * map_type + (1 | geometry)`; với VCC trial-level thêm random intercept cho geometry.

Khi mở rộng nhiều cấu hình, `geometry` phải bao gồm đầy đủ `(map_type, map_seed, L, density, size, mode)`. Không pool trực tiếp metrics qua `L` khác nhau: dùng tỷ số với baseline cùng geometry hoặc thêm `L` vào model.

## 10. Mẫu câu báo cáo kết quả

> Trên 50 geometry đã khóa trước, ACD hoàn thành hợp lệ ở `a/50` geometry. VCC có median map-level success rate `s%` (IQR `[q1,q3]`), với `z` geometry không có VCC success. Trên `n` successful pairs, chênh lệch median ACD–VCC của `t_solve` là `d` s (paired-bootstrap 95% CI `[l,u]`), tương ứng geometric ratio `r`. Wilcoxon signed-rank hai phía: `p_raw`, Holm-adjusted `p_adj`. Kết quả runtime này được diễn giải cùng `t_decomp`, partition size và failure table, không tách rời tỷ lệ hoàn thành.

Mọi con số trong mẫu phải được điền từ raw CSV và script phân tích phiên bản hóa; không suy ra ý nghĩa thống kê từ Q1/median/Q3 của summary CSV một mình.
