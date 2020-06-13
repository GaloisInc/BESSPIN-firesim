// Note: struct_guards just as in the headers
#ifdef DMIBRIDGEMODULE_struct_guard

#include "dmi.h"
#include "sim_socket.h"
#include "sim_dmi.h"
#include <sys/stat.h>

#include <stdlib.h>
#include <stdio.h>

dmi_t::dmi_t(simif_t* sim, DMIBRIDGEMODULE_struct * mmio_addrs): bridge_driver_t(sim)
{
    this->mmio_addrs = mmio_addrs;
    printf("Configuring DMI\n");
    this->sock = socket_open(5555);
    this->fd = 0;
    if (this->sock < 0) {
        printf("Could not open socket. Error = %d\n", this->sock);
        abort();	
    }
    printf("DMI: Opened socket on port 5555\n");
}

dmi_t::~dmi_t() {
    free(this->mmio_addrs);
}

void dmi_t::init() {
    printf("DMI: Opening socket\n");
    this->fd = socket_accept(this->sock);
    printf("DMI: fd = %d\n", this->fd);
}

void dmi_t::finish() {
    printf("DMI: Closing socket\n");
    socket_shutdown(this->sock);
}

void dmi_t::recv_resp() {
    if (read(this->mmio_addrs->resp_valid)) {
        int data, response;
        int err;
        data = read(this->mmio_addrs->resp_data);
        response = read(this->mmio_addrs->resp);
        printf("DMI: Received data = 0x%x | response = 0x%x\n", data, response);
        err = vpidmi_response(this->fd, data, response);
        if (err < 0) {
            printf("DMI: vpidmi_response() error = %d\n", err);
            abort();
        }
	write(this->mmio_addrs->resp_ready, true);
    }
}

void dmi_t::send_req() {
    if (read(this->mmio_addrs->req_ready)) {
       int addr;
       int data;
       int op;
       int err;
       err = vpidmi_request(this->fd, &addr, &data, &op);
       if (err < 0) {
           printf("DMI: vpidmi_request() error = %d\n", err);
       } else if (err > 0) {
	   printf("DMI: Writing to target: addr = 0x%x | data = 0x%x | op = 0x%x\n", addr, data, op);
           write(this->mmio_addrs->req_addr, addr);
           write(this->mmio_addrs->req_data, data);
           write(this->mmio_addrs->req_op, op);
           write(this->mmio_addrs->req_valid, true);
       }
    } else {
       printf("DMI: req_ready not ready\n");
    }
}

void dmi_t::tick() {
    if (this->fd > 0) {
        this->recv_resp();
        this->send_req();
    }
}
#endif // DMIBRIDGEMODULE_struct_guard
