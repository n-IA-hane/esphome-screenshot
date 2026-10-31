"""Run the complete production component against allocator/task/HTTP boundaries.

JPEG encoding is a platform boundary here. Actual codec pixels remain a device
qualification; allocation, publication, worker code and HTTP leases are real.
"""
from pathlib import Path
import subprocess
import pytest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "esphome/components/esp_screenshot"


PLATFORM = r'''
#pragma once
#include <algorithm>
#include <atomic>
#include <cassert>
#include <condition_variable>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <map>
#include <mutex>
#include <string>
#include <vector>
constexpr uint32_t MALLOC_CAP_8BIT=1,MALLOC_CAP_INTERNAL=2,MALLOC_CAP_SPIRAM=4,MALLOC_CAP_DMA=8;
constexpr int JPEG_PIXEL_FORMAT_RGB565_LE=1,JPEG_SUBSAMPLE_444=1,JPEG_ERR_OK=0;
constexpr int HTTP_GET=0,portMAX_DELAY=1,pdTRUE=1,tskNO_AFFINITY=0x7fffffff;
constexpr unsigned portNUM_PROCESSORS=2;
using StackType_t=uint8_t;using TaskHandle_t=void*;
struct StaticTask_t {};
struct StaticSemaphore_t {std::mutex value;};
using SemaphoreHandle_t=std::mutex*;
inline SemaphoreHandle_t xSemaphoreCreateMutexStatic(StaticSemaphore_t *s){return &s->value;}
inline int xSemaphoreTake(SemaphoreHandle_t m,int){m->lock();return 1;}
inline void xSemaphoreGive(SemaphoreHandle_t m){m->unlock();}
namespace platform {
struct Allocation {size_t bytes;uint32_t caps;};
inline std::map<void*,Allocation> allocations;
inline size_t calls=0,fail_call=0,budget=100000000,peak=0;
inline bool fail_shrink=false,encode_failure=false;
inline uint8_t pattern=17;
inline std::function<void()> wake;
inline size_t bytes(){size_t total=0;for(auto &entry:allocations)total+=entry.second.bytes;return total;}
}
inline void *heap_caps_malloc(size_t bytes,uint32_t caps){
 if(++platform::calls==platform::fail_call||bytes>platform::budget-platform::bytes())return nullptr;
 auto *p=std::malloc(bytes);assert(p);platform::allocations[p]={bytes,caps};
 platform::peak=std::max(platform::peak,platform::bytes());return p;
}
inline void *heap_caps_aligned_alloc(size_t,size_t bytes,uint32_t caps){return heap_caps_malloc(bytes,caps);}
inline void heap_caps_free(void *p){if(p){assert(platform::allocations.erase(p)==1);std::free(p);}}
inline void *heap_caps_realloc(void *p,size_t bytes,uint32_t caps){
 auto old=platform::allocations.at(p);assert(bytes<=old.bytes&&caps==old.caps);
 if(platform::fail_shrink)return nullptr;
 auto *next=std::malloc(bytes);assert(next);std::memcpy(next,p,bytes);
 heap_caps_free(p);platform::allocations[next]={bytes,caps};return next;
}
inline size_t heap_caps_get_free_size(uint32_t){return platform::budget-platform::bytes();}
inline size_t heap_caps_get_largest_free_block(uint32_t caps){return heap_caps_get_free_size(caps);}
inline uint32_t esp_random(){return 42;}
inline uint32_t millis(){return 1;}
inline unsigned uxTaskGetStackHighWaterMark(TaskHandle_t){return 100;}
inline void xTaskNotifyGive(TaskHandle_t){}
inline unsigned ulTaskNotifyTake(int,int){platform::wake();return 1;}
inline void vTaskDelete(void*){}
inline TaskHandle_t xTaskCreateStaticPinnedToCore(void(*)(void*),const char*,size_t,void*,unsigned,StackType_t*,StaticTask_t*,int){return reinterpret_cast<void*>(2);}
struct jpeg_enc_config_t{unsigned width{},height{};int src_type{},subsampling{},quality{};bool task_enable{};};
#define DEFAULT_JPEG_ENC_CONFIG() jpeg_enc_config_t{}
using jpeg_enc_handle_t=void*;
inline int jpeg_enc_open(jpeg_enc_config_t*,void **out){*out=reinterpret_cast<void*>(1);return 0;}
inline void jpeg_enc_close(void*){}
inline int jpeg_enc_process(void*,uint8_t *raw,int,uint8_t *out,int capacity,int *size){
 assert(raw&&platform::allocations.count(raw)&&capacity>=50);
 if(platform::encode_failure){*size=0;return 1;}
 std::memset(out,platform::pattern++,50);*size=50;return 0;
}
template<typename... Args>inline void sink(Args...args){((void)args,...);}
#define ESP_LOGE(...) sink(__VA_ARGS__)
#define ESP_LOGW(...) sink(__VA_ARGS__)
#define ESP_LOGI(...) sink(__VA_ARGS__)
#define ESP_LOGD(...) sink(__VA_ARGS__)
#define ESP_LOGCONFIG(...) sink(__VA_ARGS__)
namespace esphome {
namespace setup_priority {constexpr float LATE=0;}
struct Component {
 bool failed=false,loop_enabled=false;
 virtual ~Component()=default;
 virtual void setup(){} virtual void loop(){} virtual void dump_config(){} virtual void on_shutdown(){}
 virtual float get_setup_priority()const{return 0;}
 void mark_failed(){failed=true;} bool is_failed()const{return failed;}
 void disable_loop(){loop_enabled=false;}void enable_loop_soon_any_context(){loop_enabled=true;}
};
template<typename...Ts>struct Action{virtual ~Action()=default;virtual void play(const Ts&...)=0;};
namespace text_sensor {struct TextSensor{std::string state;std::vector<std::string> history;void publish_state(const std::string&s){state=s;history.push_back(s);}};}
namespace display {enum DisplayRotation{DISPLAY_ROTATION_0_DEGREES=0,DISPLAY_ROTATION_90_DEGREES=90,DISPLAY_ROTATION_180_DEGREES=180,DISPLAY_ROTATION_270_DEGREES=270};}
namespace mipi_dsi {struct MipiDsi {
 bool copyable=true;unsigned copies=0;
 unsigned get_width(){return 8;}unsigned get_height(){return 8;}
 bool copy_frame_buffer_rgb565(uint8_t *out,size_t bytes,display::DisplayRotation){++copies;if(!copyable)return false;std::memset(out,0x55,bytes);return true;}
};}
}
struct AsyncWebServerResponse {
 const uint8_t *data;size_t bytes;std::map<std::string,std::string> headers;
 void addHeader(const char*k,const char*v){headers[k]=v;}
};
struct Param {std::string data;const std::string&value()const{return data;}};
struct AsyncWebServerRequest {
 static constexpr size_t URL_BUF_SIZE=100;
 std::string path="/esp_screenshot/screen/image.jpg",status,type,body;
 Param param;bool requested=false;std::function<void()> sending;
 int method()const{return HTTP_GET;}
 template<typename T>std::string url_to(T&)const{return path;}
 Param *getParam(const char*){return requested?&param:nullptr;}
 AsyncWebServerResponse *beginResponse(int,const char*mime,const uint8_t *data,size_t size){type=mime;return new AsyncWebServerResponse{data,size,{}};}
 AsyncWebServerResponse *beginResponse(int code,const char*mime,const char*data){return beginResponse(code,mime,reinterpret_cast<const uint8_t*>(data),std::strlen(data));}
 void send(AsyncWebServerResponse *response){if(sending)sending();body.assign(reinterpret_cast<const char*>(response->data),response->bytes);delete response;}
 operator AsyncWebServerRequest*(){return this;}
};
inline void httpd_resp_set_status(AsyncWebServerRequest*r,const char*value){r->status=value;}
struct AsyncWebHandler {virtual ~AsyncWebHandler()=default;virtual bool canHandle(AsyncWebServerRequest*)const{return false;}virtual void handleRequest(AsyncWebServerRequest*){}};
namespace esphome::web_server_base {struct WebServerBase{void add_handler(AsyncWebHandler*){}void init(){}};}
'''


