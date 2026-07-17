#include <psp2/ctrl.h>
#include <psp2/kernel/processmgr.h>
#include <psp2/kernel/threadmgr.h>
#include <psp2/net/net.h>
#include <psp2/net/netctl.h>
#include <psp2/sysmodule.h>
#include <psp2/touch.h>
#include <vita2d.h>

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define INPUT_PORT 5000
#define DISCOVERY_PORT 5001
#define SEND_INTERVAL_US 8333
#define DISCOVERY_MAGIC "VGPD_HOST_V1"
#define PACKET_MAGIC "VGPD"
#define PACKET_VERSION 1

enum ProtocolButton {
    BTN_A = 1u << 0,
    BTN_B = 1u << 1,
    BTN_X = 1u << 2,
    BTN_Y = 1u << 3,
    BTN_LB = 1u << 4,
    BTN_RB = 1u << 5,
    BTN_BACK = 1u << 6,
    BTN_START = 1u << 7,
    BTN_L3 = 1u << 8,
    BTN_R3 = 1u << 9,
    BTN_UP = 1u << 10,
    BTN_DOWN = 1u << 11,
    BTN_LEFT = 1u << 12,
    BTN_RIGHT = 1u << 13,
};

typedef struct __attribute__((packed)) InputPacket {
    char magic[4];
    uint8_t version;
    uint8_t flags;
    uint16_t size;
    uint32_t sequence;
    uint16_t buttons;
    uint8_t lx;
    uint8_t ly;
    uint8_t rx;
    uint8_t ry;
    uint8_t lt;
    uint8_t rt;
} InputPacket;

_Static_assert(sizeof(InputPacket) == 20, "InputPacket must be exactly 20 bytes");

static uint8_t net_memory[1024 * 1024];
static volatile bool exiting = false;

static int exit_callback(int argc, const void *args) {
    (void)argc;
    (void)args;
    exiting = true;
    return 0;
}

static int callback_thread(SceSize args, void *argp) {
    (void)args;
    (void)argp;
    int callback = sceKernelCreateCallback("Exit callback", exit_callback, NULL);
    sceKernelRegisterExitCallback(callback);
    sceKernelDelayThreadCB(0xFFFFFFFF);
    return 0;
}

static void setup_callbacks(void) {
    int thread = sceKernelCreateThread(
        "callback thread", callback_thread, 0x10000100, 0x1000, 0, 0, NULL
    );
    if (thread >= 0) {
        sceKernelStartThread(thread, 0, NULL);
    }
}

static int init_network(void) {
    int result = sceSysmoduleLoadModule(SCE_SYSMODULE_NET);
    if (result < 0) {
        return result;
    }
    SceNetInitParam params;
    memset(&params, 0, sizeof(params));
    params.memory = net_memory;
    params.size = sizeof(net_memory);
    result = sceNetInit(&params);
    if (result < 0) {
        return result;
    }
    return sceNetCtlInit();
}

static int create_socket(void) {
    int sock = sceNetSocket(
        "vita-gamepad", SCE_NET_AF_INET, SCE_NET_SOCK_DGRAM, 0
    );
    if (sock < 0) {
        return sock;
    }

    int nonblocking = 1;
    sceNetSetsockopt(
        sock, SCE_NET_SOL_SOCKET, SCE_NET_SO_NBIO,
        &nonblocking, sizeof(nonblocking)
    );

    SceNetSockaddrIn local;
    memset(&local, 0, sizeof(local));
    local.sin_len = sizeof(local);
    local.sin_family = SCE_NET_AF_INET;
    local.sin_port = sceNetHtons(DISCOVERY_PORT);
    local.sin_addr.s_addr = sceNetHtonl(SCE_NET_INADDR_ANY);
    int result = sceNetBind(sock, (SceNetSockaddr *)&local, sizeof(local));
    if (result < 0) {
        sceNetSocketClose(sock);
        return result;
    }
    return sock;
}

static bool find_host(int sock, SceNetSockaddrIn *host) {
    char buffer[32];
    SceNetSockaddrIn source;
    unsigned int source_length = sizeof(source);
    int count = sceNetRecvfrom(
        sock, buffer, sizeof(buffer), 0,
        (SceNetSockaddr *)&source, &source_length
    );
    if (count != (int)strlen(DISCOVERY_MAGIC) ||
        memcmp(buffer, DISCOVERY_MAGIC, strlen(DISCOVERY_MAGIC)) != 0) {
        return false;
    }
    *host = source;
    host->sin_port = sceNetHtons(INPUT_PORT);
    return true;
}

