"""Exercise the production LVGL setup, flush callback and RGB565 copy path."""

from pathlib import Path
import subprocess

import pytest

from test_esp_screenshot_dynamic import PLATFORM


COMPONENT = Path(__file__).resolve().parents[1] / "esphome/components/esp_screenshot"

LVGL = r'''
enum lv_color_format_t {LV_COLOR_FORMAT_RGB565, LV_COLOR_FORMAT_RGB565_SWAPPED,
                        LV_COLOR_FORMAT_RGB888};
enum lv_display_render_mode_t {LV_DISPLAY_RENDER_MODE_PARTIAL,
                              LV_DISPLAY_RENDER_MODE_DIRECT, LV_DISPLAY_RENDER_MODE_FULL};
constexpr int LV_EVENT_FLUSH_START=1;
struct lv_area_t {int x1,y1,x2,y2;};
struct lv_draw_buf_t {struct {unsigned stride;} header;uint8_t *data;};
struct lv_event_t {void *user_data;const lv_area_t *area;};
using lv_event_cb_t=void(*)(lv_event_t*);
struct lv_display_t {
 lv_color_format_t format=LV_COLOR_FORMAT_RGB565;
 lv_display_render_mode_t mode=LV_DISPLAY_RENDER_MODE_PARTIAL;
 int x=0,y=0,width=4,height=3;lv_draw_buf_t *buffer=nullptr;
 lv_event_cb_t callback=nullptr;void *user_data=nullptr;std::function<void()> refresh;
};
inline auto lv_display_get_color_format(lv_display_t*d){return d->format;}
inline auto lv_display_get_render_mode(lv_display_t*d){return d->mode;}
inline int lv_display_get_offset_x(lv_display_t*d){return d->x;}
inline int lv_display_get_offset_y(lv_display_t*d){return d->y;}
inline int lv_display_get_horizontal_resolution(lv_display_t*d){return d->width;}
inline int lv_display_get_vertical_resolution(lv_display_t*d){return d->height;}
inline unsigned lv_display_get_event_count(lv_display_t*d){return d->callback?1:0;}
inline void lv_display_add_event_cb(lv_display_t*d,lv_event_cb_t cb,int,void*ctx){d->callback=cb;d->user_data=ctx;}
inline void lv_display_remove_event_cb_with_user_data(lv_display_t*d,lv_event_cb_t cb,void*ctx){
 assert(d->callback==cb&&d->user_data==ctx);d->callback=nullptr;d->user_data=nullptr;
}
inline void *lv_display_get_screen_active(lv_display_t*d){return d;}
inline void lv_obj_invalidate(void*){}
inline void lv_refr_now(lv_display_t*d){d->refresh();}
inline void *lv_event_get_user_data(lv_event_t*e){return e->user_data;}
inline const void *lv_event_get_param(lv_event_t*e){return e->area;}
inline lv_draw_buf_t *lv_display_get_buf_active(lv_display_t*d){return d->buffer;}
inline int lv_area_get_width(const lv_area_t*a){return a->x2-a->x1+1;}
inline int lv_area_get_height(const lv_area_t*a){return a->y2-a->y1+1;}
namespace esphome::lvgl {
struct LvglComponent {
 lv_display_t display;bool paused=false;
 lv_display_t *get_disp(){return &display;}bool is_paused(){return paused;}
};
}
'''

