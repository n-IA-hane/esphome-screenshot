# Changelog

## 2026.11.1-dev

- Extract `esp_screenshot` from ESPHome Intercom without changing its four core
  implementation files.
- Provide standalone LVGL capture, bounded JPEG publication and HTTP access
  using ESPHome and Espressif's software JPEG codec.
- Include the optional native button/API package, complete S3 example, P4
  provider fragment, configuration/code-generation tests and host runtime tests.
- Keep the synchronized P4 `mipi_dsi` driver and its tests in Intercom. The
  optional framebuffer backend requires its `copy_frame_buffer_rgb565` API.

This extraction adds packaging and validation. It does not claim new physical
hardware qualification.
