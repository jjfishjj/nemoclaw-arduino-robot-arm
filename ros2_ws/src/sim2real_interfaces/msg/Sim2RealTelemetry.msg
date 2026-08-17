# Stable telemetry boundary shared by Isaac Sim, HIL bridge, and dashboard.
std_msgs/Header header
uint32 episode
string phase
string message
string backend
float32 success_rate
float32 sim_success_rate
uint32 latency_ms
float32[] joint_errors_deg
bool running
bool estop_latched