DRIVER = r'''
#include "esp_screenshot.h"
#include <thread>
using namespace esphome::esp_screenshot;
struct Probe:EspScreenshot {
 using EspScreenshot::pixels_;using EspScreenshot::coverage_;using EspScreenshot::jpeg_;
 using EspScreenshot::slots_;using EspScreenshot::busy_;using EspScreenshot::worker_;
 using EspScreenshot::stopping_;using EspScreenshot::fail_setup_;
 int current(){auto result=slots_.acquire();slots_.release(result);return result;}
 void encode(){unsigned wake=0;platform::wake=[&](){if(++wake>1)stopping_=true;};worker_();stopping_=false;platform::wake={};loop();}
};
int main(){
 esphome::mipi_dsi::MipiDsi display;esphome::web_server_base::WebServerBase server;
 esphome::text_sensor::TextSensor status,id;
 Probe p;p.set_mipi_display(&display);p.set_web_server(&server);p.set_max_jpeg_size(4096);
 p.set_preallocate_buffers(false);p.set_capture_status_sensor(&status);p.set_capture_id_sensor(&id);p.setup();
 assert(!p.is_failed()&&platform::allocations.size()==1&&platform::bytes()==6144);
 assert(!p.pixels_&&!p.coverage_&&!p.jpeg_[0]&&!p.jpeg_[1]);
 assert(p.capture());p.loop();assert(p.pixels_&&p.jpeg_[0]);p.encode();
 assert(status.state=="Ready"&&!p.pixels_&&platform::bytes()==6144+50);
 const auto first_id=id.state;auto *first=p.jpeg_[p.current()];assert(platform::allocations.at(first).bytes==50);

 // Total admission failure and an allocation race preserve the current ID/data.
 auto before=platform::calls;platform::budget=platform::bytes()+128+4096-1;
 assert(p.capture());p.loop();assert(!p.busy_&&id.state==first_id&&platform::calls==before&&p.jpeg_[p.current()]==first);
 platform::budget=100000000;platform::fail_call=platform::calls+2;
 assert(p.capture());p.loop();assert(!p.busy_&&!p.pixels_&&id.state==first_id&&platform::bytes()==6194);
 platform::fail_call=0;
 display.copyable=false;assert(p.capture());p.loop();assert(id.state==first_id&&!p.pixels_&&platform::bytes()==6194);display.copyable=true;
 platform::encode_failure=true;assert(p.capture());p.loop();p.encode();assert(id.state==first_id&&platform::bytes()==6194);platform::encode_failure=false;

 // Execute production HTTP handling while another capture publishes. The
 // retired byte pointer must survive until send() releases its real lease.
 std::mutex barrier;std::condition_variable ready;bool entered=false,release=false;
 AsyncWebServerRequest request;request.sending=[&](){std::unique_lock lock(barrier);entered=true;ready.notify_all();ready.wait(lock,[&](){return release;});};
 std::thread reader([&](){p.handleRequest(&request);});
 {std::unique_lock lock(barrier);ready.wait(lock,[&](){return entered;});}
 assert(p.capture());p.loop();p.encode();assert(id.state!=first_id&&platform::allocations.count(first));
 auto second_id=id.state;before=platform::calls;assert(p.capture());p.loop();assert(!p.busy_&&id.state==second_id&&platform::calls==before);
 {std::lock_guard lock(barrier);release=true;}ready.notify_all();reader.join();
 assert(request.body==std::string(50,char(17))&&!platform::allocations.count(first));

 // A failed realloc keeps the private writer; no aliased pointer is resized.
 platform::fail_shrink=true;assert(p.capture());p.loop();p.encode();
 assert(platform::allocations.at(p.jpeg_[p.current()]).bytes==4096&&status.state=="Ready");
 platform::fail_shrink=false;
 for(unsigned i=0;i<20;i++){assert(p.capture());p.loop();p.encode();assert(platform::bytes()==6194);}
 // The explicit realloc-failure fallback may retain one max-capacity image.
 assert(platform::allocations.size()==2&&platform::peak<=6144+128+2*4096);
 p.fail_setup_("host worker finished");assert(platform::allocations.empty());

 // The existing default still reserves raw and both max-sized JPEG slots.
 Probe fixed;fixed.set_mipi_display(&display);fixed.set_web_server(&server);fixed.set_max_jpeg_size(4096);fixed.setup();
 assert(platform::allocations.size()==4&&platform::bytes()==6144+128+2*4096);
 fixed.fail_setup_("host worker finished");assert(platform::allocations.empty());
}
'''


