"""Controlled LVGL boundary shared by screenshot production-method tests."""

LVGL = r'''
#include <vector>
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
 lv_display_t display;bool paused=false,copyable=true;
 LvglComponent(){display.refresh=[this](){
   std::vector<uint8_t> pixels(size_t(display.width)*display.height*2,0x55);
   lv_draw_buf_t buffer{{unsigned(display.width)*2},pixels.data()};
   lv_area_t area{0,0,display.width-1,display.height-1};display.buffer=&buffer;
   lv_event_t event{display.user_data,&area};display.callback(&event);display.buffer=nullptr;
 };}
 lv_display_t *get_disp(){return &display;}bool is_paused(){return paused||!copyable;}
};
}
'''
