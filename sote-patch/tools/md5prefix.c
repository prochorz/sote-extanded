/* Find an 8-byte nonce for the last bytes of a file so that its MD5 starts with a given
 * 32-bit prefix (mupen64plus names EEPROM saves "<name>-<first 8 hex digits of MD5>.eep").
 *
 *   md5prefix <file> <8 hex digits>      (file length must be a multiple of 64; the nonce
 *                                         goes into its last 8 bytes, which are rewritten)
 *
 * MD5 of everything but the last block is computed once; each try costs two compressions
 * (last data block + the constant padding block). Expected 2^32 tries, split over threads. */
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define F(x, y, z) ((z) ^ ((x) & ((y) ^ (z))))
#define G(x, y, z) ((y) ^ ((z) & ((x) ^ (y))))
#define H(x, y, z) ((x) ^ (y) ^ (z))
#define I(x, y, z) ((y) ^ ((x) | ~(z)))
#define STEP(f, a, b, c, d, x, t, s) \
    (a) += f((b), (c), (d)) + (x) + (t); (a) = (((a) << (s)) | ((a) >> (32 - (s)))); (a) += (b);

static void md5_block(uint32_t st[4], const uint32_t x[16]) {
    uint32_t a = st[0], b = st[1], c = st[2], d = st[3];
    STEP(F, a, b, c, d, x[0], 0xd76aa478, 7) STEP(F, d, a, b, c, x[1], 0xe8c7b756, 12)
    STEP(F, c, d, a, b, x[2], 0x242070db, 17) STEP(F, b, c, d, a, x[3], 0xc1bdceee, 22)
    STEP(F, a, b, c, d, x[4], 0xf57c0faf, 7) STEP(F, d, a, b, c, x[5], 0x4787c62a, 12)
    STEP(F, c, d, a, b, x[6], 0xa8304613, 17) STEP(F, b, c, d, a, x[7], 0xfd469501, 22)
    STEP(F, a, b, c, d, x[8], 0x698098d8, 7) STEP(F, d, a, b, c, x[9], 0x8b44f7af, 12)
    STEP(F, c, d, a, b, x[10], 0xffff5bb1, 17) STEP(F, b, c, d, a, x[11], 0x895cd7be, 22)
    STEP(F, a, b, c, d, x[12], 0x6b901122, 7) STEP(F, d, a, b, c, x[13], 0xfd987193, 12)
    STEP(F, c, d, a, b, x[14], 0xa679438e, 17) STEP(F, b, c, d, a, x[15], 0x49b40821, 22)
    STEP(G, a, b, c, d, x[1], 0xf61e2562, 5) STEP(G, d, a, b, c, x[6], 0xc040b340, 9)
    STEP(G, c, d, a, b, x[11], 0x265e5a51, 14) STEP(G, b, c, d, a, x[0], 0xe9b6c7aa, 20)
    STEP(G, a, b, c, d, x[5], 0xd62f105d, 5) STEP(G, d, a, b, c, x[10], 0x02441453, 9)
    STEP(G, c, d, a, b, x[15], 0xd8a1e681, 14) STEP(G, b, c, d, a, x[4], 0xe7d3fbc8, 20)
    STEP(G, a, b, c, d, x[9], 0x21e1cde6, 5) STEP(G, d, a, b, c, x[14], 0xc33707d6, 9)
    STEP(G, c, d, a, b, x[3], 0xf4d50d87, 14) STEP(G, b, c, d, a, x[8], 0x455a14ed, 20)
    STEP(G, a, b, c, d, x[13], 0xa9e3e905, 5) STEP(G, d, a, b, c, x[2], 0xfcefa3f8, 9)
    STEP(G, c, d, a, b, x[7], 0x676f02d9, 14) STEP(G, b, c, d, a, x[12], 0x8d2a4c8a, 20)
    STEP(H, a, b, c, d, x[5], 0xfffa3942, 4) STEP(H, d, a, b, c, x[8], 0x8771f681, 11)
    STEP(H, c, d, a, b, x[11], 0x6d9d6122, 16) STEP(H, b, c, d, a, x[14], 0xfde5380c, 23)
    STEP(H, a, b, c, d, x[1], 0xa4beea44, 4) STEP(H, d, a, b, c, x[4], 0x4bdecfa9, 11)
    STEP(H, c, d, a, b, x[7], 0xf6bb4b60, 16) STEP(H, b, c, d, a, x[10], 0xbebfbc70, 23)
    STEP(H, a, b, c, d, x[13], 0x289b7ec6, 4) STEP(H, d, a, b, c, x[0], 0xeaa127fa, 11)
    STEP(H, c, d, a, b, x[3], 0xd4ef3085, 16) STEP(H, b, c, d, a, x[6], 0x04881d05, 23)
    STEP(H, a, b, c, d, x[9], 0xd9d4d039, 4) STEP(H, d, a, b, c, x[12], 0xe6db99e5, 11)
    STEP(H, c, d, a, b, x[15], 0x1fa27cf8, 16) STEP(H, b, c, d, a, x[2], 0xc4ac5665, 23)
    STEP(I, a, b, c, d, x[0], 0xf4292244, 6) STEP(I, d, a, b, c, x[7], 0x432aff97, 10)
    STEP(I, c, d, a, b, x[14], 0xab9423a7, 15) STEP(I, b, c, d, a, x[5], 0xfc93a039, 21)
    STEP(I, a, b, c, d, x[12], 0x655b59c3, 6) STEP(I, d, a, b, c, x[3], 0x8f0ccc92, 10)
    STEP(I, c, d, a, b, x[10], 0xffeff47d, 15) STEP(I, b, c, d, a, x[1], 0x85845dd1, 21)
    STEP(I, a, b, c, d, x[8], 0x6fa87e4f, 6) STEP(I, d, a, b, c, x[15], 0xfe2ce6e0, 10)
    STEP(I, c, d, a, b, x[6], 0xa3014314, 15) STEP(I, b, c, d, a, x[13], 0x4e0811a1, 21)
    STEP(I, a, b, c, d, x[4], 0xf7537e82, 6) STEP(I, d, a, b, c, x[11], 0xbd3af235, 10)
    STEP(I, c, d, a, b, x[2], 0x2ad7d2bb, 15) STEP(I, b, c, d, a, x[9], 0xeb86d391, 21)
    st[0] += a; st[1] += b; st[2] += c; st[3] += d;
}

