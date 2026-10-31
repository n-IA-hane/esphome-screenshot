# Source provenance

The four component files were copied byte for byte from
[ESPHome Intercom commit `03436d6e433c6a4306f095fe4f1b01de389f0c2e`](https://github.com/n-IA-hane/esphome-intercom/tree/03436d6e433c6a4306f095fe4f1b01de389f0c2e/esphome/components/esp_screenshot).

The source directory was `esphome/components/esp_screenshot/`. The same path is
used here. This extraction changes packaging, examples and ownership of tests;
it does not refactor the capture, HTTP publication or worker implementation.

| File | SHA256 |
| --- | --- |
| `__init__.py` | `2de06c3ee47efb1ccda35ad9099526c7b9986a5945f3f7e5286cf669cb1de3e5` |
| `esp_screenshot.cpp` | `70635be34c2709ff3bb01ebba18f136f9de474b94e04be4c5d724d52d582037f` |
| `esp_screenshot.h` | `3d97cb8d65e08f48d084adf2ccaa79ca8103f11eb5c4f89bf622ac63a20cae89` |
| `snapshot_store.h` | `f4127d1b1c3780876f6eb86cf6525b18dca2a0b91a4aab228994f5dd701b5f2f` |

The original MIT [LICENSE](LICENSE) and generic native button/API package are
preserved. Screenshot-owned configuration and runtime tests live here; the
P4 provider-copy test and optional Home Assistant helper test remain in
Intercom, with their owning integrations.

The framebuffer provider remains Intercom's `mipi_dsi` implementation and must
provide `copy_frame_buffer_rgb565`. LVGL capture needs no Intercom component.
