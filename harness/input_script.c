#include <string.h>
#include "m64p_plugin.h"
#include "m64p_types.h"
#define EXPORT __attribute__((visibility("default")))
static CONTROL *ctl;
static volatile unsigned int cur_buttons;
EXPORT void set_input(unsigned int v){ cur_buttons=v; }
EXPORT m64p_error PluginStartup(m64p_dynlib_handle h, void *c, void (*d)(void*,int,const char*)){return M64ERR_SUCCESS;}
EXPORT m64p_error PluginShutdown(void){return M64ERR_SUCCESS;}
EXPORT m64p_error PluginGetVersion(m64p_plugin_type *t,int *v,int *a,const char **n,int *caps){
 if(t)*t=M64PLUGIN_INPUT; if(v)*v=0x020000; if(a)*a=0x020100; if(n)*n="script input"; if(caps)*caps=0; return M64ERR_SUCCESS;}
EXPORT void InitiateControllers(CONTROL_INFO ci){ ctl=ci.Controls; for(int i=0;i<4;i++){ctl[i].Present=(i==0);ctl[i].RawData=0;ctl[i].Plugin=PLUGIN_NONE;} }
EXPORT void GetKeys(int c, BUTTONS *k){ k->Value = c==0? cur_buttons:0; }
EXPORT void ControllerCommand(int c, unsigned char *cmd){}
EXPORT void ReadController(int c, unsigned char *cmd){}
EXPORT int RomOpen(void){return 1;}
EXPORT void RomClosed(void){}
EXPORT void SDL_KeyDown(int m,int s){}
EXPORT void SDL_KeyUp(int m,int s){}
