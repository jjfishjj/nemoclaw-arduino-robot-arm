# Jetson TensorRT deployment

Run this directory on an NVIDIA Jetson Orin/Nano with JetPack and TensorRT installed.
TensorRT engines are hardware/runtime-specific and must be built on the target Jetson.

```bash
chmod +x jetson/*.sh
./jetson/build_engine.sh
./jetson/benchmark_tensorrt.sh
.venv/bin/python jetson/compare_engines.py --warmup 20 --iterations 200
```

The build uses FP16 and a fixed `features:1x2` input profile. The benchmark uses
`trtexec`, a 1-second warm-up and a 10-second measured duration. Keep the device in
a documented power mode (`sudo nvpmodel -q`) and record `tegrastats` alongside results.
`compare_engines.py` runs both engines, prints their P50/P95 and speedup, and saves
both measured records into the same SQLite benchmark history.

Do not commit `model.plan`: it is not portable between TensorRT/CUDA/Jetson versions.