DRIVER = r'''
#include "esp_screenshot.h"
#include <array>
using namespace esphome::esp_screenshot;
struct Probe:EspScreenshot {
 using EspScreenshot::pixels_;using EspScreenshot::copy_display_;
 using EspScreenshot::fail_setup_;using EspScreenshot::worker_handle_;
};
int main(){
 esphome::web_server_base::WebServerBase server;
 const std::array<uint16_t,12> colors={0xf800,0x07e0,0x001f,0xffff,
                                    0x0000,0x1234,0xabcd,0x8410,
                                    0xffe0,0xf81f,0x07ff,0x4208};
 std::array<uint8_t,24> expected{},native{};
 for(size_t i=0;i<colors.size();i++){
   expected[i*2]=uint8_t(colors[i]);expected[i*2+1]=uint8_t(colors[i]>>8);
 }
 for(auto format:{LV_COLOR_FORMAT_RGB565,LV_COLOR_FORMAT_RGB565_SWAPPED}){
   esphome::lvgl::LvglComponent lvgl;auto &d=lvgl.display;d.format=format;
   Probe p;p.set_lvgl(&lvgl);p.set_web_server(&server);p.set_max_jpeg_size(4096);p.setup();
   assert(!p.is_failed()&&p.worker_handle_&&platform::allocations.size()==5);
   const auto allocation_calls=platform::calls;
   auto emit=[&](lv_area_t area){
     // Padded, nonzero-origin rectangles and repeated coverage all use the
     // actual component callback and FrameAssembler, never a test copy.
     std::array<uint8_t,24> input;input.fill(0xa5);
     const unsigned width=lv_area_get_width(&area),height=lv_area_get_height(&area);
     for(unsigned row=0;row<height;row++)for(unsigned col=0;col<width;col++){
       auto color=colors[(area.y1+row)*4+area.x1+col];auto *pixel=input.data()+row*12+col*2;
       pixel[0]=uint8_t(format==LV_COLOR_FORMAT_RGB565?color:color>>8);
       pixel[1]=uint8_t(format==LV_COLOR_FORMAT_RGB565?color>>8:color);
     }
     const auto immutable=input;lv_draw_buf_t buffer{{12},input.data()};d.buffer=&buffer;
     lv_event_t event{d.user_data,&area};d.callback(&event);
     assert(input==immutable);d.buffer=nullptr;
   };
   d.refresh=[&](){emit({0,0,3,0});emit({0,1,3,2});emit({1,1,2,1});};
   assert(p.copy_display_()&&!d.callback);
   assert(platform::calls==allocation_calls);
   assert(std::memcmp(p.pixels_,expected.data(),expected.size())==0);
   if(format==LV_COLOR_FORMAT_RGB565)std::memcpy(native.data(),p.pixels_,native.size());
   else assert(std::memcmp(p.pixels_,native.data(),native.size())==0);
   lvgl.paused=true;assert(!p.copy_display_());lvgl.paused=false;
   d.refresh=[&](){emit({0,0,3,0});};assert(!p.copy_display_()&&!d.callback);
   p.fail_setup_("host worker finished");assert(platform::allocations.empty());
 }
 // The new format is the only expansion: offsets and other render modes
 // still fail before any resource allocation or worker is admitted.
 for(int rejected=0;rejected<5;rejected++){
   esphome::lvgl::LvglComponent lvgl;auto &d=lvgl.display;
   if(rejected==0)d.format=LV_COLOR_FORMAT_RGB888;
   if(rejected==1)d.mode=LV_DISPLAY_RENDER_MODE_DIRECT;
   if(rejected==2)d.mode=LV_DISPLAY_RENDER_MODE_FULL;
   if(rejected==3)d.x=1;
   if(rejected==4)d.y=1;
   const auto allocation_calls=platform::calls;
   Probe p;p.set_lvgl(&lvgl);p.set_web_server(&server);p.setup();
   assert(p.is_failed()&&!p.worker_handle_&&!p.capture());
   assert(platform::calls==allocation_calls&&platform::allocations.empty());
 }
}
'''


@pytest.mark.parametrize("mutation", [None, "legacy_guard", "omit_normalization"])
def test_lvgl_setup_and_flush_normalize_identical_images(tmp_path, mutation):
    platform = PLATFORM.replace(
        "inline int jpeg_enc_open(jpeg_enc_config_t*,void **out){",
        "inline int jpeg_enc_open(jpeg_enc_config_t*cfg,void **out){"
        "assert(cfg->src_type==JPEG_PIXEL_FORMAT_RGB565_LE);",
    )
    (tmp_path / "platform.h").write_text(platform + LVGL)
    headers = [
        "esphome/components/text_sensor/text_sensor.h",
        "esphome/components/web_server_base/web_server_base.h",
        "esphome/components/lvgl/lvgl_esphome.h",
        "esphome/core/automation.h", "esphome/core/component.h",
        "esphome/core/hal.h", "esphome/core/log.h", "esp_heap_caps.h",
        "esp_random.h", "esp_jpeg_enc.h", "freertos/FreeRTOS.h",
        "freertos/semphr.h", "freertos/task.h",
    ]
    for name in headers:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#include "platform.h"\n')
    component = tmp_path / "component"
    component.mkdir()
    for name in ("esp_screenshot.cpp", "esp_screenshot.h", "snapshot_store.h"):
        text = (COMPONENT / name).read_text()
        if name == "esp_screenshot.cpp" and mutation == "legacy_guard":
            needle = "format != LV_COLOR_FORMAT_RGB565_SWAPPED"
            assert text.count(needle) == 1
            text = text.replace(needle, "true")
        if name == "snapshot_store.h" and mutation == "omit_normalization":
            assert text.count("if (swapped) {") == 1
            text = text.replace("if (swapped) {", "if (false && swapped) {")
        (component / name).write_text(text)
    source = tmp_path / "lvgl.cpp"
    source.write_text(DRIVER)
    binary = tmp_path / "lvgl"
    subprocess.run([
        "g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-DUSE_ESP_SCREENSHOT_LVGL", "-I", str(tmp_path), "-I", str(component),
        str(source), str(component / "esp_screenshot.cpp"), "-o", str(binary),
    ], check=True, capture_output=True, text=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True)
    if mutation is None:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0, "The pixel/setup oracle accepted the broken candidate"
        assert "Assertion" in result.stderr or "AddressSanitizer" in result.stderr, result.stderr
