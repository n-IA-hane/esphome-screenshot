"""Select and exercise the public driver-owned composed-frame readback."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from screenshot_lvgl_fixture import LVGL
from test_esp_screenshot_dynamic import PLATFORM

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "esphome/components/esp_screenshot"


@pytest.fixture(scope="module")
def screenshot_schema():
    spec = importlib.util.spec_from_file_location("screenshot_schema", COMPONENT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lvgl_owner_selects_advertised_composed_readback(screenshot_schema, monkeypatch):
    from esphome.core import CORE, ID
    from esphome.final_validate import full_config

    # The public display schema advertises readback; ordinary displays do not.
    screen, ui = ID("screen"), ID("ui")
    monkeypatch.setitem(CORE.data, "mipi_dsi", {"framebuffer_readback_ids": [ID("screen")]})
    config = {"lvgl_id": ui, "path": "screen", "task_stack_in_psram": False,
              "buffer_in_psram": False, "rotation": 90}
    token = full_config.set({"lvgl": [{"id": ui, "displays": [screen], "rotation": 270}],
                             "esp_screenshot": [config]})
    try:
        validated = screenshot_schema.FINAL_VALIDATE_SCHEMA(config)
    finally:
        full_config.reset(token)
    assert str(validated["_framebuffer_display_id"]) == "screen"
    assert validated["rotation"] == 90  # Additional output rotation only.


@pytest.mark.parametrize("capable,legacy", [(False, False), (False, True), (True, True)])
def test_unadvertised_display_uses_lvgl_and_legacy_readback_needs_no_lvgl(
    screenshot_schema, monkeypatch, capable, legacy
):
    from esphome.core import CORE, ID
    from esphome.final_validate import full_config

    screen, ui = ID("screen"), ID("ui")
    monkeypatch.setitem(CORE.data, "mipi_dsi", {
        "framebuffer_readback_ids": [screen] if capable else []
    })
    config = {"mipi_dsi_id" if legacy else "lvgl_id": screen if legacy else ui,
              "path": "screen", "task_stack_in_psram": False, "buffer_in_psram": False}
    token = full_config.set({"esp_screenshot": [config], "lvgl": [] if capable else [
        {"id": ui, "displays": [screen]}
    ]})
    try:
        validated = screenshot_schema.FINAL_VALIDATE_SCHEMA(config)
    finally:
        full_config.reset(token)
    if capable:
        assert str(validated["_framebuffer_display_id"]) == "screen"
        assert "lvgl_id" not in validated
    else:
        assert "_framebuffer_display_id" not in validated
        assert str(validated["lvgl_id"]) == "ui"


def test_ambiguous_readback_requires_explicit_display(screenshot_schema, monkeypatch):
    from esphome.core import CORE, ID
    from esphome.final_validate import full_config
    import esphome.config_validation as cv

    screens, ui = [ID("screen"), ID("other")], ID("ui")
    monkeypatch.setitem(CORE.data, "mipi_dsi", {"framebuffer_readback_ids": screens})
    config = {"lvgl_id": ui}
    token = full_config.set({"lvgl": [{"id": ui, "displays": screens}]})
    try:
        with pytest.raises(cv.Invalid, match="multiple readback displays"):
            screenshot_schema.FINAL_VALIDATE_SCHEMA(config)
    finally:
        full_config.reset(token)


@pytest.mark.parametrize("with_lvgl", [False, True], ids=["mipi-only", "mixed-backends"])
def test_composed_readback_rotation_no_redraw_and_busy_retains_published_image(tmp_path, with_lvgl):
    (tmp_path / "platform.h").write_text(PLATFORM + LVGL)
    headers = [
        "esphome/components/text_sensor/text_sensor.h",
        "esphome/components/web_server_base/web_server_base.h",
        "esphome/components/lvgl/lvgl_esphome.h",
        "esphome/components/mipi_dsi/mipi_dsi.h", "esphome/core/automation.h",
        "esphome/core/component.h", "esphome/core/hal.h", "esphome/core/log.h",
        "esp_heap_caps.h", "esp_random.h", "esp_jpeg_enc.h",
        "freertos/FreeRTOS.h", "freertos/semphr.h", "freertos/task.h",
    ]
    for name in headers:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#include "platform.h"\n')
    source = tmp_path / "readback.cpp"
    source.write_text(r'''
#include "esp_screenshot.h"
#include <array>
using namespace esphome::esp_screenshot;
struct Probe:EspScreenshot {
 using EspScreenshot::pixels_;using EspScreenshot::busy_;using EspScreenshot::worker_;
 using EspScreenshot::stopping_;using EspScreenshot::fail_setup_;using EspScreenshot::width_;
 using EspScreenshot::height_;using EspScreenshot::pixel_size_;
 void encode(){unsigned wake=0;platform::wake=[&](){if(++wake>1)stopping_=true;};
  worker_();stopping_=false;platform::wake={};loop();}
};
int main(){
 esphome::web_server_base::WebServerBase server;
 // The driver boundary supplies its already composed/logically oriented image.
 // Literal pixels include an overlay absent from the separate LVGL composition.
 const std::array<uint8_t,12> composed={0,0xf8,0xe0,7,0x1f,0,0xff,0xff,0,0,0x34,0x12};
 for(unsigned rotation:{0,90,180,270})for(bool preallocate:{false,true}){
  esphome::mipi_dsi::MipiDsi display;display.width=3;display.height=2;
  display.readback=[&](uint8_t *out,size_t bytes,esphome::display::DisplayRotation extra){
   assert(unsigned(extra)==rotation&&bytes==composed.size());
   std::memcpy(out,composed.data(),bytes);return true;
  };
  esphome::text_sensor::TextSensor status,id;
  Probe p;p.set_mipi_display(&display);p.set_web_server(&server);p.set_rotation(rotation);
  p.set_max_jpeg_size(4096);p.set_preallocate_buffers(preallocate);
  p.set_capture_status_sensor(&status);p.set_capture_id_sensor(&id);
#ifdef USE_ESP_SCREENSHOT_LVGL
  // Even an available, paused LVGL owner must not be invalidated/refreshed.
  esphome::lvgl::LvglComponent lvgl;lvgl.paused=true;
  lvgl.display.refresh=[](){assert(false&&"readback must not redraw LVGL");};
  p.set_lvgl(&lvgl);
#endif
  p.setup();assert(!p.is_failed());
  assert(p.width_==(rotation==90||rotation==270?2U:3U));
  assert(p.height_==(rotation==90||rotation==270?3U:2U)&&p.pixel_size_==12);
  assert(p.capture());p.loop();assert(display.copies==1);
  assert(std::memcmp(p.pixels_,composed.data(),composed.size())==0);
  p.encode();assert(status.state=="Ready"&&!id.state.empty());
  auto first_id=id.state;AsyncWebServerRequest first;p.handleRequest(&first);
  display.copyable=false;assert(p.capture());p.loop();
  assert(!p.busy_&&id.state==first_id&&status.state.find("Error:")==0);
  AsyncWebServerRequest retained;p.handleRequest(&retained);assert(retained.body==first.body);
  // A later successful readback still publishes. Logical geometry changes fail
  // closed before invoking the driver with a buffer of obsolete dimensions.
  display.copyable=true;assert(p.capture());p.loop();p.encode();assert(id.state!=first_id);
  auto second_id=id.state;auto copies=display.copies;display.width=4;
  assert(p.capture());p.loop();assert(!p.busy_&&id.state==second_id&&display.copies==copies);
  p.fail_setup_("host worker finished");assert(platform::allocations.empty());
 }
}
''')
    binary = tmp_path / "readback"
    subprocess.run([
        "g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pthread",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-DUSE_ESP_SCREENSHOT_MIPI", *(["-DUSE_ESP_SCREENSHOT_LVGL"] if with_lvgl else []),
        "-I", str(tmp_path), "-I", str(COMPONENT), str(source),
        str(COMPONENT / "esp_screenshot.cpp"), "-o", str(binary),
    ], check=True, capture_output=True, text=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("selector", ["lvgl_id", "mipi_dsi_id"])
@pytest.mark.parametrize("rotation", [0, 90])
def test_mipi_owner_capability_real_schema_codegen(tmp_path, selector, rotation):
    source = os.environ.get("ESP_SCREENSHOT_MIPI_SOURCE")
    if not source:
        pytest.skip("ESP_SCREENSHOT_MIPI_SOURCE requires the public readback-capable display component")
    config = {
        "esphome": {"name": "screenshot-readback", "build_path": str(tmp_path / "build")},
        "esp32": {"board": "esp32-p4-evboard", "framework": {"type": "esp-idf"}},
        "network": {}, "psram": {}, "esp_ldo": [{"channel": 3, "voltage": "2.5V"}],
        "external_components": [
            {"source": {"type": "local", "path": str(COMPONENT.parent)},
             "components": ["esp_screenshot"]},
            {"source": {"type": "local", "path": source}, "components": ["mipi_dsi"]},
        ],
        "display": [{"platform": "mipi_dsi", "id": "screen", "model": "WAVESHARE-10.1-DSI-TOUCH-A",
                     "update_interval": "never", "auto_clear_enabled": False}],
        "lvgl": {"id": "ui", "displays": ["screen"], "rotation": 270},
        "esp_screenshot": {"id": "screen_capture", selector: "ui" if selector == "lvgl_id" else "screen",
                           "rotation": rotation},
    }
    path = tmp_path / "readback.yaml"
    path.write_text(yaml.safe_dump(config))
    result = subprocess.run([
        sys.executable, "-m", "esphome", "compile", str(path), "--only-generate"
    ], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    main = (tmp_path / "build/src/main.cpp").read_text()
    defines = (tmp_path / "build/src/esphome/core/defines.h").read_text()
    assert "screen_capture->set_mipi_display(screen)" in main
    assert "screen_capture->set_lvgl" not in main
    assert f"screen_capture->set_rotation(display::DISPLAY_ROTATION_{rotation}_DEGREES)" in main
    assert "#define USE_ESP_SCREENSHOT_MIPI" in defines
    assert "#define USE_ESP_SCREENSHOT_LVGL" not in defines
