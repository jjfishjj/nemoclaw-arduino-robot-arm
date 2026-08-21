# EdgeSense Forge — MVP 驗收標準

## 1. 驗收原則

- 每一條標準必須能由 UI、API、測試或匯出檔案觀察。
- 「畫面存在」不等於功能完成；核心流程必須真正傳遞資料。
- 模擬與真實硬體結果必須分開標示。
- 未通過阻斷性檢查時，不得顯示全案 PASS。

## 2. P0：主流程

### AC-01 有效需求生成方案

Given 使用者載入內建馬達監測需求
When 點擊生成方案
Then 系統顯示 ESP32、BME280、MPU6050、MQTT 與 Jetson 的結構化方案，且 Project Spec 可下載。

### AC-02 無效需求保留內容

Given 使用者輸入空白或少於必要資訊的需求
When 點擊生成
Then 顯示可操作的錯誤提示、不清除原輸入、不產生偽造方案。

### AC-03 未支援硬體

Given 需求包含 MVP 不支援的感測器
When 系統解析需求
Then 明確列出未支援元件與可用替代方案，不靜默替換。

### AC-04 模擬資料端到端

Given 已建立有效方案
When 使用者啟動 normal 模擬
Then telemetry 經 MQTT、schema validation 與 inference pipeline 後在 Dashboard 於 1 秒目標內更新。

### AC-05 異常警報

Given Live Lab 正在運行
When 使用者切換到 vibration anomaly
Then UI 顯示 `is_anomaly=true`、`VIBRATION_HIGH`、分數、engine 與 timestamp。

### AC-06 過熱警報

Given Live Lab 正在運行
When 使用者切換到 overheat
Then UI 顯示 `TEMP_HIGH`，且警報門檻與當前溫度可見。

### AC-07 格式錯誤資料

Given telemetry 缺少 device_id 或 timestamp
When edge service 收到 payload
Then 回報 validation failed、記錄原因，且不呼叫 inference adapter。

### AC-08 連線中斷

Given 裝置原本 online
When MQTT 或 edge service 中斷超過 freshness threshold
Then UI 顯示 offline／stale 與最後成功時間，不繼續顯示 online。

### AC-09 TensorRT 誠實狀態

Given 系統不在可用的 Jetson TensorRT 環境
When 使用者打開 Benchmark
Then TensorRT 顯示 unavailable，不呈現虛構 latency。

### AC-10 匯出不含 secrets

Given 使用者已填入本機 credential
When 匯出專案包
Then 匯出內容只含環境變數名稱或 placeholder，測試掃描不到明文 credential。

## 3. P1：品質與體驗

### AC-11 可重現模擬

相同 seed、情境與步數產生相同 telemetry 序列。

### AC-12 Benchmark 完整性

結果包含環境、engine、warm-up 次數、測量次數、平均、P50、P95 與 timestamp。

### AC-13 窄螢幕

在 360×800 viewport，主流程可操作、文字不被主要控制項遮住、無水平捲動。

### AC-14 鍵盤操作

需求輸入、生成、情境選擇、開始／暫停、分頁與匯出可使用鍵盤完成，焦點可見。

### AC-15 啟動文件

乾淨環境依 README 操作，可在 10 分鐘內啟動 local simulation 並看見第一筆 telemetry。

## 4. 測試矩陣

| 層級 | 必要測試 |
|---|---|
| Unit | Project Spec parser、rules、schema、scenario generator、alert evaluator |
| Contract | MQTT payload、inference response、benchmark result |
| Integration | Simulator → MQTT → ingest → inference → event store |
| UI | 生成方案、三種情境、離線、錯誤、匯出 |
| Deployment | Docker Compose local startup、Jetson runtime detection |
| Security | secret scan、invalid payload、log redaction |

## 5. Definition of Done

MVP 只有在以下條件全部成立時才完成：

- P0 AC-01 至 AC-10 全數通過。
- P1 不得有阻斷主流程的問題。
- local simulation 可由單一 documented command 啟動。
- 自動測試覆蓋所有 schema 與 alert 固定案例。
- 至少完成一次真實 Jetson benchmark，或明確將其標記為尚未驗證而不宣稱完成。
- README 包含架構圖、啟動方式、demo 劇本、已知限制與 benchmark 方法。

## 6. Phase B 驗收切片

下一階段 Web Prototype 的完成條件：

1. 有效與無效需求流程可操作。
2. 能生成固定但結構化的 Project Spec。
3. 能在前端執行三種 seeded 情境。
4. Dashboard 顯示 telemetry、score、reason 與 engine。
5. TensorRT 在非 Jetson 環境顯示 unavailable。
6. 桌面與 360px viewport 完成可用性檢查。

Phase B 可以先使用 in-memory pipeline；真正 MQTT 與 Python edge service 留到 Phase C。
