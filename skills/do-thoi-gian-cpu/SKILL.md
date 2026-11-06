---
name: do-thoi-gian-cpu
description: Đo thời gian suy luận trên CPU có kiểm soát (ghim core, 2 thread, khởi động, >=200 lần đo, ghi `_env`) cho một thành phần mô hình đã đóng băng, để thay số gõ tay như "2.5 ms" bằng số có nguồn. Dùng khi paper báo độ trễ / chi phí của một module (encoder, classifier head, scorer...) hoặc khi `ghi-so-tu-log-vao-results` gặp số loại E.
phases: experiment, results, writing
---
# Đo thời gian CPU có kiểm soát

## Mục tiêu
Một con số độ trễ (median ms) tái lập được, của đúng một thành phần đã đóng băng, đo trên CPU thật với 2 thread ghim vào 2 core. Kết quả vào `results/latency_<tên>.json` có `_env` và `_src`; paper lấy qua macro (quy tắc 2), không gõ tay. Kỹ năng này chi tiết hoá mục 2E của `ghi-so-tu-log-vao-results`.

## Bước 1. Xác định cái được đo
Ghi vào đầu script và vào json (`target`):
- Thành phần nào (vd `scorer.head`), checkpoint/hash, độ chính xác (fp32...), `eval()` và `inference_mode`.
- **Đo gì**: chỉ forward của thành phần, hay gồm tiền xử lý / tokenize? Paper phải nói đúng phạm vi. Mặc định chỉ forward, đầu vào là tensor dựng sẵn.
- Cỡ batch và độ dài đầu vào (`batch`, `seq_len`). Nếu độ trễ phụ thuộc độ dài, đo trên vài độ dài đại diện lấy từ dữ liệu thật, không dùng một đầu vào ngẫu nhiên tuỳ ý.
- Thành phần đóng băng: không `train()`, không cập nhật trọng số, không autograd.

## Bước 2. Kiểm soát môi trường
1. **Đặt biến môi trường TRƯỚC khi import numpy/torch** (đặt sau là vô hiệu):
```python
import os
for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[k] = "2"
import torch; torch.set_num_threads(2); torch.set_num_interop_threads(1)
```
2. **Ghim core** (2 core logic cố định, tránh core 0 vì hệ điều hành hay dùng):
```python
import psutil
CORES = [2, 3]                       # ghi vào _env
psutil.Process().cpu_affinity(CORES)  # Windows & Linux; Linux có thể dùng os.sched_setaffinity(0, CORES)
```
   Có hyper-threading thì 2 core logic có thể là cùng 1 core vật lý; ghi `physical_cores`/`logical` vào `_env` và nói rõ trong báo cáo.
3. **Máy yên tĩnh**: trước khi đo, `psutil.cpu_percent(interval=2, percpu=True)` trên các core đã ghim phải < 10%; không chạy job nền khác trên 2 core đó. Windows: bật plan High performance, cắm điện. Nếu không kiểm soát được, ghi vào `_env.notes`, đừng im lặng.
4. Không đo trong IDE debug, không bật profiler, `gc.collect()` rồi `gc.disable()` trong vòng đo.

## Bước 3. Vòng đo
```python
import time, gc, statistics as st, numpy as np
def bench(fn, warmup=20, n=300):
    for _ in range(warmup): fn()                 # bỏ đi
    gc.collect(); gc.disable()
    t = []
    for _ in range(n):
        a = time.perf_counter_ns(); fn(); t.append((time.perf_counter_ns()-a)/1e6)
    gc.enable()
    return np.array(t)
with torch.inference_mode():
    t = bench(lambda: model(x))
```
- Khởi động >= 20 lần bỏ đi, đo >= 200 lần (khuyến nghị 300). Dùng `perf_counter_ns`, không dùng `time.time`.
- Lặp lại cả phép đo 3 lượt (tiến trình mới mỗi lượt) để thấy dao động giữa các lần chạy; báo median của 3 median và khoảng min-max.
- Đầu ra của `fn` phải được dùng/giữ (tránh bị tối ưu bỏ), nhưng không `.item()`/copy trong vùng đo nếu không thuộc phạm vi.

## Bước 4. Ghi results/
```python
q1, med, q3 = np.percentile(t, [25, 50, 75])
rng = np.random.default_rng(0)
boots = [np.median(rng.choice(t, len(t))) for _ in range(2000)]
out = {"target": {"component": "...", "ckpt_sha256": "...", "dtype": "fp32", "batch": 1, "seq_len": 128,
                  "scope": "forward only"},
       "unit": "ms", "n": len(t), "warmup": 20,
       "median": med, "iqr": [q1, q3], "p95": np.percentile(t, 95),
       "median_ci95": list(np.percentile(boots, [2.5, 97.5])),
       "_env": {"cpu": platform.processor(), "cpu_model": "<tên CPU đầy đủ>", "cores_pinned": CORES,
                "threads": 2, "os": platform.platform(), "python": platform.python_version(),
                "torch": torch.__version__, "numpy": np.__version__, "power_plan": "...", "notes": "..."},
       "_src": {"script": "experiments/bench_<tên>.py", "cmd": "...", "date": datetime.date.today().isoformat()}}
```
Lưu cả mảng thô `t` vào `results/latency_<tên>_raw.csv` để dựng lại được. Tên CPU lấy từ `wmic cpu get name` hoặc `/proc/cpuinfo`, không gõ tay theo trí nhớ.

## Bước 5. Thay số trong paper
- Sinh macro (`\latencyMedianMs` định dạng `{:.1f}`) từ json qua script macro hiện có; sửa `main.tex` bằng Edit.
- Paper viết "2.5 ms" chỉ khi median đo lại làm tròn ra 2.5 trong cùng điều kiện. Lệch thì dùng số mới và báo sếp số cũ sai bao nhiêu; không chọn số đẹp.
- Câu trong paper nêu đủ: CPU, 2 thread ghim core, batch, phạm vi đo, median (và IQR hoặc CI).
- Thêm dòng vào `evidence/repro.md`: lệnh đã chạy.

## Tiêu chí xong
- Json có `median`, `iqr`, `p95`, `n >= 200`, `warmup`, `unit`, `target`, `_env` (CPU, core ghim, 2 thread, OS, phiên bản thư viện), `_src`.
- 3 lượt cho median cách nhau < ~5%; nếu lệch hơn, xác định nguồn nhiễu rồi đo lại.
- Số trong paper là macro, `check_numbers.py --prose` ra `MATCH`.

## Lỗi hay gặp
- Đặt `OMP_NUM_THREADS` sau khi đã import torch/numpy: thực tế chạy nhiều hơn 2 thread.
- Quên ghim core hoặc ghim vào core đang bận: đuôi p95 phình to.
- Lần gọi đầu chậm (cấp phát, nạp thư viện): thiếu khởi động.
- Đo cả tokenize/copy dữ liệu rồi gọi là "độ trễ của mô hình".
- Chỉ báo trung bình: bị đuôi lệch kéo; dùng median + IQR/p95.
- Quên `inference_mode`/`eval()`: dropout hoặc autograd làm lệch số.
- Đo trên máy khác máy mô tả trong paper: `_env` phải là máy thật đã đo.
- Chép số từ log cũ vào paper thay vì chạy lại.
