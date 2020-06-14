// Note: struct_guards just as in the headers
#ifdef DMIBRIDGEMODULE_struct_guard

#include "dmi.h"
#include "sim_socket.h"
#include "sim_dmi.h"
#include <sys/stat.h>

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <string>

dmi_t::dmi_t(simif_t* sim, const std::vector<std::string>& args, uint32_t mmint_present, 
             DMIBRIDGEMODULE_struct * mmio_addrs): bridge_driver_t(sim)
{
    this->mmio_addrs = mmio_addrs;
    this->mmint_present = (mmint_present == 1) ? true : false;
    this->fd = 0;
    this->sock = 0;
    this->busy = false;
    this->memloaded = false;
    bool enable = false;
    int port_num = 5555;

    std::string enable_arg = std::string("+debug_enable");
    std::string port_arg = std::string("+debug_port=");

    for (auto &arg: args) {
        if (arg.find(enable_arg) == 0) {
            enable = true;
        }
        if (arg.find(port_arg) == 0) {
            port_num = atoi(const_cast<char*>(arg.c_str()) + port_arg.length());
        }
    }

    if (enable) {
        printf("[DMI] Configuring DMI Bridge\n");
        if (this->mmint_present) { printf("[DMI] MMInt device detected!\n"); }
        this->sock = socket_open(port_num);
        if (this->sock < 0) {
            printf("Could not open socket. Error = %d\n", this->sock);
            abort();	
        }
        printf("[DMI] Opened socket on port %d\n", port_num);
    }
}

dmi_t::~dmi_t() {
    free(this->mmio_addrs);
}

void dmi_t::init() {
    if (this->sock) {
        write(this->mmio_addrs->connected, true);
        printf("[DMI] Waiting for connection from gdb / openocd ...\n");
        this->fd = socket_accept(this->sock);
        printf("[DMI] Connection accepted!\n");
    }
}

void dmi_t::finish() {
    if (this->sock) {
        printf("[DMI] Closing socket\n");
        socket_shutdown(this->sock);
    }
}

void dmi_t::recv_resp() {
    if (read(this->mmio_addrs->resp_valid)) {
        int data, response;
        int err;
        data = read(this->mmio_addrs->resp_data);
        response = read(this->mmio_addrs->resp);
        //printf("[DMI] Received data = 0x%x | response = 0x%x\n", data, response);
        err = vpidmi_response(this->fd, data, response);
        if (err < 0) {
            printf("[DMI] vpidmi_response() error = %d\n", err);
            abort();
        }
        write(this->mmio_addrs->resp_ready, true);
        this->busy = false;
    }
}

void dmi_t::send_req() {
    if (this->mmint_present && !this->memloaded) {
        this->memloaded = read(this->mmio_addrs->memloaded);
	if (this->memloaded) { printf("[DMI] Received signal that target memory has been loaded. Now allowing DMI traffic.\n"); }
        return;
    }
    if (read(this->mmio_addrs->req_ready)) {
       int addr;
       int data;
       int op;
       int err;
       err = vpidmi_request(this->fd, &addr, &data, &op);
       if (err < 0) {
           printf("[DMI] vpidmi_request() error = %d\n", err);
       } else if (err > 0) {
           //printf("[DMI] Writing to target: addr = 0x%x | data = 0x%x | op = 0x%x\n", addr, data, op);
           write(this->mmio_addrs->req_addr, addr);
           write(this->mmio_addrs->req_data, data);
           write(this->mmio_addrs->req_op, op);
           write(this->mmio_addrs->req_valid, true);
           this->busy = true;
       }
    } else {
       printf("[DMI] req_ready not ready\n");
    }
}

void dmi_t::tick() {
    if (this->fd > 0) {
        if ( this->busy) { this->recv_resp(); }
        if (!this->busy) { this->send_req();  }
    }
}
#endif // DMIBRIDGEMODULE_struct_guard