static uint32_t mid[4], last[16], pad[16], want;   /* want: digest bytes 0..3 as LE word */
static volatile int found;
static uint64_t result;
static int nthreads;

static void *worker(void *arg) {
    uint64_t id = (uint64_t)(uintptr_t)arg;
    uint32_t blk[16];
    memcpy(blk, last, sizeof blk);
    for (uint64_t n = id; !found; n += nthreads) {
        blk[14] = (uint32_t)n; blk[15] = (uint32_t)(n >> 32);
        uint32_t st[4] = { mid[0], mid[1], mid[2], mid[3] };
        md5_block(st, blk);
        md5_block(st, pad);
        if (st[0] == want) { found = 1; result = n; }
    }
    return NULL;
}

int main(int argc, char **argv) {
    if (argc != 3) { fprintf(stderr, "usage: md5prefix <file> <8 hex>\n"); return 2; }
    FILE *f = fopen(argv[1], "r+b");
    if (!f) { perror(argv[1]); return 1; }
    fseek(f, 0, SEEK_END); long len = ftell(f); fseek(f, 0, SEEK_SET);
    if (len < 64 || len % 64) { fprintf(stderr, "length must be a multiple of 64\n"); return 1; }
    uint8_t *data = malloc(len);
    if (fread(data, 1, len, f) != (size_t)len) return 1;
    uint32_t p = (uint32_t)strtoul(argv[2], NULL, 16);       /* hex digits = digest bytes 0..3 */
    want = ((p >> 24) & 0xff) | ((p >> 8) & 0xff00) | ((p << 8) & 0xff0000) | (p << 24);
    mid[0] = 0x67452301; mid[1] = 0xefcdab89; mid[2] = 0x98badcfe; mid[3] = 0x10325476;
    for (long o = 0; o < len - 64; o += 64) md5_block(mid, (const uint32_t *)(data + o));  /* host is LE */
    memcpy(last, data + len - 64, 64);
    memset(pad, 0, sizeof pad);
    pad[0] = 0x80;
    pad[14] = (uint32_t)((uint64_t)len * 8); pad[15] = (uint32_t)(((uint64_t)len * 8) >> 32);
    nthreads = (int)sysconf(_SC_NPROCESSORS_ONLN);
    pthread_t t[64];
    if (nthreads > 64) nthreads = 64;
    for (int i = 0; i < nthreads; i++) pthread_create(&t[i], NULL, worker, (void *)(uintptr_t)i);
    for (int i = 0; i < nthreads; i++) pthread_join(t[i], NULL);
    uint8_t nonce[8];
    for (int i = 0; i < 8; i++) nonce[i] = (uint8_t)(result >> (8 * i));
    fseek(f, len - 8, SEEK_SET); fwrite(nonce, 1, 8, f); fclose(f);
    printf("nonce %016llx\n", (unsigned long long)result);
    return 0;
}
