# EdgeSense Forge — Product Requirements Document

版本：0.1
階段：MVP 規格
日期：2026-07-29

## 1. 產品摘要

EdgeSense Forge 將自然語言描述的設備監測需求，轉換成一套可執行的 Edge AI 原型方案。MVP 聚焦在 ESP32 感測端、MQTT 傳輸、Jetson 邊緣推論與 Web Dashboard，並提供 CPU／ONNX Runtime 與 TensorRT 推論比較。

產品不是通用電路 CAD，也不承諾自動產生可直接量產的硬體。它的價值是縮短「想法 → 可驗證原型」的距離，同時把接線、資料契約、模型與部署風險顯性化。

## 2. 問題

建立一個 Edge AI IoT 原型通常要跨越硬體選型、韌體、通訊協定、資料格式、模型部署與效能驗證。對產品經理、應用開發者與教學使用者而言，困難不是單一技術，而是缺乏一條能被檢查和重現的端到端流程。

目前常見工具的缺口：

- 電路工具能畫接線，但不處理 edge inference 與資料契約。
- AI notebook 能展示模型，但不描述感測器資料如何進入系統。
- Dashboard 能顯示資料，但無法證明模型是否適合在 Jetson 上部署。
- 生成式 AI 可產生程式片段，但容易忽略電壓、共地、topic、schema 與離線狀態。

## 3. 目標與非目標

### 3.1 MVP 目標

1. 使用者能輸入設備異常監測需求並產生結構化方案。
2. 方案包含支援的硬體、接線摘要、MQTT topics 與 JSON schema。
3. 不需實體硬體即可模擬正常、過熱與異常震動資料。
4. Edge service 能接收資料、產生異常分數與警報。
5. Dashboard 能說明資料從裝置到推論結果的完整路徑。
6. 在有 Jetson 的環境中可比較 baseline 與 TensorRT 的推論指標；沒有 Jetson 時顯示清楚的未執行狀態，不偽造數據。
7. 產生可下載或複製的設定、韌體範本與部署說明。

### 3.2 非目標

- 不支援任意 MCU、感測器或電路拓撲。
- 不取代資料表、電氣審查或安全認證。
- 不在 MVP 自動訓練客戶的生產模型。
- 不提供雲端 fleet management、OTA 更新或多租戶帳號系統。
- 不做通用 LLM agent 或自由生成未經驗證的 GPIO 接線。
- 不宣稱 TensorRT 一定優於所有 baseline；以實測結果為準。

## 4. 目標使用者

### Persona A：AI／IoT 應用開發者

- 想快速驗證 ESP32 + Jetson 架構。
- 熟悉 Python 或 Arduino，但不一定熟悉完整部署鏈。
- 成功標準：30 分鐘內跑通模擬資料到異常警報。

### Persona B：Solution Architect／Technical PM

- 需要向客戶或團隊展示可落地的 edge AI 方案。
- 關心架構選擇、風險、成本與驗收指標。
- 成功標準：能從需求生成一套可討論、可匯出的方案。

### Persona C：教學者／工作坊學員

- 需要理解 sensor-to-edge 的資料路徑。
- 成功標準：不用真實硬體也能操作三種情境並觀察結果。

## 5. 核心使用情境

預設情境：工廠馬達狀態監測。

使用者輸入：

> 使用 ESP32 收集設備溫度與三軸震動，透過 MQTT 傳給 Jetson。Jetson 在本地判斷設備是否異常，超過門檻時顯示告警。

系統輸出：

- 支援矩陣：ESP32、BME280、MPU6050、Jetson。
- GPIO／I2C 接線摘要與電氣注意事項。
- `telemetry`, `status`, `alert` 三組 MQTT topics。
- telemetry JSON schema 與範例 payload。
- ESP32 韌體範本與 edge service 設定。
- 正常、過熱、異常震動三種資料模擬。
- 即時讀值、異常分數、警報原因與連線狀態。
- baseline／TensorRT benchmark 結果或「尚未於 Jetson 執行」。

## 6. 五區塊產品 Brief

### Goal

讓使用者從設備監測需求建立一條可觀察、可驗證、可部署的 sensor-to-edge 原型。

### Input

- 自然語言需求。
- 應用模板：馬達監測。
- 裝置識別碼、採樣頻率與警報門檻。
- 模擬情境：正常、過熱、異常震動。
- 執行環境：local simulation 或 Jetson。

### Output

- 結構化方案與支援／不支援提示。
- 接線摘要與安全檢查。
- MQTT topic map 與 JSON schema。
- 即時 telemetry、inference 和 alert 狀態。
- 可匯出的設定、程式範本與部署步驟。
- 真實 benchmark 或明確的未執行狀態。

### Layout

