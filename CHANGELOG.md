# Changelog

## 2026.12.0-dev

- Preserve the standalone Core 10 compatibility gate and add four actual MIPI
  provider code-generation cases against the coordinated official Core 373.
  Require the selected source identities and reject skipped cases in that gate.
- Automatically select the display's public coherent MIPI readback from
  `lvgl_id` when that capability is advertised. Capture composed P4 UI and direct
  renderer video without requesting a redraw or exposing a framebuffer pointer.
  Keep the normal S3 LVGL refresh/coverage path and compile the MIPI backend only
  when selected by configuration.
- Preserve legacy `mipi_dsi_id`, configured IDs and native capture actions.
  Explicit screenshot rotation remains additional and is applied once, without
  repeating the display owner's rotation.
- Keep the last successful image when an on-demand allocation or encoding
  fails. Publish only a complete bounded JPEG, with existing readers retaining
  a valid image while the next capture is prepared.
- Document a native Home Assistant Image entity and Picture Glance setup so
  screenshots can coexist with the device's ordinary camera.

A busy readback retains the preceding JPEG and identifier. A display without
the public copy capability uses normal LVGL composition and cannot capture
unrelated writers outside that owner. No image server or periodic capture is added.

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