static uint16_t map_buttons(uint32_t vita_buttons) {
    uint16_t buttons = 0;
    if (vita_buttons & SCE_CTRL_CROSS) buttons |= BTN_A;
    if (vita_buttons & SCE_CTRL_CIRCLE) buttons |= BTN_B;
    if (vita_buttons & SCE_CTRL_SQUARE) buttons |= BTN_X;
    if (vita_buttons & SCE_CTRL_TRIANGLE) buttons |= BTN_Y;
    if (vita_buttons & SCE_CTRL_LTRIGGER) buttons |= BTN_LB;
    if (vita_buttons & SCE_CTRL_RTRIGGER) buttons |= BTN_RB;
    if (vita_buttons & SCE_CTRL_SELECT) buttons |= BTN_BACK;
    if (vita_buttons & SCE_CTRL_START) buttons |= BTN_START;
    if (vita_buttons & SCE_CTRL_UP) buttons |= BTN_UP;
    if (vita_buttons & SCE_CTRL_DOWN) buttons |= BTN_DOWN;
    if (vita_buttons & SCE_CTRL_LEFT) buttons |= BTN_LEFT;
    if (vita_buttons & SCE_CTRL_RIGHT) buttons |= BTN_RIGHT;
    return buttons;
}

static void read_touch(uint16_t *buttons, uint8_t *lt, uint8_t *rt) {
    SceTouchData touch;
    *lt = 0;
    *rt = 0;

    memset(&touch, 0, sizeof(touch));
    if (sceTouchPeek(SCE_TOUCH_PORT_BACK, &touch, 1) >= 0) {
        for (uint32_t i = 0; i < touch.reportNum; ++i) {
            if (touch.report[i].x < 960) {
                *lt = 255;
            } else {
                *rt = 255;
            }
        }
    }

    memset(&touch, 0, sizeof(touch));
    if (sceTouchPeek(SCE_TOUCH_PORT_FRONT, &touch, 1) >= 0) {
        for (uint32_t i = 0; i < touch.reportNum; ++i) {
            if (touch.report[i].y >= 850 && touch.report[i].x < 480) {
                *buttons |= BTN_L3;
            } else if (touch.report[i].y >= 850 &&
                       touch.report[i].x > 1440) {
                *buttons |= BTN_R3;
            }
        }
    }
}

static void make_packet(
    InputPacket *packet, const SceCtrlData *pad, uint32_t sequence
) {
    memset(packet, 0, sizeof(*packet));
    memcpy(packet->magic, PACKET_MAGIC, sizeof(packet->magic));
    packet->version = PACKET_VERSION;
    packet->size = sceNetHtons(sizeof(*packet));
    packet->sequence = sceNetHtonl(sequence);
    uint16_t buttons = map_buttons(pad->buttons);
    read_touch(&buttons, &packet->lt, &packet->rt);
    packet->buttons = sceNetHtons(buttons);
    packet->lx = pad->lx;
    packet->ly = pad->ly;
    packet->rx = pad->rx;
    packet->ry = pad->ry;
}

static void format_ip(const SceNetSockaddrIn *address, char *out, size_t size) {
    uint32_t ip = sceNetNtohl(address->sin_addr.s_addr);
    snprintf(
        out, size, "%u.%u.%u.%u",
        (unsigned)((ip >> 24) & 0xff), (unsigned)((ip >> 16) & 0xff),
        (unsigned)((ip >> 8) & 0xff), (unsigned)(ip & 0xff)
    );
}

