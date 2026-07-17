#include <psp2/ctrl.h>
#include <psp2/kernel/processmgr.h>
#include <psp2/kernel/threadmgr.h>
#include <psp2/net/net.h>
#include <psp2/net/netctl.h>
#include <psp2/power.h>
#include <psp2/rtc.h>
#include <psp2/sysmodule.h>
#include <psp2/touch.h>
#include <vita2d.h>

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define INPUT_PORT 5000
#define DISCOVERY_PORT 5001
#define POLL_INTERVAL_US 8333
#define IDLE_HEARTBEAT_US 100000
#define DRAW_INTERVAL_US 100000
#define STATUS_INTERVAL_US 1000000
#define DISCOVERY_MAGIC "VGPD_HOST_V1"
#define VITA_DISCOVERY_MAGIC "VGPD_VITA_V1"
#define PACKET_MAGIC "VGPD"
#define PACKET_VERSION 1
#define MAX_HOSTS 8
#define HOST_TIMEOUT_US (5 * 1000 * 1000ULL)

typedef struct HostEntry {
    SceNetSockaddrIn address;
    uint64_t last_seen_us;
} HostEntry;

typedef struct DeviceStatus {
    char time_text[6];
    int battery_percent;
    bool charging;
} DeviceStatus;

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
    int broadcast = 1;
    sceNetSetsockopt(
        sock, SCE_NET_SOL_SOCKET, SCE_NET_SO_BROADCAST,
        &broadcast, sizeof(broadcast)
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

static void send_discovery_probe(int sock) {
    SceNetSockaddrIn target;
    memset(&target, 0, sizeof(target));
    target.sin_len = sizeof(target);
    target.sin_family = SCE_NET_AF_INET;
    target.sin_port = sceNetHtons(DISCOVERY_PORT);
    target.sin_addr.s_addr = sceNetHtonl(SCE_NET_INADDR_BROADCAST);
    sceNetSendto(
        sock, VITA_DISCOVERY_MAGIC, strlen(VITA_DISCOVERY_MAGIC), 0,
        (SceNetSockaddr *)&target, sizeof(target)
    );
}

static bool receive_host(int sock, SceNetSockaddrIn *host) {
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

static void remember_host(
    HostEntry *hosts, unsigned int *host_count,
    const SceNetSockaddrIn *address, uint64_t now_us
) {
    for (unsigned int i = 0; i < *host_count; ++i) {
        if (hosts[i].address.sin_addr.s_addr == address->sin_addr.s_addr) {
            hosts[i].address = *address;
            hosts[i].last_seen_us = now_us;
            return;
        }
    }
    unsigned int index;
    if (*host_count < MAX_HOSTS) {
        index = (*host_count)++;
    } else {
        index = 0;
        for (unsigned int i = 1; i < *host_count; ++i) {
            if (hosts[i].last_seen_us < hosts[index].last_seen_us) {
                index = i;
            }
        }
    }
    hosts[index].address = *address;
    hosts[index].last_seen_us = now_us;
}

static void expire_hosts(
    HostEntry *hosts, unsigned int *host_count,
    unsigned int *selected_host, uint64_t now_us
) {
    unsigned int write_index = 0;
    for (unsigned int i = 0; i < *host_count; ++i) {
        if (now_us - hosts[i].last_seen_us <= HOST_TIMEOUT_US) {
            if (write_index != i) hosts[write_index] = hosts[i];
            write_index++;
        }
    }
    *host_count = write_index;
    if (*host_count == 0) {
        *selected_host = 0;
    } else if (*selected_host >= *host_count) {
        *selected_host = *host_count - 1;
    }
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

static bool input_matches(
    const InputPacket *left, const InputPacket *right
) {
    return left->flags == right->flags &&
           left->buttons == right->buttons &&
           left->lx == right->lx && left->ly == right->ly &&
           left->rx == right->rx && left->ry == right->ry &&
           left->lt == right->lt && left->rt == right->rt;
}

static void update_device_status(DeviceStatus *status) {
    SceDateTime local_time;
    memset(&local_time, 0, sizeof(local_time));
    if (sceRtcGetCurrentClockLocalTime(&local_time) >= 0) {
        unsigned int hour = (unsigned int)local_time.hour % 24;
        unsigned int minute = (unsigned int)local_time.minute % 60;
        snprintf(
            status->time_text, sizeof(status->time_text), "%02u:%02u",
            hour, minute
        );
    } else {
        snprintf(status->time_text, sizeof(status->time_text), "--:--");
    }
    int battery = scePowerGetBatteryLifePercent();
    if (battery < 0) battery = 0;
    if (battery > 100) battery = 100;
    status->battery_percent = battery;
    status->charging = scePowerIsBatteryCharging() == SCE_TRUE;
}

static void draw_status_bar(vita2d_pgf *font, const DeviceStatus *status) {
    const float battery_x = 833.0f;
    const float battery_y = 35.0f;
    const float battery_width = 48.0f;
    const float battery_height = 20.0f;
    uint32_t battery_color = status->charging
        ? RGBA8(80, 225, 155, 255)
        : status->battery_percent <= 20
            ? RGBA8(255, 105, 105, 255)
            : RGBA8(180, 190, 205, 255);

    vita2d_pgf_draw_text(
        font, 744, 54, RGBA8(220, 230, 240, 255), 0.78f,
        status->time_text
    );
    vita2d_draw_rectangle(
        battery_x, battery_y, battery_width, 2, RGBA8(180, 190, 205, 255)
    );
    vita2d_draw_rectangle(
        battery_x, battery_y + battery_height - 2,
        battery_width, 2, RGBA8(180, 190, 205, 255)
    );
    vita2d_draw_rectangle(
        battery_x, battery_y, 2, battery_height,
        RGBA8(180, 190, 205, 255)
    );
    vita2d_draw_rectangle(
        battery_x + battery_width - 2, battery_y, 2, battery_height,
        RGBA8(180, 190, 205, 255)
    );
    vita2d_draw_rectangle(
        battery_x + battery_width, battery_y + 6, 4, 8,
        RGBA8(180, 190, 205, 255)
    );
    float fill_width =
        (battery_width - 6) * (float)status->battery_percent / 100.0f;
    if (fill_width > 0) {
        vita2d_draw_rectangle(
            battery_x + 3, battery_y + 3, fill_width,
            battery_height - 6, battery_color
        );
    }
    char battery_text[12];
    snprintf(
        battery_text, sizeof(battery_text), "%d%%%s",
        status->battery_percent, status->charging ? "+" : ""
    );
    vita2d_pgf_draw_text(
        font, 894, 54, battery_color, 0.72f, battery_text
    );
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
    uint32_t sent, int connection_error,
    const HostEntry *hosts, unsigned int host_count,
    unsigned int selected_host, const DeviceStatus *device_status
) {
    vita2d_start_drawing();
    vita2d_clear_screen();
    vita2d_draw_rectangle(0, 0, 960, 544, RGBA8(18, 24, 38, 255));
    vita2d_draw_rectangle(0, 0, 960, 8, RGBA8(38, 190, 125, 255));
    vita2d_pgf_draw_text(
        font, 54, 92, RGBA8(255, 255, 255, 255), 1.6f, "Vita Gamepad"
    );
    draw_status_bar(font, device_status);
    vita2d_pgf_draw_text(
        font, 54, 132, RGBA8(180, 190, 205, 255), 0.8f,
        "Connection: Wi-Fi"
    );
    if (connection_error < 0) {
        char error[96];
        snprintf(
            error, sizeof(error), "Network error: 0x%08X", connection_error
        );
        vita2d_pgf_draw_text(
            font, 54, 176, RGBA8(255, 105, 105, 255), 1.0f, error
        );
    } else if (!connected) {
        char status[64];
        snprintf(
            status, sizeof(status), "Computers found: %u",
            host_count
        );
        vita2d_pgf_draw_text(
            font, 54, 176, RGBA8(245, 200, 80, 255), 1.0f, status
        );
        if (host_count == 0) {
            vita2d_pgf_draw_text(
                font, 54, 218, RGBA8(180, 190, 205, 255), 0.8f,
                "Scanning the local network..."
            );
        } else {
            unsigned int first = selected_host > 1 ? selected_host - 1 : 0;
            if (first + 4 > host_count) {
                first = host_count > 4 ? host_count - 4 : 0;
            }
            unsigned int end = first + 4;
            if (end > host_count) end = host_count;
            for (unsigned int i = first; i < end; ++i) {
                float y = 205.0f + (float)(i - first) * 38.0f;
                char ip[32];
                format_ip(&hosts[i].address, ip, sizeof(ip));
                if (i == selected_host) {
                    vita2d_draw_rectangle(
                        48, y - 22, 420, 32,
                        RGBA8(38, 190, 125, 80)
                    );
                }
                snprintf(
                    status, sizeof(status), "%s  %s",
                    i == selected_host ? ">" : " ", ip
                );
                vita2d_pgf_draw_text(
                    font, 62, y, RGBA8(220, 230, 240, 255),
                    0.82f, status
                );
            }
            vita2d_pgf_draw_text(
                font, 520, 218, RGBA8(180, 190, 205, 255), 0.75f,
                "UP / DOWN: select"
            );
            vita2d_pgf_draw_text(
                font, 520, 256, RGBA8(80, 225, 155, 255), 0.75f,
                "X: connect"
            );
        }
    } else {
        char status[128];
        snprintf(
            status, sizeof(status), "Connected: %s", host_ip
        );
        vita2d_pgf_draw_text(
            font, 54, 176, RGBA8(80, 225, 155, 255), 1.0f, status
        );
        snprintf(status, sizeof(status), "Packets sent: %u", (unsigned)sent);
        vita2d_pgf_draw_text(
            font, 54, 218, RGBA8(180, 190, 205, 255), 0.8f, status
        );
        vita2d_pgf_draw_text(
            font, 54, 260, RGBA8(180, 190, 205, 255), 0.72f,
            "START + O: choose another computer"
        );
    }
    vita2d_pgf_draw_text(
        font, 54, 350, RGBA8(180, 190, 205, 255), 0.75f,
        "Rear touch: L2 / R2     Front bottom corners: L3 / R3"
    );
    vita2d_pgf_draw_text(
        font, 54, 420, RGBA8(140, 150, 165, 255), 0.7f,
        "Hold START + SELECT for 2 seconds to exit"
    );
    vita2d_end_drawing();
    vita2d_swap_buffers();
}

int main(void) {
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
    bool reselect_was_pressed = false;
    bool consume_connect_button = false;
    SceNetSockaddrIn host;
    memset(&host, 0, sizeof(host));
    HostEntry hosts[MAX_HOSTS];
    memset(hosts, 0, sizeof(hosts));
    unsigned int host_count = 0;
    unsigned int selected_host = 0;
    char host_ip[32] = "";
    uint32_t sequence = 0;
    uint32_t sent = 0;
    uint32_t exit_frames = 0;
    uint32_t discovery_frames = 0;
    uint32_t previous_buttons = 0;
    InputPacket last_sent_packet;
    memset(&last_sent_packet, 0, sizeof(last_sent_packet));
    bool has_last_sent_packet = false;
    uint64_t last_send_us = 0;
    uint64_t next_draw_us = 0;
    uint64_t next_status_us = 0;
    DeviceStatus device_status;
    memset(&device_status, 0, sizeof(device_status));
    update_device_status(&device_status);
    next_status_us =
        sceKernelGetProcessTimeWide() + STATUS_INTERVAL_US;

    while (!exiting) {
        uint64_t now_us = sceKernelGetProcessTimeWide();
        if (sock >= 0) {
            SceNetSockaddrIn discovered;
            while (receive_host(sock, &discovered)) {
                remember_host(hosts, &host_count, &discovered, now_us);
            }
            expire_hosts(hosts, &host_count, &selected_host, now_us);
        }
        if (sock >= 0 && discovery_frames++ >= 120) {
            send_discovery_probe(sock);
            discovery_frames = 0;
        }

        SceCtrlData pad;
        memset(&pad, 0, sizeof(pad));
        if (sceCtrlPeekBufferPositive(0, &pad, 1) > 0) {
            bool reselect_pressed =
                (pad.buttons & (SCE_CTRL_START | SCE_CTRL_CIRCLE)) ==
                (SCE_CTRL_START | SCE_CTRL_CIRCLE);
            if (
                connected && reselect_pressed && !reselect_was_pressed
            ) {
                connected = false;
                sequence = 0;
                sent = 0;
            }
            reselect_was_pressed = reselect_pressed;

            bool exit_pressed =
                (pad.buttons & (SCE_CTRL_START | SCE_CTRL_SELECT)) ==
                (SCE_CTRL_START | SCE_CTRL_SELECT);
            if (exit_pressed) {
                exit_frames++;
                if (exit_frames >= 240) exiting = true;
            } else {
                exit_frames = 0;
            }

            bool up_pressed =
                (pad.buttons & SCE_CTRL_UP) &&
                !(previous_buttons & SCE_CTRL_UP);
            bool down_pressed =
                (pad.buttons & SCE_CTRL_DOWN) &&
                !(previous_buttons & SCE_CTRL_DOWN);
            bool cross_pressed =
                (pad.buttons & SCE_CTRL_CROSS) &&
                !(previous_buttons & SCE_CTRL_CROSS);
            if (!connected && host_count > 0) {
                if (up_pressed) {
                    selected_host =
                        selected_host == 0 ? host_count - 1 : selected_host - 1;
                } else if (down_pressed) {
                    selected_host = (selected_host + 1) % host_count;
                } else if (cross_pressed) {
                    host = hosts[selected_host].address;
                    connected = true;
                    sequence = 0;
                    sent = 0;
                    has_last_sent_packet = false;
                    format_ip(&host, host_ip, sizeof(host_ip));
                    consume_connect_button = true;
                }
            }

            if (reselect_pressed) {
                pad.buttons &= ~(SCE_CTRL_START | SCE_CTRL_CIRCLE);
            }
            if (exit_pressed) {
                pad.buttons &= ~(SCE_CTRL_START | SCE_CTRL_SELECT);
            }
            if (consume_connect_button) {
                pad.buttons &= ~SCE_CTRL_CROSS;
                if (!(previous_buttons & SCE_CTRL_CROSS) && !cross_pressed) {
                    consume_connect_button = false;
                }
            }

            if (connected) {
                InputPacket packet;
                make_packet(&packet, &pad, sequence);
                bool input_changed =
                    !has_last_sent_packet ||
                    !input_matches(&packet, &last_sent_packet);
                bool heartbeat_due =
                    now_us - last_send_us >= IDLE_HEARTBEAT_US;
                if (input_changed || heartbeat_due) {
                    packet.sequence = sceNetHtonl(sequence++);
                    int result = sceNetSendto(
                        sock, &packet, sizeof(packet), 0,
                        (SceNetSockaddr *)&host, sizeof(host)
                    );
                    if (result == (int)sizeof(packet)) {
                        last_sent_packet = packet;
                        has_last_sent_packet = true;
                        last_send_us = now_us;
                        sent++;
                    } else if (result < 0) {
                        connected = false;
                        has_last_sent_packet = false;
                        network_result = result;
                    }
                }
            }
            previous_buttons = pad.buttons;
        }

        if (now_us >= next_status_us) {
            update_device_status(&device_status);
            next_status_us = now_us + STATUS_INTERVAL_US;
        }
        if (now_us >= next_draw_us) {
            draw_ui(
                font, connected, host_ip, sent, network_result,
                hosts, host_count, selected_host, &device_status
            );
            next_draw_us = now_us + DRAW_INTERVAL_US;
        }
        sceKernelDelayThread(POLL_INTERVAL_US);
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
