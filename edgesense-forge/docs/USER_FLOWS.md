# EdgeSense Forge — 使用流程

## Flow 1：從需求建立方案

1. 使用者進入首頁，看到預設的馬達監測範例。
2. 使用者輸入或套用需求。
3. 系統先驗證長度、支援元件與必要資訊。
4. 系統把需求轉換成結構化 Project Spec。
5. 使用者看到資料流、硬體摘要、MQTT schema 與安全檢查。
6. 使用者可以修改採樣率、裝置 ID 或警報門檻並重新生成。

失敗路徑：

- 空白需求：提示輸入監測對象、感測資料及輸出行為。
- 未支援硬體：保留原始需求，標示未支援項目與 MVP 可用替代方案。
- 參數超出安全範圍：阻止生成 PASS 狀態並說明原因。

## Flow 2：在 Live Lab 驗證資料與警報

1. 使用者選擇 normal 情境並開始模擬。
2. Dashboard 顯示 telemetry、裝置 online 與 anomaly score。
3. 使用者切換到 overheat。
4. 下一批資料經同一 schema validator 與 inference pipeline。
5. Dashboard 顯示警報、原因碼與觸發門檻。
6. 使用者暫停或重設情境。

邊界狀態：

- payload 缺欄位：顯示 validation failed，不進入推論。
- timestamp 過期：裝置狀態顯示 stale。
- edge service 中斷：保留最後資料並標示 disconnected。

## Flow 3：比較推論引擎

1. 使用者進入 Benchmark 分頁。
2. 系統偵測可用 engine。
3. 在一般電腦上，只允許執行 baseline／ONNX Runtime；TensorRT 顯示 unavailable。
4. 在 Jetson 上，使用者執行 baseline 與 TensorRT 測試。
5. 系統完成 warm-up 後收集固定樣本數。
6. 使用者比較平均、P50、P95 latency 與資源資訊。
7. 結果附環境 metadata，可匯出為 JSON 或 Markdown 摘要。

## Flow 4：匯出原型包

1. 使用者確認方案與 checks 狀態。
2. 點擊匯出。
3. 系統產生不含 secrets 的專案包。
4. 專案包包含設定、schema、韌體範本、edge config 和啟動說明。
5. 若存在阻斷性檢查，匯出仍可進行，但檔案與 UI 都標示 DRAFT／NOT VERIFIED。

## Demo 劇本（3 分鐘）

1. 以一句自然語言生成馬達監測方案。
2. 展開 MQTT schema 與硬體安全檢查。
3. 啟動 normal 模擬，展示即時 telemetry。
4. 切換 vibration anomaly，展示警報與原因碼。
5. 開啟 Benchmark，說明實測與 unavailable 的誠實標示。
6. 匯出原型包，收尾於「需求到部署證據」的產品價值。