static void draw_ui(
    vita2d_pgf *font, bool connected, const char *host_ip,
    uint32_t sent, int network_error
) {
    vita2d_start_drawing();
    vita2d_clear_screen();
    vita2d_draw_rectangle(0, 0, 960, 544, RGBA8(18, 24, 38, 255));
    vita2d_draw_rectangle(0, 0, 960, 8, RGBA8(38, 190, 125, 255));
    vita2d_pgf_draw_text(
        font, 54, 92, RGBA8(255, 255, 255, 255), 1.6f, "Vita Gamepad"
    );
    if (network_error < 0) {
        char error[96];
        snprintf(error, sizeof(error), "Network error: 0x%08X", network_error);
        vita2d_pgf_draw_text(
            font, 54, 176, RGBA8(255, 105, 105, 255), 1.0f, error
        );
    } else if (!connected) {
        vita2d_pgf_draw_text(
            font, 54, 176, RGBA8(245, 200, 80, 255), 1.0f,
            "Waiting for a computer on the same Wi-Fi..."
        );
        vita2d_pgf_draw_text(
            font, 54, 218, RGBA8(180, 190, 205, 255), 0.8f,
            "Start 'vitapad' on Windows or macOS."
        );
    } else {
        char status[128];
        snprintf(status, sizeof(status), "Connected: %s", host_ip);
        vita2d_pgf_draw_text(
            font, 54, 176, RGBA8(80, 225, 155, 255), 1.0f, status
        );
        snprintf(status, sizeof(status), "Packets sent: %u", (unsigned)sent);
        vita2d_pgf_draw_text(
            font, 54, 218, RGBA8(180, 190, 205, 255), 0.8f, status
        );
    }
    vita2d_pgf_draw_text(
        font, 54, 390, RGBA8(180, 190, 205, 255), 0.75f,
        "Rear touch: L2 / R2     Front bottom corners: L3 / R3"
    );
    vita2d_pgf_draw_text(
        font, 54, 438, RGBA8(140, 150, 165, 255), 0.7f,
        "Hold START + SELECT for 2 seconds to exit"
    );
    vita2d_end_drawing();
    vita2d_swap_buffers();
}

int main(void) {
    setup_callbacks();
    sceCtrlSetSamplingMode(SCE_CTRL_MODE_ANALOG_WIDE);
    sceTouchSetSamplingState(SCE_TOUCH_PORT_FRONT, SCE_TOUCH_SAMPLING_STATE_START);
    sceTouchSetSamplingState(SCE_TOUCH_PORT_BACK, SCE_TOUCH_SAMPLING_STATE_START);

    vita2d_init();
    vita2d_set_clear_color(RGBA8(18, 24, 38, 255));
    vita2d_pgf *font = vita2d_load_default_pgf();

    int network_result = init_network();
    bool network_initialized = network_result >= 0;
    int sock = network_result >= 0 ? create_socket() : network_result;
    if (sock < 0) {
        network_result = sock;
    }

    bool connected = false;
    SceNetSockaddrIn host;
    memset(&host, 0, sizeof(host));
    char host_ip[32] = "";
    uint32_t sequence = 0;
    uint32_t sent = 0;
    uint32_t exit_frames = 0;
    uint32_t draw_divider = 0;

    while (!exiting) {
        if (sock >= 0 && find_host(sock, &host)) {
            connected = true;
            format_ip(&host, host_ip, sizeof(host_ip));
        }

        SceCtrlData pad;
        memset(&pad, 0, sizeof(pad));
        if (sceCtrlPeekBufferPositive(0, &pad, 1) > 0) {
            if ((pad.buttons & (SCE_CTRL_START | SCE_CTRL_SELECT)) ==
                (SCE_CTRL_START | SCE_CTRL_SELECT)) {
                exit_frames++;
                if (exit_frames >= 240) exiting = true;
            } else {
                exit_frames = 0;
            }

            if (connected) {
                InputPacket packet;
                make_packet(&packet, &pad, sequence++);
                int result = sceNetSendto(
                    sock, &packet, sizeof(packet), 0,
                    (SceNetSockaddr *)&host, sizeof(host)
                );
                if (result == (int)sizeof(packet)) {
                    sent++;
                } else if (result < 0) {
                    connected = false;
                }
            }
        }

        if (++draw_divider >= 4) {
            draw_ui(font, connected, host_ip, sent, network_result);
            draw_divider = 0;
        }
        sceKernelDelayThread(SEND_INTERVAL_US);
    }

    if (sock >= 0) sceNetSocketClose(sock);
    if (network_initialized) {
        sceNetCtlTerm();
        sceNetTerm();
        sceSysmoduleUnloadModule(SCE_SYSMODULE_NET);
    }
    vita2d_free_pgf(font);
    vita2d_fini();
    sceKernelExitProcess(0);
    return 0;
}