@pytest.mark.parametrize("mutation", [None, "keep_raw", "retain_capacity", "ignore_reader"],
                         ids=["production", "reject-retained-raw", "reject-unshrunk-jpeg", "reject-reader-reaping"])
def test_complete_component_dynamic_admission_and_reader_ownership(tmp_path, mutation):
    (tmp_path / "platform.h").write_text(PLATFORM)
    headers = ["esphome/components/text_sensor/text_sensor.h", "esphome/components/web_server_base/web_server_base.h",
               "esphome/core/automation.h", "esphome/core/component.h", "esphome/core/hal.h", "esphome/core/log.h",
               "esphome/components/mipi_dsi/mipi_dsi.h", "esp_heap_caps.h", "esp_random.h", "esp_jpeg_enc.h",
               "freertos/FreeRTOS.h", "freertos/semphr.h", "freertos/task.h"]
    for name in headers:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#include "platform.h"\n')
    source = tmp_path / "dynamic.cpp"
    source.write_text(DRIVER)
    component = tmp_path / "component"
    component.mkdir()
    for name in ("esp_screenshot.cpp", "esp_screenshot.h", "snapshot_store.h"):
        text = (COMPONENT / name).read_text()
        if name == "esp_screenshot.cpp" and mutation == "keep_raw":
            needle = "if (!this->preallocate_buffers_)\n      this->release_capture_buffers_();"
            assert text.count(needle) == 1
            text = text.replace(needle, "if (false)\n      this->release_capture_buffers_();")
        if name == "esp_screenshot.cpp" and mutation == "retain_capacity":
            needle = "heap_caps_realloc(this->jpeg_[index], size_t(size), caps)"
            assert text.count(needle) == 1
            # Leave the private allocation untouched as if compaction vanished.
            text = text.replace(needle, "((void)caps, static_cast<void *>(nullptr))")
        if name == "snapshot_store.h" and mutation == "ignore_reader":
            needle = "index != this->writing_ && this->readers_[index] == 0"
            assert text.count(needle) == 1
            text = text.replace(needle, "index != this->writing_")
        (component / name).write_text(text)
    binary = tmp_path / "dynamic"
    subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pthread",
                    "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-DUSE_ESP_SCREENSHOT_MIPI_DSI",
                    "-I", str(tmp_path), "-I", str(component), str(source), str(component / "esp_screenshot.cpp"),
                    "-o", str(binary)], capture_output=True, text=True, check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True)
    if mutation is None:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0, "The ownership oracle accepted the deliberately broken candidate"
        assert "Assertion" in result.stderr or "AddressSanitizer" in result.stderr, result.stderr
