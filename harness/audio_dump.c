/* mupen64plus audio plugin that writes the AI output to a raw PCM file
 * (16-bit stereo little-endian) instead of playing it. */
#include <stdio.h>
#include <string.h>
#include "m64p_plugin.h"
#include "m64p_types.h"
#define EXPORT __attribute__((visibility("default")))
static AUDIO_INFO info;
static FILE *out;
static int freq = 32000;
static long frames_written;
static int paused;
EXPORT void audio_dump_pause(int p) { paused = p; }
static FILE *logf;
EXPORT void audio_dump_log(const char *path) { if (logf) fclose(logf); logf = path ? fopen(path, "w") : NULL; }
EXPORT void audio_dump_start(const char *path) { if (out) fclose(out); out = fopen(path, "wb"); frames_written = 0; }
EXPORT void audio_dump_stop(void) { if (out) fclose(out); out = NULL; if (logf) fclose(logf); logf = NULL; }
EXPORT int audio_dump_freq(void) { return freq; }
EXPORT long audio_dump_frames(void) { return frames_written; }
EXPORT m64p_error PluginStartup(m64p_dynlib_handle h, void *c, void (*d)(void*,int,const char*)) { return M64ERR_SUCCESS; }
EXPORT m64p_error PluginShutdown(void) { audio_dump_stop(); return M64ERR_SUCCESS; }
EXPORT m64p_error PluginGetVersion(m64p_plugin_type *t, int *v, int *a, const char **n, int *caps) {
    if (t) *t = M64PLUGIN_AUDIO; if (v) *v = 0x020000; if (a) *a = 0x020000; if (n) *n = "audio dump"; if (caps) *caps = 0;
    return M64ERR_SUCCESS; }
EXPORT int InitiateAudio(AUDIO_INFO a) { info = a; return 1; }
EXPORT void AiDacrateChanged(int system) {
    unsigned clock = system == SYSTEM_PAL ? 49656530 : (system == SYSTEM_MPAL ? 48628316 : 48681812);
    freq = (int)(clock / (*info.AI_DACRATE_REG + 1));
}
EXPORT void AiLenChanged(void) {
    if (!out || paused) return;
    unsigned len = *info.AI_LEN_REG & ~3u;
    unsigned char *p = info.RDRAM + (*info.AI_DRAM_ADDR_REG & 0xFFFFFF);
    unsigned char buf[4];
    for (unsigned i = 0; i < len; i += 4) {        /* RDRAM is stored as host-endian words */
        buf[0] = p[i + 2]; buf[1] = p[i + 3]; buf[2] = p[i]; buf[3] = p[i + 1];
        fwrite(buf, 1, 4, out);
    }
    if (logf) fprintf(logf, "%ld %08x %u %u\n", frames_written, *info.AI_DRAM_ADDR_REG & 0xFFFFFF, len, *info.AI_STATUS_REG);
    frames_written += len / 4;
}
EXPORT void ProcessAList(void) {}
EXPORT int RomOpen(void) { return 1; }
EXPORT void RomClosed(void) {}
EXPORT void SetSpeedFactor(int f) {}
EXPORT void VolumeUp(void) {}
EXPORT void VolumeDown(void) {}
EXPORT int VolumeGetLevel(void) { return 100; }
EXPORT void VolumeSetLevel(int l) {}
EXPORT void VolumeMute(void) {}
EXPORT const char *VolumeGetString(void) { return "100%"; }