- 左側：需求、模板與方案設定。
- 中央：sensor → MQTT → Jetson → alert 的資料流視圖。
- 右側：方案細節，分為 Wiring、Schema、Code、Checks、Benchmark。
- 下方或次頁：Live Lab，控制情境並查看 telemetry 與推論紀錄。
- 窄螢幕：改成步驟式單欄，不產生水平捲動。

### Features

- 範例需求一鍵帶入。
- 需求驗證與不支援項目說明。
- 規則式方案生成，輸出可重現。
- 模擬資料播放器與即時狀態。
- 推論結果附原因碼與閾值資訊。
- 複製／下載產物。
- 空白、載入、錯誤、離線與 Jetson unavailable 狀態。

## 7. 功能需求

### FR-01 需求輸入

- 使用者可輸入 20–500 字需求。
- 系統提供一個馬達監測範例。
- 空白或資訊不足時，不生成方案並提供可行修正。

### FR-02 方案解析

- MVP 僅接受 ESP32 + BME280 + MPU6050 + MQTT + Jetson 組合。
- 系統把需求正規化為裝置、感測欄位、採樣率、推論方式與警報條件。
- 不支援的元件不得靜默替換，必須標示原因與建議。

### FR-03 硬體與安全檢查

- 顯示 I2C pins、3.3V、GND 與共地要求。
- 顯示「原型輔助、上電前核對板型與資料表」警告。
- 電壓或 pin 衝突時阻止輸出 PASS。

### FR-04 MQTT 契約

- 產生版本化 topic：`edgesense/v1/{device_id}/telemetry|status|alert`。
- telemetry 至少包含 `schema_version`, `device_id`, `ts`, `temperature_c`, `accel_rms_g`, `sample_rate_hz`。
- 狀態包含 online/offline 與最後接收時間。
- MVP 設定頁提示正式環境使用 TLS 與 credential isolation。

### FR-05 模擬器

- 可切換 normal、overheat、vibration anomaly。
- 使用固定 seed 時，同一情境可重現。
- 可開始、暫停、重設。
- 模擬資料走與真實裝置相同的 validation 與 inference 介面。

### FR-06 Edge inference

- MVP baseline 為可解釋的規則或輕量 anomaly score。
- 模型介面必須可替換為 ONNX Runtime／TensorRT adapter。
- 回傳 `score`, `is_anomaly`, `reason_codes`, `engine`, `latency_ms`。
- 無模型或模型載入失敗時不得輸出正常結果，必須進入 degraded state。

### FR-07 Dashboard

- 顯示連線狀態、最新 telemetry、異常分數、engine 與警報紀錄。
- 異常狀態不能只靠顏色表達。
- 資料過期時顯示 stale，而不是延續 online。

### FR-08 Benchmark

- 分開記錄 warm-up 與測量區間。
- 至少顯示平均、P50、P95 latency、樣本數與 engine。
- 若不是在 Jetson／TensorRT 環境執行，明確顯示 unavailable 或 simulated，不以模擬值冒充實測。

### FR-09 匯出

- 可輸出 `project.json`, MQTT schema、ESP32 範本、edge config 與 README。
- 匯出內容不得包含實際 Wi-Fi、MQTT 密碼或 token。

## 8. 非功能需求

- 可重現性：相同 spec version 和相同輸入產生相同核心設定。
- 可觀察性：每筆事件保留 device、timestamp、engine 和 validation 狀態。
- 效能：本地模擬時，Dashboard 更新延遲目標小於 1 秒。
- 韌性：MQTT 中斷後採退避重連；UI 顯示離線與最後成功時間。
- 安全：secret 只從環境變數讀取；log 不輸出 credential。
- 可近用性：鍵盤可操作、焦點可見、文字對比符合 WCAG AA 目標。
- 響應式：360px 寬度不出現橫向捲動。
- 文件：新使用者依 README 可在 10 分鐘內啟動模擬模式。

## 9. 成功指標

- Time to First Signal：首次啟動至看到 telemetry 小於 10 分鐘。
- Main Journey Completion：內部測試 5 次至少 4 次無協助完成。
- Alert Correctness：三個內建情境得到預期狀態，100% 通過固定測試資料。
- Contract Validity：所有內建 payload 通過 schema validation。
- Evidence Quality：benchmark 清楚標示硬體、engine、樣本數與是否實測。
- Demo Readiness：三分鐘內可完成需求生成、模擬異常與查看 benchmark 的展示。

## 10. 產品決策原則

1. 可驗證優先於支援數量。
2. 規則與 schema 優先於自由生成。
3. 真實測量與模擬數據必須清楚分離。
4. MVP 先證明一條完整路徑，再增加感測器與模型。
5. NVIDIA 技術的價值用部署與 benchmark 證明，不只出現在介面文案。
