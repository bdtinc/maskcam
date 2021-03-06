import os
import configparser
from maskcam.common import CONFIG_FILE
from maskcam.prints import print_common as print

config = configparser.ConfigParser()
config.read(CONFIG_FILE)
config.sections()

# Environment variables overriding config file values
# Each row is: (ENV_VAR_NAME, (config-section, config-param))
ENV_CONFIG_OVERRIDES = (
    ("MASKCAM_INPUT", ("maskcam", "default-input")),  # Redundant with start.sh script
    ("MASKCAM_DEVICE_ADDRESS", ("maskcam", "device-address")),
    ("MASKCAM_DETECTION_THRESHOLD", ("face-processor", "detection-threshold")),
    ("MASKCAM_VOTING_THRESHOLD", ("face-processor", "voting-threshold")),
    ("MASKCAM_MIN_FACE_SIZE", ("face-processor", "min-face-size")),
    ("MASKCAM_DISABLE_TRACKER", ("face-processor", "disable-tracker")),
    ("MASKCAM_ALERT_MIN_VISIBLE_PEOPLE", ("maskcam", "alert-min-visible-people")),
    ("MASKCAM_ALERT_MAX_TOTAL_PEOPLE", ("maskcam", "alert-max-total-people")),
    ("MASKCAM_ALERT_NO_MASK_FRACTION", ("maskcam", "alert-no-mask-fraction")),
    ("MASKCAM_STATISTICS_PERIOD", ("maskcam", "statistics-period")),
    ("MASKCAM_TIMEOUT_INFERENCE_RESTART", ("maskcam", "timeout-inference-restart")),
    ("MASKCAM_CAMERA_FRAMERATE", ("maskcam", "camera-framerate")),
    ("MASKCAM_CAMERA_FLIP_METHOD", ("maskcam", "camera-flip-method")),
    ("MASKCAM_OUTPUT_VIDEO_WIDTH", ("maskcam", "output-video-width")),
    ("MASKCAM_OUTPUT_VIDEO_HEIGHT", ("maskcam", "output-video-height")),
    ("MASKCAM_INFERENCE_INTERVAL_AUTO", ("maskcam", "inference-interval-auto")),
    ("MASKCAM_INFERENCE_MAX_FPS", ("maskcam", "inference-max-fps")),
    ("MASKCAM_INFERENCE_LOG_INTERVAL", ("maskcam", "inference-log-interval")),
    ("MASKCAM_STREAMING_START_DEFAULT", ("maskcam", "streaming-start-default")),
    ("MASKCAM_STREAMING_PORT", ("maskcam", "streaming-port")),
    ("MASKCAM_FILESERVER_ENABLED", ("maskcam", "fileserver-enabled")),
    ("MASKCAM_FILESERVER_FORCE_SAVE", ("maskcam", "fileserver-force-save")),
    ("MASKCAM_FILESERVER_VIDEO_PERIOD", ("maskcam", "fileserver-video-period")),
    ("MASKCAM_FILESERVER_VIDEO_DURATION", ("maskcam", "fileserver-video-duration")),
    ("MASKCAM_FILESERVER_HDD_DIR", ("maskcam", "fileserver-hdd-dir")),
    ("MQTT_BROKER_IP", ("mqtt", "mqtt-broker-ip")),
    ("MQTT_BROKER_PORT", ("mqtt", "mqtt-broker-port")),
    ("MQTT_DEVICE_NAME", ("mqtt", "mqtt-device-name")),
    ("MQTT_DEVICE_DESCRIPTION", ("mqtt", "mqtt-device-description")),
)

# Apply overrides
for env_var, config_param in ENV_CONFIG_OVERRIDES:
    override_value = os.environ.get(env_var, None)
    if override_value is not None:
        config[config_param[0]][config_param[1]] = override_value


def print_config_overrides():
    # Leave prints separated so that it can be executed on demand
    # by one single process instead of each import
    for env_var, config_param in ENV_CONFIG_OVERRIDES:
        override_value = os.environ.get(env_var, None)
        if override_value is not None:
            print(f"\nConfig override {env_var}={override_value}")
